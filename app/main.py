"""
EduSpark Support Chatbot - FastAPI backend.

Endpoints:
  POST /session/start        -> create a new chat session (session mgmt)
  POST /chat                 -> send a message, get bot reply (multi-turn, context-aware)
  POST /feedback              -> thumbs up/down or text feedback on a bot message
  GET  /history/{session_id} -> retrieve full conversation for a session
  GET  /logs                 -> all logged conversations (admin/debug)
  GET  /feedback/disliked    -> disliked responses queue (bonus: retraining feedback loop)
  GET  /health                -> health check
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import database
from app.conversation import handle_message
from app.retrieval import get_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    get_engine()  # warm up embedding model / index at startup, not on first request
    yield


app = FastAPI(
    title="EduSpark Support Chatbot API",
    description="Multi-turn, RAG-based customer support chatbot for an EdTech platform.",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow the simple frontend (opened as a local file or served separately) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Schemas ----------

class SessionStartRequest(BaseModel):
    user_id: str | None = None


class SessionStartResponse(BaseModel):
    session_id: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    user_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    message_id: str
    matched_faq_id: int | None
    similarity_score: float | None
    sentiment: dict
    escalated: bool


class FeedbackRequest(BaseModel):
    message_id: str
    session_id: str
    rating: str  # "up" or "down"
    comment: str | None = None


# ---------- Endpoints ----------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/session/start", response_model=SessionStartResponse)
def start_session(req: SessionStartRequest):
    session_id = database.create_session(user_id=req.user_id)
    return {"session_id": session_id}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not database.session_exists(req.session_id):
        raise HTTPException(status_code=404, detail="Session not found. Start a new session first.")
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    result = handle_message(req.session_id, req.message, user_id=req.user_id)
    return result


@app.post("/feedback")
def feedback(req: FeedbackRequest):
    if req.rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="rating must be 'up' or 'down'")
    feedback_id = database.save_feedback(
        message_id=req.message_id,
        session_id=req.session_id,
        rating=req.rating,
        comment=req.comment,
    )
    return {"feedback_id": feedback_id, "status": "recorded"}


@app.get("/history/{session_id}")
def history(session_id: str):
    if not database.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")
    return database.get_session_history(session_id)


@app.get("/logs")
def logs():
    return database.get_all_logs()


@app.get("/feedback/disliked")
def disliked():
    return database.get_disliked_responses()
