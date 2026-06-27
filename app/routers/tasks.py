"""
app/routers/tasks.py
---------------------
CRUD REST API for tasks.
Follows REST conventions: GET /tasks, POST /tasks, PATCH /tasks/{id}, DELETE /tasks/{id}
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate
from app.services.task_service import TaskService
from app.utils.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/tasks", tags=["Tasks"])


def _get_service(db: AsyncSession = Depends(get_db)) -> TaskService:
    return TaskService(db)


@router.get("", response_model=TaskListResponse, summary="List all tasks")
async def list_tasks(
    status_filter: Optional[str] = Query(default="all", description="Filter: all | pending | in_progress | completed | overdue"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: TaskService = Depends(_get_service),
) -> TaskListResponse:
    """
    Return all top-level tasks with summary statistics.
    Pass ?status_filter=pending to filter by status.
    """
    tasks = await service.get_tasks(status_filter=status_filter, limit=limit, offset=offset)
    stats = await service.get_workload_stats()
    return TaskListResponse(
        tasks=tasks,
        total=stats["total_tasks"],
        pending=stats["pending_tasks"],
        overdue=stats["overdue_tasks"],
        completed_today=stats["completed_today"],
    )


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, summary="Create task")
async def create_task(
    payload: TaskCreate,
    service: TaskService = Depends(_get_service),
) -> TaskResponse:
    """Create a new task. Gemini auto-categorises if no category is provided."""
    task = await service.create_task(payload)
    return task


@router.get("/{task_id}", response_model=TaskResponse, summary="Get task by ID")
async def get_task(
    task_id: int,
    service: TaskService = Depends(_get_service),
) -> TaskResponse:
    task = await service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@router.patch("/{task_id}", response_model=TaskResponse, summary="Update task")
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    service: TaskService = Depends(_get_service),
) -> TaskResponse:
    """Partial update – only provided fields are changed."""
    try:
        task = await service.update_task(task_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete task")
async def delete_task(
    task_id: int,
    service: TaskService = Depends(_get_service),
) -> None:
    deleted = await service.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


@router.get("/stats/workload", summary="Get workload statistics")
async def get_workload_stats(
    service: TaskService = Depends(_get_service),
) -> dict:
    """Returns burnout score, task counts, and urgency breakdown."""
    return await service.get_workload_stats()
