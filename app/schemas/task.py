"""
app/schemas/task.py
-------------------
Pydantic v2 schemas for Task CRUD operations.
These are the API contract – separate from the ORM models (single responsibility).
"""

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.task import TaskPriority, TaskStatus


def _to_naive_utc(dt: datetime) -> datetime:
    """Convert any datetime to naive UTC for SQLite-compatible storage."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


# ------------------------------------------------------------------
# Base schema (shared fields)
# ------------------------------------------------------------------
class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Task title")
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[str] = Field(None, max_length=100)
    priority: int = Field(default=3, ge=1, le=5, description="1=Critical … 5=Minimal")
    deadline: Optional[datetime] = Field(None, description="UTC deadline datetime")
    estimated_minutes: Optional[int] = Field(None, ge=1, le=14400)
    scheduled_start: Optional[datetime] = None
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = Field(None, max_length=100)

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        return v.strip()

    @field_validator("deadline", "scheduled_start", mode="before")
    @classmethod
    def normalize_datetime(cls, v: object) -> object:
        """Normalize to naive UTC so SQLite comparisons are consistent."""
        if v is None:
            return v
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime):
            return _to_naive_utc(v)
        return v


# ------------------------------------------------------------------
# Create request
# ------------------------------------------------------------------
class TaskCreate(TaskBase):
    parent_id: Optional[int] = Field(None, description="Parent task ID for subtasks")


# ------------------------------------------------------------------
# Update request (all fields optional for PATCH semantics)
# ------------------------------------------------------------------
class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[str] = Field(None, max_length=100)
    priority: Optional[int] = Field(None, ge=1, le=5)
    status: Optional[TaskStatus] = None
    deadline: Optional[datetime] = None
    estimated_minutes: Optional[int] = Field(None, ge=1, le=14400)
    scheduled_start: Optional[datetime] = None
    is_recurring: Optional[bool] = None
    recurrence_pattern: Optional[str] = Field(None, max_length=100)
    ai_plan: Optional[str] = None
    ai_summary: Optional[str] = None


# ------------------------------------------------------------------
# Response schema (read model)
# ------------------------------------------------------------------
class TaskResponse(TaskBase):
    id: int
    status: TaskStatus
    ai_plan: Optional[str] = None
    ai_summary: Optional[str] = None
    burnout_score: Optional[float] = None
    urgency_score: Optional[float] = None
    parent_id: Optional[int] = None
    subtasks: List["TaskResponse"] = []
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Allow forward reference resolution
TaskResponse.model_rebuild()


# ------------------------------------------------------------------
# List response with metadata
# ------------------------------------------------------------------
class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int
    pending: int
    overdue: int
    completed_today: int
