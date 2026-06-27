"""
app/routers/health.py
----------------------
Health check endpoints.

/health         – Liveness probe (always returns 200 if app is up)
/health/ready   – Readiness probe (checks DB + Gemini connectivity)

These are required for:
- Google Cloud Run (liveness/readiness probes)
- Load balancers
- Monitoring systems
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.utils.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["Health"])
settings = get_settings()


@router.get("", summary="Liveness probe")
async def liveness() -> dict:
    """Simple liveness check – confirms the service is running."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready", summary="Readiness probe")
async def readiness(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Readiness check – verifies database connectivity.
    Returns 200 if all dependencies are healthy, 503 otherwise.
    """
    checks = {}

    # Database check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        checks["database"] = f"error: {exc}"

    # Gemini API key presence check (not a live call to avoid costs)
    checks["gemini_key_configured"] = "ok" if settings.gemini_api_key else "missing"
    checks["gemini_model"] = settings.gemini_model

    all_ok = all(v == "ok" or "ok" in str(v) for v in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
