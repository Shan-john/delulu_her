from ytmusicapi import YTMusic
import sys

def test_ytm():
    try:
        yt = YTMusic()
        print("Searching for 'blinding lights'...")
        results = yt.search("blinding lights", filter="songs", limit=1)
        if results:
            track = results[0]
            print(f"Success! Found: {track['title']} by {track['artists'][0]['name']}")
            print(f"Video ID: {track['videoId']}")
        else:
            print("No results found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_ytm()
