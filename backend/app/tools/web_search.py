import httpx
from app.core.config import settings

async def web_search(query: str) -> dict:
    """
    Executes a web search query via the Tavily Search API.
    
    This function exists as a standalone tool so it can be tested independently
    of the ResearchAgent lifecycle and easily integrated into other workflows.
    
    Args:
        query: The search query string.
        
    Returns:
        A dictionary containing the list of search results. Each result contains
        a 'title', 'url', and 'content' snippet.
    """
    if not settings.tavily_api_key:
        raise ValueError("Tavily API key is not configured in settings.")

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": 5
    }

    headers = {
        "Content-Type": "application/json"
    }

    # We use httpx.AsyncClient for non-blocking asynchronous HTTP requests in FastAPI.
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
