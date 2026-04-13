"""
Tasks package: combines all workflow task apps into a single Workflows entry point.

Four task modules register with the Workflows runtime:
  - plan: breaks a question into subtopics
  - research_agent: runs a LangGraph ReAct agent per subtopic (Exa tools)
  - synthesize: merges findings into a report
  - research: orchestrator that chains the above three

All Claude calls go through the shared ChatAnthropic model in tasks/llm.py.
Each module defines its own per-task compute plan, timeout, and retry strategy.
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
