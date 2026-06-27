# app/models package – import all models here so Base.metadata is populated
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import UserProfile

__all__ = ["Task", "TaskStatus", "TaskPriority", "UserProfile"]
