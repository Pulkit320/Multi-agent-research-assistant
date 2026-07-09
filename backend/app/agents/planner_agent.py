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

    async def plan(self, query: str) -> dict:
        """
        Generates a list of 1 to 4 research sub-questions for a query and tracks token usage.
        
        Args:
            query: The user's query string.
            
        Returns:
            A dict containing:
              - 'plan': List[str] (sub-questions)
              - 'input_tokens': int
              - 'output_tokens': int
        """
        if settings.gemini_api_key:
            return await self._plan_gemini(query)
        else:
            return await self._plan_openrouter(query)

    async def _plan_gemini(self, query: str) -> dict:
        """
        Calls Google's Gemini API directly, forcing structured JSON schema output and extracting usage.
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

        input_tokens = 0
        output_tokens = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            response_json = response.json()

            # Extract token usage metadata from Gemini response format
            usage = response_json.get("usageMetadata", {})
            input_tokens = usage.get("promptTokenCount", 0)
            output_tokens = usage.get("candidatesTokenCount", 0)

            candidates = response_json.get("candidates", [])
            if not candidates:
                return {"plan": [query], "input_tokens": input_tokens, "output_tokens": output_tokens}

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                return {"plan": [query], "input_tokens": input_tokens, "output_tokens": output_tokens}

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
                    return {"plan": [query], "input_tokens": input_tokens, "output_tokens": output_tokens}
                return {"plan": sub_questions[:4], "input_tokens": input_tokens, "output_tokens": output_tokens}
            except (json.JSONDecodeError, TypeError):
                return {"plan": [query], "input_tokens": input_tokens, "output_tokens": output_tokens}

    async def _plan_openrouter(self, query: str) -> dict:
        """
        Calls OpenRouter API, forcing JSON output and extracting token usage.
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
            "response_format": {"type": "json_object"},
            "max_tokens": 1000
        }

        input_tokens = 0
        output_tokens = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            response_json = response.json()

            # Extract token usage metadata from OpenAI-compatible response format
            usage = response_json.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            choices = response_json.get("choices", [])
            if not choices:
                return {"plan": [query], "input_tokens": input_tokens, "output_tokens": output_tokens}

            raw_text = choices[0].get("message", {}).get("content", "")
            try:
                parsed = json.loads(raw_text)
                sub_questions = parsed.get("sub_questions", [])
                if not sub_questions:
                    return {"plan": [query], "input_tokens": input_tokens, "output_tokens": output_tokens}
                return {"plan": sub_questions[:4], "input_tokens": input_tokens, "output_tokens": output_tokens}
            except (json.JSONDecodeError, TypeError):
                return {"plan": [query], "input_tokens": input_tokens, "output_tokens": output_tokens}
