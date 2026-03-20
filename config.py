"""
config.py — Central configuration loader for Delulu Her.
Reads from .env file and exposes typed constants throughout the system.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_BASE_DIR = Path(__file__).parent
load_dotenv(_BASE_DIR / ".env")


def _bool(val: str) -> bool:
    return val.strip().lower() in ("true", "1", "yes")


def _int(val: str, default: int) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _float(val: str, default: float) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ── LLM / Model ─────────────────────────────────────────────────────────────
MODEL_PATH        = os.getenv("MODEL_PATH", "./models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf")
MODEL_CTX         = _int(os.getenv("MODEL_CONTEXT_LENGTH", "2048"), 2048)
MODEL_THREADS     = _int(os.getenv("MODEL_THREADS", "4"), 4)
MODEL_GPU_LAYERS  = _int(os.getenv("MODEL_GPU_LAYERS", "0"), 0)

# ── MongoDB ──────────────────────────────────────────────────────────────────
MONGO_URI         = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME     = os.getenv("MONGO_DB_NAME", "delulu_her")

# ── Audio ────────────────────────────────────────────────────────────────────
AUDIO_SAMPLE_RATE     = _int(os.getenv("AUDIO_SAMPLE_RATE", "16000"), 16000)
AUDIO_CHANNELS        = _int(os.getenv("AUDIO_CHANNELS", "1"), 1)
AUDIO_CHUNK_DURATION  = _float(os.getenv("AUDIO_CHUNK_DURATION", "0.5"), 0.5)
SILENCE_THRESHOLD     = _float(os.getenv("AUDIO_SILENCE_THRESHOLD", "0.01"), 0.01)
SPEECH_BUFFER_SEC     = _float(os.getenv("AUDIO_SPEECH_BUFFER_SEC", "5"), 5.0)
WHISPER_MODEL         = os.getenv("WHISPER_MODEL", "tiny")
TEXT_INPUT_MODE       = _bool(os.getenv("TEXT_INPUT_MODE", "false"))
AUDIO_DEVICE_ID       = _int(os.getenv("AUDIO_DEVICE_ID", "-1"), -1)

# ── Piper TTS ────────────────────────────────────────────────────────────────
PIPER_EXECUTABLE   = os.getenv("PIPER_EXECUTABLE", "./piper/piper")
PIPER_VOICE_MODEL  = os.getenv("PIPER_VOICE_MODEL", "./piper/voices/en_US-amy-medium.onnx")
PIPER_VOICE_CONFIG = os.getenv("PIPER_VOICE_CONFIG", "./piper/voices/en_US-amy-medium.onnx.json")

# ── Email (IMAP) ─────────────────────────────────────────────────────────────
EMAIL_ENABLED          = _bool(os.getenv("EMAIL_ENABLED", "false"))
EMAIL_IMAP_HOST        = os.getenv("EMAIL_IMAP_HOST", "imap.gmail.com")
EMAIL_IMAP_PORT        = _int(os.getenv("EMAIL_IMAP_PORT", "993"), 993)
EMAIL_ADDRESS          = os.getenv("EMAIL_ADDRESS", "")
EMAIL_PASSWORD         = os.getenv("EMAIL_PASSWORD", "")
EMAIL_CHECK_INTERVAL   = _int(os.getenv("EMAIL_CHECK_INTERVAL_MIN", "10"), 10)
EMAIL_MAX_FETCH        = _int(os.getenv("EMAIL_MAX_FETCH", "5"), 5)

# ── Personality & Consciousness ───────────────────────────────────────────────
AI_NAME                  = os.getenv("AI_NAME", "Delulu")
THOUGHT_LOOP_MIN_SEC     = _int(os.getenv("THOUGHT_LOOP_MIN_SEC", "30"), 30)# ── Music ────────────────────────────────────────────────────────────────────
RAPIDAPI_KEY          = os.getenv("RAPIDAPI_KEY", "")
MUSIC_API_HOST        = os.getenv("MUSIC_API_HOST", "shazam-core.p.rapidapi.com")
THOUGHT_LOOP_MAX_SEC     = _int(os.getenv("THOUGHT_LOOP_MAX_SEC", "120"), 120)
SPEAK_THOUGHT_PROB       = _float(os.getenv("SPEAK_THOUGHT_PROBABILITY", "0.25"), 0.25)
CURIOSITY_DECAY          = _float(os.getenv("CURIOSITY_DECAY_RATE", "0.05"), 0.05)

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# ── Gemini ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
USE_GEMINI        = _bool(os.getenv("USE_GEMINI", "false"))
GEMINI_MODEL      = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# ── Groq ──────────────────────────────────────────────────────────────────
GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
USE_GROQ          = _bool(os.getenv("USE_GROQ", "false"))
GROQ_MODEL        = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# ── NVIDIA ────────────────────────────────────────────────────────────────
NVIDIA_API_KEY    = os.getenv("NVIDIA_API_KEY", "")
USE_NVIDIA        = _bool(os.getenv("USE_NVIDIA", "false"))
NVIDIA_MODEL      = os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")

# ── Language ───────────────────────────────────────────────────────────────
CURRENT_LANGUAGE  = os.getenv("CURRENT_LANGUAGE", "en") # 'en' or 'ml'
SILENCE_THRESHOLD = _float(os.getenv("AUDIO_SILENCE_THRESHOLD", "0.01"), 0.01)

# ── Derived paths ────────────────────────────────────────────────────────────
BASE_DIR   = _BASE_DIR
MODELS_DIR = _BASE_DIR / "models"
PIPER_DIR  = _BASE_DIR / "piper"
