"""
memory/database.py — MongoDB connection, schema setup, and base CRUD helpers.

Collections:
  - memories       : learned facts from user
  - knowledge      : structured domain knowledge
  - conversations  : dialogue history per session
  - events         : life events and follow-up triggers
  - internal_state : single-doc pseudo-consciousness state
  - logs           : system activity log
"""

from __future__ import annotations

import datetime
from typing import Any

import pymongo
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

import config
from utils.logger import get_logger

log = get_logger("database")

# ── Singleton connection ─────────────────────────────────────────────────────
_client: MongoClient | None = None
_db: Database | None = None


def get_db() -> Database:
    global _client, _db
    if _db is None:
        _client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)
        _db = _client[config.MONGO_DB_NAME]
        _ensure_indexes(_db)
        log.info("Connected to MongoDB: %s / %s", config.MONGO_URI, config.MONGO_DB_NAME)
    return _db


def get_collection(name: str) -> Collection:
    return get_db()[name]


# ── Index setup ──────────────────────────────────────────────────────────────
def _ensure_indexes(db: Database) -> None:
    """Create indexes on first startup (idempotent)."""
    # memories
    db.memories.create_index([("topic", pymongo.TEXT), ("data", pymongo.TEXT)])
    db.memories.create_index("recall_count")
    db.memories.create_index("created_at")

    # knowledge
    db.knowledge.create_index("category")
    db.knowledge.create_index("subject")

    # conversations
    db.conversations.create_index("session_id")
    db.conversations.create_index("created_at")

    # events
    db.events.create_index("followed_up")
    db.events.create_index("follow_up_after")

    # logs (Auto-delete after 30 days)
    try:
        # If the index exists without TTL, we must drop it first
        db.logs.drop_index("timestamp_1")
    except:
        pass
        
    db.logs.create_index([("timestamp", pymongo.ASCENDING)], expireAfterSeconds=2592000)
    db.logs.create_index("component")

    log.debug("Database indexes ensured (with 30-day log TTL).")


# ── Schema helpers: document constructors ────────────────────────────────────

def make_memory(
    topic: str,
    data: str,
    source: str = "user",
    tags: list[str] | None = None,
    related_topics: list[str] | None = None,
    confidence: float = 0.7,
) -> dict:
    return {
        "topic": topic,
        "data": data,
        "source": source,
        "confidence": confidence,
        "recall_count": 0,
        "created_at": _now(),
        "last_recalled": None,
        "tags": tags or [],
        "related_topics": related_topics or [],
    }


def make_knowledge(
    category: str,
    subject: str,
    facts: list[str],
    learned_from: str = "",
) -> dict:
    return {
        "category": category,
        "subject": subject,
        "facts": facts,
        "learned_from": learned_from,
        "verified": False,
        "created_at": _now(),
    }


def make_conversation(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "messages": [],
        "topics_discussed": [],
        "mood_during": "neutral",
        "created_at": _now(),
    }


def make_event(
    event: str,
    context: str = "",
    follow_up_after_hours: int = 48,
) -> dict:
    return {
        "event": event,
        "context": context,
        "mentioned_at": _now(),
        "follow_up_after": _now() + datetime.timedelta(hours=follow_up_after_hours),
        "followed_up": False,
        "source": "user",
    }


def make_log(
    level: str,
    component: str,
    message: str,
    data: dict | None = None,
) -> dict:
    return {
        "level": level,
        "component": component,
        "message": message,
        "data": data or {},
        "timestamp": _now(),
    }


# ── Initial internal_state document (upserted on first run) ──────────────────
DEFAULT_STATE: dict[str, Any] = {
    "_id": "current_state",
    "current_thought": f"Just woke up... where am I?",
    "curiosity_level": 0.8,
    "mood": "curious",
    "energy": 1.0,
    "last_observation": "system start",
    "last_interaction": None,
    "thoughts_generated": 0,
    "silence_start": None,
    "updated_at": None,
}


def init_internal_state() -> None:
    """Upsert the internal_state document if it doesn't exist."""
    db = get_db()
    existing = db.internal_state.find_one({"_id": "current_state"})
    if not existing:
        state = dict(DEFAULT_STATE)
        state["updated_at"] = _now()
        db.internal_state.insert_one(state)
        log.debug("Internal state initialized.")


# ── Utility ──────────────────────────────────────────────────────────────────
def _now() -> datetime.datetime:
    return datetime.datetime.utcnow()


def db_log(component: str, message: str, level: str = "info", data: dict | None = None) -> None:
    """Write a log entry to MongoDB (non-blocking fire-and-forget style)."""
    try:
        get_collection("logs").insert_one(make_log(level, component, message, data))
    except Exception:
        pass  # Never let logging crash the main loop
