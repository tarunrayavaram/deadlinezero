"""
app/services/scheduler_service.py
-----------------------------------
Background APScheduler job that monitors deadlines and flags overdue tasks.

Why APScheduler?
- Lightweight, pure-Python, no external broker required
- Runs in-process with FastAPI
- In production, replace with Cloud Scheduler + Cloud Tasks for horizontal scale

Jobs:
1. deadline_monitor: runs every N minutes, marks overdue tasks, logs warnings
2. daily_briefing: runs at work-start time, logs a daily productivity summary
"""

import asyncio
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.utils.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Module-level scheduler singleton
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


async def _deadline_monitor_job() -> None:
    """
    Background job: scan for tasks past their deadline and mark them OVERDUE.
    Logs a warning for any newly-overdue tasks.
    """
    try:
        async with AsyncSessionLocal() as db:
            from app.services.task_service import TaskService
            service = TaskService(db)
            overdue = await service.get_overdue_tasks()
            if overdue:
                logger.warning(
                    "⚠️  Deadline monitor: %d overdue task(s) detected: %s",
                    len(overdue),
                    [t.title for t in overdue],
                )
            else:
                logger.debug("Deadline monitor: no overdue tasks")
            await db.commit()
    except Exception as exc:
        logger.error("Deadline monitor job failed: %s", exc, exc_info=True)


async def _daily_briefing_job() -> None:
    """
    Daily briefing job: logs a workload summary at the start of each day.
    In a full implementation, this would send push/email notifications.
    """
    try:
        async with AsyncSessionLocal() as db:
            from app.services.task_service import TaskService
            service = TaskService(db)
            stats = await service.get_workload_stats()
            logger.info(
                "📋 Daily Briefing | Pending: %d | Due today: %d | Overdue: %d | "
                "Burnout: %s (%.0f%%)",
                stats["pending_tasks"],
                stats["due_today"],
                stats["overdue_tasks"],
                stats["burnout_level"],
                stats["burnout_score"] * 100,
            )
            await db.commit()
    except Exception as exc:
        logger.error("Daily briefing job failed: %s", exc, exc_info=True)


def start_scheduler() -> None:
    """Register jobs and start the scheduler. Called once at app startup."""
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled via SCHEDULER_ENABLED=false")
        return

    scheduler = get_scheduler()

    # Job 1: Check overdue tasks every N minutes
    scheduler.add_job(
        _deadline_monitor_job,
        trigger=IntervalTrigger(minutes=settings.deadline_check_interval_minutes),
        id="deadline_monitor",
        name="Deadline Monitor",
        replace_existing=True,
        misfire_grace_time=60,
    )

    # Job 2: Daily briefing at 09:00 UTC
    scheduler.add_job(
        _daily_briefing_job,
        trigger=CronTrigger(hour=9, minute=0),
        id="daily_briefing",
        name="Daily Productivity Briefing",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Scheduler started | deadline_monitor every %dm | daily_briefing at 09:00 UTC",
        settings.deadline_check_interval_minutes,
    )


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler. Called at app shutdown."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
