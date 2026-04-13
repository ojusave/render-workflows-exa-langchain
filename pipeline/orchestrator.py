"""
Pipeline orchestrator: starts the research workflow task and streams SSE.

This is the bridge between the stateless web service and the durable
workflow service. It:
  1. Triggers the `research` orchestrator task via the Render SDK
  2. Polls for completion, streaming live progress as SSE
  3. Extracts the final report and sends it to the frontend

The orchestrator itself does no research work. All compute happens in
the workflow service on isolated instances with their own retry/timeout
config.
"""

import asyncio
import json
import os
import time

from render_sdk import RenderAsync
from render_sdk.client.errors import TaskRunError

from .tracking import start_run, complete_run, fail_run

WORKFLOW_SLUG = os.environ.get("WORKFLOW_SLUG", "research-agent-workflow")
POLL_INTERVAL = 4  # seconds between status checks

render = RenderAsync()

# Pipeline phases shown in order as time progresses.
# (min_elapsed_seconds, label)
_PHASES = [
    (0, "Planning research approach…"),
    (10, "Searching for sources…"),
    (25, "Analyzing findings…"),
    (50, "Synthesizing final report…"),
]


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
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _extract_report(results) -> dict:
    """Pull the report dict out of whatever shape the SDK gives us for results."""
    if not results:
        return {}
    raw = results
    if isinstance(results, list) and len(results) > 0:
        raw = results[0]
    if isinstance(raw, dict):
        return raw
    return _to_dict(raw) if raw is not None else {}


def _phase_message(elapsed: int) -> str:
    msg = _PHASES[0][1]
    for threshold, label in _PHASES:
        if elapsed >= threshold:
            msg = label
    return msg


async def run_pipeline(question: str):
    """Start the research task and poll for completion, streaming progress."""
    run_id = None
    try:
        run_id = start_run(question)

        started = await render.workflows.start_task(
            f"{WORKFLOW_SLUG}/research", {"question": question}
        )
        task_run_id = started.id
        t0 = time.monotonic()

        yield sse("status", {
            "message": _phase_message(0),
            "task_run_id": task_run_id,
            "elapsed": 0,
        })

        # Poll until the task reaches a terminal state
        while True:
            await asyncio.sleep(POLL_INTERVAL)
            elapsed = int(time.monotonic() - t0)

            details = await render.workflows.get_task_run(task_run_id)
            status_val = details.status if isinstance(details.status, str) else details.status.value

            if status_val in ("completed", "failed", "canceled"):
                break

            yield sse("status", {
                "message": _phase_message(elapsed),
                "elapsed": elapsed,
            })

        elapsed = int(time.monotonic() - t0)

        if status_val == "completed":
            report = _extract_report(details.results)

            if report:
                complete_run(run_id, report)
                yield sse("done", {"report": report, "run_id": run_id, "elapsed": elapsed})
            else:
                yield sse("error", {
                    "message": "Workflow completed but returned empty results. Check workflow logs.",
                    "elapsed": elapsed,
                })
        elif status_val == "failed":
            err = getattr(details, "error", None) or "Task failed"
            fail_run(run_id, str(err))
            yield sse("error", {"message": str(err), "elapsed": elapsed})
        else:
            fail_run(run_id, f"Task was {status_val}")
            yield sse("error", {"message": f"Task was {status_val}", "elapsed": elapsed})

    except TaskRunError as e:
        fail_run(run_id, str(e))
        yield sse("error", {"message": str(e)})

    except Exception as e:
        fail_run(run_id, str(e))
        yield sse("error", {"message": str(e)})
