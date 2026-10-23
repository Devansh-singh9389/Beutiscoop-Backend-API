import os
import unittest
from unittest.mock import patch

from stream_resolver import (
    resolve_direct_stream,
    resolve_first_direct_stream,
    resolve_zephyrix_stream,
)


class StreamResolverTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("RESOLVE_DIRECT_STREAMS", None)
        os.environ.pop("DIRECT_STREAM_ALLOWED_HOSTS", None)

    def test_disabled_by_default_preserves_existing_behavior(self):
        self.assertEqual(resolve_direct_stream("https://media.example/video"), {})

    def test_rejects_host_not_in_allowlist(self):
        os.environ["RESOLVE_DIRECT_STREAMS"] = "true"
        os.environ["DIRECT_STREAM_ALLOWED_HOSTS"] = "allowed.example"
        result = resolve_direct_stream("https://other.example/video")
        self.assertIn("direct_stream_error", result)

    @patch("stream_resolver._extract_info")
    def test_returns_hls_stream(self, extract_info):
        os.environ["RESOLVE_DIRECT_STREAMS"] = "true"
        os.environ["DIRECT_STREAM_ALLOWED_HOSTS"] = "media.example"
        extract_info.return_value = {
            "formats": [{"url": "https://media.example/video.m3u8", "protocol": "m3u8"}]
        }
        self.assertEqual(
            resolve_direct_stream("https://media.example/player/1"),
            {
                "direct_stream_url": "https://media.example/video.m3u8",
                "direct_stream_type": "hls",
            },
        )

    @patch("stream_resolver._extract_info")
    def test_returns_first_direct_stream(self, extract_info):
        os.environ["RESOLVE_DIRECT_STREAMS"] = "true"
        os.environ["DIRECT_STREAM_ALLOWED_HOSTS"] = "media.example"
        extract_info.return_value = {
            "formats": [{"url": "https://media.example/video.mp4", "ext": "mp4"}]
        }
        result = resolve_first_direct_stream([
            "https://media.example/player/1",
            "https://media.example/player/2",
        ])
        self.assertEqual(result["direct_stream_type"], "mp4")

    @patch("stream_resolver.requests.post")
    @patch("stream_resolver.requests.get")
    def test_returns_zephyrix_hls_stream_and_keeps_embed_separate(
        self, get_request, post_request
    ):
        response = get_request.return_value
        response.text = (
            '<script>file: "https://play.zephyrix.org/cdn/hls/'
            '4d62cf5785b4f71e28240c3c5e0ca2f5/master.txt"</script>'
        )
        result = resolve_zephyrix_stream(
            "https://play.zephyrix.org/video/embed-hash",
            "https://watchanimeworld.one/episode/example/",
        )
        self.assertEqual(
            result,
            {
                "direct_stream_url": (
                    "https://play.zephyrix.org/cdn/hls/"
                    "4d62cf5785b4f71e28240c3c5e0ca2f5/master.txt"
                ),
                "direct_stream_type": "hls",
            },
        )
        post_request.assert_not_called()

    @patch("stream_resolver.requests.get")
    def test_zephyrix_failure_has_error_without_null_direct_url(self, get_request):
        response = get_request.return_value
        response.text = "<html><body>No video source</body></html>"
        result = resolve_zephyrix_stream(
            "https://play.zephyrix.org/video/embed-hash",
            "https://watchanimeworld.one/episode/example/",
        )
        self.assertEqual(
            result,
            {"direct_stream_error": "Could not extract direct stream link from Zephyrix"},
        )


if __name__ == "__main__":
    unittest.main()
