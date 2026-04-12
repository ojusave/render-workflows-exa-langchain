"""
Research agent task: wraps the LangGraph ReAct agent in a Workflow task.

This is the bridge between Render Workflows and LangGraph. The Workflow
provides durable execution (retries, timeout, isolated compute). LangGraph
provides the agentic loop (Claude decides what to search and when to stop).

Each research_agent task runs in its own compute instance. When the
orchestrator fans out 3-5 of these in parallel, each gets independent
retry and timeout handling. If one subtopic's agent hits a rate limit
and retries, the others are unaffected.

Workflow config rationale:
  - plan: standard (1 CPU, 2 GB) — the agent processes multiple search
    results in memory across several loop iterations.
  - timeout: 120s — the agent might loop 3-8 times, each involving a
    Claude call + Exa search. 120s covers worst-case chains.
  - retry: 2 retries, 3s base wait, 2x backoff — handles Claude rate
    limits and Exa transient failures. The entire agent loop restarts
    on retry, which is acceptable because results are not cached.
"""

from render_sdk import Workflows, Retry

from .agent import run_research_agent

app = Workflows()


@app.task(
    plan="standard",
    timeout_seconds=120,
    retry=Retry(max_retries=2, wait_duration_ms=3000, backoff_scaling=2),
)
def research_subtopic(subtopic: str, criteria: str) -> dict:
    """Run a LangGraph research agent for one subtopic."""
    return run_research_agent(subtopic, criteria)
