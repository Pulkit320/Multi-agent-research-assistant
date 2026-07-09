# Phase 4: Report Generation & Writer Agent

## What We Built

We introduced a specialized report-drafting agent and rich markdown rendering:
1. **Writer Agent**: Created the `WriterAgent` class in [writer_agent.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/agents/writer_agent.py). It receives the original user query and the Analyst's consolidated evidence list, and outputs a formatted Markdown report.
2. **LangGraph Pipeline Integration**: Updated [graph.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/graph.py) by adding a `"writer"` node and updating the workflow order to: `combine` node (Analyst) -> `writer` node (Writer) -> `END`. Added `final_report` to the `GraphState` shared memory.
3. **FastAPI Route Upgrades**: Modified the `POST /research` route in [research.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/routers/research.py) to return `final_report`.
4. **Rich Markdown Render**: Installed the `marked` library in the React project and updated [App.jsx](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/frontend/src/App.jsx) to render the report using `dangerouslySetInnerHTML={{ __html: marked.parse(finalReport) }}` with clean styling.
5. **State Monitor Grid**: Expanded the workflow visualization panel to include the new `"writer"` step.

---

## Why Is Writing Its Own Agent?

Splitting the **Analyst** and the **Writer** into separate, sequential agents is a key application of the **Separation of Concerns (SoC)** principle.

| Layer | Agent | Concern / Objective |
| --- | --- | --- |
| **Logic & Truth** | **Analyst Agent** | Evaluates raw facts, resolves duplicates, handles conflicts, and structures evidence. Focuses strictly on *what is true/factual*. |
| **Presentation & Style** | **Writer Agent** | Formats text, arranges sections, organizes tables, manages narrative flow, and applies markdown tags. Focuses strictly on *how to present it*. |

### The Risk of a Combined Agent
If a single LLM call is asked to perform both tasks simultaneously (truth extraction and report writing), it causes severe cognitive strain:
1. **Hallucination & Omission**: The model frequently becomes distracted by styling parameters (headers, tables, bold structures) and forgets to include key evidence claims or misreports page/URL citations.
2. **Poor Synthesis**: The model may output a beautiful report that is factually shallow or repeats duplicate claims because it did not run a dedicated deduplication turn.
3. **Rigid Presentation**: The business logic (extracting evidence) becomes coupled to a specific output format (Markdown). If you want to change the format later (e.g. to PDF, slides, or JSON API payloads), you are forced to rewrite the entire reasoning prompt instead of just replacing the Writer Agent layer.

---

## How the Writer's Prompt Is Structured

Here is the system prompt configured inside [writer_agent.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/agents/writer_agent.py):

```text
You are an expert report writer. Your job is to take the original user query and a structured list of evidence items, and generate a professional, polished research report in Markdown format.

Your report must follow this exact structure:
1. # [Title based on query]
2. ## Summary
   A 1-2 paragraph executive summary answering the core query.
3. ## Detailed Findings
   Create an H3 section for each sub-question answered (e.g. `### Q1: [Question text]`). 
   Under each sub-question, write the detailed findings based on the evidence. 
   Use bracketed superscript numbers to cite facts (e.g. [1], [2]).
4. ## Sources Table
   Create a Markdown table listing each citation used in the report:
   | Citation | Claim | Source Type | Location / URL |
   | --- | --- | --- | --- |
   | [1] | Claim text | Web or Document | URL or filename (page) |

Rules:
- Rely ONLY on the provided evidence claims. Do not extrapolate or add outside knowledge.
- Return ONLY the raw markdown text of the report. Do not wrap it in ```markdown code blocks.
```

### System Prompt Annotation

- **"Your report must follow this exact structure..."**:
  *Why*: Enforces a reliable, clean document layout so the frontend markdown parser renders heading margins, block spacing, and source tables consistently.
- **"Create an H3 section for each sub-question answered..."**:
  *Why*: Forces the writer to map the report directly back to the Planner Agent's sub-questions, ensuring that no part of the original research plan is omitted in the final text.
- **"Use bracketed superscript numbers to cite facts..."**:
  *Why*: Aligns text claims directly to the rows in the Sources table. This matches academic research standards and makes citations fully auditable.
- **"Rely ONLY on the provided evidence claims..."**:
  *Why*: Acts as a guardrail preventing the model from hallucinating or inserting outdated parameters from its pre-training weights, maintaining strict factual truth.
- **"Return ONLY the raw markdown text..."**:
  *Why*: Prevents the model from wrapping the output in markdown code fence wraps (````markdown ... ````), which would otherwise render as a single large gray block in the frontend.

---

## In My Own Words

In Phase 4, we transitioned the research assistant from a raw factual aggregator into a professional document compiler. By adding a dedicated `WriterAgent` behind the `AnalystAgent`, we cleanly separated the task of "determining what claims are true and factual" (logic) from "formatting and presenting those claims" (presentation). In the backend, the LangGraph workflow was expanded to a 5-step pipeline. In the frontend, we upgraded the execution visualizer to monitor this new step and integrated the `marked` library with custom styling rules in `index.css` to render high-contrast, structured markdown reports (summaries, detailed findings with superscript citations, and sources tables) directly in the user dashboard.

---

## Questions I Still Have
- so if no file is Added for thr RAG agent does the agent not give any answers, because no evidence is found, even though there might be answers for the question in the web for that query?
  - **Answer**: No, the agent **will still** provide answers if they can be found on the web! The parallel nodes (`research` and `document`) execute concurrently. If no documents are uploaded, the `document` retrieval node returns an empty chunks list, but the `research` node will still retrieve active web search results from the Tavily API. The `combine` (Analyst) node merges findings from *both* branches. If the web search succeeded, the analyst will compile those web findings into structured evidence, and the writer will successfully draft the report. The only scenario where the report states "No evidence was provided" is if the query pertains to private information that is neither searchable on the public web nor uploaded to the RAG vector store database.
- so why in the screenshot provided in the walkthrough answers as "Based on the provided evidence, there is no information available to determine the capital of Canada or its population.

Detailed Findings
What is the capital of Canada?
The provided evidence does not contain information regarding the capital city of Canada.

What is its population?
The provided evidence does not contain information regarding the population of Canada's capital.

"