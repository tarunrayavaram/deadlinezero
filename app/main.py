"""
app/main.py
-----------
FastAPI application entry point.

Lifecycle:
1. startup  → init DB, start background scheduler, setup logging
2. request  → routers handle, DI injects DB session
3. shutdown → stop scheduler, close DB connections
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.routers import agent, health, tasks
from app.services.scheduler_service import start_scheduler, stop_scheduler
from app.utils.logging_config import get_logger, setup_logging

settings = get_settings()
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle startup and shutdown events."""
    # --- Startup ---
    logger.info("🚀 Starting %s [%s]", settings.app_name, settings.app_env)
    await init_db()
    logger.info("Database initialised")
    start_scheduler()

    yield  # App is running

    # --- Shutdown ---
    logger.info("Shutting down %s", settings.app_name)
    stop_scheduler()


def create_app() -> FastAPI:
    """Application factory – makes testing easy."""
    app = FastAPI(
        title=settings.app_name,
        description=(
            "🎯 DeadlineZero – AI-powered productivity companion that proactively helps you "
            "plan, prioritise, and complete tasks before deadlines are missed. "
            "Powered by Google Gemini with agentic function calling."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Global exception handler
    # ------------------------------------------------------------------
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception on %s: %s", request.url, exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal error occurred. Please try again."},
        )

    # ------------------------------------------------------------------
    # Routers
    # ------------------------------------------------------------------
    app.include_router(health.router)
    app.include_router(tasks.router)
    app.include_router(agent.router)

    # ------------------------------------------------------------------
    # Static files (frontend)
    # ------------------------------------------------------------------
    import os
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    if os.path.isdir(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=not settings.is_production,
        log_level="debug" if settings.app_debug else "info",
    )
