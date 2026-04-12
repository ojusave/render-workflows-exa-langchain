import os

from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from tools import exa_search, calculate

SYSTEM_PROMPT = """You are a helpful assistant. You have access to tools:
- exa_search: search the web for real-time information on any topic
- calculate: do math

Use tools when they'd help answer the user's question. Be concise and friendly."""

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
TEMPERATURE = float(os.environ.get("AGENT_TEMPERATURE", "0.3"))


def build_agent():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    llm = ChatAnthropic(model=MODEL, temperature=TEMPERATURE)
    return create_react_agent(llm, tools=[exa_search, calculate])
