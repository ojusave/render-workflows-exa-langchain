"""
Exa tool definitions for the LangGraph research agent.

Configures ExaSearchResults and ExaFindSimilarResults as LangGraph-compatible
tools. The agent calls these dynamically during its reasoning loop: it might
search once and stop, or search five times and use find_similar to chase down
a promising lead. The decision is the LLM's, not hardcoded.

ExaSearchResults: semantic web search. Unlike keyword search, the agent can
query with natural language ("recent breakthroughs in quantum error correction")
and get meaning-matched results.

ExaFindSimilarResults: given a URL the agent found useful, discover related
pages. Enables discovery chains the agent cannot plan upfront.
"""

import os

from langchain_exa import ExaSearchResults, ExaFindSimilarResults


def build_tools() -> list:
    api_key = os.environ["EXA_API_KEY"]
    return [
        ExaSearchResults(
            exa_api_key=api_key,
            max_results=5,
        ),
        ExaFindSimilarResults(
            exa_api_key=api_key,
            max_results=3,
        ),
    ]
