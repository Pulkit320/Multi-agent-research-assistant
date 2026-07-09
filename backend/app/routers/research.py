from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from uuid import uuid4
from langgraph.errors import GraphInterrupt

# Initialize router for research operations.
# Separating research routes from other domains keeps our api structure modular.
router = APIRouter()


class ResearchRequest(BaseModel):
    """
    Validation schema for incoming research requests.
    """
    query: str = Field(..., description="The query to research.")


class ResearchResponse(BaseModel):
    """
    Validation schema for outgoing research responses.

    Phase 5 adds:
      - report_id: the UUID that identifies this session in the SQLite checkpoint.
        The client uses this to call /report/{id}/approve or /report/{id}/reject.
      - review_verdict: the structured output from ReviewerAgent.
      - human_decision: None until a human acts; "approved" or "rejected" after.
    """
    report_id: str = Field(..., description="UUID identifying this checkpoint session.")
    plan: List[str] = Field(default=[], description="Sub-questions from the Planner.")
    evidence: List[Dict[str, Any]] = Field(default=[], description="Structured evidence from the Analyst.")
    review_verdict: Dict[str, Any] = Field(default={}, description="Reviewer's verdict: {approved, issues}.")
    human_decision: Optional[str] = Field(default=None, description="'approved', 'rejected', or null.")
    final_report: str = Field(default="", description="Compiled Markdown report from the Writer.")
    sources: List[str] = Field(default=[], description="Unique source URLs cited.")


@router.post("/research", response_model=ResearchResponse)
async def run_research(request_body: ResearchRequest, request: Request):
    """
    Endpoint to trigger the LangGraph Research + Review workflow.

    Generates a unique report_id (used as the LangGraph thread_id), invokes the
    graph, and handles the GraphInterrupt that fires when the graph pauses at the
    human_review node. Returns all state collected up to that pause point plus
    the report_id so the frontend can call the approve/reject endpoints.
    """
    # Generate a unique ID for this research session.
    # This is the LangGraph thread_id used to checkpoint and resume the graph.
    report_id = str(uuid4())

    initial_state = {
        "original_query": request_body.query,
        "report_id": report_id,
    }

    # Thread config binds this invocation to its specific SQLite checkpoint entry.
    thread_config = {"configurable": {"thread_id": report_id}}

    # graph is compiled at startup in main.py and attached to app.state
    graph = request.app.state.graph

    try:
        # The graph will run through planner -> research/document -> combine ->
        # writer -> reviewer -> human_review, where it calls interrupt() and pauses.
        # ainvoke() raises GraphInterrupt at that pause point.
        await graph.ainvoke(initial_state, config=thread_config)

        # If we reach here the graph completed without interruption (shouldn't happen
        # in normal flow, but handle it gracefully just in case).
        snapshot = await graph.aget_state(thread_config)
        state_values = snapshot.values

    except GraphInterrupt:
        # Normal expected path: graph paused at human_review_node.
        # Fetch the checkpointed state to build the response.
        snapshot = await graph.aget_state(thread_config)
        state_values = snapshot.values

    except ValueError as val_error:
        raise HTTPException(status_code=400, detail=str(val_error))
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"An error occurred: {err}")

    return ResearchResponse(
        report_id=report_id,
        plan=state_values.get("plan", []),
        evidence=state_values.get("evidence", []),
        review_verdict=state_values.get("review_verdict", {}),
        human_decision=state_values.get("human_decision"),
        final_report=state_values.get("final_report", ""),
        sources=state_values.get("sources", [])
    )
