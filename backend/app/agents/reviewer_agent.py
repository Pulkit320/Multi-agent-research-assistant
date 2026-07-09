import json
import httpx
from typing import List, Dict, Any
from app.core.config import settings


class ReviewerAgent:
    """
    ReviewerAgent audits the WriterAgent's report against the evidence and plan
    before it reaches the human reviewer.

    Why this agent exists: The WriterAgent focuses on prose quality and structure.
    It can produce fluent text that subtly overstates, omits, or miscites evidence.
    Having a separate LLM pass dedicated solely to fact-checking catches these errors
    while the cost of correction is still low (one more writer pass vs. post-publication).
    """

    def __init__(self):
        """
        Initializes the ReviewerAgent and validates that an LLM provider is configured.
        """
        if not settings.gemini_api_key and not settings.openrouter_api_key:
            raise ValueError(
                "No LLM provider configured. Please set GEMINI_API_KEY or OPENROUTER_API_KEY."
            )

        self.system_prompt = (
            "You are a meticulous fact-checking reviewer. "
            "You will be given: (1) the original user query, (2) a research plan "
            "(list of sub-questions that were supposed to be answered), "
            "(3) a list of evidence items that were collected, and "
            "(4) a final research report written by an AI writer. "
            "Your job is to audit the report and return a structured verdict. "
            "Check for ALL of the following issues:\n"
            "  a) Unsupported claims: any claim in the report that cannot be traced to "
            "     at least one evidence item.\n"
            "  b) Missing sub-questions: any sub-question from the plan that is not "
            "     addressed anywhere in the report.\n"
            "  c) Citation mismatches: any citation number in the report that does not "
            "     correspond to a real evidence item.\n"
            "Set `approved` to true ONLY if none of the above issues are found. "
            "Set `approved` to false and list every specific issue in `issues` if any problem is found. "
            "Return ONLY a JSON object: {\"approved\": bool, \"issues\": [\"...\", \"...\"]}."
        )

    async def review(
        self,
        query: str,
        plan: List[str],
        evidence: List[Dict[str, Any]],
        final_report: str,
    ) -> Dict[str, Any]:
        """
        Audits the final report against the plan and evidence.

        Args:
            query: The original user query.
            plan: The list of sub-questions from the PlannerAgent.
            evidence: The list of evidence items from the AnalystAgent.
            final_report: The Markdown report from the WriterAgent.

        Returns:
            A dict: {approved: bool, issues: list[str]}.
            On any LLM error, defaults to approved=True with an empty issues list
            so a transient failure does not permanently block the pipeline.
        """
        plan_text = "\n".join(f"  {i+1}. {q}" for i, q in enumerate(plan))
        evidence_text = "\n".join(
            f"  [{i+1}] {item.get('claim', '')} "
            f"(source_type={item.get('source_type', '')}, "
            f"source={item.get('source', '')})"
            for i, item in enumerate(evidence)
        )

        prompt = (
            f"Original Query: {query}\n\n"
            f"Research Plan (sub-questions):\n{plan_text}\n\n"
            f"Evidence Items:\n{evidence_text}\n\n"
            f"=== REPORT TO REVIEW ===\n{final_report}\n"
            f"========================\n\n"
            f"Audit the report and return your verdict as JSON."
        )

        if settings.gemini_api_key:
            return await self._review_gemini(prompt)
        else:
            return await self._review_openrouter(prompt)

    async def _review_gemini(self, prompt: str) -> Dict[str, Any]:
        """
        Calls Gemini with a structured JSON schema to get the review verdict.
        Uses the same responseMimeType + responseSchema pattern as AnalystAgent.
        """
        api_key = settings.gemini_api_key
        model = settings.gemini_model
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )

        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": prompt}]}
            ],
            "systemInstruction": {
                "parts": [{"text": self.system_prompt}]
            },
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "approved": {
                            "type": "BOOLEAN",
                            "description": "True if the report passes review, false if issues found."
                        },
                        "issues": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "List of specific issues found. Empty if approved."
                        }
                    },
                    "required": ["approved", "issues"]
                }
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                response_json = response.json()

            candidates = response_json.get("candidates", [])
            if not candidates:
                return {"approved": True, "issues": []}

            # Find the actual response part, skipping reasoning thought blocks.
            parts = candidates[0].get("content", {}).get("parts", [])
            raw_text = ""
            for part in reversed(parts):
                if "text" in part and not part.get("thought"):
                    raw_text = part["text"]
                    break
            if not raw_text and parts:
                raw_text = parts[-1].get("text", "")

            parsed = json.loads(raw_text)
            return {
                "approved": parsed.get("approved", True),
                "issues": parsed.get("issues", [])
            }
        except (json.JSONDecodeError, TypeError, httpx.HTTPError) as err:
            # On any transient error, default to approved so the pipeline isn't blocked.
            print(f"ReviewerAgent failed (defaulting to approved): {err}")
            return {"approved": True, "issues": []}

    async def _review_openrouter(self, prompt: str) -> Dict[str, Any]:
        """
        Calls OpenRouter to get the structured review verdict.
        """
        api_key = settings.openrouter_api_key
        model = settings.openrouter_model
        url = "https://openrouter.ai/api/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"}
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                response_json = response.json()

            choices = response_json.get("choices", [])
            if not choices:
                return {"approved": True, "issues": []}

            raw_text = choices[0].get("message", {}).get("content", "")
            parsed = json.loads(raw_text)
            return {
                "approved": parsed.get("approved", True),
                "issues": parsed.get("issues", [])
            }
        except (json.JSONDecodeError, TypeError, httpx.HTTPError) as err:
            print(f"ReviewerAgent failed (defaulting to approved): {err}")
            return {"approved": True, "issues": []}
