# Research Agent

Ask a research question. The workflow classifies it, plans subtopics, runs parallel LangGraph agents with Exa search, then returns a synthesized report with sources. Powered by [Render Workflows](https://render.com/workflows).

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/ojusave/langchain-test)
[![Discord: Render Developers](https://img.shields.io/badge/Discord-Render%20Developers-5865F2?logo=discord&logoColor=white)](https://discord.gg/gvC7ceS9YS)

This repo doubles as a **Render learning path**: you get a working LangGraph + Exa research stack, and you can read the code as a map of where Render fits (FastAPI and SSE on one service, tasks and retries on another). The Python SDK (`render_sdk`) is the glue.

## Table of contents

- [Highlights](#highlights)
- [Overview](#overview)
- [Why build it this way on Render](#why-build-it-this-way-on-render)
- [Prerequisites](#prerequisites)
- [Deploy](#deploy)
- [Configuration](#configuration)
- [Usage](#usage)
- [API](#api)
- [How it works](#how-it-works)
- [Project structure](#project-structure)
- [Community](#community)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Highlights

- **Same SDK, two processes**: the workflow service registers tasks with `Workflows()` and `@app.task(...)` from `render_sdk`; the web service dispatches and polls with `RenderAsync`. One mental model: define work in `tasks/`, trigger it from `pipeline/orchestrator.py`.
- **Workflow-backed research**: planning, search agents, and synthesis run as Render Workflow tasks, not inside the FastAPI process.
- **Streaming client**: the UI shows an activity feed while the pipeline runs; status arrives over SSE from `POST /research`.
- **Optional threaded history**: add Postgres (`DATABASE_URL`) for multi-turn threads and follow-ups.
- **Optional observability**: LangSmith keys enable traces and in-UI feedback when you wire `LANGCHAIN_API_KEY` on both services.
- **Ports and adapters**: threaded history goes through `ThreadRepository`; LangSmith ratings through `FeedbackSubmitter` — both wired in [`composition.py`](composition.py). Postgres and LangSmith stay in [`adapters/`](adapters/).
- **One JSON contract**: non-streaming HTTP responses use `{ data, error, meta }` ([`shared/api_envelope.py`](shared/api_envelope.py)). The UI uses a single module ([`static/api-client.js`](static/api-client.js)). `POST /research` stays SSE (not wrapped).

## Overview

This repo is a Python FastAPI front end plus a Python workflow service that hosts LangGraph + Anthropic + Exa. Simple or off-topic questions get a fast path without spinning up research. The pattern matches the Render guidance: thin web, fat tasks.

## Why build it this way on Render

The research loop is slow and chatty: classification, planning, parallel agents, synthesis. Running all of that inside the same process as your HTTP server ties deploys, memory, and timeouts together. You fix a prompt in `tasks/` and suddenly you are redeploying the API that serves health checks.

**Render Workflows** push that work to a **separate service** with its own CPU and retry policy. FastAPI stays responsible for HTTP, SSE, and optional history: see `pipeline/orchestrator.py`, which only dispatches tasks, polls status, and streams events (no LangGraph logic in the web tier).

**Define tasks** under `tasks/`. Each `@app.task(plan=..., timeout_seconds=..., retry=...)` is a unit you tune independently (see `tasks/classify.py` for an example of explicit rationale in comments).

**Trigger from the web** with `RenderAsync` and `start_task` / polling against `${WORKFLOW_SLUG}/task_name`. That string must match the workflow service name in the Render dashboard and the Python function name registered on the workflow app.

**Change behavior** by editing task code and redeploying the workflow service. The web service keeps calling the same task names until you change the orchestration or add new tasks. That is the main payoff when you are learning Render: you can experiment with agents and tools without treating every change as a full-stack redeploy.

**Sibling examples**: same architectural story in Node with LlamaCloud ([render-workflows-llamaindex](https://github.com/ojusave/render-workflows-llamaindex)) and voice + workflows ([ravendr](https://github.com/ojusave/ravendr)). Compare orchestrators if you want one pattern in two languages.

## Prerequisites

- A [Render account](https://dashboard.render.com/register?utm_source=github&utm_medium=referral&utm_campaign=ojus_demos&utm_content=readme_link)
- API keys: [Render](https://render.com/docs/api#1-create-an-api-key), [Anthropic](https://console.anthropic.com/), [Exa](https://exa.ai/)
- Optional: [LangSmith](https://smith.langchain.com/) for tracing and feedback

## Deploy

Installation is Render: clone is only needed if you fork the repo. Use the button below or import [`render.yaml`](render.yaml).

### 1. Web service (via Blueprint)

Click **Deploy to Render** above. Set `RENDER_API_KEY` during setup.

### 2. Workflow service (manual)

1. [Render Dashboard](https://dashboard.render.com) > **New** > **Workflow**
2. Connect the same repo
3. Build: `pip install -r requirements.txt`
4. Start: `python -m tasks`
5. Name: `research-agent-workflow` (must match `WORKFLOW_SLUG`)
6. Env vars: `ANTHROPIC_API_KEY`, `EXA_API_KEY`, `PYTHON_VERSION`: `3.12.3`

### 3. History (optional)

Create a Render PostgreSQL database and set its Internal URL as `DATABASE_URL` on the web service. Tables are auto-created on startup. Enables threaded research history with follow-up queries.

### 4. LangSmith (optional)

Set `LANGCHAIN_API_KEY` on both services. Enables auto-tracing of Claude and LangGraph calls, plus user feedback (thumbs up/down in the UI).

### Monorepo (optional)

If this folder lives inside a monorepo (e.g. **Samples**), use the repository root [`render.yaml`](../render.yaml) to deploy **all** demo services with preview environments. This folder’s [`render.yaml`](render.yaml) is for **standalone** clones of **this** repo only.

## Configuration

| Variable | Where | Default | Description |
|---|---|---|---|
| `RENDER_API_KEY` | Web service | (required) | Triggers workflow tasks |
| `WORKFLOW_SLUG` | Web service | `research-agent-workflow` | Must match workflow service name |
| `DATABASE_URL` | Web service | (optional) | PostgreSQL for research history |
| `LANGCHAIN_API_KEY` | Both | (optional) | LangSmith tracing + feedback |
| `ANTHROPIC_API_KEY` | Workflow | (required) | Claude API key |
| `EXA_API_KEY` | Workflow | (required) | Exa semantic search |
| `ANTHROPIC_MODEL` | Workflow | `claude-sonnet-4-20250514` | Claude model |
| `AGENT_TEMPERATURE` | Workflow | `0.3` | LLM temperature |

## Usage

After deploy, open the web service URL. Type a question in the UI: research queries trigger the workflow; casual prompts get a direct answer. If `DATABASE_URL` is set, conversations persist as threads you can reopen.

Example API call (replace the host and use a real question):

```bash
curl -N -X POST "https://YOUR_SERVICE.onrender.com/research" \
  -H "Content-Type: application/json" \
  -d '{"question":"What are the main tradeoffs between X and Y?","thread_id":""}'
```

The response is an SSE stream (`status`, `classified`, `plan`, agent events, `done`).

## API

**JSON responses** (everything except `POST /research`) use:

```json
{ "data": <T | null>, "error": { "code": "...", "message": "..." } | null, "meta": {} }
```

**`POST /research`**: SSE stream (not an envelope). Body: `{ "question": "...", "thread_id": "..." }`. Events: `status`, `classified`, `plan`, `agent_start`, `agent_done`, `done`, `error`.

**`POST /feedback`**: `data` holds `{ "status": "ok" | "skipped" | "error", ... }`. Body: `{ "run_id": "...", "score": 1 }`.

**`GET /history`**: `data` is an array of thread summaries. **`GET /history/:id`**: `data` is thread detail. **`DELETE /history/:id`**: `data` is `{ "status": "ok" }` on success.

**`GET /health`**: `data` is `{ "status": "ok" }`.

**Static files** are served under `/static/*` (including [`static/app.js`](static/app.js) and [`static/api-client.js`](static/api-client.js)).

## How it works

![Architecture](static/images/architecture.png)

![Pipeline flow](static/images/pipeline.png)

Non-research queries (greetings, coding help, simple questions) get a direct reply without triggering search. The UI streams live progress as an activity feed.

## Project structure

```
main.py                  FastAPI web service
composition.py         Wires ports to adapters
shared/api_envelope.py JSON response envelope helpers
ports/                 ThreadRepository, FeedbackSubmitter protocols
adapters/              Postgres history + LangSmith feedback
pipeline/
  orchestrator.py        Dispatch tasks, poll, stream SSE
  history.py             PostgreSQL threaded history (optional)
  tracking.py            LangSmith pipeline run lifecycle (optional)
tasks/
  __init__.py            Combines task apps for the workflow service
  __main__.py            Workflow entry point (python -m tasks)
  llm.py                 Shared ChatAnthropic model
  tools.py               Exa tools for LangGraph
  agent.py               LangGraph ReAct agent
  research_agent.py      Workflow task wrapping the agent
  classify.py            classify_query task
  plan.py                plan_research task
  synthesize.py          synthesize task
static/index.html        UI shell
static/app.js            UI logic (ES module)
static/api-client.js     Single client for JSON APIs + SSE helpers
render.yaml              Render Blueprint
```

## Community

Questions about Render, workflows, or troubleshooting a deploy: join the [Render Developers Discord](https://discord.gg/gvC7ceS9YS).

## Troubleshooting

**Workflow tasks not starting**: check that `WORKFLOW_SLUG` matches the workflow service name (default: `research-agent-workflow`).

**LangSmith traces not appearing**: set `LANGCHAIN_API_KEY` on the workflow service too (not just the web service). The workflow is where Claude and LangGraph calls happen.

**Exa returning empty**: check `EXA_API_KEY`. Exa occasionally returns 503s under load: Render Workflows auto-retries with backoff.

## Contributing

Open an issue or a focused PR; match the existing `main.py` / `pipeline/` / `tasks/` layout. Do not commit secrets. Full end-to-end runs need Render plus Anthropic and Exa keys—note in the PR what you verified if you cannot run a live deploy.

## License

[MIT](LICENSE). Copyright (c) 2026 Ojusave.
