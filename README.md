# Research Agent

 A deep research tool that breaks any question into subtopics, runs parallel AI search agents, and synthesizes a structured report with sources. Powered by [Render Workflows](https://render.com/workflows).

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/ojusave/langchain-test)
&nbsp;&nbsp;

---

## Table of Contents

- [How It Works](#how-it-works)
- [Why These Tools](#why-these-tools)
- [Prerequisites](#prerequisites)
- [Quick Start (Deploy)](#quick-start-deploy)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [API](#api)
- [History (Optional)](#history-optional)
- [LangSmith (Optional)](#langsmith-optional)
- [Troubleshooting](#troubleshooting)

---

## How It Works

Ask a question. The agent:

1. **Plans**: Claude breaks it into focused subtopics with success criteria (as many as the question needs).
2. **Researches**: LangGraph agents run in parallel (one per subtopic), each using Exa semantic search. Claude decides the search strategy at runtime: how many searches, when to refine, when to stop.
3. **Synthesizes**: Claude merges all findings into a structured report with sections and sources.

The UI streams live progress as an activity feed, showing which tool is doing what at each step.

```
User question
  → plan_research (Claude)
  → N× research_subtopic (LangGraph + Exa, in parallel)
  → synthesize (Claude)
  → Structured report
```

### What Each Layer Does

| Layer | Tool | Role |
|---|---|---|
| **Agent loop** | [LangGraph](https://www.langchain.com/langgraph) | ReAct agent: Claude calls Exa tools, evaluates results, decides next step |
| **Orchestration** | [Render Workflows](https://render.com/workflows) | Durable parallel execution, per-task retries, timeouts, observability |
| **Search** | [Exa](https://exa.ai/) | AI-native semantic search: meaning-matched results, not SEO links |
| **LLM** | [ChatAnthropic](https://python.langchain.com/docs/integrations/chat/anthropic/) | All Claude calls go through one shared model instance |
| **Tracing** | [LangSmith](https://smith.langchain.com/) | Optional: auto-traces every LLM call, collects user feedback |

---

## Why These Tools

**LangGraph**: a research question can't be answered with a fixed number of searches. The agent might search once and get great results, or search 5 times, refine queries, and use `find_similar` to discover related work. The ReAct loop lets Claude decide the search strategy at runtime.

**Render Workflows**: parallel agents each making multiple LLM + search calls need isolated compute, per-task retries, and observability. A single Exa 503 shouldn't kill the pipeline. A slow agent shouldn't block the web server. The Dashboard shows the full task tree: which subtopic failed, what it searched, how many retries it took.

**Exa**: the agent queries with natural language like "recent breakthroughs in quantum error correction". Exa returns meaning-matched results. `find_similar` enables discovery chains from good sources.

---

## Prerequisites

- A [Render account](https://render.com/register?utm_source=github&utm_medium=referral&utm_campaign=ojus_demos&utm_content=readme_link)
- API keys for: [Render](https://render.com/docs/api#1-create-an-api-key), [Anthropic](https://console.anthropic.com/), [Exa](https://exa.ai/)
- Optional: [LangSmith](https://smith.langchain.com/) API key for tracing

---

## Quick Start (Deploy)

This app runs as two Render services: a **web service** and a **workflow service**.

### 1. Deploy the web service

Click **Deploy to Render** above. Set:

- `RENDER_API_KEY`: your Render API key (triggers workflow tasks)

Click **Apply**. The Blueprint creates the web service.

### 2. Create the workflow service

Render Workflows aren't yet supported in Blueprints, so create it manually:

1. In the [Dashboard](https://dashboard.render.com): **New** > **Workflow**
2. Connect the same GitHub repo
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `python -m tasks`
5. **Name**: `research-agent-workflow` (matches the default `WORKFLOW_SLUG`)
6. Set environment variables:

| Variable | Required | Value |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic key |
| `EXA_API_KEY` | Yes | Your Exa key |
| `PYTHON_VERSION` | Yes | `3.12.3` |
| `ANTHROPIC_MODEL` | No | Default: `claude-sonnet-4-20250514` |
| `AGENT_TEMPERATURE` | No | Default: `0.3` |
| `LANGCHAIN_API_KEY` | No | LangSmith key (enables tracing) |

7. Click **Create Workflow**

The web service discovers the workflow by its slug automatically.

---

## Configuration

### Web service

| Variable | Required | Default | Description |
|---|---|---|---|
| `RENDER_API_KEY` | Yes | — | Triggers workflow tasks |
| `WORKFLOW_SLUG` | No | `research-agent-workflow` | Workflow service slug |
| `DATABASE_URL` | No | — | Enables research history sidebar (Render PostgreSQL) |
| `LANGCHAIN_API_KEY` | No | — | Enables LangSmith tracing + feedback |
| `LANGCHAIN_TRACING_V2` | No | `true` | LangSmith tracing flag |
| `LANGCHAIN_PROJECT` | No | `research-agent` | LangSmith project name |

### Workflow service

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — | Claude API key |
| `EXA_API_KEY` | Yes | — | Exa semantic search |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-20250514` | Claude model |
| `AGENT_TEMPERATURE` | No | `0.3` | LLM temperature |
| `LANGCHAIN_API_KEY` | No | — | Enables LangSmith auto-tracing |
| `LANGCHAIN_TRACING_V2` | No | `true` | LangSmith tracing flag |
| `LANGCHAIN_PROJECT` | No | `research-agent` | LangSmith project name |

---

## Project Structure

```
├── main.py                  # FastAPI web service (HTTP + CORS + static files)
├── pipeline/
│   ├── __init__.py          # Exports run_pipeline
│   ├── orchestrator.py      # Dispatches workflow tasks, polls, streams SSE
│   ├── history.py           # PostgreSQL research history (optional)
│   ├── tracking.py          # LangSmith pipeline run lifecycle (optional)
│   └── feedback.py          # POST /feedback: LangSmith user ratings (optional)
├── tasks/
│   ├── __init__.py          # Combines task apps for the workflow service
│   ├── __main__.py          # Workflow entry point (python -m tasks)
│   ├── llm.py               # Shared ChatAnthropic model + helpers
│   ├── tools.py             # Exa tools for LangGraph
│   ├── agent.py             # LangGraph ReAct agent
│   ├── research_agent.py    # Workflow task wrapping the agent
│   ├── plan.py              # plan_research task
│   └── synthesize.py        # synthesize task
├── static/
│   └── index.html           # UI (activity feed + report, light/dark mode)
├── render.yaml              # Render Blueprint (web service)
├── requirements.txt
└── .env.example
```

---

## API

### `POST /research`

Starts the research workflow. Returns a Server-Sent Events stream.

**Request:**
```json
{ "question": "What are the latest advances in quantum computing?" }
```

**SSE events:**
```
event: status
data: {"phase": "planning", "tools": ["Render Workflows", "LangChain", "Claude"]}

event: plan
data: {"subtopics": ["quantum hardware", "error correction", "quantum software"], "tools": [...]}

event: agent_start
data: {"index": 0, "subtopic": "quantum hardware", "tools": ["Render Workflows", "LangGraph", "Exa", "Claude"]}

event: agent_done
data: {"index": 0, "subtopic": "quantum hardware", "tools": [...]}

event: status
data: {"phase": "synthesizing", "tools": ["Render Workflows", "LangChain", "Claude"]}

event: done
data: {"report": {...}, "run_id": "...", "elapsed": 68, "tools": [...]}
```

### `POST /feedback`

Submits a thumbs up/down rating to LangSmith. No-ops if LangSmith is not configured.

```json
{ "run_id": "uuid-from-done-event", "score": 1, "comment": "Great report" }
```

### `GET /history`

Returns recent research history entries (newest first). Returns `[]` if no database is configured.

### `GET /history/:id`

Returns a single history entry with the full report.

### `DELETE /history/:id`

Deletes a history entry.

### `GET /health`

Returns `{ "status": "ok" }`.

---

## History (Optional)

Set `DATABASE_URL` on the web service to enable a sidebar with research history, similar to ChatGPT/Claude.

1. Create a **PostgreSQL** database on the [Render Dashboard](https://dashboard.render.com)
2. Copy the **Internal URL** and set it as `DATABASE_URL` on the web service
3. The table is auto-created on first startup

To disable: unset `DATABASE_URL`. The sidebar shows "No history yet" and all history functions no-op.

To remove entirely: delete `pipeline/history.py` and the related imports in `main.py` and `pipeline/orchestrator.py`.

---

## LangSmith (Optional)

Set `LANGCHAIN_API_KEY` on both services to enable:

- **Auto-tracing**: every ChatAnthropic and LangGraph call appears in LangSmith with token counts, latency, and tool call details
- **Pipeline tracking**: each request creates a root run linking question → report
- **User feedback**: thumbs up/down in the UI submits ratings linked to the pipeline run

To disable: unset `LANGCHAIN_API_KEY`. Everything gracefully no-ops.

To remove entirely: delete `pipeline/feedback.py`, `pipeline/tracking.py`, and the related import lines in `main.py` and `pipeline/orchestrator.py`.

---

## Troubleshooting

**`ValueError: Either provide a token or set the RENDER_API_KEY environment variable`**
The web service can't find its Render API key. Set `RENDER_API_KEY` in the service's environment variables in the Dashboard. This key is marked `sensitive` in the Blueprint and must be set manually.

**Workflow tasks not starting**
Check that the workflow service is named `research-agent-workflow` (or that `WORKFLOW_SLUG` matches). The web service discovers the workflow by slug.

**LangSmith traces not appearing**
Ensure `LANGCHAIN_API_KEY` is set on the workflow service too (not just the web service). The workflow service is where Claude and LangGraph calls happen.

**Exa search returning empty results**
Check your `EXA_API_KEY` is valid. Exa occasionally returns 503s under load: Render Workflows will auto-retry with backoff.
