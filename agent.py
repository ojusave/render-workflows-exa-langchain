import os

from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from tools import search_wikipedia, calculate

SYSTEM_PROMPT = """You are a helpful assistant. You have access to tools:
- search_wikipedia: look up factual information
- calculate: do math

Use tools when they'd help answer the user's question. Be concise and friendly."""

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
TEMPERATURE = float(os.environ.get("AGENT_TEMPERATURE", "0.3"))


def build_agent():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    llm = ChatAnthropic(model=MODEL, temperature=TEMPERATURE)
    return create_react_agent(llm, tools=[search_wikipedia, calculate])
