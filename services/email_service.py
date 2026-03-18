"""
services/email_service.py — Background email polling.

Connects strictly via IMAP. Extracts sender and subject.
Stores important-looking emails as life events in MongoDB.
"""

from __future__ import annotations

import email
import imaplib
import threading
import time
from email.header import decode_header
from typing import Any

import schedule

import config
from memory.database import get_db, make_event, db_log
from utils.logger import get_logger

log = get_logger("email_service")

_running = False
_thread: threading.Thread | None = None


def start() -> None:
    """Start the background email checker."""
    if not config.EMAIL_ENABLED:
        log.info("Email service disabled in config.")
        return

    global _running, _thread
    _running = True
    _thread = threading.Thread(target=_loop, name="email-poller", daemon=True)
    _thread.start()
    log.info("Email service started. Polling every %dm.", config.EMAIL_CHECK_INTERVAL)


def stop() -> None:
    global _running
    _running = False


# ── Internal Loop ────────────────────────────────────────────────────────────

def _loop() -> None:
    # Schedule periodic checks
    schedule.every(config.EMAIL_CHECK_INTERVAL).minutes.do(_check_email)

    # Initial check on startup
    _check_email()

    while _running:
        schedule.run_pending()
        time.sleep(10)


def _check_email() -> None:
    """Connect to IMAP, fetch recent UNSEEN emails."""
    try:
        mail = imaplib.IMAP4_SSL(config.EMAIL_IMAP_HOST, config.EMAIL_IMAP_PORT)
        mail.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)
        mail.select("inbox")

        status, data = mail.search(None, "UNSEEN")
        if status != "OK":
            log.warning("Failed to search emails.")
            return

        mail_ids = data[0].split()
        if not mail_ids:
            log.debug("No new unread emails.")
            mail.logout()
            return

        # Fetch only maximum allowed
        mail_ids = mail_ids[-config.EMAIL_MAX_FETCH:]
        new_count = 0

        for num in mail_ids:
            status, msg_data = mail.fetch(num, "(RFC822)")
            if status == "OK" and isinstance(msg_data[0], tuple):
                msg = email.message_from_bytes(msg_data[0][1])
                _process_message(msg)
                new_count += 1

        db_log("email_service", f"Fetched {new_count} new emails.")
        mail.logout()

    except Exception as e:
        log.error("Email polling error: %s", e)


def _process_message(msg: Any) -> None:
    """Decode and store email info if it seems important."""
    subject, encoding = decode_header(msg.get("Subject", ""))[0]
    if isinstance(subject, bytes):
        subject = subject.decode(encoding or "utf-8")

    sender, encoding = decode_header(msg.get("From", ""))[0]
    if isinstance(sender, bytes):
        sender = sender.decode(encoding or "utf-8")

    log.info("New email from: %s (Subject: %s)", sender, subject)

    # Filter rules: store as an event if it contains certain keywords
    important_keywords = ["urgent", "important", "meeting", "invoice", "flight", "booking", "deadline"]
    subj_lower = subject.lower()

    is_important = any(kw in subj_lower for kw in important_keywords)

    if is_important:
        db = get_db()
        ev_text = f"User received an important email from {sender} about {subject}"

        # Insert as an event due for follow-up immediately
        db.events.insert_one(make_event(
            event=ev_text,
            context="Email",
            follow_up_after_hours=0,  # immediate follow-up
        ))
        log.info("Email flagged as important and stored as event.")
