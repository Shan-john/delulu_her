import requests
import pygame
import os
import threading
import tempfile
import config
from utils.logger import get_logger

log = get_logger("music")

_is_playing = False

def search_and_play(query: str):
    """Search for a song and play its preview."""
    global _is_playing
    
    if not config.RAPIDAPI_KEY:
        log.error("RapidAPI Key missing. Cannot search music.")
        return "I'm sorry, I don't have the keys to the music library yet."

    url = f"https://{config.MUSIC_API_HOST}/v1/search/multi"
    querystring = {"query": query, "search_type": "SONGS"}
    headers = {
        "X-Rapidapi-Key": config.RAPIDAPI_KEY,
        "X-Rapidapi-Host": config.MUSIC_API_HOST
    }

    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        data = response.json()
        
        tracks = data.get("tracks", {}).get("hits", [])
        if not tracks:
            return f"I couldn't find any songs titled '{query}'."

        track = tracks[0].get("track", {})
        title = track.get("title", "Unknown Song")
        artist = track.get("subtitle", "Unknown Artist")
        
        # Extract preview URL
        actions = track.get("hub", {}).get("actions", [])
        preview_url = None
        for action in actions:
            if action.get("type") == "uri":
                preview_url = action.get("uri")
                break
        
        if not preview_url:
            return f"I found '{title}' by {artist}, but I can't play it right now."

        # Play in background
        stop_music()
        threading.Thread(target=_play_url, args=(preview_url,), daemon=True).start()
        _is_playing = True
        
        return f"Playing '{title}' by {artist}."

    except Exception as e:
        log.error("Music search error: %s", e)
        return "Something went wrong while searching for music."

def play_random():
    """Play a random popular song (Shazam doesn't have a direct 'random' but we can search for a common term)."""
    random_terms = ["pop", "rock", "lofi", "chill", "top hits", "dance"]
    import random
    term = random.choice(random_terms)
    return search_and_play(term)

def stop_music():
    """Stop any currently playing music."""
    global _is_playing
    try:
        pygame.mixer.init() # Ensure mixer is up
        pygame.mixer.music.stop()
        _is_playing = False
    except:
        pass

def _play_url(url: str):
    """Download and play the audio preview."""
    try:
        response = requests.get(url, stream=True)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
            temp_path = f.name
        
        pygame.mixer.init()
        pygame.mixer.music.load(temp_path)
        pygame.mixer.music.play()
        
        # Wait for it to finish or be stopped
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        
        # Cleanup
        pygame.mixer.music.unload()
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
    except Exception as e:
        log.error("Error playing music: %s", e)
