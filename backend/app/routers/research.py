import asyncio
import json
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Optional
from langgraph.types import Command
from app.core.sse_manager import sse_manager

# first example of SSE stream in this codebase
#
# This router registers GET /research/stream, which provides real-time updates
# on graph execution states. We transitioned to a streaming design to prevent
# frontend timeouts during long-running agent workflows (which can take 30+ seconds).
router = APIRouter()


def format_sse(event: str, data: dict) -> str:
    """
    Formats the payload as a standard Server-Sent Event (SSE) message.
    Requires a double newline at the end to flush the event to the browser.
    """
    payload = {"event": event, **data}
    return f"data: {json.dumps(payload)}\n\n"


@router.get("/research/stream")
async def stream_research(query: str, request: Request, report_id: Optional[str] = None):
    """
    GET endpoint that yields a Server-Sent Events (SSE) stream of the research graph execution.

    Why GET: SSE protocol natively requires GET requests.
    If report_id is provided, the handler tries to reconnect to an existing session.
    Otherwise, it initiates a new research graph execution.
    """
    graph = request.app.state.graph

    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    async def event_generator():
        # 1. Establish the session ID (report_id) and register with sse_manager
        nonlocal report_id
        if not report_id:
            report_id = str(uuid4())

        # Register sync event immediately so other threads can notify this stream
        sync_event = sse_manager.register(report_id)

        try:
            # Emit the start event immediately so the client learns the report_id
            yield format_sse("start", {"report_id": report_id})

            # 2. Setup the graph execution config
            thread_config = {"configurable": {"thread_id": report_id}}
            initial_state = {
                "original_query": query.strip(),
                "report_id": report_id,
            }

            # 3. Stream the graph execution using LangGraph's astream() under 'tasks' mode.
            # stream_mode='tasks' yields detailed start/finish snapshots for each node.
            async for chunk in graph.astream(initial_state, config=thread_config, stream_mode="tasks"):
                node_name = chunk.get("name", "")

                # Skip execution logging for START, END, or system steps
                if node_name in ("__start__", "__end__"):
                    continue

                # Check if this chunk is a node START or FINISH event
                if "result" in chunk or "error" in chunk:
                    # Node has finished. Extract any updated state fields for the frontend.
                    res_val = chunk.get("result") or {}
                    
                    data_payload = {}
                    if node_name == "planner":
                        data_payload["plan"] = res_val.get("plan", [])
                    elif node_name == "combine":
                        data_payload["evidence"] = res_val.get("evidence", [])
                        data_payload["sources"] = res_val.get("sources", [])
                    elif node_name == "writer":
                        data_payload["final_report"] = res_val.get("final_report", "")
                    elif node_name == "reviewer":
                        data_payload["review_verdict"] = res_val.get("review_verdict", {})

                    # Extract accumulated cost and tokens from snapshot at this step
                    snap = await graph.aget_state(thread_config)
                    data_payload["accumulated_tokens_input"] = snap.values.get("accumulated_tokens_input", 0)
                    data_payload["accumulated_tokens_output"] = snap.values.get("accumulated_tokens_output", 0)
                    data_payload["accumulated_cost_usd"] = snap.values.get("accumulated_cost_usd", 0.0)

                    yield format_sse("node_finish", {
                        "node": node_name,
                        "status": f"Completed: {node_name}",
                        "data": data_payload
                    })
                else:
                    # Node has started
                    yield format_sse("node_start", {
                        "node": node_name,
                        "status": f"Running: {node_name}"
                    })

            # 4. Check if the graph is currently paused at the human_review node
            state_snapshot = await graph.aget_state(thread_config)
            
            # If the next node in the graph queue is 'human_review', we have hit the interrupt.
            # We emit 'paused' and sleep until the human acts.
            if "human_review" in state_snapshot.next:
                # Retrieve the review verdict from the state values
                verdict = state_snapshot.values.get("review_verdict", {})
                yield format_sse("paused", {
                    "node": "human_review",
                    "status": "Awaiting human approval...",
                    "data": {"review_verdict": verdict}
                })

                # Await the click event from POST /report/{id}/approve or reject
                await sync_event.wait()

                # 5. Retrieve decision from manager and resume graph execution
                decision = sse_manager.get_decision(report_id)
                yield format_sse("node_start", {
                    "node": "human_review",
                    "status": f"Resuming: human_review with decision '{decision}'"
                })

                # Resume the graph. Command(resume=decision) triggers human_review_node to finish.
                async for chunk in graph.astream(
                    Command(resume=decision),
                    config=thread_config,
                    stream_mode="tasks"
                ):
                    node_name = chunk.get("name", "")
                    if node_name == "human_review" and ("result" in chunk or "error" in chunk):
                        # human_review completed
                        yield format_sse("node_finish", {
                            "node": "human_review",
                            "status": "Human review completed",
                            "data": {"human_decision": decision}
                        })

                # Re-fetch state values after resumption to get final report and citations
                final_snapshot = await graph.aget_state(thread_config)
                final_vals = final_snapshot.values

                yield format_sse("done", {
                    "status": f"Research complete. Decision: {decision}",
                    "data": {
                        "human_decision": decision,
                        "final_report": final_vals.get("final_report", ""),
                        "sources": final_vals.get("sources", []),
                        "accumulated_tokens_input": final_vals.get("accumulated_tokens_input", 0),
                        "accumulated_tokens_output": final_vals.get("accumulated_tokens_output", 0),
                        "accumulated_cost_usd": final_vals.get("accumulated_cost_usd", 0.0)
                    }
                })
            else:
                # Graph completed normally without hitting human review pause
                yield format_sse("done", {
                    "status": "Research complete.",
                    "data": {
                        "human_decision": "approved",
                        "final_report": state_snapshot.values.get("final_report", ""),
                        "sources": state_snapshot.values.get("sources", []),
                        "accumulated_tokens_input": state_snapshot.values.get("accumulated_tokens_input", 0),
                        "accumulated_tokens_output": state_snapshot.values.get("accumulated_tokens_output", 0),
                        "accumulated_cost_usd": state_snapshot.values.get("accumulated_cost_usd", 0.0)
                    }
                })

        except Exception as stream_err:
            print(f"Error in SSE event generator: {stream_err}")
            yield format_sse("error", {"status": f"Streaming error: {stream_err}"})
        finally:
            # Clean up memory references for this session
            sse_manager.cleanup(report_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
