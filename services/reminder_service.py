"""
services/reminder_service.py — Background reminder checker.

Periodically queries MongoDB `events` collection for pending follow-ups.
When found, generates a reminder thought and speaks it.
"""

from __future__ import annotations

import datetime
import threading
import time
from typing import Callable

import schedule

import config
from memory.database import get_db, db_log
from utils.logger import get_logger

log = get_logger("reminder_service")

_running = False
_thread: threading.Thread | None = None
_speak_fn: Callable[[str], None] | None = None


def start(speak_fn: Callable[[str], None]) -> None:
    """Start the background reminder checker."""
    global _running, _thread, _speak_fn
    _speak_fn = speak_fn
    _running = True
    _thread = threading.Thread(target=_loop, name="reminder-checker", daemon=True)
    _thread.start()
    log.info("Reminder service started. Checking every 5m.")


def stop() -> None:
    global _running
    _running = False


def _loop() -> None:
    schedule.every(5).minutes.do(_check_reminders)

    while _running:
        schedule.run_pending()
        time.sleep(10)


def _check_reminders() -> None:
    """Find due events, mark as followed_up, and trigger a spoken reminder."""
    db = get_db()
    now = datetime.datetime.utcnow()

    due_events = list(db.events.find({
        "followed_up": False,
        "follow_up_after": {"$lte": now},
    }).limit(1))

    if not due_events:
        return

    ev = due_events[0]
    ev_id = ev["_id"]
    event_text = ev.get("event", "something")

    log.info("🔔 Reminder triggered for event: %s", event_text)

    # Mark as followed up so we don't repeat it endlessly
    db.events.update_one({"_id": ev_id}, {"$set": {"followed_up": True}})
    db_log("reminder_service", f"Followed up on event: {event_text}")

    # Speak it aloud via TTS
    if _speak_fn:
        msg = f"Oh, wait! I just remembered... {event_text}. Did you want me to remind you?"
        _speak_fn(msg)

    # Optional: could also push it to internal_thought queue
