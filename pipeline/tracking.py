"""
Optional LangSmith run tracking for the research pipeline.

Creates a top-level LangSmith run per research request so we have a
run_id to attach user feedback to. If LANGCHAIN_API_KEY is not set,
every function returns None and the orchestrator ignores it.

To remove: delete this file and remove the 3 import/call lines from
pipeline/orchestrator.py.
"""

import os
import uuid


_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not os.environ.get("LANGCHAIN_API_KEY"):
        return None
    try:
        from langsmith import Client

        _client = Client()
        return _client
    except ImportError:
        return None


def start_run(question: str) -> str | None:
    """Create a pipeline run in LangSmith. Returns run_id or None."""
    client = _get_client()
    if not client:
        return None
    try:
        run_id = str(uuid.uuid4())
        client.create_run(
            name="research_pipeline",
            run_type="chain",
            inputs={"question": question},
            id=run_id,
            project_name=os.environ.get("LANGCHAIN_PROJECT", "research-agent"),
        )
        return run_id
    except Exception:
        return None


def complete_run(run_id: str | None, report: dict):
    """Mark the pipeline run as completed with the report output."""
    if not run_id:
        return
    client = _get_client()
    if client:
        try:
            client.update_run(run_id, outputs={"report": report})
        except Exception:
            pass


def fail_run(run_id: str | None, error: str):
    """Mark the pipeline run as failed."""
    if not run_id:
        return
    client = _get_client()
    if client:
        try:
            client.update_run(run_id, error=error)
        except Exception:
            pass
