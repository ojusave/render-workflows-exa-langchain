"""
User feedback endpoint: submits thumbs-up/down ratings to LangSmith.

Standalone FastAPI router. If LANGCHAIN_API_KEY is not set, returns a
"skipped" response instead of crashing.

To remove: delete this file and remove the include_router line from main.py.
"""

import os

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class FeedbackRequest(BaseModel):
    run_id: str
    score: int
    comment: str = ""


@router.post("/feedback")
async def submit_feedback(body: FeedbackRequest):
    if not os.environ.get("LANGCHAIN_API_KEY"):
        return {"status": "skipped", "reason": "LangSmith not configured"}

    try:
        from langsmith import Client

        Client().create_feedback(
            run_id=body.run_id,
            key="user-rating",
            score=body.score,
            comment=body.comment or None,
        )
        return {"status": "ok"}
    except ImportError:
        return {"status": "skipped", "reason": "langsmith package not installed"}
    except Exception as e:
        return {"status": "error", "reason": str(e)}
