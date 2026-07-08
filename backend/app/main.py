from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import health

def create_app() -> FastAPI:
    """
    Factory function to initialize and configure the FastAPI application.
    
    This function sets up the application instance, registers routers, and
    configures CORS permissions so that the React frontend can query the API.
    """
    fastapi_app = FastAPI(
        title="Multi-Agent Research Assistant API",
        version="0.1.0"
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

    return fastapi_app

app = create_app()
