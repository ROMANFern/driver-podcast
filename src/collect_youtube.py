"""Collect new videos from configured YouTube channels and fetch transcripts.

Uses the public per-channel RSS feed (no API key) to find videos published in
the last `youtube.lookback_hours`, then youtube-transcript-api for transcripts.
YouTube commonly blocks cloud-provider IPs, so the transcript client supports
optional Webshare residential or generic proxies configured through env vars.
If transcripts still fail, the episode falls back to feed metadata.
"""

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser

from .common import get_logger, load_settings, load_yaml

log = get_logger("collect_youtube")

FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


def _build_transcript_api() -> Any:
    """Build one reusable youtube-transcript-api client, optionally proxied."""
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

    webshare_username = os.environ.get("YOUTUBE_WEBSHARE_PROXY_USERNAME")
    webshare_password = os.environ.get("YOUTUBE_WEBSHARE_PROXY_PASSWORD")
    http_proxy = os.environ.get("YOUTUBE_HTTP_PROXY")
    https_proxy = os.environ.get("YOUTUBE_HTTPS_PROXY")

    if webshare_username and webshare_password:
        locations = [
            value.strip().lower()
            for value in os.environ.get("YOUTUBE_PROXY_LOCATIONS", "").split(",")
            if value.strip()
        ]
        log.info("Using Webshare residential proxy for YouTube transcripts")
        return YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(
                proxy_username=webshare_username,
                proxy_password=webshare_password,
                filter_ip_locations=locations or None,
            )
        )

    if http_proxy or https_proxy:
        log.info("Using generic proxy for YouTube transcripts")
        return YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(
                http_url=http_proxy,
                https_url=https_proxy or http_proxy,
            )
        )

    if webshare_username or webshare_password:
        log.warning(
            "Both YOUTUBE_WEBSHARE_PROXY_USERNAME and "
            "YOUTUBE_WEBSHARE_PROXY_PASSWORD are required; using direct access"
        )
    return YouTubeTranscriptApi()


def _fetch_with_language_fallback(api: Any, video_id: str,
                                  languages: list[str]) -> Any:
    """Fetch preferred captions, or translate/fetch another available track."""
    from youtube_transcript_api._errors import NoTranscriptFound

    try:
        return api.fetch(video_id, languages=languages)
    except NoTranscriptFound:
        transcript_list = api.list(video_id)
        available = list(transcript_list)
        if not available:
            raise

        target_language = languages[0].split("-")[0]
        for transcript in available:
            if transcript.is_translatable:
                log.info(
                    "No preferred transcript for %s; translating %s to %s",
                    video_id, transcript.language_code, target_language,
                )
                return transcript.translate(target_language).fetch()

        transcript = available[0]
        log.info(
            "No preferred/translated transcript for %s; using %s",
            video_id, transcript.language_code,
        )
        return transcript.fetch()


def _fetch_transcript(api: Any, video_id: str, max_chars: int,
                      languages: list[str]) -> str | None:
    try:
        from youtube_transcript_api._errors import IpBlocked, RequestBlocked

        for attempt in range(2):
            try:
                fetched = _fetch_with_language_fallback(api, video_id, languages)
                text = " ".join(snippet.text for snippet in fetched)
                return text[:max_chars]
            except (IpBlocked, RequestBlocked) as e:
                log.warning(
                    "YouTube blocked transcript requests for %s (%s). "
                    "Configure residential proxy secrets; feed metadata will be used.",
                    video_id, type(e).__name__,
                )
                return None
            except Exception as e:  # noqa: BLE001 - library raises many types
                if attempt == 0:
                    time.sleep(3)
                else:
                    log.warning(
                        "Transcript unavailable for %s (%s): %s",
                        video_id, type(e).__name__, e,
                    )
    except ImportError:
        log.warning("youtube-transcript-api not installed; skipping transcripts")
    return None


def collect() -> list[dict]:
    settings = load_settings()["youtube"]
    channels = load_yaml("channels.yaml")["channels"]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings["lookback_hours"])
    languages = settings.get("transcript_languages", ["en", "en-US", "en-GB"])

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

    if videos:
        try:
            transcript_api = _build_transcript_api()
        except ImportError:
            log.warning("youtube-transcript-api not installed; skipping transcripts")
            transcript_api = None

        for v in videos:
            transcript = (
                _fetch_transcript(
                    transcript_api,
                    v["video_id"],
                    settings["max_transcript_chars"],
                    languages,
                )
                if transcript_api else None
            )
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
