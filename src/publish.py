"""Publish stage: upload the episode MP3 as a GitHub Release asset and
regenerate the podcast RSS feed served from docs/ via GitHub Pages.

Release assets keep big MP3s out of git history. Episode metadata is kept in
docs/episodes.json; the feed is rebuilt from it every run and old releases are
pruned beyond episode.keep_last.

Requires the `gh` CLI authenticated via GITHUB_TOKEN (default in Actions) and
GITHUB_REPOSITORY set (e.g. "user/driver-podcast"). The repo must be public for
podcast apps to download the enclosure URLs.
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from feedgen.feed import FeedGenerator

from .common import DOCS_DIR, get_logger, load_settings
import os

log = get_logger("publish")

EPISODES_JSON = DOCS_DIR / "episodes.json"


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _load_episodes() -> list[dict]:
    if EPISODES_JSON.exists():
        return json.loads(EPISODES_JSON.read_text(encoding="utf-8"))
    return []


def _upload_release(mp3_path: Path, tag: str, title: str) -> str:
    repo = os.environ["GITHUB_REPOSITORY"]
    # Recreate the tag if today's run is a re-run
    subprocess.run(
        ["gh", "release", "delete", tag, "--yes", "--cleanup-tag"],
        capture_output=True, text=True,
    )
    _run([
        "gh", "release", "create", tag, str(mp3_path),
        "--title", title, "--notes", "Daily Drive episode",
    ])
    return f"https://github.com/{repo}/releases/download/{tag}/{mp3_path.name}"


def _prune_old_releases(episodes: list[dict], keep: int) -> list[dict]:
    keep_eps, drop_eps = episodes[:keep], episodes[keep:]
    for ep in drop_eps:
        subprocess.run(
            ["gh", "release", "delete", ep["tag"], "--yes", "--cleanup-tag"],
            capture_output=True, text=True,
        )
        log.info("Pruned old episode %s", ep["tag"])
    return keep_eps


def _build_feed(episodes: list[dict], settings: dict) -> None:
    pod = settings["podcast"]
    base_url = pod["base_url"].rstrip("/")
    feed_path = DOCS_DIR / f"feed-{pod['feed_slug']}.xml"

    fg = FeedGenerator()
    fg.load_extension("podcast")
    fg.title(pod["title"])
    fg.description(pod["description"])
    fg.author({"name": pod["author"]})
    fg.language(pod["language"])
    fg.link(href=base_url or "https://example.com", rel="alternate")
    fg.podcast.itunes_block(True)  # ask directories not to index

    for ep in reversed(episodes):  # feedgen outputs newest-last as written
        fe = fg.add_entry()
        fe.id(ep["url"])
        fe.title(ep["title"])
        fe.description(ep["show_notes"])
        fe.published(ep["published"])
        fe.enclosure(ep["url"], str(ep["size_bytes"]), "audio/mpeg")

    DOCS_DIR.mkdir(exist_ok=True)
    fg.rss_file(str(feed_path), pretty=True)
    log.info("Feed written: %s (%d episodes)", feed_path, len(episodes))


def publish(mp3_path: Path, episode_title: str, show_notes: str) -> None:
    settings = load_settings()
    today = datetime.now(timezone.utc)
    tag = f"ep-{today.strftime('%Y-%m-%d')}"
    title = f"{today.strftime('%b %d, %Y')} — {episode_title}"

    url = _upload_release(mp3_path, tag, title)

    episodes = [ep for ep in _load_episodes() if ep["tag"] != tag]
    episodes.insert(0, {
        "tag": tag,
        "title": title,
        "url": url,
        "published": today.isoformat(),
        "size_bytes": mp3_path.stat().st_size,
        "show_notes": show_notes,
    })
    episodes = _prune_old_releases(episodes, settings["episode"]["keep_last"])

    EPISODES_JSON.write_text(
        json.dumps(episodes, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _build_feed(episodes, settings)
    log.info("Published %s -> %s", tag, url)
