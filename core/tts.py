import os
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
import pygame
import tempfile
import config
from utils.logger import get_logger

log = get_logger("tts")

_pygame_inited = False

def start():
    """Start the TTS subsystem."""
    global _pygame_inited
    try:
        pygame.mixer.init()
        _pygame_inited = True
        log.info("Google TTS (gTTS) Subsystem Ready.")
    except Exception as e:
        log.error("Failed to init pygame for TTS: %s", e)

def speak_sync(text: str) -> None:
    """Send text to speakers (Blocking)."""
    if not text: return
    
    # 1. Determine language — can detect if text contains Malayalam
    lang = config.CURRENT_LANGUAGE 
    # If the user explicitly asks to switch, Gemini can be told in prompt, 
    # and we can optionally detect language here too.
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            temp_path = f.name
        
        # 2. Get audio from Google
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(temp_path)
        
        # 3. Play via PyGame
        if not _pygame_inited: start()
        
        pygame.mixer.music.load(temp_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
            
        # Clean up
        pygame.mixer.music.unload()
        try: os.remove(temp_path)
        except: pass
        
    except Exception as e:
        log.error("gTTS Error: %s", e)
        # Fallback to local pyttsx3
        _say_local(text)

def speak(text: str) -> None:
    """Speak in a non-blocking thread."""
    import threading
    threading.Thread(target=speak_sync, args=(text,), daemon=True).start()

def _say_local(text: str) -> None:
    import pyttsx3
    engine = pyttsx3.init()
    # Try local female voice
    voices = engine.getProperty('voices')
    for voice in voices:
        if "female" in voice.name.lower() or "zira" in voice.name.lower():
            engine.setProperty('voice', voice.id)
            break
    engine.say(text)
    engine.runAndWait()

def stop():
    try: pygame.mixer.quit()
    except: pass
