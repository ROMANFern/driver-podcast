import os
import unittest
from unittest.mock import MagicMock, patch

from src.collect_youtube import (
    _build_transcript_api,
    _fetch_transcript,
    _fetch_with_language_fallback,
)


class TranscriptSnippet:
    def __init__(self, text):
        self.text = text


class Transcript:
    language_code = "ja"
    is_translatable = True

    def translate(self, language):
        self.translated_to = language
        return self

    def fetch(self):
        return [TranscriptSnippet("translated captions")]


class CollectYouTubeTests(unittest.TestCase):
    def test_fetch_transcript_joins_and_truncates_snippets(self):
        api = MagicMock()
        api.fetch.return_value = [
            TranscriptSnippet("hello"),
            TranscriptSnippet("world"),
        ]

        result = _fetch_transcript(api, "video", 8, ["en"])

        self.assertEqual(result, "hello wo")

    def test_falls_back_to_translated_available_transcript(self):
        from youtube_transcript_api._errors import NoTranscriptFound

        api = MagicMock()
        api.fetch.side_effect = NoTranscriptFound("video", ["en"], [])
        transcript = Transcript()
        api.list.return_value = [transcript]

        result = _fetch_with_language_fallback(api, "video", ["en"])

        self.assertEqual(result[0].text, "translated captions")
        self.assertEqual(transcript.translated_to, "en")

    @patch.dict(
        os.environ,
        {
            "YOUTUBE_WEBSHARE_PROXY_USERNAME": "user",
            "YOUTUBE_WEBSHARE_PROXY_PASSWORD": "pass",
            "YOUTUBE_PROXY_LOCATIONS": "au, us",
        },
        clear=True,
    )
    def test_builds_webshare_proxy_client_from_environment(self):
        with patch("youtube_transcript_api.YouTubeTranscriptApi") as api_class:
            _build_transcript_api()

        proxy_config = api_class.call_args.kwargs["proxy_config"]
        self.assertEqual(proxy_config.proxy_username, "user")
        self.assertEqual(proxy_config.proxy_password, "pass")
        self.assertIn("user-AU-US-rotate", proxy_config.to_requests_dict()["https"])


if __name__ == "__main__":
    unittest.main()
