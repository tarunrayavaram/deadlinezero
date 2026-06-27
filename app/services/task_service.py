"""
app/services/task_service.py
-----------------------------
Business logic layer for task management.
All database operations are here – routers stay thin.

Responsibilities:
- CRUD operations on Task model
- AI-powered task decomposition (calls Gemini)
- Workload statistics computation
- Schedule generation
- Urgency scoring algorithm
"""

import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.task import Task, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.gemini_service import generate_json, generate_text
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class TaskService:
    """All task-related database and AI operations."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_task(self, data: TaskCreate) -> Task:
        """Create a task and auto-assign an AI-generated category if missing."""
        task = Task(**data.model_dump(exclude_unset=True))

        # Auto-categorise with Gemini if no category provided
        if not task.category:
            try:
                task.category = await self._ai_categorise(task.title, task.description)
            except Exception as exc:
                logger.warning("AI categorisation failed: %s", exc)
                task.category = "General"

        # Compute initial urgency score
        task.urgency_score = self._compute_urgency(task)

        self._db.add(task)
        await self._db.flush()
        await self._db.refresh(task)
        logger.info("Task created: id=%d title=%r", task.id, task.title)
        return task

    async def get_task(self, task_id: int) -> Optional[Task]:
        result = await self._db.execute(
            select(Task)
            .options(selectinload(Task.subtasks))
            .where(Task.id == task_id)
        )
        return result.scalar_one_or_none()

    async def get_tasks(
        self,
        status_filter: str = "all",
        limit: int = 100,
        offset: int = 0,
    ) -> List[Task]:
        """Return tasks, optionally filtered by status."""
        q = (
            select(Task)
            .options(selectinload(Task.subtasks))  # eager-load within session
            .where(Task.parent_id.is_(None))       # top-level only
        )

        if status_filter and status_filter != "all":
            try:
                q = q.where(Task.status == TaskStatus(status_filter))
            except ValueError:
                pass  # ignore invalid filter

        q = q.order_by(Task.priority.asc(), Task.deadline.asc().nullslast())
        q = q.limit(limit).offset(offset)
        result = await self._db.execute(q)
        return list(result.scalars().all())

    async def update_task(self, task_id: int, data: TaskUpdate) -> Task:
        task = await self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")

        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(task, field, value)

        # Mark completion timestamp (naive UTC — SQLite strips tzinfo anyway)
        if data.status == TaskStatus.COMPLETED and task.completed_at is None:
            task.completed_at = datetime.utcnow()

        # Recompute urgency on update
        task.urgency_score = self._compute_urgency(task)

        await self._db.flush()
        await self._db.refresh(task)
        return task

    async def delete_task(self, task_id: int) -> bool:
        task = await self.get_task(task_id)
        if task is None:
            return False
        await self._db.delete(task)
        await self._db.flush()
        return True

    async def get_overdue_tasks(self) -> List[Task]:
        """Tasks whose deadline has passed and are not completed/cancelled."""
        now_naive = datetime.utcnow()  # naive UTC — matches SQLite stored values
        q = (
            select(Task)
            .options(selectinload(Task.subtasks))
            .where(
                and_(
                    Task.deadline < now_naive,
                    Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
                )
            )
        )
        result = await self._db.execute(q)
        tasks = list(result.scalars().all())

        # Auto-mark as overdue
        for task in tasks:
            if task.status != TaskStatus.OVERDUE:
                task.status = TaskStatus.OVERDUE
        await self._db.flush()
        return tasks

    # ------------------------------------------------------------------
    # AI-powered operations
    # ------------------------------------------------------------------

    async def ai_decompose_task(self, task_id: int, num_subtasks: int = 4) -> List[Task]:
        """
        Use Gemini to break a task into subtasks and persist them.
        This is a key agentic feature – autonomous task planning.
        """
        task = await self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")

        prompt = f"""
You are a productivity expert. Break this task into {num_subtasks} concrete, actionable subtasks.

Task: {task.title}
Description: {task.description or 'N/A'}
Deadline: {task.deadline.isoformat() if task.deadline else 'Not set'}
Category: {task.category or 'General'}

