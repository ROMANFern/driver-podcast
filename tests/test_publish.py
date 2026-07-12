import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import publish


class PublishTests(unittest.TestCase):
    def test_build_feed_includes_spotify_metadata(self):
        settings = {
            "podcast": {
                "title": "Manusha's Daily Drive",
                "author": "Daily Drive Bot",
                "description": "Daily briefing",
                "language": "en",
                "base_url": "https://example.com/podcast",
                "feed_slug": "private-feed",
                "category": "Technology",
                "artwork": "podcast-cover.png",
                "owner_email_env": "SPOTIFY_OWNER_EMAIL",
            }
        }
        episodes = [{
            "title": "Episode",
            "url": "https://example.com/episode.mp3",
            "show_notes": "Notes",
            "published": "2026-06-16T00:00:00+00:00",
            "size_bytes": 1234,
        }]

        with tempfile.TemporaryDirectory() as tmp, patch.object(
            publish, "DOCS_DIR", Path(tmp)
        ), patch.dict(
            os.environ, {"SPOTIFY_OWNER_EMAIL": "owner@example.com"}, clear=False
        ):
            publish._build_feed(episodes, settings)
            xml = (Path(tmp) / "feed-private-feed.xml").read_text(encoding="utf-8")

        self.assertIn("<itunes:owner>", xml)
        self.assertIn("<itunes:email>owner@example.com</itunes:email>", xml)
        self.assertIn("<itunes:image href=\"https://example.com/podcast/podcast-cover.png\"", xml)
        self.assertIn("<itunes:category text=\"Technology\"", xml)
        self.assertNotIn("<itunes:block>yes</itunes:block>", xml)


if __name__ == "__main__":
    unittest.main()
