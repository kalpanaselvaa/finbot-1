---
name: project-cb-finbot
description: "Core facts about the cb-finbot project — stack, endpoints, config, what's been built"
metadata: 
  node_type: memory
  type: project
  originSessionId: 799d0a03-80c9-4f43-a33f-b00d3d2bb93a
---

FinBot is an AI-powered equity research assistant built with FastAPI + LangGraph.

**Why:** Bootcamp project using Azure AI Foundry, now running locally with Ollama/llama3.2 because the Azure subscription (f1d64acd-32c9-4753-9677-7377652e4006) is disabled.

**How to apply:** When making changes, assume Azure is disabled. Use local llama3.2 via Ollama as the LLM. Re-enable Azure paths when subscription is active again.

## Stack
- **LLM:** Ollama llama3.2 (local, `ollama list` shows it installed)
- **Agent:** LangGraph ReAct agent with SQLite checkpointer at `.data/finance_agent.db`
- **API:** FastAPI on port 8000 (`run.py` → `app/main.py`)
- **Frontend:** Next.js on port 3000 (`frontend/`)
- **Package manager:** `uv` (not pip directly)

## Key endpoints
- `GET /` → API info
- `GET /health` → `{"status": "ok"}`
- `POST /brief` → `{"query": "AAPL", "thread_id": "..."}` → analyst brief

## Tools available to agent
- `get_stock_fundamentals` — yfinance
- `yahoo_finance_news` — Yahoo Finance
- `wikipedia` — Wikipedia
- `search_news` (SerpAPI) — disabled, key is empty in .env

## Files
- `app/agent.py` — LangGraph agent, llama3.2 via ChatOllama
- `app/tools.py` — tool definitions
- `app/guardrails.py` — scope + safety checks
- `app/config.py` — pydantic-settings from .env
- `app/main.py` — FastAPI routes with guardrails wired in
- `app/schemas.py` — BriefRequest / BriefResponse
- `eval/test_brief_quality.py` — deepeval test suite (30 tests)
