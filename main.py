import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from render_sdk import RenderAsync

WORKFLOW_SLUG = os.environ.get("WORKFLOW_SLUG", "langchain-chat-workflow")

app = FastAPI(title="LangChain Example")
render = RenderAsync()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/chat")
async def chat(req: ChatRequest):
    async def event_stream():
        try:
            started = await render.workflows.start_task(
                f"{WORKFLOW_SLUG}/agent_chat",
                {"message": req.message, "history": req.history},
            )
            yield sse("status", {"status": "pending", "message": "Queuing agent..."})

            async for event in render.workflows.task_run_events([started.id]):
                if event.status == "running":
                    yield sse("status", {"status": "running", "message": "Agent is reasoning..."})
                elif event.status == "completed":
                    reply = event.results[0] if event.results else "No response."
                    yield sse("done", {"status": "completed", "reply": reply})
                elif event.status in ("failed", "canceled"):
                    msg = getattr(event, "error", None) or "Agent failed after retries"
                    yield sse("error", {"status": "failed", "message": msg})
        except Exception as e:
            yield sse("error", {"status": "failed", "message": str(e)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok"}


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")
