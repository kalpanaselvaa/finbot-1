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
