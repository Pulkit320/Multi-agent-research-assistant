import logging

logger = logging.getLogger(__name__)

# Model pricing registry (price per 1,000,000 tokens)
MODEL_PRICING = {
    # Gemma: $0.07 / M input, $0.21 / M output
    "gemma-4-31b-it": {
        "input_cost_per_million": 0.07,
        "output_cost_per_million": 0.21,
    },
    # Gemini Flash: $0.075 / M input, $0.30 / M output
    "gemini-1.5-flash": {
        "input_cost_per_million": 0.075,
        "output_cost_per_million": 0.30,
    },
    "google/gemini-2.5-flash": {
        "input_cost_per_million": 0.075,
        "output_cost_per_million": 0.30,
    },
}

# Fallback pricing (used if the configured model is not in the registry)
DEFAULT_PRICING = {
    "input_cost_per_million": 0.15,
    "output_cost_per_million": 0.60,
}


def calculate_llm_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculates the USD cost of an LLM invocation based on token counts.

    Why this function exists: To centralize model pricing rules, preventing
    hardcoded calculations in different agent or graph nodes.

    Args:
        model_name: Name of the LLM model used.
        input_tokens: Count of prompt tokens.
        output_tokens: Count of generation tokens.

    Returns:
        Calculated cost in USD as a float.
    """
    pricing = MODEL_PRICING.get(model_name, DEFAULT_PRICING)
    
    input_cost = (input_tokens / 1_000_000.0) * pricing["input_cost_per_million"]
    output_cost = (output_tokens / 1_000_000.0) * pricing["output_cost_per_million"]
    total_cost = input_cost + output_cost

    logger.debug(
        f"Cost calculated for {model_name}: input={input_tokens}, output={output_tokens} -> "
        f"cost=${total_cost:.8f} (input_cost=${input_cost:.8f}, output_cost=${output_cost:.8f})"
    )
    return total_cost
