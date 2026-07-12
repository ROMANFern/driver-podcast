import unittest
from datetime import datetime, timezone

from src.pipeline import _episode_filename


class PipelineTests(unittest.TestCase):
    def test_episode_filename_uses_utc_date(self):
        now = datetime(2026, 6, 15, 23, 59, tzinfo=timezone.utc)

        self.assertEqual(_episode_filename(now), "2026-06-15-episode.mp3")


if __name__ == "__main__":
    unittest.main()
