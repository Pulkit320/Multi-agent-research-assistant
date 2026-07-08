# Phase 1: Research Agent & Tool Calling

## What We Built

We expanded our monorepo by adding a single "Research Agent" capable of performing Google-style web searches dynamically:
1. **Web Search Tool**: Created a standalone function in [web_search.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/tools/web_search.py) that contacts the Tavily Search API.
2. **Research Agent**: Created the `ResearchAgent` class in [research_agent.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/agents/research_agent.py) implementing a native LLM tool-calling loop (for either Gemini or OpenRouter).
3. **Endpoint**: Added a `POST /research` route in [research.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/routers/research.py) validating payloads and returning structured answers and sources.
4. **Client Interface**: Built an interactive research query form in [App.jsx](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/frontend/src/App.jsx) that displays synthesized text answers and clickable sources.

---

## What Is an Agent, Really?

In artificial intelligence, an **Agent** is not simply a raw Large Language Model (LLM). Instead, an agent is a system consisting of:

$$\text{Agent} = \text{LLM} + \text{System Prompt} + \text{Tools} + \text{Orchestration Loop}$$

1. **The LLM (The Brain)**: The core neural network capable of parsing text, reasoning, and predicting structured intents.
2. **System Prompt (The Persona & Instructions)**: A set of high-priority instructions defining the agent's constraints, role, and operational procedures.
3. **Tools (The Hands)**: Functions or API integrations exposing the external world to the LLM (e.g. searching the web, executing calculations, querying a database).
4. **The Orchestration Loop (The Control flow)**: Code written in a programming language (like Python) that manages the execution flow. It sends requests to the LLM, parses the LLM's requests to use a tool, calls the tool, feeds the result back to the LLM, and repeats until the LLM decides to stop.

---

## How Tool Calling Works Here

Let's walk through the actual sequence of calls when a user queries: *"Who won the latest soccer match between Real Madrid and Barcelona?"*

### Step 1: User Request Submission
- The user types the query into the form in [App.jsx](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/frontend/src/App.jsx) and clicks **Search**.
- The frontend makes a POST request to `http://localhost:8000/research` with `{"query": "Who won the latest soccer match between Real Madrid and Barcelona?"}`.

### Step 2: Route Entry & Agent Initialization
- In [research.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/routers/research.py), the `run_research` function intercepts the request, instantiates a `ResearchAgent`, and calls `await agent.run(request.query)`.

### Step 3: First LLM Inference Turn (Checking for Web Search)
- In [research_agent.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/agents/research_agent.py), `ResearchAgent` compiles the initial request. It sends:
  - System prompt (explicitly instructing the model to use `web_search` for current facts).
  - The user query.
  - The `web_search` function signature (metadata declaration).
- This is sent to the LLM REST API endpoint (e.g., Gemini's `generateContent` URL).
- **The LLM's Decision**: Recognizing that it lacks real-time facts about the "latest soccer match", the LLM returns a structured instruction to call a function instead of a text answer. In Gemini, this is parsed as a `functionCall` part: `{"name": "web_search", "args": {"query": "latest Real Madrid vs Barcelona soccer match score"}}`.

### Step 4: Local Tool Execution
- The Python execution loop in `_run_gemini` (or `_run_openrouter`) intercepts the `functionCall`.
- It executes `await web_search("latest Real Madrid vs Barcelona soccer match score")` inside [web_search.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/tools/web_search.py).
- `web_search` makes an asynchronous POST request to the Tavily API, which retrieves search engine results and returns a JSON dictionary containing matching document contents and URLs.
- The agent extracts the URLs to populate the `sources` list.

### Step 5: Second LLM Inference Turn (Synthesis)
- The agent prepares a second call to the LLM. It appends the history:
  1. Turn 1 (User): Original query.
  2. Turn 2 (Assistant): The model's `functionCall` request.
  3. Turn 3 (Tool): The `functionResponse` containing the search results JSON.
- It sends this history back to the LLM.
- **Final Answer Generation**: The LLM reads the context, synthesizes the final text answer, and returns it.

### Step 6: Response Delivery
- The agent returns `{"answer": final_text, "sources": urls}` to the router.
- The router returns it to the React client.
- The frontend renders the answer and list of sources.

---

## In My Own Words



---

## Questions I Still Have


