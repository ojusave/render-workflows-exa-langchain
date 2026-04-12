"""
Tasks package: combines all workflow task apps into a single Workflows entry point.

Four task modules register with the Workflows runtime:
  - plan: breaks a question into subtopics (raw Anthropic SDK)
  - research_agent: runs a LangGraph ReAct agent per subtopic (LangGraph + Exa)
  - synthesize: merges findings into a report (raw Anthropic SDK)
  - research: orchestrator that chains the above three

Each module defines its own per-task compute plan, timeout, and retry strategy.
No defaults are set here: all config is explicit in each task file.
"""

from render_sdk import Workflows

from .plan import app as plan_app
from .research_agent import app as research_agent_app
from .synthesize import app as synthesize_app
from .research import app as research_app

app = Workflows.from_workflows(
    research_app,
    plan_app,
    research_agent_app,
    synthesize_app,
)

__all__ = ["app"]
