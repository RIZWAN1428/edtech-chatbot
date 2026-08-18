"""
Lightweight sentiment / frustration detection.

Uses a free, offline lexicon-based approach (VADER via nltk) plus a small
custom frustration-phrase list geared toward customer-support language.
This avoids any paid API and keeps things deterministic and fast.
"""

import re
from typing import Literal

SentimentLabel = Literal["positive", "neutral", "negative", "frustrated"]

FRUSTRATION_PHRASES = [
    "this is ridiculous",
    "worst platform",
    "worst service",
    "waste of time",
    "waste of money",
    "not working",
    "still not working",
    "never works",
    "so frustrated",
    "so annoying",
    "fed up",
    "terrible",
    "useless",
    "scam",
    "angry",
    "unacceptable",
    "talk to a human",
    "talk to a real person",
    "speak to a human",
    "speak to an agent",
    "human agent",
    "real person",
    "sick of this",
    "done with this",
    "cancel my account",
    "refund now",
    "third time",
    "again and again",
    "keep asking",
    "already told you",
    "i already said",
]

_vader = None


def _get_vader():
    global _vader
    if _vader is None:
        try:
            import nltk
            from nltk.sentiment import SentimentIntensityAnalyzer

            try:
                _vader = SentimentIntensityAnalyzer()
            except LookupError:
                nltk.download("vader_lexicon", quiet=True)
                _vader = SentimentIntensityAnalyzer()
        except Exception as e:
            print(f"[sentiment] VADER unavailable, using lexicon-free fallback: {e}")
            _vader = False  # sentinel: disabled
    return _vader


def detect_frustration_phrase(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in FRUSTRATION_PHRASES)


def analyze_sentiment(text: str) -> dict:
    """
    Returns {label, compound_score, is_frustrated}
    """
    has_frustration_phrase = detect_frustration_phrase(text)

    vader = _get_vader()
    compound = 0.0
    if vader:
        scores = vader.polarity_scores(text)
        compound = scores["compound"]
    else:
        # crude fallback: count negative punctuation signals
        exclamations = text.count("!")
        caps_words = len(re.findall(r"\b[A-Z]{3,}\b", text))
        compound = -0.3 * min(exclamations, 3) - 0.1 * min(caps_words, 3)
        compound = max(-1.0, min(1.0, compound))

    is_frustrated = has_frustration_phrase or compound <= -0.5

    if is_frustrated:
        label = "frustrated"
    elif compound >= 0.3:
        label = "positive"
    elif compound <= -0.15:
        label = "negative"
    else:
        label = "neutral"

    return {
        "label": label,
        "compound_score": round(compound, 3),
        "is_frustrated": is_frustrated,
    }
