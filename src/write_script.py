"""Script writer: turns the content brief into a TTS-ready podcast script."""

import json
from datetime import datetime, timezone

from .common import get_logger, load_settings
from .llm import chat

log = get_logger("write_script")

SYSTEM_PROMPT = """\
You are {host_name}, the host of a personalized daily podcast made for one
listener, {listener_name}, who listens during a morning drive.

Write a complete spoken script. Rules:
- Target length: about {target_words} words (roughly 15-20 minutes spoken).
- Plain spoken prose only: no markdown, no headings, no stage directions,
  no sound-effect cues, no host name labels. Just the words to be spoken.
- Conversational, warm, and direct - like a smart friend catching them up.
- Spell out things TTS mispronounces: read URLs as publication names, expand
  unusual acronyms on first use, write numbers the way you'd say them.
- Structure: short cold open teasing the best stories; the news segments by
  topic; a "from your creators" segment covering the new YouTube videos
  (attribute each to its channel); a brief outro.
- Be selective: skip weak items rather than padding. Add brief context or your
  own take where it helps, but never invent facts not in the brief.
"""

USER_PROMPT = """\
Today is {today}. Here is this morning's content brief as JSON.

News research by topic:
{news_json}

New YouTube videos (with transcripts or descriptions):
{videos_json}

Write today's full episode script now. Output only the script text.
"""


def write_script(brief: dict, videos: list[dict]) -> str:
    settings = load_settings()
    cfg = settings["script"]

    # Keep video payload compact for the prompt
    video_summaries = [
        {
            "channel": v["channel"],
            "title": v["title"],
            "content": v["content"][:8000],
        }
        for v in videos
    ]

    script = chat(
        [
            {
                "role": "system",
                "content": SYSTEM_PROMPT.format(
                    host_name=cfg["host_name"],
                    listener_name=cfg["listener_name"],
                    target_words=settings["episode"]["target_words"],
                ),
            },
            {
                "role": "user",
                "content": USER_PROMPT.format(
                    today=datetime.now(timezone.utc).strftime("%A, %B %d, %Y"),
                    news_json=json.dumps(brief["topics"], ensure_ascii=False),
                    videos_json=json.dumps(video_summaries, ensure_ascii=False),
                ),
            },
        ]
    ).strip()

    log.info("Script written: %d words", len(script.split()))
    return script


if __name__ == "__main__":
    import sys

    brief = json.load(open(sys.argv[1], encoding="utf-8"))
    videos = json.load(open(sys.argv[2], encoding="utf-8")) if len(sys.argv) > 2 else []
    print(write_script(brief, videos))
