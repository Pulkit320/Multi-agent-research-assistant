import httpx
import logging
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from app.core.config import settings
from app.agents.planner_agent import PlannerAgent
from app.agents.research_agent import ResearchAgent
from app.agents.document_agent import DocumentAgent
from app.agents.analyst_agent import AnalystAgent

logger = logging.getLogger(__name__)

class GraphState(BaseModel):
    """
    GraphState represents the shared memory schema of the LangGraph workflow.
    
    Now expanded in Phase 3 to support document RAG search results and a combined
    evidence list synthesized by the Analyst.
    """
    original_query: str = ""
    plan: List[str] = Field(default_factory=list)
    research_results: List[Dict[str, Any]] = Field(default_factory=list)
    document_results: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    final_answer: str = ""
    sources: List[str] = Field(default_factory=list)

async def planner_node(state: GraphState) -> Dict[str, Any]:
    """
    Planner node in the graph.
    
    Invokes the PlannerAgent to deconstruct the query into focused sub-questions.
    """
    planner = PlannerAgent()
    sub_questions = await planner.plan(state.original_query)
    return {"plan": sub_questions}

async def research_node(state: GraphState) -> Dict[str, Any]:
    """
    Research node in the graph.
    
    Runs sequentially on all plan sub-questions to perform web Tavily searches.
    Runs in parallel with the document retrieval branch.
    """
    research_agent = ResearchAgent()
    compiled_results = []

    for sub_q in state.plan:
        agent_result = await research_agent.run(sub_q)
        compiled_results.append({
            "sub_question": sub_q,
            "answer": agent_result.get("answer", ""),
            "sources": agent_result.get("sources", [])
        })

    return {"research_results": compiled_results}

async def document_node(state: GraphState) -> Dict[str, Any]:
    """
    Document node in the graph.
    
    Runs sequentially on all plan sub-questions to retrieve relevant text
    chunks from the pgvector database.
    Runs in parallel with the web search branch.
    """
    doc_agent = DocumentAgent()
    compiled_results = []

    for sub_q in state.plan:
        agent_result = await doc_agent.run(sub_q)
        compiled_results.append({
            "sub_question": sub_q,
            "chunks": agent_result.get("chunks", []),
            "sources": agent_result.get("sources", [])
        })

    return {"document_results": compiled_results}

async def combine_node(state: GraphState) -> Dict[str, Any]:
    """
    Combine node in the graph.
    
    This acts as the merge/fan-in point after parallel execution branches finish.
    1. Invokes AnalystAgent to clean, deduplicate, and compile evidence.
    2. Invokes LLM to synthesize the final comparative answer from the evidence.
    """
    # 1. Deduplicate and merge claims using AnalystAgent
    analyst = AnalystAgent()
    evidence_list = await analyst.analyze(
        query=state.original_query,
        research_results=state.research_results,
        document_results=state.document_results
    )

    # 2. Extract sources and compile prompt context
    unique_sources = set()
    synthesis_evidence_context = ""
    
    for idx, item in enumerate(evidence_list):
        claim = item.get("claim", "")
        source_type = item.get("source_type", "")
        source = item.get("source", "")
        
        synthesis_evidence_context += f"[{idx+1}] [{source_type.upper()}] (Source: {source}): {claim}\n"
        unique_sources.add(source)

    # 3. Formulate the final synthesis prompt
    synthesis_prompt = (
        f"You are a research synthesis agent. Your job is to take the original user query, "
        f"read the consolidated evidence items compiled by our analyst, and write a single, "
        f"comprehensive, and coherent final response answering the original query.\n\n"
        f"Original Query: {state.original_query}\n\n"
        f"Consolidated Evidence Findings:\n{synthesis_evidence_context}\n"
        f"Generate the final unified answer now. Ensure you reference the bracketed citation numbers "
        f"(e.g., [1], [2]) where facts are mentioned."
    )

    # 4. Request LLM synthesis
    final_answer = ""
    if settings.gemini_api_key:
        final_answer = await _synthesize_gemini(synthesis_prompt)
    else:
        final_answer = await _synthesize_openrouter(synthesis_prompt)

    return {
        "evidence": evidence_list,
        "final_answer": final_answer,
        "sources": list(unique_sources)
    }

async def _synthesize_gemini(prompt: str) -> str:
    """
    Direct REST call to Gemini to synthesize the final answer.
    """
    api_key = settings.gemini_api_key
    model = settings.gemini_model
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ]
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        response_json = response.json()
        candidates = response_json.get("candidates", [])
        if candidates:
            return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return "Failed to synthesize final answer."

async def _synthesize_openrouter(prompt: str) -> str:
    """
    Direct REST call to OpenRouter to synthesize the final answer.
    """
    api_key = settings.openrouter_api_key
    model = settings.openrouter_model
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    messages = [
        {"role": "user", "content": prompt}
    ]

    payload = {
        "model": model,
        "messages": messages
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        response_json = response.json()
        choices = response_json.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return "Failed to synthesize final answer."

# Assemble and compile the parallel LangGraph workflow.
workflow = StateGraph(GraphState)

workflow.add_node("planner", planner_node)
workflow.add_node("research", research_node)
workflow.add_node("document", document_node)
workflow.add_node("combine", combine_node)

# Set parallel execution layout
workflow.add_edge(START, "planner")

# Parallel fan-out from planner node
workflow.add_edge("planner", "research")
workflow.add_edge("planner", "document")

# Fan-in merging parallel paths into combine node
workflow.add_edge("research", "combine")
workflow.add_edge("document", "combine")

workflow.add_edge("combine", END)

graph = workflow.compile()