Return a JSON object with this exact structure:
{{
  "subtasks": [
    {{
      "title": "Clear action verb + specific outcome",
      "description": "What exactly to do",
      "estimated_minutes": 30,
      "priority": 2
    }}
  ]
}}

Rules:
- Each subtask must be completable in a single focused session
- Title must start with an action verb (Research, Write, Review, etc.)
- estimated_minutes should be realistic (15–180)
- Priority: 1=Critical, 2=High, 3=Medium, 4=Low
"""
        result = generate_json(prompt)
        subtask_data = result.get("subtasks", [])

        created = []
        for i, st in enumerate(subtask_data):
            subtask = Task(
                title=st.get("title", f"Subtask {i+1}"),
                description=st.get("description"),
                estimated_minutes=st.get("estimated_minutes", 30),
                priority=st.get("priority", 3),
                category=task.category,
                parent_id=task_id,
                deadline=task.deadline,  # inherit parent deadline
            )
            self._db.add(subtask)
            created.append(subtask)

        await self._db.flush()
        for s in created:
            await self._db.refresh(s)

        # Update parent with AI plan
        task.ai_plan = json.dumps([s.title for s in created])
        await self._db.flush()

        logger.info("Decomposed task %d into %d subtasks", task_id, len(created))
        return created

    async def get_workload_stats(self) -> Dict[str, Any]:
        """Compute workload statistics used by the AI coach and dashboard."""
        # Use naive UTC throughout — matches how SQLite returns datetimes
        now = datetime.utcnow()
        today_end = now.replace(hour=23, minute=59, second=59)
        week_end = now + timedelta(days=7)

        all_tasks = await self.get_tasks(limit=500)
        pending = [t for t in all_tasks if t.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)]
        overdue = [
            t for t in all_tasks
            if t.deadline and t.deadline < now
            and t.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)
        ]
        due_today = [t for t in pending if t.deadline and t.deadline <= today_end]
        due_week = [t for t in pending if t.deadline and now < t.deadline <= week_end]

        total_pending_minutes = sum(t.estimated_minutes or 60 for t in pending)
        available_minutes_today = 8 * 60  # assume 8h workday

        # Burnout score: ratio of pending work to available time, capped at 1.0
        burnout_score = min(total_pending_minutes / max(available_minutes_today, 1), 1.0)

        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        completed_today = await self._db.execute(
            select(func.count(Task.id)).where(
                and_(
                    Task.status == TaskStatus.COMPLETED,
                    Task.completed_at >= today_start,
                )
            )
        )
        completed_today_count = completed_today.scalar() or 0

        return {
            "total_tasks": len(all_tasks),
            "pending_tasks": len(pending),
            "overdue_tasks": len(overdue),
            "due_today": len(due_today),
            "due_this_week": len(due_week),
            "total_pending_minutes": total_pending_minutes,
            "total_pending_hours": round(total_pending_minutes / 60, 1),
            "burnout_score": round(burnout_score, 2),
            "burnout_level": (
                "critical" if burnout_score > 0.9 else
                "high" if burnout_score > 0.7 else
                "moderate" if burnout_score > 0.4 else "healthy"
            ),
            "completed_today": completed_today_count,
            "high_priority_pending": len([t for t in pending if t.priority <= 2]),
        }

    async def generate_schedule(
        self,
        target_date: str,
        work_start_hour: int = 9,
        work_end_hour: int = 18,
    ) -> Dict[str, Any]:
        """Generate a time-blocked daily schedule using Gemini."""
        tasks = await self.get_tasks(limit=50)
        pending = [
            t for t in tasks
            if t.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
        ]

        task_list_str = "\n".join(
            f"- [{t.priority}] {t.title} "
            f"(est: {t.estimated_minutes or 60}min, "
            f"deadline: {t.deadline.strftime('%Y-%m-%d') if t.deadline else 'none'})"
            for t in pending[:20]
        )

        prompt = f"""
Create an optimal daily schedule for {target_date}.
Work hours: {work_start_hour}:00 – {work_end_hour}:00

