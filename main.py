"""
FastAPI web service: the HTTP layer for the research agent.

This file is intentionally thin. It handles:
  - CORS middleware (so the browser UI can call the API)
  - The /research POST endpoint (delegates to the pipeline orchestrator)
  - The /feedback POST endpoint (LangSmith user ratings)
  - The /history endpoints (optional PostgreSQL research history)
  - The /health GET endpoint (for Render health checks)
  - Static file serving (the browser UI)

The pipeline orchestrator (pipeline/orchestrator.py) dispatches individual
workflow tasks via the Render SDK, polls each one, and streams real-time
progress to the frontend as SSE. Research execution happens on the
workflow service.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pipeline import run_pipeline
from pipeline.feedback import router as feedback_router
from pipeline.history import init_db, close_db, list_history, get_history_entry, delete_history_entry


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(title="Research Agent", lifespan=lifespan)
app.include_router(feedback_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    question: str


@app.post("/research")
async def research(req: ResearchRequest):
    return StreamingResponse(run_pipeline(req.question), media_type="text/event-stream")


@app.get("/history")
async def history():
    entries = await list_history()
    return entries


@app.get("/history/{entry_id}")
async def history_entry(entry_id: str):
    entry = await get_history_entry(entry_id)
    if not entry:
        return JSONResponse({"error": "not found"}, status_code=404)
    return entry


@app.delete("/history/{entry_id}")
async def history_delete(entry_id: str):
    deleted = await delete_history_entry(entry_id)
    if not deleted:
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")
