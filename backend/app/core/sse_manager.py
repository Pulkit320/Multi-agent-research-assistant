import asyncio
from typing import Dict


class SSEManager:
    """
    SSEManager maintains in-memory synchronization events and decisions for active
    Server-Sent Events (SSE) research streams.

    Why this class exists: When GET /research/stream is invoked, the LangGraph graph execution
    pauses at the human-review node. The HTTP request must stay open. By registering an
    asyncio.Event for the report_id, the generator thread can await the event. When a separate
    HTTP call (POST /report/{id}/approve or /reject) is received, it notifies this manager,
    waking up the generator thread to resume graph execution and stream the final response.
    """

    def __init__(self):
        # Maps report_id to its corresponding asyncio.Event synchronization flag
        self.active_events: Dict[str, asyncio.Event] = {}
        # Maps report_id to the human decision string ("approved" or "rejected")
        self.active_decisions: Dict[str, str] = {}

    def register(self, report_id: str) -> asyncio.Event:
        """
        Registers a new synchronization event for a research session.
        """
        event = asyncio.Event()
        self.active_events[report_id] = event
        return event

    def set_decision(self, report_id: str, decision: str) -> None:
        """
        Sets the human decision for a session and fires the sync event to wake up the stream.
        """
        self.active_decisions[report_id] = decision
        event = self.active_events.get(report_id)
        if event:
            event.set()

    def get_decision(self, report_id: str) -> str:
        """
        Retrieves the decision for a session. Returns empty string if not found.
        """
        return self.active_decisions.get(report_id, "")

    def cleanup(self, report_id: str) -> None:
        """
        Removes session resources from memory to prevent leaks.
        """
        self.active_events.pop(report_id, None)
        self.active_decisions.pop(report_id, None)


# Singleton manager instance shared across the research and reports routers
sse_manager = SSEManager()
