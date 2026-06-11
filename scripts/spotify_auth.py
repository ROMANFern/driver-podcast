"""One-time local script: run the Spotify OAuth flow and print the refresh token.

Usage (PowerShell):
    $env:SPOTIFY_CLIENT_ID = "..."; $env:SPOTIFY_CLIENT_SECRET = "..."
    python scripts/spotify_auth.py

The redirect URI must exactly match one registered in your Spotify app
(override with the SPOTIFY_REDIRECT_URI env var if yours differs).
Paste the printed refresh token into the SPOTIFY_REFRESH_TOKEN GitHub secret.
"""

import os
import sys

from spotipy.oauth2 import SpotifyOAuth

SCOPES = (
    "playlist-modify-private playlist-modify-public "
    "user-top-read user-library-read user-follow-read"
)
DEFAULT_REDIRECT_URI = "http://127.0.0.1:43827/spotify/callback"


def main() -> None:
    for var in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET"):
        if not os.environ.get(var):
            sys.exit(f"Set {var} first.")

    auth = SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=os.environ.get("SPOTIFY_REDIRECT_URI", DEFAULT_REDIRECT_URI),
        scope=SCOPES,
        cache_path=".spotify_cache",
        open_browser=True,
    )
    token_info = auth.get_access_token(as_dict=True)
    print("\n=== Success! Add this GitHub secret ===")
    print(f"SPOTIFY_REFRESH_TOKEN = {token_info['refresh_token']}\n")


if __name__ == "__main__":
    main()
