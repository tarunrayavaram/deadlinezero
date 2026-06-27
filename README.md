# ⚡ DeadlineZero – AI-Powered Productivity Companion

> *"Stop reacting to deadlines. Start eliminating them."*

DeadlineZero is an agentic productivity companion powered by **Google Gemini** with **function calling**. It proactively helps users plan, prioritise, and complete tasks before deadlines are missed — moving far beyond passive reminders.

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Solution Overview](#solution-overview)
3. [Why Google Gemini?](#why-google-gemini)
4. [Architecture](#architecture)
5. [Folder Structure](#folder-structure)
6. [Key Features](#key-features)
7. [Technology Stack & Justification](#technology-stack--justification)
8. [Evaluation Criteria Mapping](#evaluation-criteria-mapping)
9. [Local Setup & Running](#local-setup--running)
10. [API Reference](#api-reference)
11. [Testing](#testing)
12. [Deployment Guide](#deployment-guide)
13. [Google AI Studio Setup](#google-ai-studio-setup)
14. [GitHub Guide](#github-guide)
15. [Security Considerations](#security-considerations)
16. [Scalability Considerations](#scalability-considerations)
17. [Future Enhancements](#future-enhancements)

---

## Problem Statement

**The Last-Minute Life Saver** — Students, professionals, and entrepreneurs frequently miss deadlines. Existing tools offer passive reminders that are easy to ignore and do nothing to help users actually complete their work.

---

## Solution Overview

DeadlineZero is a full-stack AI productivity application featuring:

- A **FastAPI** REST backend with async SQLite persistence
- **Google Gemini 2.0 Flash** as the AI engine with **native function calling**
- A **ReAct (Reason + Act) agentic loop** — Gemini autonomously decides which tools to call
- A **real-time dashboard** UI with AI chat, scheduling, and coaching
- A **background scheduler** that monitors deadlines and flags overdue tasks

### The Core Innovation: Agentic Function Calling

Rather than just generating text, the agent uses Gemini's function calling to **take actions**:

```
User: "Help me plan my presentation deadline"
    ↓
Gemini reasons → calls get_all_tasks() to read DB
    ↓
Observes workload → calls analyse_workload() 
    ↓
Identifies the task → calls decompose_task(task_id=7)
    ↓
Creates 4 subtasks in DB → returns actionable plan
```

This is genuine agentic behaviour: multi-step, autonomous, data-grounded.

---

## Why Google Gemini?

| Criterion | Gemini 2.0 Flash | Why it wins |
|-----------|-----------------|-------------|
| **Function Calling** | Native, structured | Powers the ReAct agent loop |
| **Speed** | ~300ms median | Critical for real-time productivity UX |
| **Context Window** | 1M tokens | Handles full task history + chat |
| **JSON mode** | Built-in | Reliable structured output for schedule/plan endpoints |
| **Cost** | Very low | Sustainable for hackathon + production |
| **Ecosystem** | Google Cloud native | One-click Cloud Run deploy from AI Studio |

### Model Switching

The model is controlled entirely via the `GEMINI_MODEL` env var — no code changes needed:

```bash
GEMINI_MODEL=gemini-1.5-pro      # Switch to Pro for complex reasoning
GEMINI_MODEL=gemini-2.0-flash    # Default: fast and cheap
GEMINI_MODEL=gemini-1.5-flash    # Alternative flash model
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (index.html)                  │
│  Dashboard │ AI Chat │ Schedule │ Coach │ Tasks          │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP/REST
┌────────────────────────▼────────────────────────────────┐
│                    FastAPI Application                    │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │ /tasks   │  │ /agent   │  │ /health              │  │
│  │ CRUD API │  │ AI API   │  │ Liveness/Readiness   │  │
│  └────┬─────┘  └────┬─────┘  └──────────────────────┘  │
│       │             │                                    │
│  ┌────▼─────────────▼──────────────────────────────┐   │
│  │              Service Layer                        │   │
│  │  TaskService │ AgentService │ SchedulerService   │   │
│  └────┬──────────────┬──────────────────────────────┘   │
│       │              │                                   │
│  ┌────▼────┐   ┌─────▼──────────────────────────────┐  │
│  │ SQLite  │   │      Gemini Agent (ReAct Loop)       │  │
│  │  (DB)   │   │                                      │  │
│  └─────────┘   │  GeminiAgentSession                  │  │
│                │    ├─ send_message()                  │  │
│                │    ├─ dispatch_tool()                 │  │
│                │    │    ├─ get_all_tasks              │  │
│                │    │    ├─ create_task                │  │
│                │    │    ├─ update_task_status         │  │
│                │    │    ├─ analyse_workload           │  │
│                │    │    ├─ decompose_task             │  │
│                │    │    ├─ suggest_schedule          │  │
│                │    │    └─ get_productivity_insights  │  │
│                │    └─ send_tool_result()              │  │
│                └────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
          │ background
┌─────────▼──────────────────────────────┐
│  APScheduler                           │
│  - Deadline monitor (every 30 min)     │
│  - Daily briefing (09:00 UTC)          │
└────────────────────────────────────────┘
```

### Request Flow

1. Browser sends request to FastAPI router
2. Router validates input via Pydantic schema
3. Dependency injection provides an async DB session
4. Router delegates to Service layer (business logic)
5. Service calls Gemini SDK or SQLAlchemy as needed
6. Response serialised via Pydantic schema back to browser

---

## Folder Structure

```
deadlinezero/
├── app/
│   ├── main.py                   # FastAPI app factory & lifespan
│   ├── config.py                 # Settings via pydantic-settings
│   ├── database.py               # Async SQLAlchemy engine & session
│   ├── models/
│   │   ├── task.py               # Task ORM model (with subtask hierarchy)
│   │   └── user.py               # UserProfile ORM model
│   ├── schemas/
│   │   ├── task.py               # Task Pydantic schemas (Create/Update/Response)
│   │   └── agent.py              # Agent request/response schemas
│   ├── routers/
│   │   ├── tasks.py              # CRUD REST endpoints
│   │   ├── agent.py              # AI agent endpoints
│   │   └── health.py             # Health check endpoints
│   ├── services/
│   │   ├── gemini_service.py     # Gemini SDK wrapper + retry logic
│   │   ├── agent_service.py      # ReAct agentic loop orchestration
│   │   ├── task_service.py       # Task business logic + AI features
│   │   └── scheduler_service.py  # APScheduler background jobs
│   ├── agents/
│   │   └── tools.py              # Gemini function declarations
│   └── utils/
│       ├── logging_config.py     # Structured logging setup
│       └── validators.py         # Reusable validation helpers
├── static/
│   └── index.html                # Single-page dashboard UI
├── tests/
│   ├── test_tasks.py             # Task CRUD + validation tests
│   └── test_agent.py             # Urgency algorithm + unit tests
├── .env.example                  # Environment variable template
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Multi-stage production Docker image
├── .gitignore
└── README.md
```

---

## Key Features

### 1. Agentic Chat (ReAct Loop)
The AI agent autonomously calls tools to answer your questions with real data:
- *"What should I work on today?"* → reads DB, analyses workload, returns priority-ordered plan
- *"I have a presentation in 2 days"* → creates task, decomposes into subtasks, assesses risk

### 2. Intelligent Task Decomposition
Gemini breaks any complex task into 2–7 concrete, timed subtasks and saves them to the DB.

### 3. Urgency Scoring
Every task gets a 0–1 urgency score using exponential time-decay × priority weight. Tasks approaching their deadline auto-escalate.

### 4. Burnout Detection
The system computes a real-time burnout score (pending work hours ÷ available hours). The dashboard shows colour-coded workload health and warns before burnout hits.

### 5. AI Schedule Generation
Gemini generates a time-blocked daily schedule, placing high-priority tasks in morning peak hours with 15-minute breaks every 90 minutes.

### 6. Productivity Coach
Personalised coaching based on completion rate, streak, and workload analysis. Includes focus window suggestions and anti-burnout advice.

### 7. Background Deadline Monitor
APScheduler checks for overdue tasks every 30 minutes and auto-marks them. A daily briefing at 09:00 UTC logs a workload summary (extendable to push notifications).

### 8. Auto-Categorisation
On task creation, Gemini automatically assigns a category (Work, Study, Finance, Health, etc.) if none is provided.

---

## Technology Stack & Justification

### FastAPI
**Why chosen:** Async-first, auto-generates OpenAPI docs, Pydantic integration, fastest Python web framework. **Alternatives:** Flask (sync, verbose), Django (heavyweight for an API). FastAPI wins for production-quality async I/O with minimal boilerplate.

### Google Gemini Python SDK (`google-generativeai`)
**Why chosen:** Official SDK, supports function calling natively, JSON mode, long context. **Alternatives:** OpenAI SDK (different vendor, no Google Cloud benefit), LangChain (adds complexity). Direct SDK gives the most control for hackathon evaluation of Google tech usage.

### SQLAlchemy 2.0 + aiosqlite
**Why chosen:** Industry-standard ORM, fully async with `aiosqlite`, type-safe with mapped columns. **Alternatives:** Tortoise ORM, databases library. SQLAlchemy has the widest ecosystem and production support.

### Pydantic v2 + pydantic-settings
**Why chosen:** ~5-10x faster than v1, Rust-based validation, settings management built-in. All API input/output validated with zero boilerplate. **Alternatives:** marshmallow (older), dataclasses (no validation).

### APScheduler
**Why chosen:** Pure Python, no external broker, async-compatible, cron + interval triggers. **Alternatives:** Celery (requires Redis/RabbitMQ — overkill for this scope), Cloud Scheduler (requires GCP project setup).

### Tenacity
**Why chosen:** Battle-tested retry library with exponential backoff. Gemini API calls can transiently fail — retries make the service resilient. **Alternatives:** Manual retry loops (error-prone).

### python-dotenv
**Why chosen:** Industry standard for `.env` file loading. Simple, zero-dependency. All secrets stay out of code. **Alternatives:** Direct `os.environ` (no `.env` support).

---

## Evaluation Criteria Mapping

| Criterion | Weight | How DeadlineZero addresses it |
|-----------|--------|-------------------------------|
| **Problem Solving & Impact** | 20% | Directly solves deadline management with AI that takes action, not just reminds. Real data-driven recommendations based on actual task state. |
| **Agentic Depth** | 20% | Full ReAct loop with 8 Gemini function calling tools. Agent autonomously reads DB, creates tasks, decomposes work, and generates schedules in a single conversation turn. Multi-step, stateful. |
| **Innovation & Creativity** | 20% | Urgency scoring algorithm, burnout detection metric, AI task DNA decomposition, flow-state window detection, procrastination-aware scheduling. |
| **Usage of Google Technologies** | 15% | Google Gemini 2.0 Flash (primary AI), native function calling (agentic tools), JSON mode (structured output), Dockerfile ready for Google Cloud Run + AI Studio deploy. |
| **Product Experience & Design** | 10% | Dark-mode dashboard UI, real-time stats, typing indicators, quick action chips, toast notifications, responsive layout. No framework needed — pure clean HTML/CSS/JS. |
| **Technical Implementation** | 10% | Async FastAPI, SQLAlchemy 2.0 mapped columns, Pydantic v2, multi-stage Dockerfile, structured logging, retry logic, health endpoints, proper separation of concerns. |
| **Completeness & Usability** | 5% | Full CRUD, 5 distinct AI agent capabilities, tests, README, .env.example, Dockerfile, health endpoints. Ready to deploy. |

---

## Local Setup & Running

### Prerequisites
- Python 3.11+
- A Google Gemini API key (free tier available)

### Step 1: Clone and setup

```bash
git clone https://github.com/tarunrayavaram/deadlinezero.git
cd deadlinezero

# Create virtual environment
python -m venv .venv
source .venv/bin/activate          # Linux/Mac
# .venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure environment

```bash
cp .env.example .env
```

Edit `.env` and add your Gemini API key:

```
GEMINI_API_KEY=your_key_here
```

### Step 3: Run the application

```bash
# Development mode (auto-reload)
uvicorn app.main:app --reload --port 8000

# Or directly
python -m app.main
```

Open http://localhost:8000 in your browser.

### Step 4: Verify

```bash
# Health check
curl http://localhost:8000/health

# Readiness check
curl http://localhost:8000/health/ready

# API docs
open http://localhost:8000/docs
```

---

## API Reference

### Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/tasks` | List all tasks (filterable by status) |
| `POST` | `/tasks` | Create a task |
| `GET` | `/tasks/{id}` | Get task by ID |
| `PATCH` | `/tasks/{id}` | Update task (partial) |
| `DELETE` | `/tasks/{id}` | Delete task |
| `GET` | `/tasks/stats/workload` | Workload statistics + burnout score |

### AI Agent

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/agent/chat` | Conversational agent (ReAct loop) |
| `POST` | `/agent/plan/{task_id}` | AI task decomposition + risk assessment |
| `POST` | `/agent/prioritise` | Reprioritise pending tasks |
| `POST` | `/agent/coach` | Productivity coaching insights |
| `POST` | `/agent/schedule` | Generate daily time-blocked schedule |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness probe |
| `GET` | `/health/ready` | Readiness probe (checks DB + API key) |

---

## Deployment Guide

### Option A: Google AI Studio (Recommended — One Click)

1. Go to https://aistudio.google.com
2. Open a new project → select "Deploy to Cloud Run"
3. Connect your GitHub repository
4. Set environment variables:
   - `GEMINI_API_KEY` = your key
   - `APP_ENV` = production
5. Click Deploy → get your public URL in ~2 minutes

Reference: https://ai.google.dev/gemini-api/docs/aistudio-deploying

### Option B: Google Cloud Run (Manual)

```bash
# 1. Build and push Docker image
gcloud builds submit --tag gcr.io/YOUR_PROJECT/deadlinezero

# 2. Deploy to Cloud Run
gcloud run deploy deadlinezero \
  --image gcr.io/YOUR_PROJECT/deadlinezero \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your_key,APP_ENV=production \
  --port 8000
```

### Option C: Local Docker

```bash
# Build
docker build -t deadlinezero .

# Run
docker run -p 8000:8000 \
  -e GEMINI_API_KEY=your_key \
  -e APP_ENV=production \
  deadlinezero
```

### Production Recommendations

- Use **Cloud SQL** (PostgreSQL) instead of SQLite for multi-instance deployments
- Store `GEMINI_API_KEY` in **Google Secret Manager**, not plain env vars
- Enable **Cloud Run min-instances=1** to avoid cold starts
- Set `SCHEDULER_ENABLED=false` in multi-replica deployments; use **Cloud Scheduler** instead
- Enable **Cloud Logging** for structured log aggregation

---

## Google AI Studio Setup

### Step 1: Create Account
1. Go to https://aistudio.google.com
2. Sign in with your Google account
3. Accept terms and conditions

### Step 2: Generate API Key
1. Click **"Get API key"** in the top navigation
2. Click **"Create API key"**
3. Select an existing Google Cloud project or create a new one
4. Copy the key (shown only once!)

### Step 3: Configure Environment
```bash
# In your .env file:
GEMINI_API_KEY=AIzaSy...your_key_here
GEMINI_MODEL=gemini-2.0-flash    # Recommended
```

### Step 4: Model Selection Guide

| Model | Best for | Notes |
|-------|----------|-------|
| `gemini-2.0-flash` | **Default – recommended** | Fast, cheap, function calling |
| `gemini-1.5-pro` | Complex reasoning tasks | Higher cost, better for multi-step |
| `gemini-1.5-flash` | High-volume scenarios | Faster than Pro |

### Step 5: Testing API Key
```bash
python -c "
import google.genai as genai
genai.configure(api_key='YOUR_KEY')
model = genai.GenerativeModel('gemini-2.0-flash')
print(model.generate_content('Hello!').text)
"
```

### Troubleshooting

- **401 Unauthorized** → API key is incorrect or expired. Generate a new one.
- **429 Rate Limit** → Free tier has 15 RPM limit. Add delay or upgrade.
- **Empty response** → Check `agent_temperature` and `agent_max_output_tokens` in `.env`
- **Function calling fails** → Ensure you're using a model that supports it (`gemini-2.0-flash` ✓)

---

## GitHub Guide

### Initialise Repository

```bash
cd deadlinezero
git init
git add .
git commit -m "feat: initial DeadlineZero implementation

- FastAPI backend with async SQLAlchemy
- Google Gemini ReAct agent with 8 function calling tools
- Task CRUD with AI categorisation and urgency scoring
- AI schedule generation and productivity coaching
- APScheduler background deadline monitoring
- Single-page dashboard UI
- Docker + Cloud Run deployment ready"
```

### Create GitHub Repository

```bash
# Via GitHub CLI
gh repo create deadlinezero --public --push

# Or manually on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/deadlinezero.git
git branch -M main
git push -u origin main
```

### Commit Strategy

Follow Conventional Commits:
- `feat:` New features
- `fix:` Bug fixes
- `refactor:` Code restructuring
- `test:` Test additions
- `docs:` Documentation
- `chore:` Build/config changes

### .gitignore Key Rules

The `.gitignore` ensures:
- `.env` (secrets) is **never committed** ✓
- `*.db` (database) is excluded ✓
- `__pycache__` and `.venv` excluded ✓
- `.env.example` **is committed** (template without secrets) ✓

---

## Security Considerations

1. **API Key Management** — Gemini key stored in env var only, never in code. Use Google Secret Manager in production.
2. **Input Validation** — All inputs validated by Pydantic v2 before reaching services.
3. **SQL Injection Prevention** — SQLAlchemy ORM with parameterised queries throughout.
4. **Non-root Docker** — Container runs as `appuser`, not root.
5. **CORS** — Configurable via `ALLOWED_ORIGINS` env var; defaults to `*` in dev only.
6. **Error Masking** — Global exception handler returns generic 500 messages; details go to logs.
7. **No Secret Logging** — API keys never appear in log output.

---

## Scalability Considerations

| Component | Current | Production Scale |
|-----------|---------|-----------------|
| Database | SQLite (single file) | Cloud SQL (PostgreSQL) |
| Sessions | In-memory dict | Redis (GCP Memorystore) |
| Scheduler | In-process APScheduler | Cloud Scheduler + Cloud Tasks |
| Deployment | Single instance | Cloud Run (auto-scale 0→N) |
| File storage | Local | Cloud Storage |

The service layer is stateless (DB session injected per request), making horizontal scaling straightforward. Switch from SQLite to PostgreSQL by changing `DATABASE_URL` only.

---

## Future Enhancements

- **Google Calendar Integration** — Sync tasks with Google Calendar via Calendar API
- **Voice Interface** — Use Gemini's multimodal audio for voice task capture
- **Email Notifications** — SendGrid integration for deadline alerts
- **Procrastination Detector** — Track task age vs. estimated time to identify patterns
- **Team Collaboration** — Multi-user with shared task boards
- **Mobile PWA** — Add service worker for offline support and push notifications
- **Gemini grounding** — Use Google Search grounding for context-aware recommendations
- **Redis session store** — Persist agent conversation history across server restarts

---

## License

MIT License — free to use, modify, and distribute.

---

*Built for the Vibe2Ship Hackathon — CodingNinjas × Google for Developers*
