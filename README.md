# LangChain Chat: Conversational Agent with Tools

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/ojusave/langchain-test)

A FastAPI app demonstrating LangChain's agent framework with [Render Workflows](https://render.com/workflows) for durable, isolated agent execution. The agent can:

- **Search the web** via [Exa](https://exa.ai/) for real-time information
- **Calculate** math expressions
- **Maintain conversation context** across messages

Built with LangChain + LangGraph + Anthropic Claude + [Exa](https://exa.ai/), running on [Render](https://render.com/).

## Deploy

Click the **Deploy to Render** button above. You'll be prompted to set:

- `RENDER_API_KEY`: your [Render API key](https://render.com/docs/api#1-create-an-api-key) (for the web service)
- `ANTHROPIC_API_KEY`: your Anthropic API key (for the workflow service)
- `EXA_API_KEY`: your [Exa API key](https://exa.ai/) (for the workflow service)

Then click **Apply**. The Blueprint creates both services automatically.

Don't have a Render account? [Sign up here](https://render.com/register).

## Architecture

```
Browser  →  FastAPI (web service)  →  Render Workflow  →  LangGraph Agent  →  Claude
                                           ↕
                                  Tools (Exa Search, Calculator)
```

The app runs as two Render services:

- **Web service** (`langchain-example`): thin FastAPI layer that serves the UI and triggers workflow tasks via the Render SDK
- **Workflow service** (`langchain-chat-workflow`): runs the LangChain agent in isolated containers with automatic retries, configurable timeouts, and full observability in the Render Dashboard

This separation means agent reasoning runs on its own compute, with retry logic and a 2-minute timeout, without blocking or crashing the web server.

## Environment Variables

### Web service

| Variable | Required | Default | Description |
|---|---|---|---|
| `RENDER_API_KEY` | Yes | — | Render API key for triggering workflows |
| `WORKFLOW_SLUG` | No | `langchain-chat-workflow` | Workflow service slug |

### Workflow service

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — | Your Anthropic API key |
| `EXA_API_KEY` | Yes | — | Your Exa API key for web search |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-20250514` | Model to use |
| `AGENT_TEMPERATURE` | No | `0.3` | LLM temperature |

## Project Structure

```
├── main.py           # FastAPI web service (API gateway)
├── workflow.py       # Render Workflow task definition
├── agent.py          # Agent config, system prompt, builder
├── tools.py          # Tool definitions (Exa search, calculator)
├── static/
│   └── index.html    # Chat UI
├── render.yaml       # Render Blueprint (web + workflow)
├── requirements.txt  # Python dependencies
└── .env.example      # Environment variable reference
```

## API

### `POST /chat`

```json
{
  "message": "What is the population of Japan?",
  "history": [
    { "role": "user", "content": "Hello" },
    { "role": "assistant", "content": "Hi! How can I help?" }
  ]
}
```

Response:

```json
{
  "reply": "According to Wikipedia, Japan has a population of approximately 125 million people."
}
```

### `GET /health`

Returns `{ "status": "ok" }`.
