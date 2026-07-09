# Phase 7 Notes — Cost Tracking and Multi-LLM Fallback

## What This Feature Adds

In Phase 7, we implemented a centralized, isolated system to calculate and aggregate the token usage and dollar cost of every LLM execution in our multi-agent workflow:

1. **Centralized Pricing Registry** (`backend/app/core/pricing.py`): centralizes prompt (input) and completion (output) costs for each supported model.
2. **Metadata extraction**: updated all agents (`PlannerAgent`, `ResearchAgent`, `AnalystAgent`, `WriterAgent`, `ReviewerAgent`) to extract token usage metrics (`usageMetadata` or `usage`) directly from raw LLM REST responses.
3. **Pydantic State Accumulation** (`backend/app/graph.py`): added three state fields annotated with `operator.add` to serve as thread-safe accumulators for parallel and sequential execution nodes.
4. **SSE Event Streaming** (`backend/app/routers/research.py`): streams intermediate and final cost/token counters to the frontend client in real-time.
5. **Real-time Cost Badges** (`frontend/src/App.jsx`): displays prompt tokens, response tokens, and total dollar cost dynamically as the graph executes.
6. **Automated Testing** (`backend/tests/test_phase7.py`): verifies the fallback to OpenRouter when direct Gemini credentials are deleted, and confirms exact cost accumulation over multiple sequential agent runs.

---

## Why It Matters in Production Systems

Without real-time cost and token tracking, production systems are vulnerable to several catastrophic failure modes:

1. **Unbounded Agent Loops / Cost Spike**: In multi-agent loops (like our writer-reviewer loop), a buggy routing condition or an overly critical reviewer can trigger endless revision cycles. If each cycle costs $0.05, a single run stuck in an infinite loop could run up a multi-thousand dollar bill before being detected by standard budget alerts. Cost tracking allows the graph to abort early if a hard budget limit (e.g. $0.50 per query) is breached.
2. **Rate Limit & Concurrency Triggers**: Understanding input/output tokens dynamically enables the application to implement token-bucket rate limiting locally, preventing transient `429 Too Many Requests` API failures on cloud providers.
3. **Unit-Cost Analysis / Billing**: In multi-tenant environments, you cannot bill customers fairly or calculate gross margins without knowing the exact cost of each user request.

---

## How It Was Implemented

### 1. Unified State Accumulators (`graph.py`)

Added the following fields to `GraphState` schema using Python's `Annotated` syntax to register the additive reducer function `operator.add`:

```python
# backend/app/graph.py
class GraphState(BaseModel):
    ...
    # Phase 7 Cost Tracking fields (using Annotated + operator.add for accumulation)
    accumulated_tokens_input: Annotated[int, operator.add] = 0
    accumulated_tokens_output: Annotated[int, operator.add] = 0
    accumulated_cost_usd: Annotated[float, operator.add] = 0.0
```

Because they use `operator.add`, LangGraph automatically sums up the values returned from parallel nodes (like `research_node` and `document_node`) and sequential runs without manual state merging.

### 2. Node Updates (`graph.py` & agents)

Inside `graph.py` node functions, the node calls the updated agent method (which now returns a dictionary of output values + `input_tokens` and `output_tokens`) and calculates the cost:

```python
async def planner_node(state: GraphState) -> Dict[str, Any]:
    planner = PlannerAgent()
    result = await planner.plan(state.original_query)
    
    sub_questions = result.get("plan", [])
    in_tokens = result.get("input_tokens", 0)
    out_tokens = result.get("output_tokens", 0)
    
    cost = calculate_llm_cost(_get_current_model(), in_tokens, out_tokens)
    return {
        "plan": sub_questions,
        "accumulated_tokens_input": in_tokens,
        "accumulated_tokens_output": out_tokens,
        "accumulated_cost_usd": cost
    }
```

### 3. Pricing Logic (`pricing.py`)

A clean cost-calculation module:

```python
# backend/app/core/pricing.py
MODEL_PRICING = {
    "gemma-4-31b-it": {
        "input_cost_per_million": 0.07,
        "output_cost_per_million": 0.21,
    },
    ...
}

def calculate_llm_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model_name, DEFAULT_PRICING)
    input_cost = (input_tokens / 1_000_000.0) * pricing["input_cost_per_million"]
    output_cost = (output_tokens / 1_000_000.0) * pricing["output_cost_per_million"]
    return input_cost + output_cost
```

---

## In My Own Words

*(Fill in after reading the phase — explain the retry loop, the interrupt mechanism, and the approve/reject flow in your own words.)*

---

## Questions I Still Have

*(Add any open questions here after reviewing the code.)*
