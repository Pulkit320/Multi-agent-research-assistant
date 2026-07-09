import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from app.agents.planner_agent import PlannerAgent
from app.agents.research_agent import ResearchAgent
from app.agents.document_agent import DocumentAgent
from app.agents.analyst_agent import AnalystAgent
from app.agents.writer_agent import WriterAgent
from app.agents.reviewer_agent import ReviewerAgent

logger = logging.getLogger(__name__)


class GraphState(BaseModel):
    """
    GraphState represents the shared memory schema of the LangGraph workflow.

    Phase 5 adds four new fields to support the Reviewer Agent and Human-in-the-Loop:
      - report_id: ties this graph run to a specific SQLite checkpoint thread.
      - review_verdict: the structured output from ReviewerAgent.
      - review_retries: counts how many times the reviewer has asked for a revision.
        Capped at 2 to prevent infinite writer-reviewer loops.
      - human_decision: set to "approved" or "rejected" once a human acts on the report.
    """
    original_query: str = ""
    plan: List[str] = Field(default_factory=list)
    research_results: List[Dict[str, Any]] = Field(default_factory=list)
    document_results: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    final_report: str = ""
    sources: List[str] = Field(default_factory=list)
    # Phase 5 fields
    report_id: str = ""
    review_verdict: Dict[str, Any] = Field(default_factory=dict)
    review_retries: int = 0
    human_decision: Optional[str] = None  # "approved" | "rejected" | None


async def planner_node(state: GraphState) -> Dict[str, Any]:
    """
    Planner node: deconstructs the user query into focused sub-questions.
    """
    planner = PlannerAgent()
    sub_questions = await planner.plan(state.original_query)
    return {"plan": sub_questions}


async def research_node(state: GraphState) -> Dict[str, Any]:
    """
    Research node: runs web Tavily searches for each sub-question.
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
    Document node: retrieves relevant text chunks from the pgvector database.
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
    Combine node: fan-in point after parallel branches.
    Invokes AnalystAgent to clean, deduplicate, and compile evidence.
    """
    analyst = AnalystAgent()
    evidence_list = await analyst.analyze(
        query=state.original_query,
        research_results=state.research_results,
        document_results=state.document_results
    )

    unique_sources = list({
        item.get("source", "")
        for item in evidence_list
        if item.get("source")
    })

    return {
        "evidence": evidence_list,
        "sources": unique_sources
    }


async def writer_node(state: GraphState) -> Dict[str, Any]:
    """
    Writer node: compiles the final Markdown research report.
    May be invoked more than once if the reviewer requests a revision.
    Receives the reviewer's issues list via state so it can address them.
    """
    writer = WriterAgent()

    # Build an augmented prompt context if the reviewer previously flagged issues.
    # We pass issues_context to WriterAgent so it can address reviewer feedback.
    issues = state.review_verdict.get("issues", [])
    issues_context = ""
    if issues:
        formatted = "\n".join(f"  - {issue}" for issue in issues)
        issues_context = (
            f"\n\nIMPORTANT — A reviewer flagged the following issues in the previous version "
            f"of this report. You MUST address ALL of them in this revision:\n{formatted}"
        )

    report_md = await writer.write(
        query=state.original_query + issues_context,
        evidence=state.evidence
    )
    return {"final_report": report_md}


async def reviewer_node(state: GraphState) -> Dict[str, Any]:
    """
    Reviewer node: fact-checks the Writer's report against the plan and evidence.

    Increments review_retries each time it runs. The route_after_review function
    reads this counter to decide whether to send the report back to the writer
    (if retries < 2) or proceed to human review (if approved or retries exhausted).
    """
    reviewer = ReviewerAgent()
    verdict = await reviewer.review(
        query=state.original_query,
        plan=state.plan,
        evidence=state.evidence,
        final_report=state.final_report
    )
    return {
        "review_verdict": verdict,
        # Increment the retry counter so route_after_review can cap the loop.
        "review_retries": state.review_retries + 1
    }


async def human_review_node(state: GraphState) -> Dict[str, Any]:
    """
    Human review node: pauses the graph until a human explicitly approves or rejects.

    interrupt() is the first example of LangGraph human-in-the-loop in this codebase.
    Calling it serializes all current state to the SQLite checkpointer and raises
    GraphInterrupt, which propagates out of graph.ainvoke() to the research router.
    The graph resumes when the /report/{id}/approve or /report/{id}/reject endpoint
    calls graph.ainvoke(Command(resume=decision), config={"configurable": {"thread_id": ...}}).
    The resume value ("approved" or "rejected") becomes the return value of interrupt().
    """
    decision = interrupt(state.review_verdict)
    return {"human_decision": decision}


def route_after_review(state: GraphState) -> str:
    """
    Conditional routing function called after reviewer_node completes.

    Returns "writer" if the report was not approved AND we haven't exhausted
    the 2-retry cap yet. Returns "human_review" in all other cases (approved,
    or retries used up).

    Why cap at 2: each writer+reviewer pair is ~10-15 s and two LLM calls.
    Beyond 2 revisions, diminishing returns make it better to let a human decide.
    """
    approved = state.review_verdict.get("approved", True)

    # review_retries was already incremented inside reviewer_node before this runs.
    # So retries=1 means one review cycle done; retries=2 means two done.
    if not approved and state.review_retries < 2:
        return "writer"

    return "human_review"


# Assemble the LangGraph workflow (uncompiled).
# Compilation (with the SQLite checkpointer) happens in main.py's lifespan context
# so the async DB connection is opened once at startup and shared across requests.
workflow = StateGraph(GraphState)

workflow.add_node("planner", planner_node)
workflow.add_node("research", research_node)
workflow.add_node("document", document_node)
workflow.add_node("combine", combine_node)
workflow.add_node("writer", writer_node)
workflow.add_node("reviewer", reviewer_node)
workflow.add_node("human_review", human_review_node)

# Linear start
workflow.add_edge(START, "planner")

# Parallel fan-out: planner triggers both research branches simultaneously
workflow.add_edge("planner", "research")
workflow.add_edge("planner", "document")

# Fan-in: both branches feed into combine
workflow.add_edge("research", "combine")
workflow.add_edge("document", "combine")

# Sequential: combine -> writer -> reviewer
workflow.add_edge("combine", "writer")
workflow.add_edge("writer", "reviewer")

# Conditional edge: first example of conditional routing in this codebase.
# route_after_review() decides whether to send the report back to writer for
# a revision, or to proceed to the human review pause point.
workflow.add_conditional_edges(
    "reviewer",
    route_after_review,
    {"writer": "writer", "human_review": "human_review"}
)

workflow.add_edge("human_review", END)
