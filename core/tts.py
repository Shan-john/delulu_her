import os
import asyncio
import edge_tts
import pygame
import tempfile
import config
from utils.logger import get_logger

log = get_logger("tts")

_pygame_inited = False

import queue
import threading
import time

_speech_queue: queue.Queue = queue.Queue()
_worker_running = False

def start():
    """Start the TTS subsystem."""
    global _pygame_inited, _worker_running
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        _pygame_inited = True
        log.info("TTS Subsystem Ready.")
        
        if not _worker_running:
            _worker_running = True
            t = threading.Thread(target=_tts_worker, name="tts-worker", daemon=True)
            t.start()
    except Exception as e:
        log.error("Failed to init pygame for TTS: %s", e)

def _tts_worker():
    """Background worker that spends words from the queue one at a time."""
    while _worker_running:
        try:
            text = _speech_queue.get(timeout=2.0)
            if not text:
                continue
            
            log.debug("Speaking from queue: %s", text[:30])
            speak_sync(text)
            _speech_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            log.error("TTS Worker error: %s", e)
            time.sleep(1.0)

def speak(text: str) -> None:
    """Add text to the background speech queue."""
    if not text: return
    if not _worker_running:
        start()
    _speech_queue.put(text)

def speak_sync(text: str) -> None:
    """Send text to speakers (Blocking/Async wrapper). Internal use or startup."""
    if not text: return
    
    # Run the async tts function safely
    try:
        try:
            # Check if we're in the main thread or if a loop is already running
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # Coroutine approach
            future = asyncio.run_coroutine_threadsafe(_speak_edge_tts(text), loop)
            future.result()
        else:
            loop.run_until_complete(_speak_edge_tts(text))
    except Exception as e:
        log.error("TTS Error: %s. Falling back to simple.", e)
        _say_local(text)

async def _speak_edge_tts(text: str) -> None:
    """Uses Microsoft Edge Neural voices for smoother, softer output."""
    # Select Voice
    voice = "en-US-AvaNeural"
    
    try:
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_path = tmp_file.name
        tmp_file.close()

        # 2. Communicate with Edge TTS
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(temp_path)

        # 3. Play via PyGame
        if not pygame.mixer.get_init(): pygame.mixer.init()
        
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

def _say_local(text: str) -> None:
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    except:
        pass

def play_chime() -> None:
    """Play a short, soft notification tone (non-blocking)."""
    def _play():
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            
            # Create a simple soft chime tone
            import numpy as np
            sample_rate = 44100
            duration = 0.12
            frequency = 440.0
            
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            envelope = np.exp(-t * 22)
            tone = 0.08 * np.sin(2 * np.pi * frequency * t) * envelope
            tone_pcm = (tone * 32767).astype(np.int16)
            tone_stereo = np.column_stack((tone_pcm, tone_pcm))
            
            sound = pygame.sndarray.make_sound(tone_stereo)
            sound.play()
        except:
            pass
            
    threading.Thread(target=_play, daemon=True).start()

def stop():
    global _worker_running
    _worker_running = False
    try: pygame.mixer.quit()
    except: pass
