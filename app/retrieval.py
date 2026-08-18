"""
Retrieval engine for the EduSpark support chatbot.

Uses sentence-transformers to embed FAQ questions and FAISS for fast
similarity search. This is the "RAG" core: given a user query, we find the
most semantically similar FAQ(s) and return their grounded answers.

Falls back gracefully to keyword matching if the embedding model can't be
loaded (e.g. no internet on first run to download the model).
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

import numpy as np

DATA_PATH = Path(__file__).parent.parent / "data" / "faqs_cleaned.json"
MODEL_NAME = "all-MiniLM-L6-v2"  # small, fast, free, ~80MB
SIMILARITY_THRESHOLD = 0.45  # below this => "I don't know" / escalate (embedding mode)
KEYWORD_THRESHOLD = 0.25  # separate, lower threshold for the keyword fallback mode


class RetrievalEngine:
    def __init__(self, data_path: Path = DATA_PATH):
        with open(data_path, "r", encoding="utf-8") as f:
            self.faqs = json.load(f)

        self.corpus_texts = [
            f"{faq['question']} {' '.join(faq['keywords'])}" for faq in self.faqs
        ]

        self.mode = "embedding"
        self.model = None
        self.index = None

        try:
            self._init_embedding_index()
        except Exception as e:
            print(f"[retrieval] Falling back to keyword search. Reason: {e}")
            self.mode = "keyword"

    def _init_embedding_index(self):
        from sentence_transformers import SentenceTransformer
        import faiss

        self.model = SentenceTransformer(MODEL_NAME)
        embeddings = self.model.encode(
            self.corpus_texts, convert_to_numpy=True, normalize_embeddings=True
        )
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)  # inner product on normalized = cosine sim
        self.index.add(embeddings.astype(np.float32))

    STOPWORDS = {
        "the", "a", "an", "is", "are", "do", "does", "did", "i", "my", "me",
        "to", "for", "of", "on", "in", "how", "what", "can", "you", "your",
        "it", "this", "that", "and", "or", "please", "with", "was", "will",
        "am", "be", "have", "has", "get", "got",
    }

    def _keyword_search(self, query: str, top_k: int = 3):
        raw_words = re.findall(r"\w+", query.lower())
        query_words = set(w for w in raw_words if w not in self.STOPWORDS) or set(raw_words)

        scored = []
        for faq in self.faqs:
            # keyword phrases matter more than loose word overlap -- check phrase containment first
            lowered_query = " " + query.lower() + " "
            phrase_hits = sum(
                1 for kw in faq["keywords"] if f" {kw.lower()} " in lowered_query or kw.lower() in query.lower()
            )

            haystack_words = set(
                re.findall(r"\w+", (faq["question"] + " " + " ".join(faq["keywords"])).lower())
            )
            haystack_words -= self.STOPWORDS
            overlap = len(query_words & haystack_words)

            score = phrase_hits * 0.6 + (overlap / max(len(query_words), 1)) * 0.4
            if phrase_hits > 0 or overlap > 0:
                scored.append((score, faq))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [(faq, min(score, 1.0)) for score, faq in scored[:top_k]]

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Returns a list of {faq, score} dicts, best match first.
        Score is a similarity value roughly in [0, 1].
        """
        if self.mode == "embedding":
            query_emb = self.model.encode(
                [query], convert_to_numpy=True, normalize_embeddings=True
            ).astype(np.float32)
            scores, idxs = self.index.search(query_emb, top_k)
            results = []
            for score, idx in zip(scores[0], idxs[0]):
                if idx == -1:
                    continue
                results.append({"faq": self.faqs[idx], "score": float(score)})
            return results
        else:
            results = self._keyword_search(query, top_k)
            return [{"faq": faq, "score": score} for faq, score in results]

    def best_match(self, query: str) -> Optional[dict]:
        results = self.search(query, top_k=1)
        if not results:
            return None
        top = results[0]
        threshold = SIMILARITY_THRESHOLD if self.mode == "embedding" else KEYWORD_THRESHOLD
        if top["score"] < threshold:
            return None
        return top


# Singleton, loaded once at app startup
_engine: Optional[RetrievalEngine] = None


def get_engine() -> RetrievalEngine:
    global _engine
    if _engine is None:
        _engine = RetrievalEngine()
    return _engine
