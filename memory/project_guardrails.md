---
name: project-guardrails
description: How the guardrails and scope check work in cb-finbot
metadata: 
  node_type: memory
  type: project
  originSessionId: 799d0a03-80c9-4f43-a33f-b00d3d2bb93a
---

Three-layer protection in `app/guardrails.py`, wired into `POST /brief` in `app/main.py`.

**Why:** Real conversation history showed the agent answering HR/hotel queries (leave policy, vacation, breakfast hotel). Azure Content Safety is installed but the subscription is disabled.

**How to apply:** When modifying the `/brief` endpoint, keep all three checks in order. When Azure is re-enabled, content safety activates automatically — no code changes needed.

## Layer 1 — Scope check (`check_scope`)
- Fast path: `_FINANCE_KEYWORDS_RE` (case-insensitive, no trailing `\b`) + `_TICKER_RE` (`[A-Z]{2,5}`, case-sensitive)
- Slow path: llama3.2 LLM classifier for ambiguous queries
- Returns 400 with `"Query out of scope: ..."` if not finance-related

## Layer 2 — Safety check (`check_text`)
- Keyword pre-screen: `_BLOCK_RE` (market manipulation, insider trading, pump-and-dump, jailbreak, etc.)
- Azure Content Safety: tries first, skips permanently after 401/disabled-subscription error (`_azure_available` flag)
- Local llama3.2 fallback: runs when Azure unavailable
- Returns 400 with `"Query blocked by content safety: ..."` for harmful content

## Layer 3 — Output safety
- Same `check_text` runs on the agent's response before returning
- Returns `"[Response withheld by content safety policy]"` if flagged

## Known behaviour
- Plural forms ("stocks", "earnings") match because trailing `\b` removed from finance keyword regex
- Azure 401 only logged once — `_azure_available = False` prevents repeated error spam
- Eval uses unique `_RUN_ID` per run to avoid stale LangGraph thread history causing 500s
