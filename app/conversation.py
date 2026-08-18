"""
Conversation manager: multi-turn context, escalation, out-of-scope detection.

Design choice: rather than a generative LLM (which risks hallucination),
responses are grounded strictly in the FAQ dataset via retrieval. This
directly satisfies the assignment's "deterministic, grounded responses,
not hallucinated" requirement. A local LLM could be swapped in later for
paraphrasing (see LLM_MODE flag) but is off by default to keep the demo
fast and dependency-light.
"""

from dataclasses import dataclass, field

from app import database
from app.retrieval import get_engine
from app.sentiment import analyze_sentiment

OUT_OF_SCOPE_MARKERS = [
    "weather",
    "stock price",
    "recipe",
    "movie",
    "cricket score",
    "election",
    "capital of",
    "who is the prime minister",
    "write me a poem",
    "translate this",
]

REPEATED_QUESTION_THRESHOLD = 3  # same/similar question asked this many times => escalate

GREETING_WORDS = {"hi", "hello", "hey", "hii", "helo", "good morning", "good evening"}


@dataclass
class SessionContext:
    session_id: str
    recent_faq_ids: list[int] = field(default_factory=list)
    unresolved_streak: int = 0  # consecutive turns with no good match


_session_contexts: dict[str, SessionContext] = {}


def _get_context(session_id: str) -> SessionContext:
    if session_id not in _session_contexts:
        _session_contexts[session_id] = SessionContext(session_id=session_id)
    return _session_contexts[session_id]


def _is_greeting(text: str) -> bool:
    t = text.strip().lower()
    return t in GREETING_WORDS or any(t.startswith(g) for g in GREETING_WORDS)


def _looks_out_of_scope(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in OUT_OF_SCOPE_MARKERS)


def handle_message(session_id: str, user_text: str, user_id: str | None = None) -> dict:
    """
    Main entry point. Returns a dict with the bot's reply plus metadata
    (used both for the API response and for logging).
    """
    ctx = _get_context(session_id)
    engine = get_engine()

    sentiment = analyze_sentiment(user_text)

    # Log the user's message first
    database.log_message(
        session_id=session_id,
        role="user",
        text=user_text,
        sentiment_label=sentiment["label"],
    )

    escalated = False
    matched_faq_id = None
    similarity_score = None

    # 1. Greeting
    if _is_greeting(user_text):
        from app.customer_profile import personalize_greeting

        reply = personalize_greeting(user_id)
        ctx.unresolved_streak = 0

    # 2. Explicit human agent request or strong frustration
    elif sentiment["is_frustrated"]:
        reply = (
            "I'm sorry this has been frustrating. I'm connecting you with a human "
            "support agent who can help further. Our team is available 9am-9pm IST "
            "and typically responds within a few minutes during chat hours."
        )
        escalated = True
        ctx.unresolved_streak = 0

    # 3. Out-of-scope
    elif _looks_out_of_scope(user_text):
        reply = (
            "That's a bit outside what I can help with here — I'm focused on EduSpark "
            "account, course, billing, and technical support questions. Is there "
            "something in that area I can help you with?"
        )
        ctx.unresolved_streak = 0

    # 4. Retrieval-based FAQ answer
    else:
        match = engine.best_match(user_text)
        if match is None:
            ctx.unresolved_streak += 1
            if ctx.unresolved_streak >= REPEATED_QUESTION_THRESHOLD:
                reply = (
                    "I'm having trouble understanding your question after a few tries. "
                    "Let me connect you with a human agent who can help directly."
                )
                escalated = True
                ctx.unresolved_streak = 0
            else:
                reply = (
                    "I'm not fully sure I understood that. Could you rephrase, or ask "
                    "about things like account setup, course enrollment, refunds, "
                    "technical issues, or pricing? I can also connect you with a human "
                    "agent if you'd prefer."
                )
        else:
            faq = match["faq"]
            similarity_score = match["score"]
            matched_faq_id = faq["id"]

            # detect repeated question (context retention across turns)
            if faq["id"] in ctx.recent_faq_ids:
                ctx.unresolved_streak += 1
            else:
                ctx.unresolved_streak = 0
            ctx.recent_faq_ids.append(faq["id"])
            ctx.recent_faq_ids = ctx.recent_faq_ids[-5:]

            if ctx.unresolved_streak >= REPEATED_QUESTION_THRESHOLD:
                reply = (
                    "It looks like this might not be fully resolving your question. "
                    "Let me connect you with a human agent for more personalized help."
                )
                escalated = True
                ctx.unresolved_streak = 0
            else:
                reply = faq["answer"]

    bot_message_id = database.log_message(
        session_id=session_id,
        role="bot",
        text=reply,
        matched_faq_id=matched_faq_id,
        similarity_score=similarity_score,
        sentiment_label=sentiment["label"],
        escalated=escalated,
    )

    return {
        "reply": reply,
        "message_id": bot_message_id,
        "matched_faq_id": matched_faq_id,
        "similarity_score": similarity_score,
        "sentiment": sentiment,
        "escalated": escalated,
    }
