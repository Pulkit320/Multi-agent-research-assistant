from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from app.graph import graph

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
    
    Now includes the generated plan (sub-questions) so that the client
    can visualize the planning phase.
    """
    plan: List[str] = Field(default=[], description="The list of sub-questions generated in the planning phase.")
    evidence: List[Dict[str, Any]] = Field(default=[], description="The consolidated list of evidence items compiled by the Analyst.")
    answer: str = Field(..., description="The synthesized answer from the agent.")
    sources: List[str] = Field(default=[], description="A list of URLs cited during research.")

@router.post("/research", response_model=ResearchResponse)
async def run_research(request: ResearchRequest):
    """
    Endpoint to trigger the LangGraph Research workflow.
    
    This handles HTTP request parsing, runs the planner and research nodes,
    and returns the plan, finalized answer, and source URLs.
    """
    try:
        # Initialize graph state
        initial_state = {
            "original_query": request.query
        }
        
        # Invoke the LangGraph compiled state graph.
        # Since our node functions are asynchronous, we call ainvoke.
        result = await graph.ainvoke(initial_state)
        
        return ResearchResponse(
            plan=result.get("plan", []),
            evidence=result.get("evidence", []),
            answer=result.get("final_answer", ""),
            sources=result.get("sources", [])
        )
    except ValueError as val_error:
        # Handle cases where API keys or configs are missing
        raise HTTPException(status_code=400, detail=str(val_error))
    except Exception as e:
        # Generic fallback exception logger
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
