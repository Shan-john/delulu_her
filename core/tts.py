import os
import asyncio
import edge_tts
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
    """Send text to speakers (Blocking/Async wrapper)."""
    if not text: return
    
    # Run the async tts function
    try:
        asyncio.run(_speak_edge_tts(text))
    except Exception as e:
        log.error("TTS Error: %s", e)
        _say_local(text)

async def _speak_edge_tts(text: str) -> None:
    """Uses Microsoft Edge Neural voices for smoother, softer output."""
    # 1. Select Voice
    if config.CURRENT_LANGUAGE == "ml":
        voice = "ml-IN-SobhanaNeural" # Soft Malayalam Female
    else:
        voice = "en-US-AvaNeural"      # Very Soft English Female (Emma or Ava)
    
    try:
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_path = tmp_file.name
        tmp_file.close()

        # 2. Communicate with Edge TTS
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(temp_path)

        # 3. Play via PyGame
        if not _pygame_inited: start()
        
        pygame.mixer.music.load(temp_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.05)
            
        # Clean up
        pygame.mixer.music.unload()
        try: os.remove(temp_path)
        except: pass
        
    except Exception as e:
        log.error("Edge-TTS Error: %s", e)
        raise e

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

def play_chime() -> None:
    """Play a short, soft notification tone (non-blocking)."""
    import threading
    def _play():
        try:
            # Ensure mixer is initialized
            if not pygame.mixer.get_init():
                start()
            
            if not pygame.mixer.get_init():
                log.error("Cannot play chime: Mixer failed to initialize.")
                return
            
            # Create a simple soft chime tone (440Hz sine wave)
            import numpy as np
            sample_rate = 44100
            duration = 0.12  # Slightly longer
            frequency = 440.0 # A4
            
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            # Create a fade-out to avoid clicks
            envelope = np.exp(-t * 22)
            tone = 0.08 * np.sin(2 * np.pi * frequency * t) * envelope # Slightly softer
            
            # Convert to 16-bit PCM
            tone_pcm = (tone * 32767).astype(np.int16)
            # Duplicate for stereo
            tone_stereo = np.column_stack((tone_pcm, tone_pcm))
            
            sound = pygame.sndarray.make_sound(tone_stereo)
            sound.play()
        except Exception as e:
            log.debug("Chime error: %s", e)
            
    threading.Thread(target=_play, daemon=True).start()

def stop():
    try: pygame.mixer.quit()
    except: pass
