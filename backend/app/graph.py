import httpx
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from app.core.config import settings
from app.agents.planner_agent import PlannerAgent
from app.agents.research_agent import ResearchAgent

class GraphState(BaseModel):
    """
    GraphState represents the shared memory/state schema of the LangGraph workflow.
    
    This schema dictates the data layout passed between nodes. Centralizing state
    in a Pydantic model ensures type-safety and validation at runtime.
    """
    original_query: str = ""
    plan: List[str] = Field(default_factory=list)
    research_results: List[Dict[str, Any]] = Field(default_factory=list)
    final_answer: str = ""
    sources: List[str] = Field(default_factory=list)

async def planner_node(state: GraphState) -> Dict[str, Any]:
    """
    Planner node in the graph.
    
    This node invokes the PlannerAgent to analyze the user's query and write
    a structured plan (a list of sub-questions) into the shared state.
    """
    planner = PlannerAgent()
    sub_questions = await planner.plan(state.original_query)
    return {"plan": sub_questions}

async def research_node(state: GraphState) -> Dict[str, Any]:
    """
    Research node in the graph.
    
    This node processes the sub-questions sequentially. For each sub-question:
    1. It runs the ResearchAgent.
    2. Gathers the text answers and source URLs.
    
    Once research for all sub-questions is complete, it calls the LLM to synthesize
    a final, comprehensive answer using the collected context.
    """
    research_agent = ResearchAgent()
    compiled_results = []
    unique_sources = set()

    # Process all sub-questions sequentially to gather focused context
    for sub_q in state.plan:
        agent_result = await research_agent.run(sub_q)
        compiled_results.append({
            "sub_question": sub_q,
            "answer": agent_result.get("answer", ""),
            "sources": agent_result.get("sources", [])
        })
        for src in agent_result.get("sources", []):
            unique_sources.add(src)

    # Prepare synthesis context
    synthesis_context = ""
    for idx, res in enumerate(compiled_results):
        synthesis_context += f"Sub-Question {idx+1}: {res['sub_question']}\n"
        synthesis_context += f"Findings: {res['answer']}\n\n"

    # Synthesis Prompt
    synthesis_prompt = (
        f"You are a research synthesis agent. Your job is to take the original user query, "
        f"read the findings gathered from multiple sub-questions, and synthesize a single, "
        f"comprehensive, and coherent response answering the original query.\n\n"
        f"Original Query: {state.original_query}\n\n"
        f"Research Findings:\n{synthesis_context}\n"
        f"Generate the final unified answer now. Cite facts where necessary."
    )

    # Call LLM to synthesize final response
    final_answer = ""
    if settings.gemini_api_key:
        final_answer = await _synthesize_gemini(synthesis_prompt)
    else:
        final_answer = await _synthesize_openrouter(synthesis_prompt)

    return {
        "research_results": compiled_results,
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

# Assemble and compile the LangGraph workflow.
workflow = StateGraph(GraphState)

workflow.add_node("planner", planner_node)
workflow.add_node("research", research_node)

# Set workflow edges: planner node -> research node -> END
workflow.add_edge(START, "planner")
workflow.add_edge("planner", "research")
workflow.add_edge("research", END)

graph = workflow.compile()
