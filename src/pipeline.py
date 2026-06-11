"""Pipeline orchestrator: runs all stages with per-stage fault tolerance.

Usage:
    python -m src.pipeline                  # full run
    python -m src.pipeline --skip tts,spotify,publish   # cheap local test

The episode ships even if YouTube transcripts or Spotify fail; only the
research+script+TTS chain is essential.
"""

import argparse
import json
import sys
from datetime import datetime, timezone

from .common import ensure_output_dir, get_logger

log = get_logger("pipeline")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip", default="",
        help="comma-separated stages to skip: youtube,research,spotify,notebooklm,tts,publish",
    )
    args = parser.parse_args()
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    out_dir = ensure_output_dir()

    # --- 1. YouTube (optional) ---
    videos: list[dict] = []
    if "youtube" not in skip:
        try:
            from .collect_youtube import collect
            videos = collect()
        except Exception:
            log.exception("YouTube stage failed — continuing without videos")
    (out_dir / "videos.json").write_text(
        json.dumps(videos, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- 2. Research (essential) ---
    if "research" in skip:
        brief = {"date": datetime.now(timezone.utc).isoformat(), "topics": {}}
    else:
        from .research import research_all
        brief = research_all()
        if not any(brief["topics"].values()) and not videos:
            log.error("No research results and no videos — nothing to make an episode from")
            return 1
    (out_dir / "brief.json").write_text(
        json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- 3. Spotify (optional; runs before script so the script can mention it) ---
    playlist = None
    if "spotify" not in skip:
        try:
            from .spotify_refresh import refresh_playlist
            playlist = refresh_playlist()
        except Exception:
            log.exception("Spotify stage failed — continuing without playlist")

    # --- 4+5. Audio generation (essential) ---
    if "tts" in skip:
        log.info("Audio generation skipped — stopping before audio/publish")
        return 0

    from .common import load_settings
    engine = load_settings()["audio"]["engine"]
    mp3_path = None

    if engine == "notebooklm" and "notebooklm" not in skip:
        try:
            from .notebooklm_audio import generate_episode
            mp3_path = generate_episode(brief, videos, playlist)
        except Exception:
            log.exception(
                "NotebookLM generation failed — falling back to script + Edge TTS. "
                "(If this keeps happening, re-run `notebooklm login` and update "
                "the NOTEBOOKLM_AUTH_JSON secret.)"
            )

    if mp3_path is None:
        from .write_script import write_script
        script = write_script(brief, videos, playlist)
        (out_dir / "script.txt").write_text(script, encoding="utf-8")
        from .synthesize import synthesize
        mp3_path = synthesize(script)

    # --- 6. Publish ---
    if "publish" in skip:
        log.info("Publish skipped — audio at %s", mp3_path)
        return 0
    from .publish import publish

    # Episode title: first topic headline if available, else date only
    headline = next(
        (items[0]["headline"] for items in brief["topics"].values() if items),
        "Your daily briefing",
    )
    show_notes = _show_notes(brief, videos)
    publish(mp3_path, headline, show_notes)
    return 0


def _show_notes(brief: dict, videos: list[dict]) -> str:
    lines = []
    for topic, items in brief["topics"].items():
        for item in items:
            lines.append(f"[{topic}] {item['headline']} — {item.get('url', '')}")
    for v in videos:
        lines.append(f"[YouTube/{v['channel']}] {v['title']} — {v['url']}")
    return "\n".join(lines) or "Personalized daily briefing."


if __name__ == "__main__":
    sys.exit(main())
