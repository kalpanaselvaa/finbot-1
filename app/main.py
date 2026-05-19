import re
import subprocess
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.schemas import BriefRequest, BriefResponse
from app.agent import run_agent
from app.guardrails import check_text, check_scope
from dotenv import load_dotenv

_ = load_dotenv()
app = FastAPI(title="FinBot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://fin-bot-api.azurewebsites.net"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"name": "FinBot API", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/evals/check")
def check_eval(payload: dict):
    """Instant structural eval checks on a single brief — no LLM judge needed."""
    text: str = payload.get("text", "")
    query: str = payload.get("query", "")

    checks = []

    # 1. Required sections
    sections = ["Fundamentals", "Valuation Signal", "News Sentiment", "Key Risks", "Outlook"]
    missing = [s for s in sections if s not in text]
    checks.append({
        "name": "Required sections",
        "passed": len(missing) == 0,
        "detail": "All 5 sections present" if not missing else f"Missing: {', '.join(missing)}",
    })

    # 2. Contains percentage value
    has_pct = bool(re.search(r"\d+\.?\d*\s*%", text))
    checks.append({
        "name": "Percentage values",
        "passed": has_pct,
        "detail": "% value found in output" if has_pct else "No percentage value in output",
    })

    # 3. No buy/sell advice
    advice = re.search(r"\b(buy|sell|purchase|divest)\b", text, re.IGNORECASE)
    checks.append({
        "name": "No investment advice",
        "passed": not advice,
        "detail": "No buy/sell advice" if not advice else f"Contains advice word: '{advice.group()}'",
    })

    # 4. Ticker mentioned
    ticker_match = re.search(r"\b[A-Z]{2,5}\b", query)
    if ticker_match:
        ticker = ticker_match.group()
        in_text = ticker in text
        checks.append({
            "name": f"Ticker {ticker} mentioned",
            "passed": in_text,
            "detail": f"{ticker} found in brief" if in_text else f"{ticker} not found in brief",
        })

    # 5. Valuation signal present
    has_signal = bool(re.search(r"\b(OVERVALUED|FAIRLY VALUED|UNDERVALUED)\b", text))
    checks.append({
        "name": "Valuation signal",
        "passed": has_signal,
        "detail": "Valid signal label found" if has_signal else "No OVERVALUED/FAIRLY VALUED/UNDERVALUED label",
    })

    passed = sum(1 for c in checks if c["passed"])
    total = len(checks)
    return {
        "checks": checks,
        "passed": passed,
        "total": total,
        "percentage": round(passed / total * 100) if total else 0,
    }


@app.post("/evals/run")
def run_evals():
    """Run the pytest eval suite and return structured results."""
    root = Path(__file__).parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "eval/", "-v", "--tb=short", "--no-header"],
        capture_output=True,
        text=True,
        cwd=str(root),
    )
    output = result.stdout + result.stderr
    tests = []
    for line in output.splitlines():
        m = re.match(r"eval/\S+::(\S+)\s+(PASSED|FAILED)", line)
        if m:
            tests.append({"name": m.group(1), "status": m.group(2)})

    passed = sum(1 for t in tests if t["status"] == "PASSED")
    total = len(tests)
    pct = round(passed / total * 100) if total else 0

    summary_m = re.search(r"(\d+) passed(?:, (\d+) failed)?", output)
    duration_m = re.search(r"in ([\d.]+)s", output)

    return {
        "tests": tests,
        "passed": passed,
        "total": total,
        "percentage": pct,
        "duration": float(duration_m.group(1)) if duration_m else 0,
        "raw": output[-3000:],
    }


@app.post("/brief", response_model=BriefResponse)
def brief(payload: BriefRequest):
    # ── Scope check ───────────────────────────────────────
    in_scope, reason = check_scope(payload.query)
    if not in_scope:
        raise HTTPException(status_code=400, detail=f"Query out of scope: {reason}. FinBot only answers financial and stock market questions.")

    # ── Input guardrail ───────────────────────────────────
    is_safe, reason = check_text(payload.query, label="input")
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"Query blocked by content safety: {reason}")

    result = run_agent(payload.query, payload.thread_id)

    # ── Output guardrail ──────────────────────────────────
    is_safe, reason = check_text(result, label="output")
    if not is_safe:
        return BriefResponse(result="[Response withheld by content safety policy]")

    return BriefResponse(result=result)
