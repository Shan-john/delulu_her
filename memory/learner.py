"""
memory/learner.py — The core learning loop.

Process:
  1. Receive user text + extraction result
  2. Avoid duplicate storage
  3. Store new facts in `memories` and `knowledge`
  4. Detect and store life events
  5. Append message to conversation record
"""

from __future__ import annotations

import datetime
import uuid

from memory.database import (
    get_db,
    make_memory,
    make_knowledge,
    make_event,
    make_conversation,
    db_log,
)
from memory.extractor import Extraction
from utils.logger import get_logger

log = get_logger("learner")

# ── Session management ─────────────────────────────────────────────────────
_current_session_id: str = str(uuid.uuid4())


def get_session_id() -> str:
    return _current_session_id


def new_session() -> str:
    global _current_session_id
    _current_session_id = str(uuid.uuid4())
    _init_conversation(_current_session_id)
    return _current_session_id


# ── Core learning functions ────────────────────────────────────────────────

def learn(extraction: Extraction, user_text: str) -> int:
    """
    Persist extracted knowledge to MongoDB.
    Returns the number of new facts stored.
    """
    db = get_db()
    stored = 0

    # ── Store individual facts ─────────────────────────────────────────────
    for fact in extraction.facts:
        topic = fact["topic"]
        data  = fact["data"]

        if _fact_exists(db, topic, data):
            log.debug("Fact already known: %s → %s", topic, data)
            # Bump confidence on re-encounter
            _reinforce_memory(db, topic, data)
            continue

        mem = make_memory(
            topic=topic,
            data=data,
            source="user",
            tags=extraction.topics,
        )
        db.memories.insert_one(mem)
        log.info("🧠 Learned: [%s] %s", topic, data)
        stored += 1

        # Also store in structured knowledge collection
        _upsert_knowledge(db, topic, data)

    # ── Store life events ──────────────────────────────────────────────────
    for event_text in extraction.events:
        if not _event_exists(db, event_text):
            db.events.insert_one(make_event(
                event=event_text,
                context=user_text[:300],
                follow_up_after_hours=48,
            ))
            log.info("📅 Event stored: %s", event_text[:80])

    db_log("learner", f"Stored {stored} new facts from user input")
    return stored


def record_message(role: str, content: str, topics: list[str] | None = None) -> None:
    """
    Append a message to the current conversation record.
    Includes automatic storage management to prevent document bloat.
    """
    db = get_db()
    session = _current_session_id

    msg = {
        "role": role,
        "content": content,
        "timestamp": datetime.datetime.utcnow(),
    }

    # 1. Push new message
    db.conversations.update_one(
        {"session_id": session},
        {
            "$push": {"messages": msg},
            "$addToSet": {"topics_discussed": {"$each": topics or []}},
        },
        upsert=True,
    )

    # 2. Storage Management: Truncate history if it gets too long
    # We keep learned facts in 'memories' collection, so we don't need infinite raw history.
    conv = db.conversations.find_one({"session_id": session}, {"messages": 1})
    if conv and len(conv.get("messages", [])) > 50:
        log.debug("Truncating chat history for session %s to save storage.", session)
        # Keep last 20 messages for context
        truncated = conv["messages"][-20:]
        db.conversations.update_one(
            {"session_id": session},
            {"$set": {"messages": truncated}}
        )


def mark_event_followed_up(event_id) -> None:
    db = get_db()
    db.events.update_one({"_id": event_id}, {"$set": {"followed_up": True}})


# ── Helpers ────────────────────────────────────────────────────────────────

def _fact_exists(db, topic: str, data: str) -> bool:
    """Check if a very similar fact already exists."""
    return db.memories.count_documents({
        "topic": topic,
        "data": {"$regex": data[:30], "$options": "i"},
    }) > 0


def _reinforce_memory(db, topic: str, data: str) -> None:
    """Increase confidence on re-mentioned facts."""
    db.memories.update_one(
        {"topic": topic, "data": {"$regex": data[:30], "$options": "i"}},
        {
            "$inc": {"confidence": 0.05, "recall_count": 1},
            "$set": {"last_recalled": datetime.datetime.utcnow()},
        }
    )


def _event_exists(db, event_text: str) -> bool:
    return db.events.count_documents({
        "event": {"$regex": event_text[:40], "$options": "i"},
        "followed_up": False,
    }) > 0


def _upsert_knowledge(db, topic: str, data: str) -> None:
    """Add fact to the structured knowledge collection."""
    existing = db.knowledge.find_one({"subject": topic})
    if existing:
        db.knowledge.update_one(
            {"subject": topic},
            {"$addToSet": {"facts": data}}
        )
    else:
        db.knowledge.insert_one(make_knowledge(
            category="general",
            subject=topic,
            facts=[data],
            learned_from=_current_session_id,
        ))


def _init_conversation(session_id: str) -> None:
    db = get_db()
    if not db.conversations.find_one({"session_id": session_id}):
        db.conversations.insert_one(make_conversation(session_id))
