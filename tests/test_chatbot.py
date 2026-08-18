"""
Basic test suite for the EduSpark support chatbot.
Run with: pytest tests/ -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import database

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """Use a throwaway DB file per test run so tests don't pollute real logs."""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", test_db)
    database.init_db()
    yield


def start_session(user_id=None):
    resp = client.post("/session/start", json={"user_id": user_id})
    assert resp.status_code == 200
    return resp.json()["session_id"]


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_session_start():
    session_id = start_session()
    assert session_id is not None
    assert len(session_id) > 0


def test_chat_requires_valid_session():
    resp = client.post("/chat", json={"session_id": "does-not-exist", "message": "hi"})
    assert resp.status_code == 404


def test_chat_rejects_empty_message():
    session_id = start_session()
    resp = client.post("/chat", json={"session_id": session_id, "message": "   "})
    assert resp.status_code == 400


def test_greeting_response():
    session_id = start_session()
    resp = client.post("/chat", json={"session_id": session_id, "message": "hi"})
    assert resp.status_code == 200
    data = resp.json()
    assert "eduspark" in data["reply"].lower() or "help" in data["reply"].lower()


def test_personalized_greeting_with_known_user():
    session_id = start_session(user_id="user_101")
    resp = client.post(
        "/chat", json={"session_id": session_id, "message": "hello", "user_id": "user_101"}
    )
    data = resp.json()
    assert "Aditi" in data["reply"]


def test_faq_retrieval_refund():
    session_id = start_session()
    resp = client.post(
        "/chat", json={"session_id": session_id, "message": "what is your refund policy"}
    )
    data = resp.json()
    assert data["matched_faq_id"] is not None
    assert "refund" in data["reply"].lower()
    assert data["escalated"] is False


def test_faq_retrieval_pricing():
    session_id = start_session()
    resp = client.post(
        "/chat", json={"session_id": session_id, "message": "how much does pro cost"}
    )
    data = resp.json()
    assert data["matched_faq_id"] is not None


def test_out_of_scope_detection():
    session_id = start_session()
    resp = client.post(
        "/chat", json={"session_id": session_id, "message": "what is the weather today"}
    )
    data = resp.json()
    assert data["matched_faq_id"] is None
    assert data["escalated"] is False


def test_frustration_triggers_escalation():
    session_id = start_session()
    resp = client.post(
        "/chat",
        json={"session_id": session_id, "message": "this is ridiculous, worst platform ever"},
    )
    data = resp.json()
    assert data["escalated"] is True
    assert data["sentiment"]["is_frustrated"] is True


def test_repeated_question_escalates():
    session_id = start_session()
    last = None
    for _ in range(4):
        resp = client.post(
            "/chat", json={"session_id": session_id, "message": "how much does pro cost"}
        )
        last = resp.json()
    assert last["escalated"] is True


def test_feedback_thumbs_down_stored():
    session_id = start_session()
    resp = client.post(
        "/chat", json={"session_id": session_id, "message": "what is your refund policy"}
    )
    message_id = resp.json()["message_id"]

    fb_resp = client.post(
        "/feedback",
        json={
            "message_id": message_id,
            "session_id": session_id,
            "rating": "down",
            "comment": "not clear enough",
        },
    )
    assert fb_resp.status_code == 200

    disliked = client.get("/feedback/disliked").json()
    assert any(d["message_id"] == message_id for d in disliked)


def test_feedback_invalid_rating_rejected():
    session_id = start_session()
    resp = client.post(
        "/chat", json={"session_id": session_id, "message": "hi"}
    )
    message_id = resp.json()["message_id"]
    fb_resp = client.post(
        "/feedback",
        json={"message_id": message_id, "session_id": session_id, "rating": "sideways"},
    )
    assert fb_resp.status_code == 400


def test_session_history_returns_messages():
    session_id = start_session()
    client.post("/chat", json={"session_id": session_id, "message": "hi"})
    client.post("/chat", json={"session_id": session_id, "message": "what is your refund policy"})
    history = client.get(f"/history/{session_id}").json()
    assert len(history) == 4  # 2 user + 2 bot
