"""TTS synthesis: script text -> episode MP3 via Edge TTS (free).

edge-tts uses Microsoft Edge's online neural voices. It handles long texts by
splitting internally and streams back MP3, so no chunking or ffmpeg needed.
Browse voices with: python -m edge_tts --list-voices
"""

import asyncio
from pathlib import Path

import edge_tts

from .common import ensure_output_dir, get_logger, load_settings

log = get_logger("synthesize")


async def _synthesize_async(script: str, out_path: Path, cfg: dict) -> None:
    communicate = edge_tts.Communicate(
        script,
        voice=cfg["voice"],
        rate=cfg.get("rate", "+0%"),
    )
    await communicate.save(str(out_path))


def synthesize(script: str, out_name: str = "episode.mp3") -> Path:
    cfg = load_settings()["tts"]
    out_dir = ensure_output_dir()
    out_path = out_dir / out_name

    log.info("Synthesizing %d words with Edge TTS voice %s",
             len(script.split()), cfg["voice"])
    asyncio.run(_synthesize_async(script, out_path, cfg))

    size = out_path.stat().st_size
    # ~2KB of 48kbps MP3 per spoken word; abort well below that
    if size < len(script.split()) * 200:
        raise RuntimeError("TTS produced a suspiciously small file — aborting")
    log.info("Episode audio: %s (%.1f MB)", out_path, size / 1e6)
    return out_path


if __name__ == "__main__":
    import sys

    script_text = open(sys.argv[1], encoding="utf-8").read()
    synthesize(script_text)