Pending tasks (priority 1=highest):
{task_list_str or 'No pending tasks'}

Return JSON:
{{
  "schedule": [
    {{
      "start_time": "09:00",
      "end_time": "10:30",
      "task_title": "...",
      "block_type": "work"
    }}
  ],
  "ai_notes": "Brief rationale for this schedule"
}}

Rules:
- Include 15-min breaks every 90 minutes
- Place high-priority tasks in morning peak hours
- Add a 30-min buffer at end of day
- block_type: work | break | buffer
"""
        result = generate_json(prompt)
        schedule = result.get("schedule", [])
        work_blocks = [b for b in schedule if b.get("block_type") == "work"]
        break_blocks = [b for b in schedule if b.get("block_type") == "break"]

        return {
            "date": target_date,
            "schedule": schedule,
            "total_work_minutes": len(work_blocks) * 90,
            "total_break_minutes": len(break_blocks) * 15,
            "ai_notes": result.get("ai_notes", ""),
        }

    async def get_productivity_insights(self) -> Dict[str, Any]:
        """Analyse productivity patterns and return coaching insights."""
        stats = await self.get_workload_stats()
        tasks = await self.get_tasks(limit=200)

        completed = [t for t in tasks if t.status == TaskStatus.COMPLETED]
        category_counts: Dict[str, int] = {}
        for t in tasks:
            cat = t.category or "General"
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "total_completed": len(completed),
            "completion_rate": round(
                len(completed) / max(len(tasks), 1) * 100, 1
            ),
            "workload_stats": stats,
            "top_categories": sorted(
                category_counts.items(), key=lambda x: x[1], reverse=True
            )[:5],
            "burnout_warning": stats["burnout_score"] > 0.7,
            "recommendations": self._generate_local_recommendations(stats),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_urgency(self, task: Task) -> float:
        """
        Urgency score 0.0–1.0.
        Factors: time until deadline (exponential decay) × priority weight.
        """
        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            return 0.0

        priority_weight = {1: 1.0, 2: 0.85, 3: 0.65, 4: 0.45, 5: 0.25}.get(task.priority, 0.5)

        if task.deadline is None:
            return 0.2 * priority_weight

        now = datetime.utcnow()
        deadline = task.deadline  # always naive UTC after schema normalization

        hours_left = (deadline - now).total_seconds() / 3600
        if hours_left <= 0:
            return 1.0

        # Exponential urgency increase as deadline approaches
        import math
        time_urgency = 1.0 - math.exp(-max(0, 48 - hours_left) / 24)
        return round(min(time_urgency * priority_weight + 0.1 * priority_weight, 1.0), 3)

    async def _ai_categorise(self, title: str, description: Optional[str]) -> str:
        """Ask Gemini to categorise a task into a short label."""
        prompt = (
            f"Categorise this task into ONE short label (max 2 words): "
            f"'{title}'. Description: '{description or ''}'. "
            f"Return only the category label, nothing else. "
            f"Examples: Work, Study, Finance, Health, Personal, Shopping, Admin"
        )
        category = await _run_sync(generate_text, prompt)
        return category.strip()[:50] if category else "General"

    def _generate_local_recommendations(self, stats: Dict) -> List[str]:
        """Generate rule-based recommendations (no AI call needed)."""
        recs = []
        if stats["overdue_tasks"] > 0:
            recs.append(f"⚠️ You have {stats['overdue_tasks']} overdue task(s). Address these immediately.")
        if stats["due_today"] > 3:
            recs.append(f"Today is packed with {stats['due_today']} deadlines. Consider time-blocking your day.")
        if stats["burnout_score"] > 0.8:
            recs.append("🔴 High workload detected. Consider delegating or pushing low-priority deadlines.")
        if stats["high_priority_pending"] > 5:
            recs.append("You have many high-priority tasks. Focus on completing 1–2 before adding more.")
        if not recs:
            recs.append("✅ Workload looks healthy. Keep up the momentum!")
        return recs


async def _run_sync(fn, *args):
    """Run a synchronous function in the async context."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn, *args)
