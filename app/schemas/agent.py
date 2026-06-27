"""
app/schemas/agent.py
--------------------
Pydantic schemas for AI agent request/response contracts.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Chat / conversational agent
# ------------------------------------------------------------------
class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="User message to the agent")
    session_id: Optional[str] = Field(None, description="Conversation session ID for context continuity")


class AgentChatResponse(BaseModel):
    reply: str = Field(..., description="Agent's natural language response")
    actions_taken: List[str] = Field(default_factory=list, description="List of tool calls made by the agent")
    session_id: str
    tokens_used: Optional[int] = None


# ------------------------------------------------------------------
# Task decomposition / planning
# ------------------------------------------------------------------
class PlanRequest(BaseModel):
    task_id: int = Field(..., description="ID of the task to plan")
    context: Optional[str] = Field(None, max_length=1000, description="Additional context for planning")


class SubtaskSuggestion(BaseModel):
    title: str
    description: Optional[str] = None
    estimated_minutes: int
    priority: int = 3


class PlanResponse(BaseModel):
    task_id: int
    plan_summary: str
    subtasks: List[SubtaskSuggestion]
    estimated_total_minutes: int
    recommended_start: Optional[str] = None
    risk_level: str = Field(..., description="low | medium | high | critical")
    risk_reasons: List[str] = Field(default_factory=list)


# ------------------------------------------------------------------
# Prioritisation
# ------------------------------------------------------------------
class PrioritiseRequest(BaseModel):
    task_ids: Optional[List[int]] = Field(None, description="Specific task IDs to prioritise; None = all pending")


class PrioritisedTask(BaseModel):
    task_id: int
    title: str
    recommended_priority: int
    urgency_score: float
    reasoning: str


class PrioritiseResponse(BaseModel):
    prioritised_tasks: List[PrioritisedTask]
    ai_commentary: str


# ------------------------------------------------------------------
# Productivity coaching
# ------------------------------------------------------------------
class CoachRequest(BaseModel):
    context: Optional[str] = Field(None, max_length=2000, description="Additional context or question")


class CoachResponse(BaseModel):
    insight: str
    recommendations: List[str]
    burnout_warning: bool
    burnout_message: Optional[str] = None
    focus_windows: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Suggested deep-work time windows"
    )
    streak: int = 0


# ------------------------------------------------------------------
# Schedule generation
# ------------------------------------------------------------------
class ScheduleRequest(BaseModel):
    date: Optional[str] = Field(None, description="ISO date YYYY-MM-DD; defaults to today")


class ScheduleBlock(BaseModel):
    start_time: str
    end_time: str
    task_id: Optional[int] = None
    task_title: str
    block_type: str  # work | break | buffer


class ScheduleResponse(BaseModel):
    date: str
    schedule: List[ScheduleBlock]
    total_work_minutes: int
    total_break_minutes: int
    ai_notes: str
