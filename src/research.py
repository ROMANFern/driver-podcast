"""Research agent: Google News RSS per topic + LLM dedupe/rank/summarize.

Google News RSS is free and needs no API key. The LLM (free tier, see
src/llm.py) turns the raw headlines into ranked, summarized items for the
script writer.
"""

import json
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser

from .common import get_logger, load_settings, load_yaml
from .llm import chat

log = get_logger("research")

NEWS_RSS = (
    "https://news.google.com/rss/search?q={query}+when:1d&hl=en-US&gl=US&ceid=US:en"
)

RESEARCH_PROMPT = """\
Today is {today}. You are the research agent for a personalized daily podcast.

Topic: {topic}
Editorial guidance: {guidance}

Below are raw news items from the last 24 hours (Google News). Deduplicate
stories covered by multiple outlets, drop weak/clickbait/off-topic items, rank
by how interesting they are to an enthusiast, and pick the top {n}.

Raw items (JSON):
{articles_json}

Return ONLY a JSON array (no prose, no markdown fence) where each item is:
{{"headline": "...", "summary": "2-4 sentence summary with the key details",
  "why_it_matters": "1 sentence", "source": "publication name", "url": "..."}}
Base summaries strictly on the items above; do not invent details.
"""


def _fetch_news(query: str, max_items: int = 30) -> list[dict]:
    feed = feedparser.parse(NEWS_RSS.format(query=quote_plus(query)))
    articles = []
    for entry in feed.entries[:max_items]:
        articles.append(
            {
                "title": entry.title,
                "source": getattr(entry, "source", {}).get("title", ""),
                "published": getattr(entry, "published", ""),
                "summary": re.sub(r"<[^>]+>", "", getattr(entry, "summary", ""))[:400],
                "url": entry.link,
            }
        )
    return articles


def _extract_json(text: str) -> list[dict]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON array in response: {text[:200]}")
    return json.loads(match.group(0))


def research_topic(topic: dict, cfg: dict) -> list[dict]:
    queries = topic.get("queries") or [topic["name"]]
    articles: list[dict] = []
    for q in queries:
        articles.extend(_fetch_news(q))
    if not articles:
        log.warning("No news found for topic '%s'", topic["name"])
        return []
    log.info("Topic '%s': %d raw articles fetched", topic["name"], len(articles))

    text = chat(
        [
            {
                "role": "user",
                "content": RESEARCH_PROMPT.format(
                    today=datetime.now(timezone.utc).strftime("%A, %B %d, %Y"),
                    topic=topic["name"],
                    guidance=topic.get(
                        "guidance", "Cover what an enthusiast would care about."
                    ),
                    n=cfg["items_per_topic"],
                    articles_json=json.dumps(articles, ensure_ascii=False),
                ),
            }
        ]
    )
    items = _extract_json(text)
    log.info("Topic '%s': %d items selected", topic["name"], len(items))
    return items


def research_all() -> dict:
    cfg = load_settings()["research"]
    topics = load_yaml("topics.yaml")["topics"]

    brief: dict = {"date": datetime.now(timezone.utc).isoformat(), "topics": {}}
    for topic in topics:
        try:
            brief["topics"][topic["name"]] = research_topic(topic, cfg)
        except Exception:
            log.exception("Research failed for topic '%s' — continuing", topic["name"])
            brief["topics"][topic["name"]] = []
    return brief


if __name__ == "__main__":
    print(json.dumps(research_all(), indent=2, ensure_ascii=False))
