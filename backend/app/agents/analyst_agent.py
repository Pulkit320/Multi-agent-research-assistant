import json
import httpx
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from app.core.config import settings

class EvidenceItem(BaseModel):
    """
    EvidenceItem represents a single atomic claim or finding.
    """
    claim: str = Field(..., description="A key fact, finding, or statement extracted from the findings.")
    source_type: str = Field(..., description="Must be either 'web' or 'document'.")
    source: str = Field(..., description="Citations: URL for web, or filename + page number for document (e.g. 'report.pdf (Page 4)').")

class EvidenceList(BaseModel):
    """
    Validation schema for AnalystAgent output.
    """
    evidence: List[EvidenceItem]

class AnalystAgent:
    """
    AnalystAgent merges search findings from both web research and document RAG.
    
    It filters out redundant claims, aligns contradictory statements, and
    compiles a clean, unified, structured list of evidence items.
    """

    def __init__(self):
        """
        Initializes the AnalystAgent and checks API keys.
        """
        if not settings.gemini_api_key and not settings.openrouter_api_key:
            raise ValueError(
                "No LLM provider configured. Please set GEMINI_API_KEY or OPENROUTER_API_KEY."
            )
            
        self.system_prompt = (
            "You are an expert analyst. Your job is to read findings from Web searches and Document searches, "
            "and compile a single consolidated list of evidence. "
            "You must:\n"
            "1. Deduplicate overlapping or duplicate claims.\n"
            "2. Label each evidence item with `source_type` ('web' or 'document').\n"
            "3. Format citations correctly inside `source`: use the exact URL for web sources, and filename with page number "
            "for documents (e.g., 'growth_plan.pdf (Page 2)').\n"
            "4. Return ONLY a JSON object matching this schema: `{\"evidence\": [{\"claim\": \"...\", \"source_type\": \"...\", \"source\": \"...\"}]}`."
        )

    async def analyze(self, query: str, research_results: List[Dict[str, Any]], document_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merges and structures findings from web and document agents.
        
        Args:
            query: The original user query.
            research_results: List of web research results.
            document_results: List of document search results.
            
        Returns:
            A list of dictionary evidence items.
        """
        # Format inputs for LLM prompt
        web_context = ""
        for idx, res in enumerate(research_results):
            answer_text = res.get('answer', '')
            sources_list = res.get('sources', [])
            sources_str = ', '.join(sources_list) if sources_list else "Web (direct answer — no URL returned)"
            web_context += f"- Sub-Question: {res.get('sub_question', '')}\n"
            web_context += f"  Web Answer: {answer_text}\n"
            web_context += f"  Web Sources: {sources_str}\n\n"

        doc_context = ""
        for idx, res in enumerate(document_results):
            doc_context += f"- Sub-Question: {res.get('sub_question', '')}\n"
            for chunk in res.get("chunks", []):
                filename = chunk.get("filename", "doc.pdf")
                page = chunk.get("page", 1)
                content = chunk.get("content", "")
                doc_context += f"  Doc Chunk ({filename}, Page {page}): {content}\n"
            doc_context += "\n"

        prompt = (
            f"Original User Query: {query}\n\n"
            f"=== WEB SEARCH FINDINGS ===\n{web_context}\n"
            f"=== DOCUMENT SEARCH FINDINGS ===\n{doc_context}\n"
            f"Compile and deduplicate these into a structured list of evidence items.\n"
            f"IMPORTANT: Even if a web source shows 'Web (direct answer — no URL returned)', "
            f"you must still include the claim in the evidence list using that phrase as the source value."
        )

        if settings.gemini_api_key:
            return await self._analyze_gemini(prompt)
        else:
            return await self._analyze_openrouter(prompt)

    async def _analyze_gemini(self, prompt: str) -> dict:
        """
        Calls Gemini to get structured evidence list and tracks token usage.
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
            },
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "evidence": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "claim": {"type": "STRING", "description": "The atomic claim extracted."},
                                    "source_type": {"type": "STRING", "description": "Either 'web' or 'document'."},
                                    "source": {"type": "STRING", "description": "Citations URL or filename + page number."}
                                },
                                "required": ["claim", "source_type", "source"]
                            }
                        }
                    },
                    "required": ["evidence"]
                }
            }
        }

        input_tokens = 0
        output_tokens = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            response_json = response.json()

            usage = response_json.get("usageMetadata", {})
            input_tokens = usage.get("promptTokenCount", 0)
            output_tokens = usage.get("candidatesTokenCount", 0)

            candidates = response_json.get("candidates", [])
            if not candidates:
                return {"evidence": [], "input_tokens": input_tokens, "output_tokens": output_tokens}

            # Find the actual response part (avoiding reasoning thoughts)
            parts = candidates[0].get("content", {}).get("parts", [])
            raw_text = ""
            for part in reversed(parts):
                if "text" in part and not part.get("thought"):
                    raw_text = part["text"]
                    break
            if not raw_text and parts:
                raw_text = parts[-1].get("text", "")
            try:
                parsed = json.loads(raw_text)
                return {"evidence": parsed.get("evidence", []), "input_tokens": input_tokens, "output_tokens": output_tokens}
            except (json.JSONDecodeError, TypeError):
                return {"evidence": [], "input_tokens": input_tokens, "output_tokens": output_tokens}

    async def _analyze_openrouter(self, prompt: str) -> dict:
        """
        Calls OpenRouter to get structured evidence list and tracks token usage.
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
            "messages": messages,
            "response_format": {"type": "json_object"}
        }

        input_tokens = 0
        output_tokens = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            response_json = response.json()

            usage = response_json.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            choices = response_json.get("choices", [])
            if not choices:
                return {"evidence": [], "input_tokens": input_tokens, "output_tokens": output_tokens}

            raw_text = choices[0].get("message", {}).get("content", "")
            try:
                parsed = json.loads(raw_text)
                return {"evidence": parsed.get("evidence", []), "input_tokens": input_tokens, "output_tokens": output_tokens}
            except (json.JSONDecodeError, TypeError):
                return {"evidence": [], "input_tokens": input_tokens, "output_tokens": output_tokens}
