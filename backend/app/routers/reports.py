from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional
from langgraph.types import Command
from app.core.sse_manager import sse_manager

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
    Sets the human decision to 'approved' and triggers the stream event
    so the active GET /research/stream thread can resume the graph.
    """
    try:
        sse_manager.set_decision(report_id, "approved")
        return HumanDecisionResponse(
            report_id=report_id,
            human_decision="approved"
        )
    except Exception as err:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to approve report '{report_id}': {err}"
        )


@router.post("/report/{report_id}/reject", response_model=HumanDecisionResponse)
async def reject_report(report_id: str, request: Request):
    """
    Sets the human decision to 'rejected' and triggers the stream event
    so the active GET /research/stream thread can resume the graph.
    """
    try:
        sse_manager.set_decision(report_id, "rejected")
        return HumanDecisionResponse(
            report_id=report_id,
            human_decision="rejected"
        )
    except Exception as err:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reject report '{report_id}': {err}"
        )
