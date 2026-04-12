from langchain_core.tools import tool
from langchain_exa import ExaSearchResults


exa_search = ExaSearchResults(
    num_results=3,
    text_contents_options={"max_characters": 3000},
    summary=True,
)


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
