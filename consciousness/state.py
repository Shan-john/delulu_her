"""
consciousness/state.py — Internal pseudo-consciousness state manager.

Maintains a single document in MongoDB `internal_state` collection.
Provides read/write access to mood, curiosity, energy, and current_thought.
"""

from __future__ import annotations

import datetime
import math

import config
from memory.database import get_db, init_internal_state
from utils.logger import get_logger

log = get_logger("state")

_STATE_ID = "current_state"

# ── Mood transition table ────────────────────────────────────────────────────
# (current_mood, trigger) → new_mood
_MOOD_TRANSITIONS: dict[tuple[str, str], str] = {
    ("curious",  "long_silence"):    "bored",
    ("bored",    "user_spoke"):      "excited",
    ("excited",  "user_quiet"):      "curious",
    ("playful",  "long_silence"):    "thoughtful",
    ("thoughtful","user_spoke"):     "curious",
    ("neutral",  "user_spoke"):      "curious",
    ("curious",  "learned_something"): "excited",
    ("excited",  "learned_something"): "playful",
}

def _mood_change(current: str, trigger: str) -> str:
    return _MOOD_TRANSITIONS.get((current, trigger), current)


# ── Read / Write ─────────────────────────────────────────────────────────────

def get_state() -> dict:
    """Return the current internal state document."""
    init_internal_state()
    doc = get_db().internal_state.find_one({"_id": _STATE_ID}) or {}
    return doc


def update_state(**kwargs) -> None:
    """Partially update internal state fields."""
    kwargs["updated_at"] = datetime.datetime.utcnow()
    get_db().internal_state.update_one(
        {"_id": _STATE_ID},
        {"$set": kwargs},
        upsert=True,
    )


def get_mood() -> str:
    return get_state().get("mood", "curious")


def get_curiosity() -> float:
    return float(get_state().get("curiosity_level", 0.7))


def get_current_thought() -> str:
    return get_state().get("current_thought", "...")


def record_interaction() -> None:
    """Called every time the user speaks — resets silence timer, boosts energy."""
    state = get_state()
    new_mood = _mood_change(state.get("mood", "neutral"), "user_spoke")
    update_state(
        last_interaction=datetime.datetime.utcnow(),
        silence_start=None,
        energy=min(1.0, float(state.get("energy", 0.8)) + 0.1),
        mood=new_mood,
        curiosity_level=min(1.0, float(state.get("curiosity_level", 0.7)) + 0.15),
    )


def record_silence_start() -> None:
    """Called when speech stops — mark silence start."""
    state = get_state()
    if not state.get("silence_start"):
        update_state(silence_start=datetime.datetime.utcnow())


def on_learned_something() -> None:
    """Boost curiosity when a new fact is stored."""
    state = get_state()
    new_mood = _mood_change(state.get("mood", "neutral"), "learned_something")
    update_state(
        curiosity_level=min(1.0, float(state.get("curiosity_level", 0.7)) + 0.2),
        mood=new_mood,
    )


def decay_state() -> None:
    """
    Called periodically to decay curiosity and energy over time.
    Simulates the AI 'getting bored' during long silences.
    """
    state = get_state()
    cur = float(state.get("curiosity_level", 0.7))
    nrg = float(state.get("energy", 0.8))
    mood = state.get("mood", "curious")

    new_cur = max(0.1, cur - config.CURIOSITY_DECAY)
    new_nrg = max(0.1, nrg - 0.02)

    # If silence has been long, shift mood
    silence_start = state.get("silence_start")
    if silence_start:
        silence_min = (datetime.datetime.utcnow() - silence_start).total_seconds() / 60
        if silence_min > 5:
            mood = _mood_change(mood, "long_silence")

    update_state(
        curiosity_level=new_cur,
        energy=new_nrg,
        mood=mood,
    )
    log.debug("State decay — curiosity=%.2f energy=%.2f mood=%s", new_cur, new_nrg, mood)


def get_silence_duration_sec() -> float:
    """Return how many seconds the environment has been silent."""
    state = get_state()
    silence_start = state.get("silence_start")
    if not silence_start:
        return 0.0
    return (datetime.datetime.utcnow() - silence_start).total_seconds()
