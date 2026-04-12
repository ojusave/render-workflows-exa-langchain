import httpx
from langchain_core.tools import tool


@tool
async def search_wikipedia(query: str) -> str:
    """Search Wikipedia for a topic and return a summary. Use this when you need factual information about a person, place, event, or concept."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://en.wikipedia.org/api/rest_v1/page/summary/" + query.replace(" ", "_"),
            headers={"User-Agent": "langchain-example/1.0"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("extract", "No summary available.")
        return f"Could not find a Wikipedia article for '{query}'."


@tool
def calculate(expression: str) -> str:
    """Evaluate a math expression. Use this for any arithmetic or math calculation."""
    allowed = set("0123456789+-*/.() ")
    if not all(c in allowed for c in expression):
        return "Error: only numeric expressions with +, -, *, /, (, ) are allowed."
    try:
        result = eval(expression)  # noqa: S307 – input is sanitized above
        return str(result)
    except Exception as e:
        return f"Error evaluating expression: {e}"
