"""
memory/retriever.py — Context-aware memory retrieval from MongoDB.

Queries the memories and knowledge collections and returns
the most relevant items ranked by topic match + recency + recall frequency.
"""

from __future__ import annotations

import datetime
import re
from typing import Any

from memory.database import get_db
from utils.logger import get_logger

log = get_logger("retriever")


# ── Public API ───────────────────────────────────────────────────────────────

def retrieve_memories(query_text: str, topics: list[str], limit: int = 5) -> list[dict]:
    """
    Retrieve relevant memories from MongoDB.

    Strategy:
    1. Full-text search on the memories collection
    2. Topic-exact matching
    3. Recency + recall_count weighted scoring
    4. Return top `limit` results
    """
    db = get_db()
    results: list[dict] = []

    # 1 — Full-text search (MongoDB text index)
    try:
        text_results = list(
            db.memories.find(
                {"$text": {"$search": _build_search_string(query_text, topics)}},
                {"score": {"$meta": "textScore"}}
            )
            .sort([("score", {"$meta": "textScore"})])
            .limit(limit * 2)  # fetch more, then re-rank
        )
        results.extend(text_results)
    except Exception as e:
        log.warning("Text search failed: %s", e)

    # 2 — Topic-exact match (catches cases where text index misses)
    for topic in topics[:3]:
        topic_results = list(
            db.memories.find({"topic": {"$regex": re.escape(topic), "$options": "i"}})
            .sort("recall_count", -1)
            .limit(3)
        )
        for doc in topic_results:
            if not _already_in(doc, results):
                results.append(doc)

    # 3 — De-duplicate and score
    scored = _score_and_rank(results, topics)[:limit]

    # 4 — Reinforce recall (bump recall_count + last_recalled)
    _reinforce(db, [m["_id"] for m in scored])

    log.debug("Retrieved %d memories for topics=%s", len(scored), topics)
    return scored


def retrieve_pending_followups() -> list[dict]:
    """Return events that are due for a follow-up and not yet followed up."""
    db = get_db()
    now = datetime.datetime.utcnow()
    events = list(
        db.events.find({
            "followed_up": False,
            "follow_up_after": {"$lte": now},
        }).limit(3)
    )
    return events


def retrieve_recent_memories(n: int = 3) -> list[dict]:
    """Return the N most recently stored memories."""
    db = get_db()
    return list(db.memories.find().sort("created_at", -1).limit(n))


def retrieve_random_memory() -> dict | None:
    """Return a random memory (used by the thought loop)."""
    db = get_db()
    pipeline = [{"$sample": {"size": 1}}]
    docs = list(db.memories.aggregate(pipeline))
    return docs[0] if docs else None


# ── Internal helpers ─────────────────────────────────────────────────────────

def _build_search_string(text: str, topics: list[str]) -> str:
    """Build MongoDB text search string from user text + extracted topics."""
    parts = topics[:3] + [text[:100]]
    return " ".join(parts)


def _score_and_rank(docs: list[dict], topics: list[str]) -> list[dict]:
    """Score documents by topic match, recency, and recall frequency."""
    scored: list[tuple[float, dict]] = []
    now = datetime.datetime.utcnow()

    for doc in docs:
        score = 0.0

        # Topic match bonus
        doc_topic = (doc.get("topic") or "").lower()
        for t in topics:
            if t.lower() in doc_topic or doc_topic in t.lower():
                score += 2.0

        # Recency bonus (max 1.0 for brand-new)
        created = doc.get("created_at")
        if created:
            age_days = (now - created).total_seconds() / 86400
            score += max(0, 1.0 - age_days / 30)

        # Recall frequency bonus (frequently recalled = important)
        score += min(doc.get("recall_count", 0) * 0.1, 1.0)

        scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored]


def _already_in(doc: dict, results: list[dict]) -> bool:
    return any(r.get("_id") == doc.get("_id") for r in results)


def _reinforce(db: Any, ids: list) -> None:
    """Bump recall_count and update last_recalled for retrieved memories."""
    if not ids:
        return
    try:
        db.memories.update_many(
            {"_id": {"$in": ids}},
            {"$inc": {"recall_count": 1}, "$set": {"last_recalled": datetime.datetime.utcnow()}}
        )
    except Exception as e:
        log.warning("Reinforce failed: %s", e)
