import json
import httpx
from pydantic import BaseModel, Field
from typing import List
from app.core.config import settings

class ResearchPlan(BaseModel):
    """
    ResearchPlan defines the structured output schema for the PlannerAgent.
    
    This exists to force the LLM to output exactly this schema rather than
    free-form text, which would be difficult to parse deterministically in the graph.
    """
    sub_questions: List[str] = Field(
        ...,
        description="A list of 1 to 4 focused sub-questions that must be researched to fully answer the original query."
    )

class PlannerAgent:
    """
    PlannerAgent takes the raw user query and outputs a structured plan
    consisting of 1 to 4 focused sub-questions.
    
    Splitting a complex query into simpler questions allows downstream agents
    to perform more targeted, higher-quality research.
    """

    def __init__(self):
        """
        Initializes the agent and verifies config setup.
        """
        if not settings.gemini_api_key and not settings.openrouter_api_key:
            raise ValueError(
                "No LLM provider configured. Please set GEMINI_API_KEY or OPENROUTER_API_KEY."
            )

        self.system_prompt = (
            "You are a strategic planning agent. Your task is to analyze a user query and "
            "break it down into 1 to 4 focused sub-questions that need to be researched "
            "independently to formulate a complete, high-quality response. "
            "For example, if asked to compare two entities, create sub-questions to research "
            "each entity individually. "
            "You MUST respond ONLY with a JSON object containing a list of strings named `sub_questions`."
        )

    async def plan(self, query: str) -> List[str]:
        """
        Generates a list of 1 to 4 research sub-questions for a query.
        
        Args:
            query: The user's query string.
            
        Returns:
            A list of sub-questions.
        """
        if settings.gemini_api_key:
            return await self._plan_gemini(query)
        else:
            return await self._plan_openrouter(query)

    async def _plan_gemini(self, query: str) -> List[str]:
        """
        Calls Google's Gemini API directly, forcing structured JSON schema output.
        """
        api_key = settings.gemini_api_key
        model = settings.gemini_model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": f"Original query: {query}"}]}
            ],
            "systemInstruction": {
                "parts": [{"text": self.system_prompt}]
            },
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "sub_questions": {
                            "type": "ARRAY",
                            "items": {
                                "type": "STRING"
                            },
                            "description": "A list of 1 to 4 focused sub-questions."
                        }
                    },
                    "required": ["sub_questions"]
                }
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            response_json = response.json()

            candidates = response_json.get("candidates", [])
            if not candidates:
                return [query] # fallback to original query if no candidates

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                return [query]

            # Find the actual response part (avoiding reasoning thoughts)
            raw_text = ""
            for part in reversed(parts):
                if "text" in part and not part.get("thought"):
                    raw_text = part["text"]
                    break
            if not raw_text:
                raw_text = parts[-1].get("text", "")
            try:
                parsed = json.loads(raw_text)
                sub_questions = parsed.get("sub_questions", [])
                # Enforce limit of 1 to 4 sub-questions
                if not sub_questions:
                    return [query]
                return sub_questions[:4]
            except (json.JSONDecodeError, TypeError):
                return [query]

    async def _plan_openrouter(self, query: str) -> List[str]:
        """
        Calls OpenRouter API, forcing JSON output via JSON mode and structured prompting.
        """
        api_key = settings.openrouter_api_key
        model = settings.openrouter_model
        url = "https://openrouter.ai/api/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Please formulate a research plan for: {query}"}
        ]

        payload = {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            response_json = response.json()

            choices = response_json.get("choices", [])
            if not choices:
                return [query]

            raw_text = choices[0].get("message", {}).get("content", "")
            try:
                parsed = json.loads(raw_text)
                sub_questions = parsed.get("sub_questions", [])
                if not sub_questions:
                    return [query]
                return sub_questions[:4]
            except (json.JSONDecodeError, TypeError):
                return [query]
