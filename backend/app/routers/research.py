from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.agents.research_agent import ResearchAgent

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
    """
    answer: str = Field(..., description="The synthesized answer from the agent.")
    sources: list[str] = Field(default_list=[], description="A list of URLs cited during research.")

@router.post("/research", response_model=ResearchResponse)
async def run_research(request: ResearchRequest):
    """
    Endpoint to trigger the ResearchAgent flow.
    
    This handles HTTP request parsing, runs the async LLM + Search loop,
    and formats the finalized answer and source URLs.
    """
    try:
        agent = ResearchAgent()
        result = await agent.run(request.query)
        return ResearchResponse(
            answer=result.get("answer", ""),
            sources=result.get("sources", [])
        )
    except ValueError as val_error:
        # Handle cases where API keys or configs are missing
        raise HTTPException(status_code=400, detail=str(val_error))
    except Exception as e:
        # Generic fallback exception logger
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
