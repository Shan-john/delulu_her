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
from services import email_service, music_service, reminder_service, ha_service
from utils.logger import get_logger

log = get_logger("main")


def on_user_speech(user_text: str) -> None:
    """Main processing callback."""
    try:
        # ── Wake-word Detection (Fuzzy) ───────────────────────────────────────
        name = config.AI_NAME.lower()
        # Common mishearings for "delulu" (Whisper often gets these)
        fuzzy_names = [name, "delulu",
"de lulu",
"delu lu",
"dellulu",
"delooloo",
"deloo loo",
"dilulu",
"dilooloo",
"delloo",
"dellooo",
"deloo",
"delooo",
"deluuu",
"deluloo",
"delulooo",
"delulul",
"delululu",
"delulz",
"deluls",
"delu",
"deluu",
"deluuu",
"dulu",
"duluu",
"duloo",
"dululu",
"dudulu",
"duduluu",
"dudu",
"duduu",
"duduuu",
"dooloo",
"doolu",
"doolulu",
"doolooo",
"lulu",
"luloo",
"lulooo",
"lululu",
"lulululu",
"looloo",
"loolu",
"loolulu",
"loooloo",
"tulu",
"tululu",
"tulooo",
"tilulu",
"tiloo",
"dalulu",
"dalooloo",
"daluluu",
"deluluu",
"delulooo",
"deloolooo",
"deooloo",
"deulu",
"deululu",
"deoolulu",
"de-lulu",
"de_lulu",
"d3lulu",
"delluluu",
"dellooloo"]
        
        user_text_lower = user_text.lower().strip()
        
        detected_name = None
        match_start = -1
        match_end = -1
        
        # Sort fuzzy names by length descending so we match longest words first
        sorted_fuzzy = sorted(fuzzy_names, key=len, reverse=True)
        
        for f in sorted_fuzzy:
            idx = user_text_lower.find(f)
            if idx != -1:
                detected_name = f
                match_start = idx
                match_end = idx + len(f)
                break
        
        if not detected_name:
            log.debug("Wake-word not detected, skipping.")
            return

        # Removing the detected wake-word from the original string
        clean_text = (user_text[:match_start] + " " + user_text[match_end:]).strip()
        # Remove any leftover punctuation around where the wake word was
        clean_text = " ".join(clean_text.split())
        clean_text = clean_text.strip(",.?! ").strip()
        
        if not clean_text:
            tts.speak(f"Yes bestie? I'm listening!")
            return

        log.info("\n👤 User (fuzzy detect): %s", user_text)
        text_lower = clean_text.lower()
        user_text = clean_text # Replace for further processing

        # ── Music Interaction ───────────────────────────────────────────────────
        import re
        
        # 0. Check for Confirmation
        pending_song = state.get_pending_song()
        if pending_song:
            if any(k in text_lower for k in ["yes", "yeah", "sure", "do it", "play it", "okay", "ok"]):
                log.info("Confirmation received for: %s", pending_song)
                state.set_pending_song(None)
                response = music_service.play_random() if pending_song == "random_music_request" else music_service.search_and_play(pending_song)
                tts.speak(response)
                return
            elif any(k in text_lower for k in ["no", "don't", "stop", "nevermind", "cancel"]):
                log.info("Confirmation denied for: %s", pending_song)
                state.set_pending_song(None)
                tts.speak("No problem, bestie! I won't play it.")
                return

        if any(k in text_lower for k in ["stop music", "stop playing", "stop the music"]):
            music_service.stop_music()
            tts.speak("Okay, bestie! I've stopped the music for you.")
            return

        if "sing a song" in text_lower or "play some music" in text_lower:
            state.set_pending_song("random_music_request")
            tts.speak("Ooh! You want to hear some music? Should I play something cute and popular for you?")
            return

        # 1. Update state & Extract basic topics (fast)
        state.record_interaction()
        extr = extractor.extract(user_text) # Use regex for prompt building (fast)
        
        session_id = learner.get_session_id()
        learner.record_message("user", user_text, extr.topics)

        # 2. Start AI Extraction in background (slow) to memory
        def run_bg_extraction(text):
            try:
                ai_extr = extractor.ai_extract(text, reasoning.generate)
                learner.learn(ai_extr, text)
            except Exception as e:
                log.error("Background extraction failed: %s", e)
        
        threading.Thread(target=run_bg_extraction, args=(user_text,), daemon=True).start()

        # 3. Build prompt & Generate Reply
        prompt = prompt_builder.build_prompt(user_text, extr, session_id)
        log.info("💭 Thinking...")
        raw_response = reasoning.generate(prompt, max_tokens=100, temperature=0.7)
        final_response = personality.apply_personality(raw_response, mood=state.get_mood())

        # 3.5 Home Assistant Integration
        if config.HA_ENABLED:
            if "turn on" in text_lower or "switch on" in text_lower:
                device = text_lower.replace("turn on", "").replace("switch on", "").replace("the", "").strip()
                if device:
                    response = ha_service.control_device(device, "on")
                    log.info("\n✨ delulu (HA): %s\n", response)
                    tts.speak(response)
                    return
            elif "turn off" in text_lower or "switch off" in text_lower:
                device = text_lower.replace("turn off", "").replace("switch off", "").replace("the", "").strip()
                if device:
                    response = ha_service.control_device(device, "off")
                    log.info("\n✨ delulu (HA): %s\n", response)
                    tts.speak(response)
                    return
            elif "toggle" in text_lower:
                device = text_lower.replace("toggle", "").replace("the", "").strip()
                if device:
                    response = ha_service.control_device(device, "toggle")
                    log.info("\n✨ delulu (HA): %s\n", response)
                    tts.speak(response)
                    return

        # 3. Mail Integration
        if any(k in text_lower for k in ["mail", "check my mail", "any mail"]):
            log.info("Fetching latest email...")
            latest_mails = email_service.fetch_latest_emails(count=1)
            mail_summary = f"Subject: {latest_mails[0]['subject']}. Content: {latest_mails[0]['body']}" if latest_mails else "Your inbox is empty."
            final_response = f"{mail_summary} {final_response}"

        # 4. Feedback handling
        if any(k in text_lower for k in ["hallucin", "never said", "wrong", "misunderstood"]):
            final_response = "I'm so sorry, bestie! I think I misunderstood or misheard you. I'll listen more carefully now, I promise."

        log.info("\n✨ delulu: %s\n", final_response)
        learner.record_message("assistant", final_response, extr.topics)
        tts.speak(final_response)

    except Exception as e:
        log.exception("Error in user speech callback: %s", e)
        tts.speak("Wait, something went a bit wrong inside my head... could you say that again, bestie?")


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
        def on_new_email(sender: str, subject: str):
            msg = f"Ooh bestie! You just got a new email from {sender} about {subject}. Should I read it for you?"
            tts.speak(msg)

        email_service.start(on_new_email=on_new_email)
        reminder_service.start(tts.speak_sync)
        ha_service.init()

        # Start Thought Loop (inject speak/generate access)
        thought_loop.start(generate_fn=reasoning.generate, speak_fn=tts.speak_sync)

        # Start Audio Capture / Keyboard Fallback
        audio.start_listening(on_transcription=on_user_speech)

        # ── Startup Greeting ──
        # Let the user know we are awake and listening!
        greeting = f"Hi bestie! I'm wide awake. Remember to start your sentences with '{config.AI_NAME}' so I know you're talking to me!"
        threading.Thread(target=tts.speak_sync, args=(greeting,), daemon=True).start()

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
