"""
Synthesize task: merges all research agent findings into a structured report.

Uses the raw Anthropic SDK (via tasks/llm.py) because this is a single-turn
Claude call: no tools, no agent loop. The input is deterministic (all findings
are already computed by the LangGraph agents).

Workflow config rationale:
  - plan: standard (1 CPU, 2 GB) — the heaviest Claude call; the prompt
    contains every agent's findings concatenated together.
  - timeout: 90s — synthesis over 3-5 subtopic findings can take 30-40s
    from Claude; 90s covers worst-case latency.
  - retry: 1 retry, 3s wait — input is deterministic, so a retry produces
    the same result. One retry handles transient Claude errors.
"""

from render_sdk import Workflows, Retry

from .llm import ask, parse_json

app = Workflows()


@app.task(
    plan="standard",
    timeout_seconds=90,
    retry=Retry(max_retries=1, wait_duration_ms=3000, backoff_scaling=1),
)
def synthesize(question: str, findings: list) -> dict:
    """Merge all research agent findings into a structured report."""
    parts = []
    for f in findings:
        section = f"**Findings:**\n{f.get('findings', '')}\n\n"
        points = f.get("key_points", [])
        if points:
            section += "**Key points:**\n" + "\n".join(f"- {p}" for p in points) + "\n\n"
        sources = f.get("sources", [])
        if sources:
            section += "**Sources:**\n" + "\n".join(
                f"- [{s.get('title', 'Source')}]({s.get('url', '')})" for s in sources
            )
        parts.append(section)

    context = "\n\n---\n\n".join(parts)
    raw = ask(
        system=(
            "You are a research synthesizer. Combine the research findings below into "
            "a structured report. Return ONLY a JSON object with:\n"
            '- "title": a concise report title\n'
            '- "summary": a 2-3 sentence executive summary\n'
            '- "sections": a list of objects with "heading" and "content" keys (use markdown in content)\n'
            '- "sources": a deduplicated list of objects with "title" and "url" keys\n'
            "No other text."
        ),
        user=f"Research question: {question}\n\nResearch findings:\n{context}",
    )
    return parse_json(raw, {
        "title": "Research Report",
        "summary": raw[:500],
        "sections": [],
        "sources": [],
    })
