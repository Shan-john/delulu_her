"""
consciousness/thought_loop.py — Continuous background thought generation.

Every 30–120 seconds (randomized), the AI:
1. Checks the environment (silence, time)
2. Picks a random memory or pending event
3. Generates a short internal thought via LLM
4. Sometimes (config.SPEAK_THOUGHT_PROB) speaks the thought aloud
5. Updates internal_state.current_thought in MongoDB
"""

from __future__ import annotations

import random
import threading
import time
from typing import Callable

import config
from consciousness.environment import get_time_context, is_silent
from consciousness.state import (
    decay_state,
    get_curiosity,
    get_mood,
    get_state,
    update_state,
)
from memory.retriever import retrieve_random_memory, retrieve_pending_followups
from utils.logger import get_logger

log = get_logger("thought_loop")

# Injected at startup by main.py to avoid circular imports
_generate_fn: Callable[[str], str] | None = None
_speak_fn: Callable[[str], None] | None = None

_running = False
_thread: threading.Thread | None = None


def start(generate_fn: Callable[[str], str], speak_fn: Callable[[str], None]) -> None:
    """Start the thought loop in a background daemon thread."""
    global _generate_fn, _speak_fn, _running, _thread
    _generate_fn = generate_fn
    _speak_fn    = speak_fn
    _running     = True

    _thread = threading.Thread(target=_loop, name="thought-loop", daemon=True)
    _thread.start()
    log.info("Thought loop started.")


def stop() -> None:
    global _running
    _running = False
    log.info("Thought loop stopping.")


# ── Main loop ────────────────────────────────────────────────────────────────

def _loop() -> None:
    while _running:
        wait = random.randint(config.THOUGHT_LOOP_MIN_SEC, config.THOUGHT_LOOP_MAX_SEC)
        log.debug("Next thought in %ds", wait)
        time.sleep(wait)

        if not _running:
            break

        try:
            _tick()
        except Exception as e:
            log.error("Thought loop error: %s", e)


def _tick() -> None:
    """One cycle of the thought loop."""
    # 1 — Decay state (simulate tiredness / boredom over time)
    decay_state()

    mood      = get_mood()
    curiosity = get_curiosity()
    time_ctx  = get_time_context()
    silent    = is_silent()

    # 2 — Choose what to think about
    subject_text, subject_origin = _pick_subject()

    # 3 — Build thought prompt
    prompt = _build_thought_prompt(
        mood=mood,
        curiosity=curiosity,
        time_context=time_ctx,
        is_silent=silent,
        subject=subject_text,
        subject_origin=subject_origin,
    )

    # 4 — Generate thought
    thought = _generate_fn(prompt) if _generate_fn else "Hmm..."
    thought = thought.strip()

    if not thought:
        return

    log.info("💭 Thought: %s", thought)

    # 5 — Update internal state
    state = get_state()
    count = state.get("thoughts_generated", 0) + 1
    update_state(current_thought=thought, thoughts_generated=count)

    # 6 — Maybe speak the thought aloud
    if random.random() < config.SPEAK_THOUGHT_PROB and _speak_fn:
        log.info("🗣️  Speaking thought aloud.")
        _speak_fn(thought)


# ── Thought prompts ──────────────────────────────────────────────────────────

def _pick_subject() -> tuple[str, str]:
    """
    Decide what to think about:
    - Pending follow-up events (highest priority)
    - Random memory
    - Generic environment observation
    """
    # Check pending follow-ups
    followups = retrieve_pending_followups()
    if followups:
        ev = followups[0]
        return (f"you were going to follow up on: {ev.get('event', '')}", "followup")

    # Try a random memory
    mem = retrieve_random_memory()
    if mem:
        return (f"{mem.get('topic', '?')}: {mem.get('data', '?')}", "memory")

    # Default environment observation
    return (f"the {get_time_context()} atmosphere", "environment")


def _build_thought_prompt(
    mood: str,
    curiosity: float,
    time_context: str,
    is_silent: bool,
    subject: str,
    subject_origin: str,
) -> str:
    env_note = "it's very quiet right now" if is_silent else "there are sounds around"

    return f"""You are {config.AI_NAME}, a curious, childlike AI companion with a playful personality.
Your current mood is: {mood}
Your curiosity level is: {curiosity:.1f} out of 1.0
It is {time_context} and {env_note}.

You are having a private internal thought about: {subject}

Generate ONE very short internal thought (1-2 sentences max).
Keep it natural, curious, slightly childlike. Use "..." for pauses.
Do not introduce yourself. Just think the thought.
"""
