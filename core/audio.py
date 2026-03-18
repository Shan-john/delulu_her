"""
core/audio.py — Continuous microphone capture + VAD + Whisper STT.

Pipeline:
  1. sounddevice streams audio in chunks
  2. Each chunk's RMS energy is measured (Voice Activity Detection)
  3. When speech is detected, chunks are buffered
  4. After speech ends (silence), buffer is sent to Whisper
  5. Transcription is passed to the callback

Also supports TEXT_INPUT_MODE=true for keyboard input (no mic required).
"""

from __future__ import annotations

import io
import queue
import threading
import time
import wave
from typing import Callable

import numpy as np
import scipy.io.wavfile as wavfile

import config
from consciousness.environment import push_audio_energy
from utils.logger import get_logger

log = get_logger("audio")

# ── Whisper model (lazy-loaded) ───────────────────────────────────────────────
_whisper_model = None

def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        import whisper
        log.info("Loading Whisper '%s' model...", config.WHISPER_MODEL)
        _whisper_model = whisper.load_model(config.WHISPER_MODEL)
        log.info("Whisper loaded.")
    return _whisper_model


# ── Audio capture state ───────────────────────────────────────────────────────
_audio_queue: queue.Queue       = queue.Queue()
_speech_buffer: list[np.ndarray] = []
_in_speech     = False
_silence_count = 0
_SILENCE_CHUNKS_NEEDED = int(1.5 / config.AUDIO_CHUNK_DURATION)  # 1.5s silence to end speech


# ── Public API ─────────────────────────────────────────────────────────────

def start_listening(on_transcription: Callable[[str], None]) -> None:
    """
    Start continuous audio listening.

    If TEXT_INPUT_MODE is enabled, starts a keyboard input thread instead.
    Otherwise, starts sounddevice capture + Whisper STT.

    Args:
        on_transcription: callback(text) called whenever speech is transcribed
    """
    if config.TEXT_INPUT_MODE:
        log.info("TEXT_INPUT_MODE active — type messages instead of speaking.")
        t = threading.Thread(
            target=_keyboard_input_loop,
            args=(on_transcription,),
            name="keyboard-input",
            daemon=True,
        )
        t.start()
    else:
        log.info("Starting microphone capture (sample_rate=%d)", config.AUDIO_SAMPLE_RATE)
        # Pre-load Whisper model
        _get_whisper()

        t = threading.Thread(
            target=_mic_capture_loop,
            args=(on_transcription,),
            name="audio-capture",
            daemon=True,
        )
        t.start()


# ── Keyboard fallback ─────────────────────────────────────────────────────────

def _keyboard_input_loop(callback: Callable[[str], None]) -> None:
    print(f"\n{'='*50}")
    print(f"  {config.AI_NAME} is listening (text mode).")
    print(f"  Type your message and press Enter.")
    print(f"{'='*50}\n")
    while True:
        try:
            text = input("You: ").strip()
            if text:
                callback(text)
        except (EOFError, KeyboardInterrupt):
            break


# ── Microphone capture ─────────────────────────────────────────────────────

def _mic_capture_loop(callback: Callable[[str], None]) -> None:
    global _in_speech, _silence_count, _speech_buffer

    import sounddevice as sd

    chunk_samples = int(config.AUDIO_SAMPLE_RATE * config.AUDIO_CHUNK_DURATION)

    def audio_callback(indata: np.ndarray, frames: int, time_info, status):
        """Called by sounddevice for each audio chunk."""
        if status:
            log.warning("Audio status: %s", status)
        _audio_queue.put(indata.copy())

    with sd.InputStream(
        samplerate=config.AUDIO_SAMPLE_RATE,
        channels=config.AUDIO_CHANNELS,
        dtype="float32",
        blocksize=chunk_samples,
        callback=audio_callback,
    ):
        log.info("Microphone open. Listening...")
        while True:
            try:
                chunk = _audio_queue.get(timeout=2.0)
                _process_chunk(chunk, callback)
            except queue.Empty:
                continue
            except Exception as e:
                log.error("Audio loop error: %s", e)
                time.sleep(1.0)


def _process_chunk(chunk: np.ndarray, callback: Callable[[str], None]) -> None:
    """VAD + speech buffering logic for one audio chunk."""
    global _in_speech, _silence_count, _speech_buffer

    rms = float(np.sqrt(np.mean(chunk ** 2)))
    push_audio_energy(rms)  # Inform consciousness

    is_voice = rms > config.SILENCE_THRESHOLD

    if is_voice:
        _silence_count = 0
        if not _in_speech:
            log.debug("Speech started (rms=%.4f)", rms)
            _in_speech = True
        _speech_buffer.append(chunk)

    elif _in_speech:
        # Still in speech window — buffer silence briefly
        _silence_count += 1
        _speech_buffer.append(chunk)

        if _silence_count >= _SILENCE_CHUNKS_NEEDED:
            # Speech ended — transcribe
            log.debug("Speech ended. Buffered %d chunks.", len(_speech_buffer))
            audio_data = np.concatenate(_speech_buffer, axis=0).flatten()
            _speech_buffer = []
            _in_speech     = False
            _silence_count = 0
            _transcribe(audio_data, callback)


def _transcribe(audio: np.ndarray, callback: Callable[[str], None]) -> None:
    """Run Whisper STT on buffered audio."""
    try:
        model  = _get_whisper()
        import whisper
        result = model.transcribe(audio, fp16=False, language="en")
        text   = result.get("text", "").strip()
        if text:
            log.info("STT: %s", text)
            callback(text)
        else:
            log.debug("Empty transcription — ignoring.")
    except Exception as e:
        log.error("Whisper error: %s", e)
