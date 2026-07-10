import logging
import os
import uuid

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from langgraph.types import Command
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.graph.builder import nexus_graph
from app.auth.dependencies import get_current_user
from app.auth.routes import router as auth_router
from app.db.database import get_db, Base, engine
from app.db.models import User, Interview
from app.models.rate_limiter import GroqRateLimitError
from app.api.schemas import (
    StartInterviewRequest,
    StartInterviewResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    ReportResponse,
    InterviewSummary,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("nexus")

# Creates the users/interviews tables if they don't exist yet. Idempotent --
# safe to run on every startup.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="NEXUS - AI Interview Prep Agent")
app.include_router(auth_router)


@app.on_event("startup")
def warm_up_models():
    """
    Loads the embedding + reranker models into memory once, at server
    startup, instead of on whichever user's request happens to hit them
    first. Without this, the very first start_interview call after a
    (re)deploy eats the full model-load time (can be 10-30+ seconds) --
    every request after that is fast because the models stay cached in
    memory, but nobody wants to be the unlucky first click.
    """
    from app.rag.retriever import get_embedder, get_reranker

    logger.info("Warming up embedding + reranker models...")
    get_embedder()
    get_reranker()
    logger.info("Models loaded, ready to serve requests.")

    # $PORT is set by Render (and similar PaaS) -- when it's absent, this is
    # a local run (docker-compose or bare uvicorn) where "localhost" is the
    # correct, clickable address. On Render, the real URL is the one shown
    # in its dashboard, not localhost, so skip the hint there.
    if not os.getenv("PORT"):
        local_port = os.getenv("UVICORN_PORT", "8000")
        logger.info("=" * 60)
        logger.info("NEXUS is ready -- open this in your browser:")
        logger.info(f"  http://localhost:{local_port}")
        logger.info("=" * 60)


@app.exception_handler(Exception)
def unhandled_exception_handler(request: Request, exc: Exception):
    """Log the real error server-side; never leak internals to the client."""
    logger.exception(f"Unhandled error on {request.method} {request.url.path}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """Liveness/readiness check for the deployment platform. Verifies the
    app can actually reach Postgres, not just that the process is up."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        logger.exception("Health check DB probe failed")
        return JSONResponse(status_code=503, content={"status": "db_unreachable"})


# --- Rate limiting (per client IP) ---
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(GroqRateLimitError)
def groq_rate_limit_handler(request: Request, exc: GroqRateLimitError):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=429, content={"detail": str(exc)})


def _get_owned_interview(thread_id: str, current_user: User, db: Session) -> Interview:
    """Looks up an interview by thread_id and verifies it belongs to the
    requesting user. Returns 404 (not 403) on mismatch so we don't confirm
    to a caller that a given thread_id exists at all."""
    interview = db.query(Interview).filter(Interview.thread_id == thread_id).first()
    if interview is None or interview.user_id != current_user.id:
        raise HTTPException(404, "No interview found for this thread_id.")
    return interview


@app.post("/start_interview", response_model=StartInterviewResponse)
@limiter.limit("10/minute")
def start_interview(
    request: Request,
    req: StartInterviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "topic": req.topic,
        "difficulty": req.difficulty,
        "max_questions": req.max_questions,
        "question_number": 0,
        "is_complete": False,
        "conversation_history": [],
        "weak_areas": [],
    }

    # Runs until it hits the interrupt() inside await_answer_node
    nexus_graph.invoke(initial_state, config=config)

    interrupt_payload = _get_interrupt_payload(config)
    if interrupt_payload is None:
        raise HTTPException(500, "Graph did not pause at await_answer as expected.")

    db.add(
        Interview(
            user_id=current_user.id,
            thread_id=thread_id,
            topic=req.topic,
            difficulty=req.difficulty,
            is_complete=False,
        )
    )
    db.commit()
    logger.info(f"Interview started: user={current_user.email} topic={req.topic} thread={thread_id}")

    return StartInterviewResponse(
        thread_id=thread_id,
        question_number=interrupt_payload["question_number"],
        question=interrupt_payload["question"],
    )


@app.post("/submit_answer", response_model=SubmitAnswerResponse)
@limiter.limit("20/minute")
def submit_answer(
    request: Request,
    req: SubmitAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    interview = _get_owned_interview(req.thread_id, current_user, db)
    config = {"configurable": {"thread_id": req.thread_id}}

    # Resumes the paused graph, feeding the candidate's answer into interrupt()
    nexus_graph.invoke(Command(resume=req.answer), config=config)

    state = nexus_graph.get_state(config).values

    if state.get("is_complete"):
        interview.is_complete = True
        db.commit()
        logger.info(f"Interview completed: user={current_user.email} thread={req.thread_id}")
        return SubmitAnswerResponse(is_complete=True)

    interrupt_payload = _get_interrupt_payload(config)
    if interrupt_payload is None:
        raise HTTPException(500, "Graph did not pause at await_answer as expected.")

    last_turn = state["conversation_history"][-1] if state.get("conversation_history") else None

    return SubmitAnswerResponse(
        is_complete=False,
        question_number=interrupt_payload["question_number"],
        question=interrupt_payload["question"],
        last_score=last_turn["score"] if last_turn else None,
        last_feedback=last_turn["feedback"] if last_turn else None,
    )


@app.get("/get_report", response_model=ReportResponse)
@limiter.limit("30/minute")
def get_report(
    request: Request,
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_interview(thread_id, current_user, db)  # ownership check
    config = {"configurable": {"thread_id": thread_id}}
    state = nexus_graph.get_state(config).values

    if not state:
        raise HTTPException(404, "No interview found for this thread_id.")

    return ReportResponse(
        thread_id=thread_id,
        is_complete=state.get("is_complete", False),
        report=state.get("final_report") if state.get("is_complete") else None,
    )


@app.get("/interviews", response_model=list[InterviewSummary])
def list_interviews(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Per-user interview history -- what makes multi-user actually useful."""
    interviews = (
        db.query(Interview)
        .filter(Interview.user_id == current_user.id)
        .order_by(Interview.created_at.desc())
        .all()
    )
    return [
        InterviewSummary(
            thread_id=i.thread_id,
            topic=i.topic,
            difficulty=i.difficulty,
            is_complete=i.is_complete,
            created_at=i.created_at.isoformat(),
        )
        for i in interviews
    ]


def _get_interrupt_payload(config: dict) -> dict | None:
    """
    Reads the pending interrupt (if any) off the checkpointed state's tasks.
    This works across langgraph versions -- unlike checking for an
    '__interrupt__' key on invoke()'s return value, which only some
    versions populate.
    """
    state = nexus_graph.get_state(config)
    for task in state.tasks:
        if task.interrupts:
            return task.interrupts[0].value
    return None


# Serves the interview console UI at "/". Mounted last so it never shadows
# the API routes above (StaticFiles only handles paths nothing else matched).
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
