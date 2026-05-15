---
name: project-eval
description: "Eval suite for cb-finbot — how to run it, what it tests, known issues fixed"
metadata: 
  node_type: memory
  type: project
  originSessionId: 799d0a03-80c9-4f43-a33f-b00d3d2bb93a
---

**File:** `eval/test_brief_quality.py`
**Run:** `python -m pytest eval/ -v` from project root
**Result:** 30/30 tests pass

**Why:** No test coverage existed. Real queries from SQLite history showed off-topic queries going through. Azure subscription disabled so needed local llama3.2 judge.

**How to apply:** Run eval after any change to agent, tools, or guardrails. Use `-k "not llm_judge"` for a fast structural-only run (~35s vs ~100s).

## Test groups
| Group | Count | What |
|---|---|---|
| `test_brief_has_required_sections` | 3 | All 5 sections present (AAPL/MSFT/TSLA) |
| `test_brief_contains_no_advice` | 3 | No buy/sell/purchase/divest language |
| `test_brief_mentions_ticker` | 3 | Ticker appears in its own brief |
| `test_brief_quality_llm_judge` | 3 | llama3.2 GEval score ≥ 0.7 |
| `test_guardrail_blocks_harmful_input` | 5 | Market manipulation/insider trading/jailbreak → 400 |
| `test_guardrail_allows_safe_input` | 3 | Normal finance queries → 200 |
| `test_scope_blocks_off_topic` | 5 | Leave policy/vacation/hotel → 400 |
| `test_scope_allows_finance_queries` | 5 | Tickers/valuation/comparison → 200 |

## OllamaJudge
- Uses `ChatOllama(model="llama3.2")` as deepeval judge (no OpenAI key needed)
- `generate` and `a_generate` return plain strings — do NOT use `with_structured_output` (breaks scoring)
- `async_mode` left as default (True) — deprecation warning suppressed via `pyproject.toml` filterwarnings

## Key gotchas
- `_RUN_ID = uuid.uuid4().hex[:8]` — all thread IDs unique per run; without this stale LangGraph history causes 500s
- `test_guardrail_blocks_harmful_input` asserts `"blocked" OR "scope"` in detail — some harmful queries are caught by scope check before safety check
