"""Generate the episode as a NotebookLM Audio Overview (two-host AI podcast).

Uses the unofficial notebooklm-py client against consumer NotebookLM (works
with a Google AI Pro account; the official API is Enterprise-only). Flow:
render the day's content into one markdown source -> new notebook -> generate
Audio Overview -> download MP3 -> delete the notebook.

Auth: run `notebooklm login` locally once, then put the contents of
~/.notebooklm/profiles/default/storage_state.json into the NOTEBOOKLM_AUTH_JSON
secret/env var. Sessions expire eventually; the pipeline falls back to the
script-writer + Edge TTS path, and you re-run `notebooklm login` when you
notice the host style changed back to single-voice.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from .common import ensure_output_dir, get_logger, load_settings

log = get_logger("notebooklm")


def build_brief_document(brief: dict, videos: list[dict], playlist: dict | None) -> str:
    """Render research + videos + playlist into one markdown source document."""
    today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
    lines = [f"# Daily Drive briefing — {today}", ""]

    for topic, items in brief["topics"].items():
        if not items:
            continue
        lines.append(f"## {topic} news")
        for it in items:
            lines.append(f"### {it['headline']}")
            lines.append(it.get("summary", ""))
            if it.get("why_it_matters"):
                lines.append(f"Why it matters: {it['why_it_matters']}")
            if it.get("source"):
                lines.append(f"(Source: {it['source']})")
            lines.append("")

    if videos:
        lines.append("## New videos from favorite YouTube creators")
        for v in videos:
            lines.append(f"### {v['channel']}: {v['title']}")
            lines.append(v["content"][:6000])
            lines.append("")

    if playlist:
        lines.append("## Today's refreshed Spotify playlist (Daily Drive Mix)")
        lines.extend(f"- {t}" for t in playlist["track_names"][:8])
        lines.append("")

    return "\n".join(lines)


async def _generate_async(doc: str, out_path: Path, cfg: dict) -> None:
    from notebooklm import AudioFormat, AudioLength, NotebookLMClient

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    async with NotebookLMClient.from_storage() as client:
        nb = await client.notebooks.create(f"Daily Drive {today}")
        try:
            await client.sources.add_text(
                nb.id, title="Today's briefing", content=doc
            )
            status = await client.artifacts.generate_audio(
                nb.id,
                audio_format=AudioFormat[cfg["audio_format"]],
                audio_length=AudioLength[cfg["audio_length"]],
                instructions=cfg["instructions"],
            )
            final = await client.artifacts.wait_for_completion(
                nb.id, status.task_id, timeout=cfg.get("timeout_seconds", 1500)
            )
            if not final.is_complete:
                raise RuntimeError(f"Audio generation did not complete: {final}")
            await client.artifacts.download_audio(nb.id, str(out_path))
        finally:
            # One audio per notebook, and we don't want daily notebook litter
            await client.notebooks.delete(nb.id)


def generate_episode(brief: dict, videos: list[dict], playlist: dict | None,
                     out_name: str = "episode.mp3") -> Path:
    cfg = load_settings()["notebooklm"]
    out_dir = ensure_output_dir()
    out_path = out_dir / out_name

    doc = build_brief_document(brief, videos, playlist)
    (out_dir / "brief_doc.md").write_text(doc, encoding="utf-8")
    log.info("Generating NotebookLM Audio Overview (%s/%s) from %d-char brief",
             cfg["audio_format"], cfg["audio_length"], len(doc))

    asyncio.run(_generate_async(doc, out_path, cfg))

    size_mb = out_path.stat().st_size / 1e6
    if size_mb < 1:
        raise RuntimeError("NotebookLM audio suspiciously small — treating as failure")
    log.info("Episode audio: %s (%.1f MB)", out_path, size_mb)
    return out_path


if __name__ == "__main__":
    import sys

    brief = json.load(open(sys.argv[1], encoding="utf-8"))
    videos = json.load(open(sys.argv[2], encoding="utf-8")) if len(sys.argv) > 2 else []
    print(generate_episode(brief, videos, None))
