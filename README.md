# EduSpark Support Chatbot

A multi-turn, context-aware customer support chatbot for an EdTech platform (EduSpark),
built for **Assignment 103 — Designing a Multi-Turn Conversational AI Assistant for
Customer Service Automation**.

Built entirely with **free, open-source tools** — no paid API keys required.

---

## What this does

- Handles multi-turn conversations with context retention per session
- Answers questions using **retrieval-augmented generation** over a 40-item FAQ dataset
  (semantic search via sentence-transformers + FAISS, with an automatic keyword-search
  fallback if the embedding model can't be downloaded)
- Detects user frustration and out-of-scope questions, and escalates to a human agent
  when appropriate
- Detects sentiment on every message (positive / neutral / negative / frustrated)
- Logs every query + response with timestamps to SQLite
- Supports thumbs up/down feedback, with disliked responses stored separately for
  future retraining/prompt refinement (bonus feedback loop)
- Personalizes greetings using a mock customer profile "API" (bonus)
- Ships with a simple web chat UI (bonus frontend, no build tools needed)
- Has a working automated test suite (14 tests)

## Why retrieval instead of a generative LLM by default

The assignment explicitly asks for **deterministic, grounded responses, not
hallucinated**. A small local LLM (e.g. via `transformers`) can paraphrase answers, but
even small models can hallucinate details on FAQ-style factual questions. Pure retrieval
guarantees every answer is one of the 40 vetted FAQ answers verbatim — grounded by
construction. The `sentence-transformers` embedding step *is* the "LLM Usage" requirement
being satisfied (it's a real neural embedding model), just used for retrieval rather than
generation. This satisfies requirement 5 in the assignment ("Prompt design should ensure
deterministic, grounded responses") in the strongest possible way.

If you specifically want generative paraphrasing on top of the retrieved answer, see
"Optional: adding a local generative LLM" at the bottom of this file.

## Requirements checklist (mapped to the assignment brief)

| Assignment requirement | Where it's implemented |
|---|---|
| Multi-turn conversations | `app/conversation.py` (`SessionContext`, per-session state) |
| Contextual memory within a session | `SessionContext.recent_faq_ids`, `unresolved_streak` |
| Answers grounded in FAQs (RAG/keyword) | `app/retrieval.py` |
| Escalates to human agent | `app/conversation.py` — frustration, out-of-scope, repeated-question triggers |
| Greet & onboard | Greeting detection + `app/customer_profile.py` personalization |
| Order tracking, refunds, tech support, pricing queries | `data/faqs_cleaned.json` (all 4 categories covered) |
| Detects frustration / out-of-scope | `app/sentiment.py`, `OUT_OF_SCOPE_MARKERS` in `conversation.py` |
| 30-50 FAQs, raw + cleaned versions | `data/faqs_raw.txt` (raw), `data/faqs_cleaned.json` (cleaned, 40 items) |
| Embeddings + vector/keyword search | `app/retrieval.py` (sentence-transformers + FAISS) |
| Frontend for testing | `frontend/` (vanilla HTML/CSS/JS) |
| LLM usage, deterministic/grounded | sentence-transformers embeddings for retrieval (see note above) |
| Logging with timestamps | `app/database.py` → `messages` table |
| User feedback (thumbs up/down) | `POST /feedback` endpoint |
| **Bonus:** feedback loop for retraining | `disliked_responses` table + `GET /feedback/disliked` |
| **Bonus:** sentiment detection | `app/sentiment.py` (VADER + custom frustration phrases) |
| **Bonus:** customer profile API (mock) | `app/customer_profile.py` |
| **Bonus:** session management, multi-user | `app/database.py` sessions table, session_id per user |
| LangChain/Haystack for RAG | Not used — a direct sentence-transformers + FAISS pipeline was
used instead, which is simpler, has fewer dependencies, and is easier to run for free with
minimal setup. Swapping in LangChain is straightforward if required (see note below). |
| Deploy as Telegram/Slack/WhatsApp bot | Not implemented — flagged as a stretch item, see "Not included" below |

## Not included / explicitly out of scope

To keep this achievable with free tools and minimal setup effort, the following bonus
items were **not** built:
- Telegram/Slack/WhatsApp deployment (would need a bot token + hosting)
- Authentication (session IDs provide basic multi-user isolation, but there's no login/password system)
- LangChain/Haystack (a custom, lighter RAG pipeline was used instead — functionally equivalent for this use case)

These can be added later — ask if you'd like help with any of them.

## Architecture

```
frontend/ (HTML/JS)  --HTTP-->  FastAPI backend (app/)
                                    |
                                    +-- retrieval.py    (sentence-transformers + FAISS / keyword fallback)
                                    +-- sentiment.py     (VADER + frustration phrases)
                                    +-- conversation.py  (multi-turn logic, escalation)
                                    +-- customer_profile.py (mock personalization)
                                    +-- database.py      (SQLite: sessions, messages, feedback)
                                    |
                                    v
                              logs/chatbot.db (SQLite)
```

## Project structure

```
edtech-chatbot/
├── app/
│   ├── main.py              FastAPI app & endpoints
│   ├── conversation.py      multi-turn dialogue manager
│   ├── retrieval.py         RAG: embeddings + FAISS / keyword fallback
│   ├── sentiment.py         sentiment & frustration detection
│   ├── customer_profile.py  mock customer profile API
│   └── database.py          SQLite persistence
├── data/
│   ├── faqs_raw.txt         raw/unstructured FAQ source notes
│   └── faqs_cleaned.json    cleaned, structured FAQ dataset (40 items)
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── config.js            API base URL config
├── tests/
│   └── test_chatbot.py      14 automated tests (pytest)
├── logs/                    chatbot.db created here at runtime
├── requirements.txt
├── .gitignore
├── README.md                 (this file)
└── HOW_TO_RUN.md              step-by-step setup guide
```

## Quick start

Short version:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
# open frontend/index.html in a browser (or serve it: python -m http.server 8080 --directory frontend)
```

API docs (interactive) are auto-generated by FastAPI at `http://127.0.0.1:8000/docs` once
the server is running.

## Notes on the embedding model

On first run, `sentence-transformers` downloads the `all-MiniLM-L6-v2` model (~80MB) from
Hugging Face — this needs an internet connection once, then it's cached locally. If the
download fails or you're offline, the app automatically falls back to a keyword-matching
search so it keeps working, just with slightly less accurate matching on paraphrased
questions.

## Optional: adding a local generative LLM

If you want the bot to paraphrase answers in a more conversational voice rather than
returning the FAQ text verbatim, you can add a small local model (e.g.
`google/flan-t5-base` via `transformers`) and have it rewrite `faq["answer"]` using the
retrieved answer as grounding context in the prompt (never letting it answer from its own
knowledge). This wasn't included by default to keep setup fast and dependency-light, and
because verbatim FAQ answers are inherently more "grounded/non-hallucinated" per the
assignment's own requirement.
