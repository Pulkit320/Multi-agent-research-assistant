# Phase 6 Notes — Real-Time Streaming via Server-Sent Events (SSE)

## What We Built

In Phase 6, we refactored the research execution from a blocking synchronous process into a live-updating stream:

1. **SSE Manager** (`backend/app/core/sse_manager.py`): An in-memory synchronization layer that maps `report_id` to `asyncio.Event` and decision string variables.
2. **GET /research/stream** (`backend/app/routers/research.py`): A Server-Sent Events (SSE) endpoint that streams the graph's execution live. It uses LangGraph's `.astream(..., stream_mode="tasks")` to capture the start and finish of each node.
3. **Stream-Only Resumption** (`backend/app/routers/reports.py`): The Approve and Reject endpoints no longer call `graph.ainvoke` directly. Instead, they write the decision to the `sse_manager` and fire the event. The original stream connection wakes up, calls `graph.astream(Command(resume=decision), ...)` to complete the graph, and outputs the final report to the same stream.
4. **Unified Frontend Monitor** (`frontend/src/App.jsx`): Replaced individual step hooks with a single `nodeStatuses` object (`'pending' | 'in-progress' | 'completed'`). It connects via `EventSource` and advances node states as SSE events arrive, rendering outputs (plan, evidence) live.

---

## Why Streaming Instead of Waiting for the Full Response?

Waiting for a full multi-agent orchestration pipeline to execute synchronously leads to a poor user experience:
1. **Perceived Performance & INP (Interaction to Next Paint)**: The total execution time of a parallel RAG + Web research loop with reviewer and writer agents is typically 20 to 45 seconds. Without streaming, the page hangs, leading the user to believe the request has failed, timed out, or crashed.
2. **Progress Transparency**: By streaming start and finish events, the user can see exactly what the orchestrator is doing (e.g. "Planner is running...", "Completed: Web Search", "Running: Analyst Merge"). This builds trust because the system's "thought process" is transparent.
3. **Immediate Content Delivery**: Intermediate outputs like the research plan (list of sub-questions) and the compiled evidence claims are displayed to the user as soon as they are completed, rather than waiting for the writer and reviewer to finish.
4. **Early Termination / Interactivity**: If the user sees the planner deconstruct their query incorrectly in the first 2 seconds, they can abort the connection early rather than waiting 30 seconds for a useless report.

---

## SSE vs WebSockets

We chose **Server-Sent Events (SSE)** over WebSockets for this feature. Here is the technical comparison:

| Metric | Server-Sent Events (SSE) | WebSockets |
| --- | --- | --- |
| **Protocol** | Standard HTTP (one-way server-to-client) | Custom TCP-based protocol (two-way/bidirectional) |
| **Complexity** | Extremely simple (native `EventSource` in browser, standard FastAPI `StreamingResponse`) | Higher complexity (requires handshake, special framing, custom client libraries) |
| **Firewall Friendliness** | Fits standard port 80/443, naturally compatible with Nginx, HTTP/2 multiplexing | Often blocked or closed prematurely by strict corporate firewalls, load balancers, or proxies |
| **Reconnection** | Built-in automatic reconnection handling by the browser | Must be implemented manually in JavaScript (reconnect loops, exponential backoff) |

### When to choose WebSockets instead
You should reach for WebSockets only when the feature requires **high-frequency, bidirectional communication** (both client-to-server and server-to-client in real-time). Examples include multiplayer gaming, collaborative canvas editors (like Figma), or text chat interfaces where the user is typing message fragments in real-time. 

For research reports, the communication is purely one-way: the client submits the query once, and the server streams the progression. SSE is the simpler, standard, and more resilient choice.

---

## How `.stream()` Differs From `.invoke()` in LangGraph

LangGraph provides two main execution patterns:

### 1. `.invoke()` (Synchronous-style execution)
- **Mechanics**: Runs the StateGraph blockingly. The execution starts at `START`, runs through all nodes and edges (handling internal retries or conditional routing), and returns only when the final state reaches `END` (or raises an exception like `GraphInterrupt`).
- **Use Case**: Simple pipelines, batch processing scripts, or offline agents.

### 2. `.stream()` / `.astream()` (Event-driven generator)
- **Mechanics**: Returns an async iterator that yields outputs progressively during execution.
- **`stream_mode` options**:
  - `updates`: Yields the output dictionary of each node after it finishes.
  - `values`: Yields the full state snapshot after each node finishes.
  - `tasks`: Yields a start chunk when a node is queued (`id`, `name`, `input`) and a finish chunk when the node completes execution (`result`, `error`).
- **Use Case**: UI-driven applications, monitoring systems, and human-in-the-loop flows. It allows you to intercept the state intermediate values and feed them to the user in real-time.

---

## In My Own Words

*(Fill in after reading the phase — explain the retry loop, the interrupt mechanism, and the approve/reject flow in your own words.)*

---

## Questions I Still Have

*(Add any open questions here after reviewing the code.)*
