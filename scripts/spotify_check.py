"""Diagnose Spotify auth: shows granted scopes and tests each API call the
pipeline makes, so a 403 can be pinned to a scope or app-access problem.

Usage (PowerShell):
    $env:SPOTIFY_CLIENT_ID = "..."; $env:SPOTIFY_CLIENT_SECRET = "..."
    $env:SPOTIFY_REFRESH_TOKEN = "..."
    python scripts/spotify_check.py
"""

import os
import sys

import spotipy
from spotipy.oauth2 import SpotifyOAuth


def main() -> None:
    for var in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REFRESH_TOKEN"):
        if not os.environ.get(var):
            sys.exit(f"Set {var} first.")

    auth = SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=os.environ.get(
            "SPOTIFY_REDIRECT_URI", "http://127.0.0.1:43827/spotify/callback"
        ),
        open_browser=False,
    )
    token = auth.refresh_access_token(os.environ["SPOTIFY_REFRESH_TOKEN"])
    print(f"Granted scopes: {token.get('scope', '(none reported)')}\n")
    sp = spotipy.Spotify(auth=token["access_token"])

    checks = [
        ("identity (current_user)", lambda: sp.current_user()["id"]),
        ("top tracks", lambda: len(sp.current_user_top_tracks(limit=1)["items"])),
        ("saved tracks", lambda: len(sp.current_user_saved_tracks(limit=1)["items"])),
        ("followed artists",
         lambda: len(sp.current_user_followed_artists(limit=1)["artists"]["items"])),
        ("list playlists", lambda: len(sp.current_user_playlists(limit=1)["items"])),
    ]
    user_id = None
    for name, fn in checks:
        try:
            result = fn()
            print(f"  OK   {name}: {result}")
            if name.startswith("identity"):
                user_id = result
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL {name}: {e}")

    if user_id:
        try:
            pl = sp.user_playlist_create(
                user_id, "Daily Drive auth check (delete me)", public=False
            )
            print(f"  OK   create playlist: {pl['id']}")
            sp.current_user_unfollow_playlist(pl["id"])
            print("  OK   cleanup (playlist removed)")
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL create playlist: {e}")
            print(
                "\nIf identity/top tracks pass but playlist creation fails with 403,"
                "\nthe app likely restricts the user: Dashboard -> your app ->"
                "\nUser Management -> add your Spotify account email. Also confirm"
                "\nthe app has 'Web API' enabled in its settings."
            )


if __name__ == "__main__":
    main()
