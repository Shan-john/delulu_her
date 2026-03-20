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
from services import email_service, music_service, reminder_service
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
    
    text_lower = user_text.lower()

    # ── Music Interaction ───────────────────────────────────────────────────
    import re
    
    # 0. Check for Confirmation
    pending_song = state.get_pending_song()
    if pending_song:
        # Broad confirmation match
        if any(k in text_lower for k in ["yes", "yeah", "sure", "do it", "play it", "okay", "yep", "ok", "play now", "shall we"]):
            log.info("Confirmation received for: %s", pending_song)
            state.set_pending_song(None) # Clear
            
            if pending_song == "random_music_request":
                response = music_service.play_random()
            else:
                response = music_service.search_and_play(pending_song)
                
            tts.speak(response)
            return
        elif any(k in text_lower for k in ["no", "don't", "stop", "nevermind", "cancel", "no thanks"]):
            log.info("Confirmation denied for: %s", pending_song)
            state.set_pending_song(None) # Clear
            tts.speak("No problem, I won't play it.")
            return

    # 1. Stop Music (Highest priority to avoid regex conflicts)
    if any(k in text_lower for k in ["stop music", "stop playing", "stop the music", "stop the song", "shut up the music"]):
        log.info("Stopping music session...")
        state.set_pending_song(None) # Clear pending if stopping
        music_service.stop_music()
        tts.speak("Okay, I've stopped the music.")
        return

    # 2. Play Random / Specific Music
    if "sing a song" in text_lower or "play some music" in text_lower:
        log.info("Requesting random music confirmation...")
        state.set_pending_song("random_music_request")
        tts.speak("You want to hear some music? Should I play something popular for you?")
        return

    play_match = re.search(r"play\s+(.+)", text_lower)
    if play_match:
        song_query = play_match.group(1).strip()
        # Filter out common false positives
        if song_query not in ["with me", "a game", "around", "playing", "music"]:
            log.info("Requesting specific music confirmation: %s", song_query)
            state.set_pending_song(song_query)
            tts.speak(f"Oh! You want to hear {song_query}? Just to be sure, should I play it?")
            return

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
    
    # ── Mail Interaction ─────────────────────────────────────────────────────
    text_lower = user_text.lower()
    # Broadened matching to catch variations like 'checked', 'check', and mishearings like 'main', 'made'
    mail_keywords = ["mail", "main", "made", "meal", "mate", "mail check", "check my mail"]
    is_mail_request = any(k in text_lower for k in mail_keywords) and ("check" in text_lower or "read" in text_lower or "any" in text_lower)

    if is_mail_request:
        log.info("Fetching latest email for user...")
        latest_mails = email_service.fetch_latest_emails(count=1)
        
        if not latest_mails:
            mail_summary = "Your inbox is empty."
        else:
            mail_summary = ""
            for m in latest_mails:
                status = "IMPORTANT: " if m["important"] else ""
                # Only include Subject and Body as requested
                mail_summary += f"{status}Subject: {m['subject']}. Content: {m['body']} "
        
        # Mix it into the final response
        final_response = f"{mail_summary} {final_response}"
    
    # Language Switch Detection
    text_lower = user_text.lower()
    if "speak in malayalam" in text_lower or "മലയാളം" in text_lower or (config.CURRENT_LANGUAGE != "ml" and "malayalam" in text_lower):
        config.CURRENT_LANGUAGE = "ml"
        log.info("Switching voice to Malayalam.")
    elif "speak in english" in text_lower or (config.CURRENT_LANGUAGE == "ml" and "english" in text_lower):
        config.CURRENT_LANGUAGE = "en"
        log.info("Switching voice to English.")


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

        # ── Startup Greeting ──
        # Let the user know we are awake and listening!
        threading.Thread(target=tts.speak_sync, args=("Hey there! I'm wide awake and listening. What's on your mind?",), daemon=True).start()

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
    music_service.stop_music()
    thought_loop.stop()
    email_service.stop()
    reminder_service.stop()
    tts.stop()
    log.info("Shutdown complete.")
    sys.exit(0)


if __name__ == "__main__":
    start_system()
