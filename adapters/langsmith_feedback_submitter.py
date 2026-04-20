import os


class LangsmithFeedbackSubmitter:
    """Submits thumbs up/down to LangSmith when configured."""

    async def submit(self, run_id: str, score: int, comment: str = "") -> dict:
        if os.environ.get("FEATURE_LANGSMITH_FEEDBACK", "true").lower() in (
            "0",
            "false",
            "no",
        ):
            return {"status": "skipped", "reason": "FEATURE_LANGSMITH_FEEDBACK disabled"}
        if not os.environ.get("LANGCHAIN_API_KEY"):
            return {"status": "skipped", "reason": "LangSmith not configured"}

        try:
            from langsmith import Client

            Client().create_feedback(
                run_id=run_id,
                key="user-rating",
                score=score,
                comment=comment or None,
            )
            return {"status": "ok"}
        except ImportError:
            return {"status": "skipped", "reason": "langsmith package not installed"}
        except Exception as e:
            return {"status": "error", "reason": str(e)}
