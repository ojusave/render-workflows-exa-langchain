from typing import Protocol


class FeedbackSubmitter(Protocol):
    """User ratings to LangSmith (or a no-op / skipped result)."""

    async def submit(self, run_id: str, score: int, comment: str = "") -> dict: ...
