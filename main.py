from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import build_agent, SYSTEM_PROMPT
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.agent = build_agent()
    yield


app = FastAPI(title="LangChain Example", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class ChatResponse(BaseModel):
    reply: str


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not app.state.agent:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY is not set.")

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for msg in req.history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=req.message))

    result = await app.state.agent.ainvoke({"messages": messages})
    ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage) and m.content]
    reply = ai_messages[-1].content if ai_messages else "I couldn't generate a response."

    return ChatResponse(reply=reply)


@app.get("/health")
async def health():
    return {"status": "ok", "agent_loaded": app.state.agent is not None}


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")
