from fastapi import APIRouter

# Initialize the router.
# We keep router endpoints separated from main.py to maintain a clean, modular structure.
router = APIRouter()

@router.get("/health")
async def health_check():
    """
    Returns the health status of the API.
    
    This exists to verify that the backend is running and reachable by external services
    or the frontend dashboard.
    """
    return {"status": "ok"}
