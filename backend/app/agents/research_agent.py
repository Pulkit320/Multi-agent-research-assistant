import json
import httpx
from app.core.config import settings
from app.tools.web_search import web_search

class ResearchAgent:
    """
    ResearchAgent is a single-turn agent that answers queries.
    
    It uses an LLM (either Gemini or OpenRouter) to determine if it needs fresh
    information from the web. If so, it invokes the standalone web_search tool,
    feeds the search result back as context, and returns a finalized answer with sources.
    """

    def __init__(self):
        """
        Initializes the agent by checking for required API keys.
        """
        # We ensure at least one LLM provider is configured in config.py
        if not settings.gemini_api_key and not settings.openrouter_api_key:
            raise ValueError(
                "No LLM provider configured. Please set GEMINI_API_KEY or OPENROUTER_API_KEY."
            )
        
        # We always force a web search for factual questions to guarantee that
        # the AnalystAgent receives URL citations. Without URLs, the Analyst returns
        # an empty evidence list and the final report says "no information found".
        self.system_prompt = (
            "You are a highly capable research assistant. "
            "Your task is to answer user queries with up-to-date, cited, accurate information. "
            "You have access to a tool named `web_search` which searches the internet. "
            "You MUST ALWAYS call the `web_search` tool for ANY factual question — "
            "including well-known facts like capital cities, populations, historical events, "
            "scientific data, and current statistics. "
            "Even if you already know the answer, call `web_search` anyway so the response "
            "includes verified source URLs that can be cited in the research report. "
            "Only skip `web_search` for purely creative or conversational requests (e.g. write a poem). "
            "After retrieving search results, synthesize a final answer citing the sources."
        )

    async def run(self, query: str) -> dict:
        """
        Runs the research agent flow for a user query.
        
        This is the main entry point for the agent logic, containing the LLM-tool execution loop.
        
        Args:
            query: The user's query string.
            
        Returns:
            A dictionary with keys 'answer' (the text answer) and 'sources' (a list of URLs).
        """
        sources = []

        if settings.gemini_api_key:
            return await self._run_gemini(query)
        else:
            return await self._run_openrouter(query)

    async def _run_gemini(self, query: str) -> dict:
        """
        Orchestrates the tool-calling loop using Google's direct Gemini REST API.
        
        This exists to provide a native, dependency-free implementation for Gemini integration.
        """
        api_key = settings.gemini_api_key
        model = settings.gemini_model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        # Define the tool in Gemini API format
        gemini_tools = [{
            "functionDeclarations": [{
                "name": "web_search",
                "description": "Searches the web for up-to-date information on a given query.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {
                            "type": "STRING",
                            "description": "The search query to look up on the web."
                        }
                    },
                    "required": ["query"]
                }
            }]
        }]

        # Set up contents history
        contents = [
            {"role": "user", "parts": [{"text": query}]}
        ]

        payload = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": self.system_prompt}]
            },
            "tools": gemini_tools,
            # mode: ANY forces the model to call at least one tool on this first turn,
            # guaranteeing that web_search is invoked and source URLs are returned.
            # The second turn uses no toolConfig (defaulting to AUTO) to get the text answer.
            "toolConfig": {
                "functionCallingConfig": {
                    "mode": "ANY"
                }
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # First turn: Ask the model if it needs the search tool
            response = await client.post(url, json=payload)
            response.raise_for_status()
            response_json = response.json()

            candidates = response_json.get("candidates", [])
            if not candidates:
                return {"answer": "No answer returned from Gemini.", "sources": []}

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            
            # Check if Gemini requested a function call
            function_call = None
            for part in parts:
                if "functionCall" in part:
                    function_call = part["functionCall"]
                    break

            if not function_call:
                # No function call required; return direct answer (avoiding reasoning thoughts)
                direct_text = ""
                for part in reversed(parts):
                    if "text" in part and not part.get("thought"):
                        direct_text = part["text"]
                        break
                if not direct_text and parts:
                    direct_text = parts[-1].get("text", "")
                return {"answer": direct_text, "sources": []}

            # If we reached here, the model requested `web_search`
            tool_name = function_call["name"]
            tool_args = function_call["args"]
            search_query = tool_args.get("query", query)

            # Invoke the web search tool
            search_result = await web_search(search_query)
            
            # Extract URLs to list as sources in the final response
            urls = [item["url"] for item in search_result.get("results", [])]

            # Construct the conversation history for the second turn:
            # Turn 1: User's original prompt (already in contents[0])
            # Turn 2: Model's function call request (re-using the exact model content to preserve thought_signature)
            contents.append(content)
            # Turn 3: Tool response
            contents.append({
                "role": "tool",
                "parts": [{
                    "functionResponse": {
                        "name": tool_name,
                        "response": {"results": search_result.get("results", [])}
                    }
                }]
            })

            # Prepare payload for second turn to get the final answer
            second_payload = {
                "contents": contents,
                "systemInstruction": {
                    "parts": [{"text": self.system_prompt}]
                },
                "tools": gemini_tools
            }

            second_response = await client.post(url, json=second_payload)
            second_response.raise_for_status()
            second_response_json = second_response.json()

            second_candidates = second_response_json.get("candidates", [])
            if not second_candidates:
                return {"answer": "Error generating final answer.", "sources": urls}

            # Find the actual response part (avoiding reasoning thoughts)
            second_parts = second_candidates[0].get("content", {}).get("parts", [])
            final_text = ""
            for part in reversed(second_parts):
                if "text" in part and not part.get("thought"):
                    final_text = part["text"]
                    break
            if not final_text and second_parts:
                final_text = second_parts[-1].get("text", "")
            return {"answer": final_text, "sources": urls}

    async def _run_openrouter(self, query: str) -> dict:
        """
        Orchestrates the tool-calling loop using OpenRouter's OpenAI-compatible API.
        
        This exists to provide a fallback if the user configures OpenRouter instead of Gemini directly.
        """
        api_key = settings.openrouter_api_key
        model = settings.openrouter_model
        url = "https://openrouter.ai/api/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # Define tools in OpenAI format
        openrouter_tools = [{
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Searches the web for up-to-date information on a given query.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to look up on the web."
                        }
                    },
                    "required": ["query"]
                }
            }
        }]

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": query}
        ]

        payload = {
            "model": model,
            "messages": messages,
            "tools": openrouter_tools
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # First turn: Ask model if tool is needed
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            response_json = response.json()

            choices = response_json.get("choices", [])
            if not choices:
                return {"answer": "No answer returned from OpenRouter.", "sources": []}

            message = choices[0].get("message", {})
            tool_calls = message.get("tool_calls", [])

            if not tool_calls:
                # No tool call; return direct answer
                direct_text = message.get("content", "")
                return {"answer": direct_text, "sources": []}

            # Model requested a tool call
            tool_call = tool_calls[0]
            tool_name = tool_call["function"]["name"]
            tool_args_str = tool_call["function"]["arguments"]
            
            try:
                tool_args = json.loads(tool_args_str)
            except json.JSONDecodeError:
                tool_args = {}
                
            search_query = tool_args.get("query", query)

            # Invoke the web search tool
            search_result = await web_search(search_query)
            
            # Extract URLs for sources
            urls = [item["url"] for item in search_result.get("results", [])]

            # Build history for second turn:
            # 1. User's query and system prompt (already in messages)
            # 2. Assistant's tool call request
            messages.append(message)
            # 3. Tool execution output
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": tool_name,
                "content": json.dumps({"results": search_result.get("results", [])})
            })

            # Request final synthesized answer
            second_payload = {
                "model": model,
                "messages": messages
            }

            second_response = await client.post(url, json=second_payload, headers=headers)
            second_response.raise_for_status()
            second_response_json = second_response.json()

            second_choices = second_response_json.get("choices", [])
            if not second_choices:
                return {"answer": "Error generating final answer.", "sources": urls}

            final_text = second_choices[0].get("message", {}).get("content", "")
            return {"answer": final_text, "sources": urls}
