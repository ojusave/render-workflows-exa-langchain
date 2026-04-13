"""
LangGraph ReAct research agent: Claude dynamically decides what to search.

This is where LangGraph earns its place. The agent runs a tool-calling loop:
  1. Claude reads the subtopic and success criteria
  2. Claude decides which Exa tool to call (search or find_similar)
  3. The tool runs and returns observations
  4. Claude evaluates: enough evidence, or search again?
  5. Repeat until Claude stops calling tools and returns findings

This loop is non-deterministic: the agent might search 2 times for a simple
subtopic or 8 times for a complex one. You cannot hardcode this pipeline.

The recursion_limit is set high (effectively unlimited) because the
Workflow task timeout (120s) is the real safety net against runaway loops.

LangGraph is used here instead of a raw while-loop because:
  - create_react_agent handles the message state, tool dispatch, and
    routing (tool calls vs final answer) without boilerplate
  - The same graph could be extended with checkpointing or human-in-the-loop
    if needed later
"""

from langgraph.prebuilt import create_react_agent

from .llm import get_model, parse_json
from .tools import build_tools

MAX_STEPS = 25


def run_research_agent(subtopic: str, criteria: str) -> dict:
    """Run a ReAct agent that researches a subtopic using Exa tools."""
    model = get_model()
    tools = build_tools()

    system_prompt = (
        f"You are a research agent investigating: {subtopic}\n\n"
        f"Success criteria: {criteria}\n\n"
        "You have two tools:\n"
        "- exa_search: semantic web search. Use natural language queries.\n"
        "- exa_find_similar_results: given a URL you found useful, find related pages.\n\n"
        "Research strategy:\n"
        "1. Do ONE broad search on the subtopic.\n"
        "2. Only do a second search if the first returned very few results.\n"
        "3. Do NOT use find_similar unless absolutely necessary.\n"
        "4. Stop as soon as you have 2-3 good sources. Do not over-research.\n"
        "5. Return your findings as a JSON object with:\n"
        '   - "findings": a detailed paragraph summarizing what you found\n'
        '   - "key_points": a list of 3-5 concise bullet points\n'
        '   - "sources": a list of objects with "title" and "url" keys\n'
        "Return ONLY the JSON object as your final message. No other text."
    )

    graph = create_react_agent(
        model,
        tools,
        prompt=system_prompt,
    )

    result = graph.invoke(
        {"messages": [{"role": "user", "content": f"Research this subtopic: {subtopic}"}]},
        config={"recursion_limit": MAX_STEPS},
    )

    final_text = result["messages"][-1].content
    if isinstance(final_text, list):
        final_text = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in final_text
        )

    return parse_json(final_text, {
        "findings": final_text,
        "key_points": [],
        "sources": [],
    })
