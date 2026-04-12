# Research Agent

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/ojusave/langchain-test)

A deep research agent where three tools each do what they're best at:

- **[LangGraph](https://www.langchain.com/langgraph)** runs a ReAct agent loop: Claude dynamically decides what to search, evaluates results, and searches again or stops. The search strategy is non-deterministic and impossible to hardcode.
- **[Render Workflows](https://render.com/workflows)** provides durable orchestration: parallel research agents on isolated compute with automatic retries, per-task timeouts, and full observability in the Dashboard.
- **[Exa](https://exa.ai/)** provides AI-native semantic search as LangGraph tools: the agent queries with natural language and gets meaning-matched results, not SEO-optimized links.

Ask a question. The agent breaks it into subtopics, dispatches a LangGraph research agent per subtopic in parallel, and synthesizes a structured report with sources.

---

## Why Three Layers

Each tool solves a problem the others can't.

### Why LangGraph (not a hardcoded pipeline)

A research question like "What are the latest advances in quantum computing?" can't be answered with a fixed number of searches. The agent might:

1. Search "quantum computing breakthroughs 2025" and get good results
2. Search "quantum error correction progress" and find sparse results
3. Refine to "topological qubits recent papers" and find a great source
4. Use `find_similar` on that source to discover related work
5. Decide it has enough evidence and return findings

That's 4 searches. A different question might need 2 or 7. **LangGraph's ReAct loop lets Claude decide the search strategy at runtime.** A hardcoded `for query in queries: search(query)` pipeline can't do this.

### Why Render Workflows (not one long function)

When you run 3-5 LangGraph agents in parallel, each making multiple Claude + Exa calls:

- **A single Exa 503 shouldn't kill the whole pipeline.** Each agent task has its own retry config (3s base, 2x backoff). Other agents are unaffected.
- **A slow agent shouldn't block your web server.** Each agent runs on its own compute instance. The web server starts one task and returns immediately.
- **You need to see what happened.** The Render Dashboard shows the full task tree: which subtopic's agent failed, what it searched, how many retries it took.
- **A server restart shouldn't lose progress.** The orchestrator is durable: already-completed subtasks don't re-run.

### Why Exa (not generic search)

The LangGraph agent queries with natural language: "fascinating recent breakthroughs in quantum error correction". Exa's neural search returns meaning-matched results. Google would return SEO-optimized listicles. `ExaFindSimilarResults` enables discovery chains: "find pages similar to this great paper I found."

---

## How It Works

```mermaid
flowchart TD
    Q["User question"] --> R["research (orchestrator task)"]
    R --> P["plan_research"]
    P -->|"subtopics + criteria"| Fan["Parallel fan-out"]

    Fan --> R1["research_subtopic"]
    Fan --> R2["research_subtopic"]
    Fan --> R3["research_subtopic"]

    R1 --> Synth["synthesize"]
    R2 --> Synth
    R3 --> Synth
    Synth --> RPT["Structured report"]

    subgraph parallel_agents ["Parallel agents (asyncio.gather)"]
        R1
        R2
        R3
    end

    subgraph langgraph_loop ["Inside each research_subtopic (LangGraph ReAct)"]
        LLM["Claude decides next action"]
        LLM -->|"tool_call"| ExaSearch["exa_search"]
        LLM -->|"tool_call"| ExaSimilar["exa_find_similar"]
        ExaSearch -->|"observation"| LLM
        ExaSimilar -->|"observation"| LLM
        LLM -->|"no more tool calls"| Done["Return findings"]
    end
```

The orchestrator (a Render Workflow task) chains three phases:

```python
@app.task
async def research(question: str) -> dict:
    plan = await plan_research(question)              # Claude breaks question into subtopics
    findings = await asyncio.gather(                   # Parallel LangGraph agents
        *[research_subtopic(st["topic"], st["criteria"]) for st in plan["subtopics"]]
    )
    return await synthesize(question, list(findings))  # Claude merges into report
```

Each `await` dispatches a separate Workflow task on its own compute instance.

---

## What Each Tool Does

| Step | Tool | What happens | Config |
|---|---|---|---|
| **Plan** | Anthropic SDK | Single Claude call: break question into subtopics with success criteria | starter, 45s, 2 retries |
| **Research** (per subtopic) | LangGraph + Exa | ReAct agent loop: Claude calls `exa_search` / `exa_find_similar` until it has enough evidence. Non-deterministic: 2-8 searches per subtopic. | standard, 120s, 2 retries |
| **Synthesize** | Anthropic SDK | Single Claude call: merge all findings into a structured report | standard, 90s, 1 retry |
| **Orchestrate** | Render Workflows | Chain the above, fan out research agents in parallel | starter, 600s, 1 retry |

**Why two Claude interfaces?** Plan and synthesize are single-turn calls: send a prompt, get a response. The raw `anthropic` SDK is simpler and has fewer dependencies for this. Research agents need tool-calling loops with message state management: LangGraph's `create_react_agent` handles this cleanly.

---

## Architecture

```mermaid
sequenceDiagram
    participant Browser
    participant Web as Web Service (FastAPI)
    participant WF as Workflow Service

    Browser->>Web: POST /research
    Web->>WF: start_task("research")
    Web-->>Browser: SSE: "Researching..."

    Note over WF: research orchestrator task
    WF->>WF: plan_research (Anthropic SDK)

    par Parallel LangGraph agents
        Note over WF: research_subtopic 1
        WF->>WF: Claude -> exa_search -> Claude -> exa_search -> findings
        Note over WF: research_subtopic 2
        WF->>WF: Claude -> exa_search -> exa_find_similar -> findings
        Note over WF: research_subtopic 3
        WF->>WF: Claude -> exa_search -> findings
    end

    WF->>WF: synthesize (Anthropic SDK)
    WF-->>Web: report
    Web-->>Browser: SSE: done + report
```

Two Render services:

- **Web service** (`research-agent`): thin FastAPI layer. Serves the UI, starts the orchestrator task, streams the result via SSE. Does no research work.
- **Workflow service** (`research-agent-workflow`): four tasks. The `research` orchestrator chains `plan_research`, parallel `research_subtopic` agents, and `synthesize`. Each task run gets its own compute instance.

---

## Dashboard Task Tree

When a research job runs, the Render Dashboard shows:

```
research (orchestrator)                    starter  600s
├── plan_research                          starter   45s   ✓ 2.1s
├── research_subtopic "quantum hardware"   standard 120s   ✓ 34s (5 searches)
├── research_subtopic "error correction"   standard 120s   ✗→✓ retry 1: 28s
├── research_subtopic "quantum software"   standard 120s   ✓ 22s (3 searches)
└── synthesize                             standard  90s   ✓ 12s
```

Every task run shows inputs, outputs, duration, retry history, and error messages. You can see exactly which subtopic's agent failed, what it searched, and why.

---

## Deploy

Click the **Deploy to Render** button above. You'll be prompted to set:

- `RENDER_API_KEY`: your [Render API key](https://render.com/docs/api#1-create-an-api-key) (for the web service to trigger workflows)
- `ANTHROPIC_API_KEY`: your [Anthropic API key](https://console.anthropic.com/) (for the workflow service)
- `EXA_API_KEY`: your [Exa API key](https://exa.ai/) (for the workflow service)

Then click **Apply**. The Blueprint creates both services automatically.

Don't have a Render account? [Sign up here](https://render.com/register).

## Environment Variables

### Web service

| Variable | Required | Default | Description |
|---|---|---|---|
| `RENDER_API_KEY` | Yes | — | Render API key for triggering workflows |
| `WORKFLOW_SLUG` | No | `research-agent-workflow` | Workflow service slug |

### Workflow service

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `EXA_API_KEY` | Yes | — | Exa API key for web search |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-20250514` | Claude model |
| `AGENT_TEMPERATURE` | No | `0.3` | LLM temperature |

## Project Structure

```
├── main.py                      # FastAPI web service (thin HTTP layer)
├── pipeline/
│   ├── __init__.py              # Exports run_pipeline
│   └── orchestrator.py          # Starts workflow task, streams SSE
├── tasks/
│   ├── __init__.py              # Combines task apps into one entry point
│   ├── __main__.py              # Workflow service entry point (python -m tasks)
│   ├── llm.py                   # Raw Anthropic SDK helpers (plan, synthesize)
│   ├── tools.py                 # Exa tools for LangGraph (search, find_similar)
│   ├── agent.py                 # LangGraph ReAct agent (Claude + Exa tools)
│   ├── research_agent.py        # Workflow task wrapping the LangGraph agent
│   ├── plan.py                  # plan_research: subtopics via Anthropic SDK
│   ├── synthesize.py            # synthesize: merge findings via Anthropic SDK
│   └── research.py              # Orchestrator: chains plan -> agents -> synthesize
├── static/
│   └── index.html               # Research UI
├── render.yaml                  # Render Blueprint (web + workflow services)
├── requirements.txt             # Python dependencies
└── .env.example                 # Environment variable reference
```

## API

### `POST /research`

Server-Sent Events endpoint. Starts the research workflow and streams status + the final report.

Request:

```json
{
  "question": "What are the latest advances in quantum computing?"
}
```

SSE events:

```
event: status
data: {"message": "Starting research..."}

event: status
data: {"message": "Researching...", "task_run_id": "tr-abc123"}

event: done
data: {"report": {"title": "...", "summary": "...", "sections": [...], "sources": [...]}}
```

### `GET /health`

Returns `{ "status": "ok" }`.
