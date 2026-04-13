"""
Pipeline orchestrator: starts the research workflow task and streams SSE.

This is the bridge between the stateless web service and the durable
workflow service. It:
  1. Triggers the `research` orchestrator task via the Render SDK
  2. Awaits its completion (the SDK handles polling)
  3. Streams status updates as Server-Sent Events (SSE)

The orchestrator itself does no research work. All compute happens in
the workflow service on isolated instances with their own retry/timeout
config.
"""

import json
import os

from render_sdk import RenderAsync
from render_sdk.client.errors import TaskRunError

WORKFLOW_SLUG = os.environ.get("WORKFLOW_SLUG", "research-agent-workflow")

render = RenderAsync()


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

    # results might be a list wrapping the return value, or the value itself
    raw = results
    if isinstance(results, list) and len(results) > 0:
        raw = results[0]

    if isinstance(raw, dict):
        return raw

    return _to_dict(raw) if raw is not None else {}


async def run_pipeline(question: str):
    """Start the research orchestrator task and yield SSE events until it completes."""
    try:
        yield sse("status", {"message": "Starting research..."})

        started = await render.workflows.start_task(
            f"{WORKFLOW_SLUG}/research", {"question": question}
        )
        yield sse("status", {"message": "Researching...", "task_run_id": started.id})

        finished = await started

        print(f"[PIPELINE] status={finished.status}", flush=True)
        print(f"[PIPELINE] results type={type(finished.results)}", flush=True)
        print(f"[PIPELINE] results value={finished.results!r}"[:2000], flush=True)

        report = _extract_report(finished.results)

        print(f"[PIPELINE] extracted report keys={list(report.keys()) if isinstance(report, dict) else type(report)}", flush=True)

        if not report:
            yield sse("error", {"message": "Workflow completed but returned empty results. Check workflow service logs."})
        else:
            yield sse("done", {"report": report})

    except TaskRunError as e:
        print(f"[PIPELINE] TaskRunError: {e}", flush=True)
        yield sse("error", {"message": str(e)})

    except Exception as e:
        print(f"[PIPELINE] Exception {type(e).__name__}: {e}", flush=True)
        yield sse("error", {"message": str(e)})
