"""
app/models/user.py
------------------
Simple user profile model.
Stores productivity preferences used by the AI agent for personalisation.
Authentication is intentionally lightweight (session-based profile)
to keep the demo focused on the AI features.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="User")

    # Productivity preferences (used by the AI coach)
    work_start_hour: Mapped[int] = mapped_column(Integer, default=9)   # 9 AM
    work_end_hour: Mapped[int] = mapped_column(Integer, default=18)     # 6 PM
    focus_duration_minutes: Mapped[int] = mapped_column(Integer, default=90)
    break_duration_minutes: Mapped[int] = mapped_column(Integer, default=15)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")

    # AI insights cache
    productivity_profile: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_ai_insight: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    total_tasks_completed: Mapped[int] = mapped_column(Integer, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<UserProfile id={self.id} name={self.name!r}>"
