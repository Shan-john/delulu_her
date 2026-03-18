"""
main.py — The main orchestrator for Delulu Her.

1. Connects to MongoDB
2. Starts text-to-speech engine
3. Loads TinyLlama reasoning engine
4. Starts autonomous loops (thoughts, emails, reminders)
5. Enters main listening loop (Audio/VAD → Whisper → Processing)
"""

from __future__ import annotations

import sys
import threading
import time

import config
from consciousness import environment, state, thought_loop
from core import audio, personality, prompt_builder, reasoning, tts
from memory import database, extractor, learner, retriever
from services import email_service, reminder_service
from utils.logger import get_logger

log = get_logger("main")


def on_user_speech(user_text: str) -> None:
    """
    Main processing callback: fired whenever user speaks (or types).
    1. Update state (user interacted)
    2. Extract meaning & learn
    3. Build context-aware prompt
    4. Generate response
    5. Speak response
    """
    log.info("\n👤 User: %s", user_text)

    # 1. Update consciousness state
    state.record_interaction()

    # 2. Extract facts & events (AI-powered to ensure we don't miss anything!)
    extr = extractor.ai_extract(user_text, reasoning.generate)

    # 3. Learn new information (MongoDB)
    session_id = learner.get_session_id()
    learner.record_message("user", user_text, extr.topics)
    facts_stored = learner.learn(extr, user_text)

    if facts_stored > 0:
        state.on_learned_something()

    # 4. Build prompt (using chat history, memories, internal state)
    prompt = prompt_builder.build_prompt(user_text, extr, session_id)

    # 5. Generate LLM response
    log.info("💭 Thinking...")
    raw_response = reasoning.generate(
        prompt,
        max_tokens=150,  # Malayalam tokens take up more space!
        temperature=0.7
    )

    # 6. Apply personality post-processing
    final_response = personality.apply_personality(raw_response, mood=state.get_mood())
    
    # Language Switch Detection
    text_lower = user_text.lower()
    if "speak in malayalam" in text_lower or "മലയാളം" in text_lower or (config.CURRENT_LANGUAGE != "ml" and "malayalam" in text_lower):
        config.CURRENT_LANGUAGE = "ml"
        log.info("Switching voice to Malayalam.")
    elif "speak in english" in text_lower or (config.CURRENT_LANGUAGE == "ml" and "english" in text_lower):
        config.CURRENT_LANGUAGE = "en"
        log.info("Switching voice to English.")

    # Add memory recall prefix optionally
    if not extr.is_question and extr.topics and facts_stored == 0:
        # User statement, no new facts -> chance to recall old memory
        if retriever.retrieve_memories(user_text, extr.topics, limit=1):
            if "I remember" not in final_response:
                prefix = personality.make_memory_recall_prefix(extr.topics[0])
                final_response = f"{prefix} {final_response}"

    log.info("\n✨ Delulu: %s\n", final_response)

    # 7. Record and Speak
    learner.record_message("assistant", final_response, extr.topics)

    # Pass to TTS queue (non-blocking)
    tts.speak(final_response)


def start_system() -> None:
    """Initialize and start all system components."""
    print(f"\n{'-'*60}")
    print(f"  Starting {config.AI_NAME} (Local AI Companion)")
    print(f"{'-'*60}\n")

    try:
        # Initialize Database
        db = database.get_db()
        database.init_internal_state()

        # Start TTS engine
        tts.start()

        # Load LLM
        reasoning.load_model()

        # Start Services
        email_service.start()
        reminder_service.start(tts.speak_sync)

        # Start Thought Loop (inject speak/generate access)
        thought_loop.start(generate_fn=reasoning.generate, speak_fn=tts.speak_sync)

        # Start Audio Capture / Keyboard Fallback
        audio.start_listening(on_transcription=on_user_speech)

        # Main thread simply sleeps and keeps daemon threads alive
        while True:
            time.sleep(1.0)

    except KeyboardInterrupt:
        log.info("\nShutdown signal received (Ctrl+C).")
    except Exception as e:
        log.exception("Fatal error during main loop: %s", e)
    finally:
        _shutdown()


def _shutdown() -> None:
    """Cleanly stop background threads."""
    log.info("Shutting down components...")
    thought_loop.stop()
    email_service.stop()
    reminder_service.stop()
    tts.stop()
    log.info("Shutdown complete.")
    sys.exit(0)


if __name__ == "__main__":
    start_system()
