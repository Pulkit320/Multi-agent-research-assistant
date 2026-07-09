import httpx
import logging
from typing import List, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

class WriterAgent:
    """
    WriterAgent compiles the final research report in structured Markdown.
    
    This agent isolates presentation formatting from the factual analysis, 
    adhering to the Separation of Concerns (SoC) design principle.
    """

    def __init__(self):
        """
        Initializes the agent and ensures LLM API keys are configured.
        """
        if not settings.gemini_api_key and not settings.openrouter_api_key:
            raise ValueError(
                "No LLM provider configured. Please set GEMINI_API_KEY or OPENROUTER_API_KEY."
            )
            
        self.system_prompt = (
            "You are an expert report writer. Your job is to take the original user query and a structured list "
            "of evidence items, and generate a professional, polished research report in Markdown format.\n\n"
            "Your report must follow this exact structure:\n"
            "1. # [Title based on query]\n"
            "2. ## Summary\n"
            "   A 1-2 paragraph executive summary answering the core query.\n"
            "3. ## Detailed Findings\n"
            "   Create an H3 section for each sub-question answered (e.g. `### Q1: [Question text]`). "
            "   Under each sub-question, write the detailed findings based on the evidence. "
            "   Use bracketed superscript numbers to cite facts (e.g. [1], [2]).\n"
            "4. ## Sources Table\n"
            "   Create a Markdown table listing each citation used in the report:\n"
            "   | Citation | Claim | Source Type | Location / URL |\n"
            "   | --- | --- | --- | --- |\n"
            "   | [1] | Claim text | Web or Document | URL or filename (page) |\n\n"
            "Rules:\n"
            "- Rely ONLY on the provided evidence claims. Do not extrapolate or add outside knowledge.\n"
            "- Return ONLY the raw markdown text of the report. Do not wrap it in ```markdown code blocks."
        )

    async def write(self, query: str, evidence: List[Dict[str, Any]]) -> str:
        """
        Generates the final markdown report based on evidence items.
        
        Args:
            query: The original research query.
            evidence: The list of consolidated evidence items from the Analyst.
            
        Returns:
            The markdown report string.
        """
        logger.info(f"WriterAgent compiling report for query: '{query}'")
        
        # Format the evidence list into a readable context
        evidence_context = ""
        for idx, item in enumerate(evidence):
            claim = item.get("claim", "")
            stype = item.get("source_type", "web")
            source = item.get("source", "")
            evidence_context += f"Evidence [{idx+1}] ({stype}) [Source: {source}]: {claim}\n"

        prompt = (
            f"Original Query: {query}\n\n"
            f"=== CONSOLIDATED EVIDENCE FINDINGS ===\n{evidence_context}\n\n"
            f"Compile the final report in Markdown format."
        )

        try:
            if settings.gemini_api_key:
                return await self._write_gemini(prompt)
            else:
                return await self._write_openrouter(prompt)
        except Exception as e:
            logger.error(f"WriterAgent failed: {e}")
            return f"# Error Generating Report\n\nFailed to compile response: {str(e)}"

    async def _write_gemini(self, prompt: str) -> str:
        """
        Queries Gemini API directly via HTTP request.
        """
        api_key = settings.gemini_api_key
        model = settings.gemini_model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": prompt}]}
            ],
            "systemInstruction": {
                "parts": [{"text": self.system_prompt}]
            }
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            response_json = response.json()
            
            candidates = response_json.get("candidates", [])
            if candidates:
                # Find the actual response part (avoiding reasoning thoughts)
                parts = candidates[0].get("content", {}).get("parts", [])
                raw_text = ""
                for part in reversed(parts):
                    if "text" in part and not part.get("thought"):
                        raw_text = part["text"]
                        break
                if not raw_text and parts:
                    raw_text = parts[-1].get("text", "")
                return raw_text
            return "No report generated."

    async def _write_openrouter(self, prompt: str) -> str:
        """
        Queries OpenRouter API directly via HTTP request.
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
            {"role": "user", "content": prompt}
        ]

        payload = {
            "model": model,
            "messages": messages
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            response_json = response.json()
            
            choices = response_json.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            return "No report generated."
