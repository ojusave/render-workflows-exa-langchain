"""
FastAPI web service: the HTTP layer for the research agent.

Thin HTTP layer: JSON responses use ``{ data, error, meta }`` (see ``shared/api_envelope.py``).
Threaded history and LangSmith feedback go through ports wired in ``composition.py``.
The pipeline orchestrator still uses ``pipeline.history.save_entry`` internally.
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from composition import get_deps
from pipeline import run_pipeline
from pipeline.history import close_db, init_db
from shared.api_envelope import fail, ok

deps = get_deps()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open optional Postgres pool on startup; close on shutdown."""
    await init_db()
    yield
    await close_db()


app = FastAPI(title="Research Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    question: str
    thread_id: Optional[str] = None


class FeedbackRequest(BaseModel):
    run_id: str
    score: int
    comment: str = ""


@app.post("/research")
async def research(req: ResearchRequest):
    """Stream research pipeline progress as SSE. Creates a thread if `thread_id` is omitted."""
    prior_context = None
    thread_id = req.thread_id
    threads = deps["threads"]

    if not thread_id:
        thread_id = await threads.create_thread(req.question)
    else:
        prior_context = await threads.get_prior_context(thread_id)

    return StreamingResponse(
        run_pipeline(req.question, thread_id=thread_id, prior_context=prior_context),
        media_type="text/event-stream",
    )


@app.get("/history")
async def history():
    """List research threads (empty list if `DATABASE_URL` is not set)."""
    rows = await deps["threads"].list_threads()
    return JSONResponse(ok(rows))


@app.get("/history/{thread_id}")
async def history_entry(thread_id: str):
    """Return one thread or 404."""
    thread = await deps["threads"].get_thread(thread_id)
    if not thread:
        return JSONResponse(fail("NOT_FOUND", "not found"), status_code=404)
    return JSONResponse(ok(thread))


@app.delete("/history/{thread_id}")
async def history_delete(thread_id: str):
    """Delete a thread or return 404 if missing."""
    deleted = await deps["threads"].delete_thread(thread_id)
    if not deleted:
        return JSONResponse(fail("NOT_FOUND", "not found"), status_code=404)
    return JSONResponse(ok({"status": "ok"}))


@app.post("/feedback")
async def submit_feedback(body: FeedbackRequest):
    result = await deps["feedback"].submit(body.run_id, body.score, body.comment)
    return JSONResponse(ok(result))


@app.get("/health")
async def health():
    """Liveness check for Render."""
    return JSONResponse(ok({"status": "ok"}))


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    """Serve the single-page UI."""
    return FileResponse("static/index.html")
