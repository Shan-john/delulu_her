"""
consciousness/environment.py — Ambient environment awareness.

Monitors:
- Audio energy level (silence vs. noise)
- Time of day context
- Sudden sound spikes (bang, clap, etc.)
"""

from __future__ import annotations

import datetime
import threading
from collections import deque
from typing import Callable

import numpy as np

import config
from utils.logger import get_logger

log = get_logger("environment")

# Rolling window of recent audio energy values (last 5 seconds of chunks)
_energy_window: deque = deque(maxlen=int(5 / config.AUDIO_CHUNK_DURATION))
_is_silent: bool = True
_sound_spike_callbacks: list[Callable] = []
_lock = threading.Lock()


def push_audio_energy(rms: float) -> None:
    """
    Called by the audio capture loop with each chunk's RMS energy.
    Detects silence/noise transitions and sound spikes.
    """
    global _is_silent
    with _lock:
        _energy_window.append(rms)

        avg_energy = sum(_energy_window) / len(_energy_window) if _energy_window else 0

        was_silent = _is_silent
        _is_silent = avg_energy < config.SILENCE_THRESHOLD

        # Detect sudden spike (sound ~3× louder than running average)
        if rms > avg_energy * 3 and rms > config.SILENCE_THRESHOLD * 2:
            log.debug("Sound spike detected! rms=%.4f avg=%.4f", rms, avg_energy)
            from consciousness.state import update_state
            update_state(last_observation=f"sudden loud sound at {_time_str()}")
            for cb in _sound_spike_callbacks:
                try:
                    cb()
                except Exception:
                    pass

        # Silence just started
        if not was_silent and _is_silent:
            log.debug("Silence started.")
            from consciousness.state import record_silence_start
            record_silence_start()


def register_spike_callback(cb: Callable) -> None:
    """Register a callback to be called on sudden audio spike."""
    _sound_spike_callbacks.append(cb)


def is_silent() -> bool:
    return _is_silent


def get_time_context() -> str:
    """Return a human-readable time-of-day context string."""
    hour = datetime.datetime.now().hour
    if 5 <= hour < 9:
        return "early morning"
    elif 9 <= hour < 12:
        return "morning"
    elif 12 <= hour < 14:
        return "midday"
    elif 14 <= hour < 18:
        return "afternoon"
    elif 18 <= hour < 21:
        return "evening"
    elif 21 <= hour < 24:
        return "night"
    else:
        return "late night"


def _time_str() -> str:
    return datetime.datetime.now().strftime("%H:%M")
