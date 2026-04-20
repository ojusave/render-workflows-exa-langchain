"""
Workflow service entry point: run with `python -m tasks`.

Starts the Render Workflows runtime, which registers tasks: classify_query,
plan_research, research_subtopic, synthesize — then polls for incoming runs.
"""

from tasks import app

app.start()
