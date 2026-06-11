"""Refresh the "Daily Drive Mix" Spotify playlist.

Auth uses a long-lived refresh token (obtained once via scripts/spotify_auth.py)
so the pipeline can run headless in CI.

Curation note: Spotify deprecated the /recommendations endpoint for new apps
(Nov 2024), so the mix is built from signals that still work: your top tracks,
a shuffle of saved tracks, and recent releases from artists you follow.
"""

import os
import random
from datetime import datetime, timedelta, timezone

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from .common import get_logger, load_settings

log = get_logger("spotify")

SCOPES = (
    "playlist-modify-private playlist-modify-public "
    "user-top-read user-library-read user-follow-read"
)


def _client() -> spotipy.Spotify:
    auth = SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri="http://127.0.0.1:8888/callback",
        scope=SCOPES,
        open_browser=False,
    )
    token = auth.refresh_access_token(os.environ["SPOTIFY_REFRESH_TOKEN"])
    return spotipy.Spotify(auth=token["access_token"])


def _new_releases_from_followed(sp: spotipy.Spotify, limit: int) -> list[dict]:
    """Tracks from albums/singles released in the last 14 days by followed artists."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    tracks: list[dict] = []
    after = None
    # Cap the scan at ~100 followed artists to keep the run fast
    for _ in range(2):
        result = sp.current_user_followed_artists(limit=50, after=after)["artists"]
        for artist in result["items"]:
            try:
                albums = sp.artist_albums(
                    artist["id"], include_groups="album,single", limit=3
                )["items"]
            except Exception:  # noqa: BLE001
                continue
            for album in albums:
                date_str = album["release_date"]
                fmt = {4: "%Y", 7: "%Y-%m", 10: "%Y-%m-%d"}.get(len(date_str))
                if not fmt:
                    continue
                released = datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
                if released >= cutoff:
                    album_tracks = sp.album_tracks(album["id"], limit=2)["items"]
                    tracks.extend(album_tracks)
            if len(tracks) >= limit:
                return tracks[:limit]
        after = result["cursors"].get("after")
        if not after:
            break
    return tracks[:limit]


def _find_or_create_playlist(sp: spotipy.Spotify, user_id: str, name: str) -> str:
    playlists = sp.current_user_playlists(limit=50)["items"]
    for pl in playlists:
        if pl["name"] == name and pl["owner"]["id"] == user_id:
            return pl["id"]
    created = sp.user_playlist_create(
        user_id, name, public=False,
        description="Auto-curated each morning by the Daily Drive pipeline.",
    )
    return created["id"]


def refresh_playlist() -> dict | None:
    cfg = load_settings()["spotify"]
    if not cfg.get("enabled", True):
        log.info("Spotify stage disabled in settings")
        return None

    sp = _client()
    user_id = sp.current_user()["id"]
    size = cfg["playlist_size"]

    top = sp.current_user_top_tracks(limit=size, time_range="short_term")["items"]
    saved = [item["track"] for item in sp.current_user_saved_tracks(limit=50)["items"]]
    random.shuffle(saved)
    fresh = _new_releases_from_followed(sp, limit=size // 3)

    # Interleave: fresh releases first, then alternate top/saved; dedupe by id
    pool = fresh + [t for pair in zip(top, saved) for t in pair] + top + saved
    seen: set[str] = set()
    track_uris, track_names = [], []
    for t in pool:
        if not t or t["id"] in seen:
            continue
        seen.add(t["id"])
        track_uris.append(t["uri"])
        track_names.append(f"{t['name']} — {t['artists'][0]['name']}")
        if len(track_uris) >= size:
            break

    playlist_id = _find_or_create_playlist(sp, user_id, cfg["playlist_name"])
    sp.playlist_replace_items(playlist_id, track_uris)
    today = datetime.now(timezone.utc).strftime("%b %d")
    sp.playlist_change_details(
        playlist_id, description=f"Auto-curated {today} by the Daily Drive pipeline."
    )
    log.info("Playlist '%s' refreshed with %d tracks", cfg["playlist_name"], len(track_uris))
    return {"playlist_id": playlist_id, "track_names": track_names}


if __name__ == "__main__":
    import json

    print(json.dumps(refresh_playlist(), indent=2, ensure_ascii=False))
