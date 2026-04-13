"""
Plan task: asks Claude to break a question into subtopics with success criteria.

Single-turn Claude call via the shared ChatAnthropic model (tasks/llm.py).
The output includes success criteria for each subtopic so the research
agent knows when it has gathered enough evidence to stop searching.

Workflow config rationale:
  - plan: starter (0.5 CPU, 512 MB): lightweight LLM call with a short prompt.
  - timeout: 45s: Claude should respond in <10s; 45s gives room for cold starts.
  - retry: 2 retries, 2s base wait, 1.5x backoff: handles Claude rate limits.
"""

from render_sdk import Workflows, Retry

from .llm import ask, parse_json

app = Workflows()


@app.task(
    plan="starter",
    timeout_seconds=45,
    retry=Retry(max_retries=2, wait_duration_ms=2000, backoff_scaling=1.5),
)
def plan_research(question: str) -> dict:
    """Break a research question into subtopics with success criteria."""
    raw = ask(
        system=(
            "You are a research planner. Given a question, break it into exactly 3 subtopics "
            "that a research agent should investigate separately. Keep subtopics focused "
            "and non-overlapping. For each, define a concise success criterion.\n\n"
            "Return ONLY a JSON object with:\n"
            '- "subtopics": a list of exactly 3 objects, each with:\n'
            '  - "topic": a concise subtopic description\n'
            '  - "criteria": what evidence the researcher should find (2-3 sources)\n'
            "No other text."
        ),
        user=question,
    )
    fallback = {
        "subtopics": [
            {"topic": question, "criteria": "Find 3-5 relevant, recent sources with key findings."}
        ]
    }
    return parse_json(raw, fallback)
