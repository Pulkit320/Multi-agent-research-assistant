from contextlib import asynccontextmanager
import aiosqlite
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.routers import health, research, documents, reports
from app.graph import workflow
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.

    Opens the SQLite connection ONCE at startup and keeps it alive for the
    process lifetime. This is necessary because AsyncSqliteSaver requires an
    open aiosqlite connection — creating it per-request would be slow and would
    close before async operations inside the graph can complete.

    The compiled graph (with checkpointer attached) is stored on app.state so
    all routers can access it via request.app.state.graph without re-creating it.
    """
    # Open the SQLite database that persists all LangGraph checkpoint states.
    # This file survives server restarts, so a paused human-review session can
    # be resumed even after the server is restarted.
    db_conn = await aiosqlite.connect(settings.sqlite_db_path)
    checkpointer = AsyncSqliteSaver(db_conn)

    # Set up the checkpointer's internal tables on first run.
    await checkpointer.setup()

    # Compile the workflow with the checkpointer so every node's output is saved.
    app.state.graph = workflow.compile(checkpointer=checkpointer)

    yield  # Application runs here

    # Cleanup: close the DB connection gracefully on shutdown.
    await db_conn.close()


def create_app() -> FastAPI:
    """
    Factory function to initialize and configure the FastAPI application.

    This function sets up the application instance, registers routers, and
    configures CORS permissions so that the React frontend can query the API.
    """
    fastapi_app = FastAPI(
        title="Multi-Agent Research Assistant API",
        version="0.1.0",
        lifespan=lifespan
    )

    # Configure CORS to permit cross-origin requests from local frontend development servers.
    # Allowing all origins during development; in production, this should be restricted.
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers.
    fastapi_app.include_router(health.router)
    fastapi_app.include_router(research.router)
    fastapi_app.include_router(documents.router)
    fastapi_app.include_router(reports.router)

    return fastapi_app


app = create_app()
