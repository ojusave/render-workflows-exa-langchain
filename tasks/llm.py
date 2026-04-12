"""
Shared Claude helpers using the raw Anthropic SDK.

Used by plan and synthesize tasks for simple, single-turn Claude calls
where a full LangGraph agent loop is unnecessary. The LangGraph agent
(tasks/agent.py) uses langchain-anthropic instead, because LangGraph
needs the ChatModel interface for tool binding.

The parse_json helper is deliberately lenient: Claude sometimes wraps JSON
in markdown code fences or adds preamble text. The fallback extraction
finds the first {...} block, which is good enough for structured output
without forcing function-calling mode.
"""

import json
import os

import anthropic

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
TEMPERATURE = float(os.environ.get("AGENT_TEMPERATURE", "0.3"))

_client = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def ask(system: str, user: str) -> str:
    response = get_client().messages.create(
        model=MODEL,
        max_tokens=4096,
        temperature=TEMPERATURE,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


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
