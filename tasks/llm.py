"""
Shared Claude helpers via ChatAnthropic.

Provides a single ChatAnthropic model instance used by every task:
plan, synthesize, and the LangGraph research agent. The ask() helper
wraps simple single-turn calls so plan.py and synthesize.py stay clean.

The parse_json helper is deliberately lenient: Claude sometimes wraps JSON
in markdown code fences or adds preamble text. The fallback extraction
finds the first {...} block, which is good enough for structured output
without forcing function-calling mode.
"""

import json
import os

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
TEMPERATURE = float(os.environ.get("AGENT_TEMPERATURE", "0.3"))

_model = None


def get_model() -> ChatAnthropic:
    global _model
    if _model is None:
        _model = ChatAnthropic(model=MODEL, temperature=TEMPERATURE, max_tokens=4096)
    return _model


def ask(system: str, user: str) -> str:
    response = get_model().invoke([
        SystemMessage(content=system),
        HumanMessage(content=user),
    ])
    return response.content


def parse_json(raw: str, fallback: dict) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end])
            except json.JSONDecodeError:
                pass
        return fallback
