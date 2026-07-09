# Phase 5 Notes — Reviewer Agent & Human-in-the-Loop

## What We Built

In Phase 5 we added a **ReviewerAgent** and a **human approval gate** to the pipeline:

1. **ReviewerAgent** (`backend/app/agents/reviewer_agent.py`): after the WriterAgent
   produces a report, the Reviewer reads the report alongside the original plan and
   all evidence items. It looks for (a) unsupported claims, (b) sub-questions left
   unanswered, and (c) citation mismatches. It returns a structured verdict:
   `{approved: bool, issues: list[str]}`.

2. **Conditional retry loop** (`graph.py`): if the Reviewer returns `approved=False`
   and fewer than 2 revision cycles have been used, the graph routes back to the Writer
   with the issues list embedded in the query so the Writer can address them. After 2
   revision cycles (3 total writer invocations) or once the Reviewer approves, the
   graph moves on regardless.

3. **Human-in-the-loop pause** (`human_review` node): LangGraph's `interrupt()` call
   halts the graph and serializes all state to a **SQLite checkpoint file**. The graph
   does not reach `END` until a human explicitly calls `POST /report/{id}/approve` or
   `POST /report/{id}/reject`. This survives server restarts.

4. **Approve / Reject endpoints** (`backend/app/routers/reports.py`): resume the
   paused graph checkpoint via `Command(resume="approved"|"rejected")`.

5. **Frontend updates** (`App.jsx`): a 6th monitor node (`reviewer`) animates during
   fact-checking; a **Reviewer Verdict panel** shows the verdict and issues list; and
   **Approve / Reject buttons** call the new endpoints. The report header shows a
   green `✅ Final` or red `❌ Rejected` badge after the human acts.

---

## Why Have an LLM Review Another LLM?

The Writer and Reviewer are optimized for different cognitive tasks:

| Agent | Optimized for | Blind to |
| --- | --- | --- |
| **Writer** | Clear prose, logical structure, engaging headers | Whether every sentence is actually supported by evidence |
| **Reviewer** | Systematic fact-checking, cross-referencing | Presentation quality, flow, reader experience |

Errors the Writer misses that the Reviewer catches:

- **Hallucinated citations**: the Writer may produce `[3]` and there are only 2 evidence
  items. A single-pass LLM rarely notices this because it doesn't "count" while writing.
- **Over-generalisation**: the Writer sees evidence saying "Ottawa's 2021 population was
  1,017,449" and writes "Ottawa has roughly 1.2 million residents" (rounding up from a
  different source). The Reviewer detects that the 1.2 M figure is not in any evidence item.
- **Silent omissions**: the planner asked "Why was Ottawa chosen as the capital?" but the
  Writer focused on population and never addressed it. The Reviewer cross-references the
  plan to catch this.

The key insight is that **writing and auditing require opposite attention patterns**. Trying
to do both in a single LLM prompt causes cognitive interference — the model balances prose
quality against fact fidelity and usually trades off one for the other.

---

## What Is Human-in-the-Loop and Why Not Automate It Fully?

**Human-in-the-Loop (HITL)** means deliberately interrupting an automated pipeline at a
specific checkpoint and requiring a human decision before it continues. In our system, this
checkpoint is after the Reviewer produces its verdict — a human reads both the verdict and
the report before it is released.

### Why not just auto-approve when the Reviewer says `approved: True`?

| Argument for full automation | Why we keep the human |
| --- | --- |
| Faster — no waiting for a person | Reviewer is also an LLM. It can approve a report that contains subtly misleading framing, politically sensitive interpretations, or domain-specific errors it lacks expertise to spot. |
| Consistent — no reviewer fatigue | Humans notice context the LLM cannot access: internal company policy, recent news that post-dates training data, audience sensitivity. |
| Cheaper at scale | The cost of a wrong research report going to a real user is often higher than the cost of 10 seconds of human review. The Reviewer reduces the _rate_ of errors; the human catches the remainder. |

The HITL step is most valuable for **high-stakes or ambiguous** queries. For a low-risk
query like "what is the capital of Canada", auto-approval would be fine — but building
the capability here means the same system can handle high-stakes use cases (medical,
legal, financial research) without re-architecture.

---

## How Conditional Routing Works in LangGraph

LangGraph conditional edges let the graph branch based on the current state. Here is
exactly how the retry loop is implemented in this codebase.

### State fields involved

```python
class GraphState(BaseModel):
    review_verdict: Dict[str, Any]   # {approved: bool, issues: list[str]}
    review_retries: int              # starts at 0, incremented inside reviewer_node
```

### The reviewer node increments the counter

```python
async def reviewer_node(state: GraphState) -> Dict[str, Any]:
    ...
    return {
        "review_verdict": verdict,
        "review_retries": state.review_retries + 1   # always increment on each pass
    }
```

### The condition function reads the counter and decides

```python
def route_after_review(state: GraphState) -> str:
    approved = state.review_verdict.get("approved", True)
    if not approved and state.review_retries < 2:
        return "writer"      # route back for a revision
    return "human_review"    # proceed to pause
```

**Trace through the retry cap of 2:**

| Pass | review_retries after reviewer runs | approved? | Route |
| --- | --- | --- | --- |
| 1st reviewer run | 1 | False | "writer" (1 < 2) |
| 2nd reviewer run (after writer revision) | 2 | False | "human_review" (2 is NOT < 2) |
| Any run | any | True | "human_review" (approved) |

### The conditional edge registration

```python
# First example of conditional routing in this codebase:
workflow.add_conditional_edges(
    "reviewer",                          # source node
    route_after_review,                  # function that returns a string key
    {"writer": "writer", "human_review": "human_review"}  # key → node name map
)
```

LangGraph calls `route_after_review(state)` after every `reviewer_node` invocation. The
returned string is looked up in the map to find the next node to execute.

---

## In My Own Words

*(Fill in after reading the phase — explain the retry loop, the interrupt mechanism, and
the approve/reject flow in your own words.)*
- The retry loop has a fixed count of total 3 writer invocation, after the first writer invocation the reviewer agent is called, if the reviewer agent finds the report unsatisfactory then it will ask the writer agent to revise the report.
- The interrupt mechanism pauses the execution of the graph and waits for a human input to resume. The final report is not created until the human approves the report.
 - The Writer Agents reply is checked by the Reviewer Agent to check for unclaimed statements, queries left unanswered, etc. based to the evaluation gives approval or denial for the reply. Later this is sent to a Human reviewer for final check. 
---

## Questions I Still Have

*(Add any open questions here after reviewing the code.)*
- **Question** What is openrouter and what is its role
- **Answer**OpenRouter (https://openrouter.ai) is an API aggregator — it gives you a single OpenAI-compatible endpoint that can route your request to dozens of different LLMs: Google Gemini, Anthropic Claude, Meta Llama, Mistral, and more.

Its role in this codebase
Every agent (ResearchAgent, AnalystAgent, WriterAgent, ReviewerAgent) has two internal methods:

python
async def run(self, query):
    if settings.gemini_api_key:
        return await self._run_gemini(query)   # calls Google directly
    else:
        return await self._run_openrouter(query)  # calls OpenRouter
OpenRouter is the fallback LLM provider. If you don't have a GEMINI_API_KEY in your .env, the system uses OPENROUTER_API_KEY and the model google/gemini-2.5-flash (or any model you configure) via OpenRouter's unified API instead.

In your current setup
You have GEMINI_API_KEY set → OpenRouter is not being used right now. It's there so the codebase works for someone who only has an OpenRouter account and no direct Gemini access.