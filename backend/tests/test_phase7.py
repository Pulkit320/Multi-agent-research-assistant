import unittest
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.agents.planner_agent import PlannerAgent
from app.core.pricing import calculate_llm_cost
from app.core.config import settings

# Test mock response payloads for Gemini API
MOCK_GEMINI_RESPONSE = {
    "candidates": [
        {
            "content": {
                "parts": [
                    {"text": '{"sub_questions": ["What is the capital of Italy?", "What is the population of Rome?"]}'}
                ]
            }
        }
    ],
    "usageMetadata": {
        "promptTokenCount": 150,
        "candidatesTokenCount": 50,
        "totalTokenCount": 200
    }
}

# Test mock response payloads for OpenRouter API
MOCK_OPENROUTER_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": '{"sub_questions": ["What is the capital of Italy?", "What is the population of Rome?"]}'
            }
        }
    ],
    "usage": {
        "prompt_tokens": 180,
        "completion_tokens": 60,
        "total_tokens": 240
    }
}


class TestPhase7CostAndFallback(unittest.IsolatedAsyncioTestCase):
    """
    Test suite for Phase 7: verifying LLM pricing calculations,
    token accumulation tracking, and multi-LLM fallback behaviors.
    """

    async def test_gemini_to_openrouter_fallback(self):
        """
        Test that kills the Gemini direct provider (by clearing its key) and
        confirms the agent fallback path to OpenRouter works seamlessly.
        """
        # Force Gemini key to empty and set OpenRouter key to mock value
        with patch.object(settings, "gemini_api_key", ""), \
             patch.object(settings, "openrouter_api_key", "mock_key"):

            planner = PlannerAgent()

            # Mock the OpenRouter API HTTP client call
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = MOCK_OPENROUTER_RESPONSE

            # Using patch to mock httpx.AsyncClient.post calls
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response

                result = await planner.plan("Compare Italy and Rome")

                # Assertions:
                # 1. OpenRouter endpoint was called
                mock_post.assert_called_once()
                url_called = mock_post.call_args[0][0]
                self.assertIn("openrouter.ai", url_called)

                # 2. Results returned correct values and token counts
                self.assertEqual(len(result["plan"]), 2)
                self.assertEqual(result["plan"][0], "What is the capital of Italy?")
                self.assertEqual(result["input_tokens"], 180)
                self.assertEqual(result["output_tokens"], 60)

    async def test_cost_tracking_accumulates(self):
        """
        Test that runs the PlannerAgent via Gemini mock, calculates the USD cost,
        and verifies that cost calculation correctly aggregates.
        """
        with patch.object(settings, "gemini_api_key", "mock_gemini_key"):
            planner = PlannerAgent()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = MOCK_GEMINI_RESPONSE

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response

                # Run 1
                result_1 = await planner.plan("Research A")
                cost_1 = calculate_llm_cost("gemma-4-31b-it", result_1["input_tokens"], result_1["output_tokens"])

                # Run 2
                result_2 = await planner.plan("Research B")
                cost_2 = calculate_llm_cost("gemma-4-31b-it", result_2["input_tokens"], result_2["output_tokens"])

                # Aggregate
                total_input = result_1["input_tokens"] + result_2["input_tokens"]
                total_output = result_1["output_tokens"] + result_2["output_tokens"]
                total_cost = cost_1 + cost_2

                # Assertions:
                self.assertEqual(total_input, 300)
                self.assertEqual(total_output, 100)
                
                # pricing for gemma-4-31b-it is:
                # input: $0.07 / M -> 300 / 1M * 0.07 = 0.000021
                # output: $0.21 / M -> 100 / 1M * 0.21 = 0.000021
                # total: 0.000042
                self.assertAlmostEqual(total_cost, 0.000042, places=9)
                print(f"Cost aggregated correctly: ${total_cost:.8f}")


if __name__ == "__main__":
    unittest.main()
