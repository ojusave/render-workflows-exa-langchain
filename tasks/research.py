"""
Research orchestrator: chains plan -> parallel research agents -> synthesize.

This is the top-level task the web service triggers. It coordinates three
phases, each running on separate compute:

  1. plan_research: Claude breaks the question into subtopics (single call)
  2. research_subtopic (fan-out): a LangGraph agent per subtopic, in parallel
  3. synthesize: Claude merges all findings into a report (single call)

The orchestrator itself does no research work. It only awaits subtasks.
Every await dispatches a separate Workflow task run on its own instance.

Workflow config rationale:
  - plan: starter (0.5 CPU, 512 MB) — orchestrator only awaits, no compute.
  - timeout: 600s — the full pipeline can take 2-4 minutes when agents loop
    multiple times. 600s covers retries and cold starts across all subtasks.
  - retry: 1 retry, 5s wait — if the orchestrator itself fails (not a subtask),
    one retry is enough. Subtask failures are handled by their own retry config.
"""

import asyncio

from render_sdk import Workflows, Retry

from .plan import plan_research
from .research_agent import research_subtopic
from .synthesize import synthesize

app = Workflows()


@app.task(
    plan="starter",
    timeout_seconds=600,
    retry=Retry(max_retries=1, wait_duration_ms=5000, backoff_scaling=1),
)
async def research(question: str) -> dict:
    """Full research pipeline: plan -> parallel agents -> synthesize."""
    plan = await plan_research(question)
    print(f"[RESEARCH] plan type={type(plan)}, value={str(plan)[:500]}", flush=True)

    subtopics = plan.get("subtopics", [{"topic": question, "criteria": "Find relevant sources."}])
    print(f"[RESEARCH] {len(subtopics)} subtopics", flush=True)

    findings = await asyncio.gather(
        *[research_subtopic(st["topic"], st["criteria"]) for st in subtopics]
    )
    print(f"[RESEARCH] findings count={len(findings)}, types={[type(f).__name__ for f in findings]}", flush=True)
    for i, f in enumerate(findings):
        print(f"[RESEARCH] finding[{i}] keys={list(f.keys()) if isinstance(f, dict) else 'NOT_DICT'}", flush=True)

    result = await synthesize(question, list(findings))
    print(f"[RESEARCH] final result type={type(result).__name__}, keys={list(result.keys()) if isinstance(result, dict) else 'NOT_DICT'}", flush=True)
    print(f"[RESEARCH] final result preview={str(result)[:500]}", flush=True)

    return result
