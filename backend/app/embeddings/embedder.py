import httpx
from app.core.config import settings

async def get_embedding(text: str, task_type: str = "retrieval_document") -> list[float]:
    """
    Generates a 768-dimensional embedding vector of the input text using Google's 
    Gemini Embedding API via direct REST request.
    
    Args:
        text: The text string to embed.
        task_type: Either 'retrieval_document' (indexing) or 'retrieval_query' (searching).
        
    Returns:
        A list of float numbers representing the embedding vector.
    """
    api_key = settings.gemini_api_key
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured in settings.")

    clean_text = text.strip() if text else ""
    if not clean_text:
        return []

    # Map task type strings to the API expectations
    # Direct Gemini REST API expects uppercase string constants
    api_task_type = "RETRIEVAL_DOCUMENT"
    if task_type == "retrieval_query":
        api_task_type = "RETRIEVAL_QUERY"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent?key={api_key}"
    payload = {
        "content": {
            "parts": [{"text": clean_text}]
        },
        "taskType": api_task_type,
        "outputDimensionality": 768
    }

    headers = {
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        response_json = response.json()
        
        embedding_obj = response_json.get("embedding", {})
        values = embedding_obj.get("values", [])
        if not values:
            raise KeyError("The API response did not contain the 'values' list in the 'embedding' object.")
            
        return values
