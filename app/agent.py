import sqlite3
from pathlib import Path

from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from app.config import settings
from app.tools import tools

SYSTEM_PROMPT = """
You are FinBot, an expert equity research analyst with deep knowledge of financial markets,
valuation methodologies, and macroeconomic trends.

## Task
Given a stock ticker or company name, produce a concise, structured analyst brief that helps users evaluate the investment. Do not give buy/sell advice. Present data-driven signals only.

## Rules
1. Gather data before analysis. Never rely on memory for numbers.
2. If a tool fails or returns empty data, state it and proceed.
3. Never fabricate prices, ratios, or news.
4. Always follow the output format.
5. Flag notable risks or red flags.
6. Format ratio fields (revenue_growth, profit_margin, gross_margin) as percentages: multiply by 100 and append % (e.g. 0.066 → 6.60%).

## Output Format

**[TICKER] — Analyst Brief**
- **Fundamentals:** price, P/E, market cap, revenue growth (one line)
- **Valuation Signal:** OVERVALUED / FAIRLY VALUED / UNDERVALUED + reason
- **News Sentiment:** bullish / neutral / bearish + key headline
- **Key Risks:** 1-2 bullets
- **Outlook:** 1-2 sentence synthesis, no advice
"""

# Lazily-initialised singleton — nothing runs at import time.
_agent = None


def _get_agent():
    global _agent

    if _agent is not None:
        return _agent

    # ── SQLite checkpointer ────────────────────────────────
    db_path = Path(settings.sqlite_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    # ── Ollama local LLM ──────────────────────────────────
    llm = ChatOllama(model="llama3.2", temperature=0)

    # ── LangGraph ReAct agent ──────────────────────────────
    _agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )

    return _agent


def run_agent(query: str, thread_id: str) -> str:
    agent = _get_agent()

    response = agent.invoke(
        {"messages": [{"role": "user", "content": query}]},
        config={"configurable": {"thread_id": thread_id}},
    )

    messages = response.get("messages", [])
    if not messages:
        return "No response returned."

    last = messages[-1]
    content = getattr(last, "content", "")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
        return "\n".join(texts).strip()

    return str(content)
