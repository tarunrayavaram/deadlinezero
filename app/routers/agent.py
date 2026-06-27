"""
app/routers/agent.py
---------------------
AI agent API endpoints.

Endpoints:
- POST /agent/chat           – Conversational agentic interface (ReAct loop)
- POST /agent/plan/{task_id} – Decompose a task into subtasks
- POST /agent/prioritise     – Re-prioritise pending tasks
- POST /agent/coach          – Get productivity coaching insights
- POST /agent/schedule       – Generate an optimised daily schedule
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    CoachRequest,
    CoachResponse,
    PlanRequest,
    PlanResponse,
    PrioritiseRequest,
    PrioritiseResponse,
    ScheduleRequest,
    ScheduleResponse,
)
from app.services.agent_service import AgentService
from app.services.gemini_service import generate_json
from app.services.task_service import TaskService
from app.utils.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/agent", tags=["AI Agent"])


def _get_agent_service(db: AsyncSession = Depends(get_db)) -> AgentService:
    return AgentService(db)


def _get_task_service(db: AsyncSession = Depends(get_db)) -> TaskService:
    return TaskService(db)


@router.post("/chat", response_model=AgentChatResponse, summary="Chat with the AI agent")
async def agent_chat(
    payload: AgentChatRequest,
    service: AgentService = Depends(_get_agent_service),
) -> AgentChatResponse:
    """
    Multi-turn conversational agent using Gemini function calling (ReAct loop).

    The agent autonomously:
    1. Reads your task database
    2. Reasons about the best course of action
    3. Creates/updates tasks if needed
    4. Returns a contextual, data-driven response

    Pass the returned session_id in subsequent requests to maintain conversation context.
    """
    result = await service.chat(
        message=payload.message,
        session_id=payload.session_id,
    )
    return AgentChatResponse(**result)


@router.post("/plan/{task_id}", response_model=PlanResponse, summary="AI task planning")
async def plan_task(
    task_id: int,
    payload: PlanRequest,
    task_service: TaskService = Depends(_get_task_service),
) -> PlanResponse:
    """
    Use Gemini to decompose a task into actionable subtasks and assess its risk level.
    """
    task = await task_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    # Decompose task using AI
    subtasks = await task_service.ai_decompose_task(task_id, num_subtasks=4)

    # Ask Gemini for risk assessment
    risk_prompt = f"""
Assess the risk level for completing this task on time.

Task: {task.title}
Deadline: {task.deadline.isoformat() if task.deadline else 'None'}
Estimated work: {task.estimated_minutes or 60} minutes
Subtasks: {len(subtasks)}
Additional context: {payload.context or 'None'}

Return JSON:
{{
  "risk_level": "low|medium|high|critical",
  "risk_reasons": ["reason1", "reason2"],
  "recommended_start": "YYYY-MM-DDTHH:MM:SS",
  "plan_summary": "2-3 sentence action plan"
}}
"""
    risk_data = generate_json(risk_prompt)

    return PlanResponse(
        task_id=task_id,
        plan_summary=risk_data.get("plan_summary", "Break the task into the subtasks above and work through them systematically."),
        subtasks=[
            {
                "title": s.title,
                "description": s.description,
                "estimated_minutes": s.estimated_minutes or 30,
                "priority": s.priority or 3,
            }
            for s in subtasks
        ],
        estimated_total_minutes=sum(s.estimated_minutes or 30 for s in subtasks),
        recommended_start=risk_data.get("recommended_start"),
        risk_level=risk_data.get("risk_level", "medium"),
        risk_reasons=risk_data.get("risk_reasons", []),
    )


@router.post("/prioritise", response_model=PrioritiseResponse, summary="AI task prioritisation")
async def prioritise_tasks(
    payload: PrioritiseRequest,
    task_service: TaskService = Depends(_get_task_service),
) -> PrioritiseResponse:
    """
    Gemini analyses all pending tasks and recommends optimal priority ordering
    using urgency, deadline proximity, and estimated effort.
    """
    if payload.task_ids:
        tasks = [await task_service.get_task(tid) for tid in payload.task_ids]
        tasks = [t for t in tasks if t is not None]
    else:
        tasks = await task_service.get_tasks(status_filter="pending", limit=50)

    if not tasks:
        return PrioritiseResponse(prioritised_tasks=[], ai_commentary="No pending tasks found.")

    task_list_str = "\n".join(
        f"- id={t.id} title={t.title!r} current_priority={t.priority} "
        f"deadline={t.deadline.isoformat() if t.deadline else 'none'} "
        f"est_minutes={t.estimated_minutes or 60}"
        for t in tasks
    )

    prompt = f"""
You are a productivity expert. Reprioritise these tasks using the Eisenhower Matrix
(Urgent+Important first, then Important, then Urgent, then neither).

Tasks:
{task_list_str}

Return JSON:
{{
  "prioritised_tasks": [
    {{
      "task_id": 1,
      "title": "...",
      "recommended_priority": 1,
      "urgency_score": 0.9,
      "reasoning": "Due in 2 hours and blocks other work"
    }}
  ],
  "ai_commentary": "Overall workload assessment in 2 sentences"
}}
"""
    result = generate_json(prompt)
    return PrioritiseResponse(**result)


@router.post("/coach", response_model=CoachResponse, summary="AI productivity coaching")
async def get_coaching(
    payload: CoachRequest,
    task_service: TaskService = Depends(_get_task_service),
) -> CoachResponse:
    """
    Personalised productivity coaching based on current workload.
    Detects burnout risk, suggests focus windows, and provides actionable recommendations.
    """
    insights = await task_service.get_productivity_insights()
    stats = insights["workload_stats"]

    prompt = f"""
You are a world-class productivity coach. Analyse this workload data and provide coaching.

Workload Stats:
- Pending tasks: {stats['pending_tasks']}
- Overdue: {stats['overdue_tasks']}
- Due today: {stats['due_today']}
- Burnout score: {stats['burnout_score']} ({stats['burnout_level']})
- Total pending hours: {stats['total_pending_hours']}h
- Completed today: {stats['completed_today']}
- Completion rate: {insights['completion_rate']}%

User context: {payload.context or 'None provided'}

Return JSON:
{{
  "insight": "Honest, empathetic 3-4 sentence assessment",
  "recommendations": ["Action 1", "Action 2", "Action 3"],
  "burnout_warning": true/false,
  "burnout_message": "If burnout_warning is true, an encouraging message",
  "focus_windows": [
    {{"time": "09:00-10:30", "type": "deep_work", "reason": "..."}}
  ],
  "streak": 0
}}
"""
    result = generate_json(prompt)
    return CoachResponse(**result)


@router.post("/schedule", response_model=ScheduleResponse, summary="Generate daily schedule")
async def generate_schedule(
    payload: ScheduleRequest,
    task_service: TaskService = Depends(_get_task_service),
) -> ScheduleResponse:
    """
    AI-generated time-blocked schedule that assigns tasks to optimal time slots
    based on priority, deadlines, and estimated duration.
    """
    from datetime import date
    target = payload.date or date.today().isoformat()
    result = await task_service.generate_schedule(target)
    return ScheduleResponse(**result)
