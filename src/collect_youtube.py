"""Collect new videos from configured YouTube channels and fetch transcripts.

Uses the public per-channel RSS feed (no API key) to find videos published in
the last `youtube.lookback_hours`, then youtube-transcript-api for transcripts.
Transcript fetching can be blocked from datacenter IPs; in that case we fall
back to the title + description from the feed so the episode still ships.
"""

import time
from datetime import datetime, timedelta, timezone

import feedparser

from .common import get_logger, load_settings, load_yaml

log = get_logger("collect_youtube")

FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


def _fetch_transcript(video_id: str, max_chars: int) -> str | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        for attempt in range(2):
            try:
                api = YouTubeTranscriptApi()
                fetched = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
                text = " ".join(snippet.text for snippet in fetched)
                return text[:max_chars]
            except Exception as e:  # noqa: BLE001 - library raises many types
                if attempt == 0:
                    time.sleep(3)
                else:
                    log.warning("Transcript unavailable for %s: %s", video_id, e)
    except ImportError:
        log.warning("youtube-transcript-api not installed; skipping transcripts")
    return None


def collect() -> list[dict]:
    settings = load_settings()["youtube"]
    channels = load_yaml("channels.yaml")["channels"]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings["lookback_hours"])

    videos: list[dict] = []
    for ch in channels:
        feed = feedparser.parse(FEED_URL.format(channel_id=ch["channel_id"]))
        if feed.bozo and not feed.entries:
            log.warning("Could not fetch feed for %s", ch["name"])
            continue
        for entry in feed.entries:
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            if published < cutoff:
                continue
            video_id = entry.yt_videoid
            videos.append(
                {
                    "channel": ch["name"],
                    "title": entry.title,
                    "url": entry.link,
                    "published": published.isoformat(),
                    "video_id": video_id,
                    "description": getattr(entry, "summary", "")[:1000],
                }
            )

    # Newest first, capped so one prolific channel can't flood the episode
    videos.sort(key=lambda v: v["published"], reverse=True)
    videos = videos[: settings["max_videos_per_day"]]

    for v in videos:
        transcript = _fetch_transcript(v["video_id"], settings["max_transcript_chars"])
        v["transcript"] = transcript
        v["content"] = transcript or v["description"] or v["title"]

    log.info(
        "Collected %d new videos (%d with transcripts)",
        len(videos),
        sum(1 for v in videos if v["transcript"]),
    )
    return videos


if __name__ == "__main__":
    import json

    print(json.dumps(collect(), indent=2, ensure_ascii=False))
