import requests
import os
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
MUSIC_API_HOST = os.getenv("MUSIC_API_HOST")

def test_music():
    print(f"Testing Music API with host: {MUSIC_API_HOST}")
    url = f"https://{MUSIC_API_HOST}/v1/search/multi"
    querystring = {"query": "blinding lights", "search_type": "SONGS"}
    headers = {
        "X-Rapidapi-Key": RAPIDAPI_KEY,
        "X-Rapidapi-Host": MUSIC_API_HOST
    }
    
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        print(f"Status Code: {response.status_code}")
        data = response.json()
        if response.status_code == 200:
            print(f"Full Response Header Keys: {data.keys()}")
            tracks_data = data.get("tracks", {})
            print(f"Tracks Keys: {tracks_data.keys()}")
            hits = tracks_data.get("hits", [])
            if hits:
                track = hits[0].get("track", {})
                print(f"Found Track: {track.get('title')} by {track.get('subtitle')}")
                # check for preview link
                actions = track.get("hub", {}).get("actions", [])
                for action in actions:
                    if action.get("type") == "uri":
                        print(f"Preview URL found: {action.get('uri')}")
                        return True
            else:
                print("No tracks found in response hits.")
                print(f"Full Data: {data}")
        else:
            print(f"Error: {data}")
    except Exception as e:
        print(f"Exception: {e}")
    return False

if __name__ == "__main__":
    test_music()
