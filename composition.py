"""Wires port implementations for the FastAPI app."""

from adapters.langsmith_feedback_submitter import LangsmithFeedbackSubmitter
from adapters.pg_thread_repository import PgThreadRepository

_threads = PgThreadRepository()
_feedback = LangsmithFeedbackSubmitter()


def get_deps() -> dict:
    return {
        "threads": _threads,
        "feedback": _feedback,
    }
