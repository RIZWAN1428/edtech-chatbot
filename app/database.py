"""
SQLite persistence layer.

Handles:
- sessions (multi-user session management)
- conversation logs (query + response + timestamp + sentiment + escalation flag)
- feedback (thumbs up/down or text, tied to a specific bot response)
- disliked responses queue (bonus: feedback loop for retraining/prompt refinement)
"""

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "logs" / "chatbot.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,              -- 'user' or 'bot'
                text TEXT NOT NULL,
                matched_faq_id INTEGER,
                similarity_score REAL,
                sentiment_label TEXT,
                escalated INTEGER DEFAULT 0,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );

            CREATE TABLE IF NOT EXISTS feedback (
                feedback_id TEXT PRIMARY KEY,
                message_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                rating TEXT,                     -- 'up' or 'down'
                comment TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (message_id) REFERENCES messages(message_id)
            );

            CREATE TABLE IF NOT EXISTS disliked_responses (
                id TEXT PRIMARY KEY,
                message_id TEXT NOT NULL,
                user_query TEXT NOT NULL,
                bot_response TEXT NOT NULL,
                comment TEXT,
                timestamp TEXT NOT NULL
            );
            """
        )


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def create_session(user_id: str | None = None) -> str:
    session_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, user_id, created_at) VALUES (?, ?, ?)",
            (session_id, user_id, datetime.now(timezone.utc).isoformat()),
        )
    return session_id


def session_exists(session_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return row is not None


def log_message(
    session_id: str,
    role: str,
    text: str,
    matched_faq_id: int | None = None,
    similarity_score: float | None = None,
    sentiment_label: str | None = None,
    escalated: bool = False,
) -> str:
    message_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO messages
               (message_id, session_id, role, text, matched_faq_id, similarity_score,
                sentiment_label, escalated, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                message_id,
                session_id,
                role,
                text,
                matched_faq_id,
                similarity_score,
                sentiment_label,
                int(escalated),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    return message_id


def get_session_history(session_id: str, limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM messages WHERE session_id = ?
               ORDER BY timestamp ASC LIMIT ?""",
            (session_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def save_feedback(message_id: str, session_id: str, rating: str, comment: str | None = None) -> str:
    feedback_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO feedback (feedback_id, message_id, session_id, rating, comment, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (feedback_id, message_id, session_id, rating, comment, datetime.now(timezone.utc).isoformat()),
        )

        # Bonus: feedback loop - store disliked responses for retraining/prompt refinement
        if rating == "down":
            msg_row = conn.execute(
                "SELECT text FROM messages WHERE message_id = ?", (message_id,)
            ).fetchone()
            # find the preceding user message in the same session
            user_row = conn.execute(
                """SELECT text FROM messages WHERE session_id = ? AND role = 'user'
                   AND timestamp < (SELECT timestamp FROM messages WHERE message_id = ?)
                   ORDER BY timestamp DESC LIMIT 1""",
                (session_id, message_id),
            ).fetchone()
            conn.execute(
                """INSERT INTO disliked_responses (id, message_id, user_query, bot_response, comment, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    message_id,
                    user_row["text"] if user_row else "",
                    msg_row["text"] if msg_row else "",
                    comment,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
    return feedback_id


def get_disliked_responses() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM disliked_responses ORDER BY timestamp DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_logs() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages ORDER BY timestamp ASC"
        ).fetchall()
        return [dict(r) for r in rows]
