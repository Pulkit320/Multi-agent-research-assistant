import logging
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from app.agents.planner_agent import PlannerAgent
from app.agents.research_agent import ResearchAgent
from app.agents.document_agent import DocumentAgent
from app.agents.analyst_agent import AnalystAgent
from app.agents.writer_agent import WriterAgent

logger = logging.getLogger(__name__)

class GraphState(BaseModel):
    """
    GraphState represents the shared memory schema of the LangGraph workflow.
    
    Now expanded in Phase 4 to include final_report (compiled markdown report).
    """
    original_query: str = ""
    plan: List[str] = Field(default_factory=list)
    research_results: List[Dict[str, Any]] = Field(default_factory=list)
    document_results: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    final_report: str = ""
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
    Invokes AnalystAgent to clean, deduplicate, and compile evidence.
    """
    # 1. Deduplicate and merge claims using AnalystAgent
    analyst = AnalystAgent()
    evidence_list = await analyst.analyze(
        query=state.original_query,
        research_results=state.research_results,
        document_results=state.document_results
    )

    # 2. Compile list of unique source citations
    unique_sources = list({item.get("source", "") for item in evidence_list if item.get("source")})

    return {
        "evidence": evidence_list,
        "sources": unique_sources
    }

async def writer_node(state: GraphState) -> Dict[str, Any]:
    """
    Writer node in the graph.
    
    Invokes the WriterAgent to compile the final report in Markdown.
    """
    writer = WriterAgent()
    report_md = await writer.write(
        query=state.original_query,
        evidence=state.evidence
    )
    return {
        "final_report": report_md
    }

# Assemble and compile the parallel LangGraph workflow.
workflow = StateGraph(GraphState)

workflow.add_node("planner", planner_node)
workflow.add_node("research", research_node)
workflow.add_node("document", document_node)
workflow.add_node("combine", combine_node)
workflow.add_node("writer", writer_node)

# Set parallel execution layout
workflow.add_edge(START, "planner")

# Parallel fan-out from planner node
workflow.add_edge("planner", "research")
workflow.add_edge("planner", "document")

# Fan-in merging parallel paths into combine node
workflow.add_edge("research", "combine")
workflow.add_edge("document", "combine")

# Route merge results into report compiler agent
workflow.add_edge("combine", "writer")

# Terminate at END after report writing completes
workflow.add_edge("writer", END)

graph = workflow.compile()
