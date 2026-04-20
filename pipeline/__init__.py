"""
Pipeline package: exposes ``run_pipeline`` for the web service.

``run_pipeline`` is loaded lazily so importing ``pipeline.history`` (used by
adapters) does not require ``RENDER_API_KEY`` or the orchestrator stack.
"""

from typing import Any

__all__ = ["run_pipeline"]


def __getattr__(name: str) -> Any:
    if name == "run_pipeline":
        from .orchestrator import run_pipeline

        return run_pipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
