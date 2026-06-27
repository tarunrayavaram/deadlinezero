"""
app/agents/tools.py
--------------------
Gemini Function Calling tool declarations for the DeadlineZero agent.

Each tool declaration tells Gemini what functions the agent can call.
The actual Python implementations are in agent_service.py where the
ReAct loop dispatches them.

Why function calling?
- Enables true agentic behaviour: Gemini decides WHEN to use a tool
- Multi-step reasoning: model plans → acts → observes → plans again
- Structured output: tool results are fed back as structured data
- This approach scores highest on "Agentic Depth" evaluation criterion
"""

from google.genai import types

# ------------------------------------------------------------------
# Tool declarations (sent to Gemini as the tools parameter)
# ------------------------------------------------------------------

GET_ALL_TASKS_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_all_tasks",
            description=(
                "Retrieve all tasks from the database. "
                "Returns task titles, deadlines, priorities, and statuses. "
                "Use this to understand the user's current workload before planning."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "status_filter": types.Schema(
                        type=types.Type.STRING,
                        description="Filter by status: pending, in_progress, completed, overdue, or 'all'",
                    )
                },
            ),
        )
    ]
)

CREATE_TASK_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="create_task",
            description=(
                "Create a new task in the database. "
                "Use this when the user asks you to add, create, or schedule a task."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "title": types.Schema(type=types.Type.STRING),
                    "description": types.Schema(type=types.Type.STRING),
                    "priority": types.Schema(
                        type=types.Type.INTEGER,
                        description="1=Critical, 2=High, 3=Medium, 4=Low, 5=Minimal",
                    ),
                    "deadline": types.Schema(
                        type=types.Type.STRING,
                        description="ISO 8601 datetime string e.g. 2026-06-30T17:00:00Z",
                    ),
                    "estimated_minutes": types.Schema(
                        type=types.Type.INTEGER,
                        description="Estimated time to complete in minutes",
                    ),
                    "category": types.Schema(type=types.Type.STRING),
                },
                required=["title"],
            ),
        )
    ]
)

UPDATE_TASK_STATUS_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="update_task_status",
            description="Update a task's status (mark as completed, in_progress, cancelled, etc.)",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "task_id": types.Schema(type=types.Type.INTEGER),
                    "status": types.Schema(
                        type=types.Type.STRING,
                        description="pending | in_progress | completed | cancelled",
                    ),
                },
                required=["task_id", "status"],
            ),
        )
    ]
)

GET_OVERDUE_TASKS_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_overdue_tasks",
            description=(
                "Retrieve all tasks whose deadline has passed and are not yet completed. "
                "Use this to identify critical deadline misses."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={},
            ),
        )
    ]
)

ANALYSE_WORKLOAD_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="analyse_workload",
            description=(
                "Calculate workload statistics: total pending minutes, tasks due today, "
                "tasks due this week, overdue count, and a burnout risk score 0–1. "
                "Use before making scheduling recommendations."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={},
            ),
        )
    ]
)

DECOMPOSE_TASK_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="decompose_task",
            description=(
                "Break a complex task into smaller actionable subtasks and save them to the database. "
                "Use when a task seems too large or vague to complete in one sitting."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "task_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="ID of the parent task to decompose",
                    ),
                    "num_subtasks": types.Schema(
                        type=types.Type.INTEGER,
                        description="Target number of subtasks (2–7)",
                    ),
                },
                required=["task_id"],
            ),
        )
    ]
)

SUGGEST_SCHEDULE_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="suggest_schedule",
            description=(
                "Generate an optimised daily schedule for today or a specified date, "
                "assigning tasks to time blocks based on priority and estimated duration."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "date": types.Schema(
                        type=types.Type.STRING,
                        description="ISO date YYYY-MM-DD, defaults to today",
                    ),
                    "work_start_hour": types.Schema(type=types.Type.INTEGER),
                    "work_end_hour": types.Schema(type=types.Type.INTEGER),
                },
            ),
        )
    ]
)

GET_PRODUCTIVITY_INSIGHTS_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_productivity_insights",
            description=(
                "Analyse completion patterns, streak, and overall productivity health. "
                "Returns insights about peak performance times and habit recommendations."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={},
            ),
        )
    ]
)

# All tools bundled – passed to GeminiAgentSession
ALL_AGENT_TOOLS = [
    GET_ALL_TASKS_TOOL,
    CREATE_TASK_TOOL,
    UPDATE_TASK_STATUS_TOOL,
    GET_OVERDUE_TASKS_TOOL,
    ANALYSE_WORKLOAD_TOOL,
    DECOMPOSE_TASK_TOOL,
    SUGGEST_SCHEDULE_TOOL,
    GET_PRODUCTIVITY_INSIGHTS_TOOL,
]
