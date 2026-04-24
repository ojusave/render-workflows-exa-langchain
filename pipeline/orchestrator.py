"""
Pipeline orchestrator: runs classify, plan, research agents, and synthesize
as individual workflow tasks, streaming real-time progress via SSE.

The web service calls run_pipeline(), which:
  1. Starts classify_query → if "direct", returns the reply immediately
  2. Starts plan_research → polls → extracts subtopics
  3. Starts N research_subtopic tasks in parallel → polls each → reports completions
  4. Starts synthesize → polls → extracts report

Each task runs on the workflow service with its own retry/timeout config.
The orchestrator only dispatches and polls: no research logic here.
"""

import asyncio
import json
import os
import time

from render_sdk import RenderAsync
from .tracking import start_run, complete_run, fail_run
from .history import save_entry

WORKFLOW_SLUG = os.environ.get("WORKFLOW_SLUG", "research-agent-workflow")
POLL_INTERVAL = 4

render = RenderAsync()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tools(*names):
    """Build a tools list, appending LangSmith when configured."""
    tools = list(names)
    if os.environ.get("LANGCHAIN_API_KEY"):
        tools.append("LangSmith")
    return tools


def _to_dict(obj):
    """Convert SDK objects to plain dicts for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    if hasattr(obj, "__dict__") and not isinstance(obj, (str, int, float, bool)):
        return {k: _to_dict(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
    return obj


def sse(event: str, data: dict) -> str:
    """Format one Server-Sent Events message for the browser EventSource client."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _extract_result(results):
    """Pull the result dict out of whatever shape the SDK gives us."""
    if not results:
        return {}
    raw = results
    if isinstance(results, list) and len(results) > 0:
        raw = results[0]
    if isinstance(raw, dict):
        return raw
    return _to_dict(raw) if raw is not None else {}


def _task_status(details) -> str:
    return details.status if isinstance(details.status, str) else details.status.value


async def _start_and_wait(task_path: str, params: dict) -> dict:
    """Start a workflow task, poll until terminal, return the result dict."""
    started = await render.workflows.start_task(
        f"{WORKFLOW_SLUG}/{task_path}", params
    )
    while True:
        await asyncio.sleep(POLL_INTERVAL)
        details = await render.workflows.get_task_run(started.id)
        status = _task_status(details)
        if status == "completed":
            return _extract_result(details.results)
        if status in ("failed", "canceled"):
            error = getattr(details, "error", "unknown error")
            raise RuntimeError(f"Task {task_path} {status}: {error}")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

async def run_pipeline(
    question: str,
    thread_id: str | None = None,
    prior_context: str | None = None,
):
    """Run the full research pipeline, yielding SSE events at each step."""
    run_id = None
    t0 = time.monotonic()

    try:
        run_id = start_run(question)

        # Phase 0: classify
        yield sse("status", {
            "phase": "classifying",
            "tools": _tools("Render Workflows", "LangChain", "Claude"),
        })

        classify_params = {"question": question}
        if prior_context:
            classify_params["prior_context"] = prior_context

        classification = await _start_and_wait("classify_query", classify_params)
        query_type = classification.get("type", "research")

        yield sse("classified", {
            "type": query_type,
            "tools": _tools("Render Workflows", "LangChain", "Claude"),
        })

        if query_type == "direct":
            elapsed = int(time.monotonic() - t0)
            reply = classification.get("reply", "I can help with research questions.")
            complete_run(run_id, {"reply": reply})
            await save_entry(thread_id, question, {"reply": reply}, run_id)
            yield sse("direct_answer", {
                "reply": reply,
                "run_id": run_id,
                "thread_id": thread_id,
                "elapsed": elapsed,
                "tools": _tools("Render Workflows", "LangChain", "Claude"),
            })
            return

        # Phase 1: plan
        yield sse("status", {
            "phase": "planning",
            "tools": _tools("Render Workflows", "LangChain", "Claude"),
        })

        plan_params = {"question": question}
        if prior_context:
            plan_params["prior_context"] = prior_context

        plan = await _start_and_wait("plan_research", plan_params)
        subtopics = plan.get("subtopics", [
            {"topic": question, "criteria": "Find relevant sources."}
        ])

        yield sse("plan", {
            "subtopics": [st["topic"] for st in subtopics],
            "tools": _tools("Render Workflows", "LangChain", "Claude"),
        })

        # Phase 2: parallel research agents
        agents = []
        for i, st in enumerate(subtopics):
            # Small delay between task launches to avoid rate limits
            if i > 0:
                await asyncio.sleep(0.5)

            try:
                started = await render.workflows.start_task(
                    f"{WORKFLOW_SLUG}/research_subtopic",
                    {"subtopic": st["topic"], "criteria": st["criteria"]},
                )
            except Exception as launch_err:
                # Retry once after a longer delay if rate limited
                await asyncio.sleep(2)
                started = await render.workflows.start_task(
                    f"{WORKFLOW_SLUG}/research_subtopic",
                    {"subtopic": st["topic"], "criteria": st["criteria"]},
                )

            agents.append({
                "id": started.id,
                "index": i,
                "subtopic": st["topic"],
                "done": False,
            })
            yield sse("agent_start", {
                "index": i,
                "subtopic": st["topic"],
                "tools": _tools("Render Workflows", "LangGraph", "Exa", "Claude"),
            })

        findings = [None] * len(agents)

        while not all(a["done"] for a in agents):
            await asyncio.sleep(POLL_INTERVAL)
            for a in agents:
                if a["done"]:
                    continue
                details = await render.workflows.get_task_run(a["id"])
                status = _task_status(details)

                if status == "completed":
                    a["done"] = True
                    findings[a["index"]] = _extract_result(details.results)
                    yield sse("agent_done", {
                        "index": a["index"],
                        "subtopic": a["subtopic"],
                        "tools": _tools("Render Workflows", "LangGraph", "Exa", "Claude"),
                    })
                elif status in ("failed", "canceled"):
                    error = getattr(details, "error", "unknown error")
                    raise RuntimeError(f"Agent '{a['subtopic']}' {status}: {error}")

        # Phase 3: synthesize
        yield sse("status", {
            "phase": "synthesizing",
            "tools": _tools("Render Workflows", "LangChain", "Claude"),
        })

        synth_params = {"question": question, "findings": findings}
        if prior_context:
            synth_params["prior_context"] = prior_context

        report = await _start_and_wait("synthesize", synth_params)

        elapsed = int(time.monotonic() - t0)

        if report:
            complete_run(run_id, report)
            await save_entry(thread_id, question, report, run_id)
            yield sse("done", {
                "report": report,
                "run_id": run_id,
                "thread_id": thread_id,
                "elapsed": elapsed,
                "tools": _tools("Render Workflows", "LangChain", "Claude"),
            })
        else:
            yield sse("error", {
                "message": "Pipeline completed but returned empty results.",
            })

    except Exception as e:
        fail_run(run_id, str(e))
        elapsed = int(time.monotonic() - t0)
        yield sse("error", {"message": str(e), "elapsed": elapsed})
