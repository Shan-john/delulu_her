"""
services/music_service.py — Real-time Streaming via YouTube.
Uses ffplay to stream direct URLs from YouTube for instant playback.
"""

import os
import threading
import subprocess
import signal
from ytmusicapi import YTMusic
import yt_dlp
import config
from utils.logger import get_logger

log = get_logger("music")

# Track the ffplay process globally so we can stop it
_ffplay_process: subprocess.Popen | None = None
_is_playing = False

def is_playing() -> bool:
    """Check if music is currently playing."""
    return _is_playing


def search_and_play(query: str):
    """Search for a song and stream its audio instantly via ffplay."""
    global _is_playing
    
    log.info("Searching YouTube Music for: '%s'", query)
    try:
        yt = YTMusic()
        # Search for songs
        results = yt.search(query, filter="songs", limit=3)
        
        if not results:
            log.warning("No YouTube Music results for: %s", query)
            return f"I couldn't find '{query}' on YouTube Music."

        track = results[0]
        video_id = track.get("videoId")
        title    = track.get("title", "Unknown Title")
        artist   = ", ".join([a.get("name") for a in track.get("artists", [])])
        
        if not video_id:
            return "Wait, I found the song but it doesn't have a playback ID?"

        # Stop existing music
        stop_music()
        
        # Start streaming in a background thread
        threading.Thread(
            target=_stream_video_audio, 
            args=(video_id, title, artist), 
            daemon=True
        ).start()
        
        _is_playing = True
        return f"Instant stream starting! Playing '{title}' by {artist}."

    except Exception as e:
        log.error("YouTube Music search failed: %s", e)
        return "My YouTube Music brain is confused... maybe ask again?"

def play_random():
    """Play trending music."""
    return search_and_play("popular top hits 2024")

def stop_music():
    """Immediately stop the ffplay stream."""
    global _is_playing, _ffplay_process
    _is_playing = False
    
    if _ffplay_process:
        try:
            log.info("Stopping ffplay process...")
            if os.name == 'nt':
                # Force kill on Windows to be sure
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(_ffplay_process.pid)], 
                               capture_output=True, timeout=1)
            else:
                _ffplay_process.terminate()
                _ffplay_process.wait(timeout=2)
        except Exception as e:
            log.debug("Error stopping ffplay: %s", e)
            try: _ffplay_process.kill()
            except: pass
        _ffplay_process = None

def _stream_video_audio(video_id: str, title: str, artist: str):
    """Fetch the direct stream URL and pipe it into ffplay."""
    global _ffplay_process, _is_playing
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    log.info("Streaming video audio: %s", url)

    try:
        # 1. Get the direct audio URL with yt-dlp (No download)
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            stream_url = info.get('url')
            
        if not stream_url or not _is_playing:
            return

        # 2. Launch ffplay to stream the URL directly
        # -nodisp: don't show video window
        # -autoexit: close when done
        # -loglevel quiet: keep logs clean
        _ffplay_process = subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", stream_url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0 # Hide window on Windows
        )
        
        log.debug("ffplay streaming active for: %s", title)
        
        # Monitor the process until it finishes
        _ffplay_process.wait()
        _is_playing = False
        _ffplay_process = None
        
    except Exception as e:
        log.error("Streaming error: %s", e)
        _is_playing = False
        _ffplay_process = None
