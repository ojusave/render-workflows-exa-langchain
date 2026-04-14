"""
Optional research history backed by Render PostgreSQL.

All functions no-op gracefully when DATABASE_URL is not set.
To remove: delete this file and remove the related imports from main.py
and pipeline/orchestrator.py.
"""

import json
import os
import uuid

DATABASE_URL = os.environ.get("DATABASE_URL")

_pool = None

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS research_history (
    id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    question    TEXT            NOT NULL,
    report      JSONB           NOT NULL,
    run_id      TEXT,
    created_at  TIMESTAMPTZ     DEFAULT now()
);
"""


async def init_db():
    """Create the connection pool and table. No-op without DATABASE_URL."""
    global _pool
    if not DATABASE_URL:
        return

    import asyncpg
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with _pool.acquire() as conn:
        await conn.execute(_CREATE_TABLE)


async def close_db():
    """Close the connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def save_research(question: str, report: dict, run_id: str | None = None) -> str | None:
    """Save a completed research to history. Returns the entry id."""
    if not _pool:
        return None

    entry_id = str(uuid.uuid4())
    await _pool.execute(
        "INSERT INTO research_history (id, question, report, run_id) VALUES ($1, $2, $3::jsonb, $4)",
        uuid.UUID(entry_id),
        question,
        json.dumps(report),
        run_id,
    )
    return entry_id


async def list_history(limit: int = 20) -> list[dict]:
    """Return recent history entries (without report body)."""
    if not _pool:
        return []

    rows = await _pool.fetch(
        "SELECT id, question, created_at FROM research_history ORDER BY created_at DESC LIMIT $1",
        limit,
    )
    return [
        {"id": str(r["id"]), "question": r["question"], "created_at": r["created_at"].isoformat()}
        for r in rows
    ]


async def get_history_entry(entry_id: str) -> dict | None:
    """Return a single history entry with full report."""
    if not _pool:
        return None

    row = await _pool.fetchrow(
        "SELECT id, question, report, run_id, created_at FROM research_history WHERE id = $1",
        uuid.UUID(entry_id),
    )
    if not row:
        return None

    return {
        "id": str(row["id"]),
        "question": row["question"],
        "report": json.loads(row["report"]) if isinstance(row["report"], str) else row["report"],
        "run_id": row["run_id"],
        "created_at": row["created_at"].isoformat(),
    }


async def delete_history_entry(entry_id: str) -> bool:
    """Delete a history entry. Returns True if deleted."""
    if not _pool:
        return False

    result = await _pool.execute(
        "DELETE FROM research_history WHERE id = $1",
        uuid.UUID(entry_id),
    )
    return result == "DELETE 1"
