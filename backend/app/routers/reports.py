from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional
from langgraph.types import Command

# Initialize router for human-decision actions on paused report sessions.
# Separated from research.py because the lifecycle is different:
# research.py creates a session; reports.py acts on a paused one.
router = APIRouter()


class HumanDecisionResponse(BaseModel):
    """
    Response schema for the approve and reject endpoints.
    """
    report_id: str
    human_decision: str = Field(..., description="Either 'approved' or 'rejected'.")
    final_report: str = Field(default="", description="The finalized report markdown (only on approval).")


@router.post("/report/{report_id}/approve", response_model=HumanDecisionResponse)
async def approve_report(report_id: str, request: Request):
    """
    Resumes a paused graph session with a human 'approved' decision.

    The graph is currently halted inside human_review_node's interrupt() call.
    Passing Command(resume="approved") replays the graph from that checkpoint,
    causing interrupt() to return "approved", which sets human_decision="approved"
    in GraphState and then the graph proceeds to END.
    """
    graph = request.app.state.graph
    config = {"configurable": {"thread_id": report_id}}

    try:
        result = await graph.ainvoke(Command(resume="approved"), config=config)
        return HumanDecisionResponse(
            report_id=report_id,
            human_decision="approved",
            final_report=result.get("final_report", "")
        )
    except Exception as err:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to approve report '{report_id}': {err}"
        )


@router.post("/report/{report_id}/reject", response_model=HumanDecisionResponse)
async def reject_report(report_id: str, request: Request):
    """
    Resumes a paused graph session with a human 'rejected' decision.

    Same mechanics as approve, but Command(resume="rejected") causes human_decision
    to be set to "rejected". The graph still proceeds to END — rejection is a
    terminal decision, not a retry.
    """
    graph = request.app.state.graph
    config = {"configurable": {"thread_id": report_id}}

    try:
        result = await graph.ainvoke(Command(resume="rejected"), config=config)
        return HumanDecisionResponse(
            report_id=report_id,
            human_decision="rejected",
            final_report=result.get("final_report", "")
        )
    except Exception as err:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reject report '{report_id}': {err}"
        )
