import logging
import os
import re
from urllib.parse import urlparse

import requests


logger = logging.getLogger("beutiscoop.stream_resolver")


class StreamResolutionError(RuntimeError):
    pass


def _enabled() -> bool:
    return os.getenv("RESOLVE_DIRECT_STREAMS", "").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _allowed_hosts() -> set[str]:
    return {
        host.strip().lower()
        for host in os.getenv("DIRECT_STREAM_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    }


def _validate_url(url: str) -> tuple[bool, str | None]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False, "The embed URL is not an HTTP(S) URL"
    if parsed.hostname.lower() not in _allowed_hosts():
        return False, "The embed host is not in DIRECT_STREAM_ALLOWED_HOSTS"
    return True, None


def _extract_info(url: str) -> dict:
    try:
        import yt_dlp
    except ImportError as exc:
        raise StreamResolutionError("yt-dlp is not installed") from exc

    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 15,
        "extract_flat": False,
    }
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            return downloader.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise StreamResolutionError(str(exc)) from exc


def _direct_format(info: dict) -> tuple[str, str] | None:
    formats = info.get("formats") or []
    candidates = [info, *formats]
    for item in candidates:
        direct_url = item.get("url")
        if not direct_url:
            continue
        protocol = str(item.get("protocol") or "").lower()
        extension = str(item.get("ext") or "").lower()
        if protocol in {"m3u8", "m3u8_native"}:
            return direct_url, "hls"
        if extension == "mp4" or protocol in {"http", "https"} and ".mp4" in direct_url.lower():
            return direct_url, "mp4"
    return None


_ZEPHYRIX_STREAM_PATTERN = re.compile(
    r'https?://[^\s"\'<>]+(?:\.m3u8|\.mp4|master\.txt)[^\s"\'<>]*',
    re.IGNORECASE,
)
_ZEPHYRIX_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _unpack_dean_edwards(packed_js: str) -> str:
    pattern = r"\}\('(.*)',\s*(\d+),\s*(\d+),\s*'([^']*)'\.split\('\|'\)"
    match = re.search(pattern, packed_js, re.DOTALL)
    if not match:
        return ""

    payload, radix, _count, symtab = match.groups()
    radix = int(radix)
    keywords = symtab.split("|")

    def lookup(value: str) -> str:
        number = 0
        for char in value:
            if "0" <= char <= "9":
                digit = ord(char) - ord("0")
            elif "a" <= char <= "z":
                digit = ord(char) - ord("a") + 10
            elif "A" <= char <= "Z":
                digit = ord(char) - ord("A") + 36
            else:
                return value
            number = number * radix + digit
        return keywords[number] if number < len(keywords) and keywords[number] else value

    return re.sub(r"\b\w+\b", lambda match: lookup(match.group(0)), payload).replace(
        "\\/", "/"
    )


def _zephyrix_result(url: str) -> dict | None:
    stream_match = _ZEPHYRIX_STREAM_PATTERN.search(url)
    if not stream_match:
        return None
    direct_url = stream_match.group(0).replace("\\/", "/")
    return {
        "direct_stream_url": direct_url,
        "direct_stream_type": (
            "hls"
            if any(marker in direct_url.lower() for marker in (".m3u8", "master.txt", "/hls/"))
            else "mp4"
        ),
    }


def resolve_zephyrix_stream(embed_url: str, parent_url: str) -> dict:
    """Resolve a direct stream from a play.zephyrix.org embed."""
    if urlparse(embed_url).hostname != "play.zephyrix.org":
        return {"direct_stream_error": "The embed URL is not a Play Zephyrix URL"}

    headers = {
        **_ZEPHYRIX_HEADERS,
        "Referer": parent_url,
        "Origin": "https://watchanimeworld.one",
        "Sec-Fetch-Dest": "iframe",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
    }
    try:
        response = requests.get(embed_url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Zephyrix request failed for %s: %s", embed_url, exc)
        return {"direct_stream_error": f"Failed to fetch Zephyrix embed: {exc}"}

    result = _zephyrix_result(response.text)
    if result:
        return result

    html = response.text
    if "eval(function(p,a,c,k,e,d)" in html:
        result = _zephyrix_result(_unpack_dean_edwards(html))
        if result:
            return result

        video_hash = embed_url.rstrip("/").split("/")[-1]
        api_url = f"https://play.zephyrix.org/player/index.php?data={video_hash}&do=getVideo"
        api_headers = {
            **headers,
            "Referer": embed_url,
            "Origin": "https://play.zephyrix.org",
            "X-Requested-With": "XMLHttpRequest",
        }
        try:
            api_response = requests.post(api_url, headers=api_headers, timeout=8)
            api_response.raise_for_status()
            source = api_response.json().get("videoSource")
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Zephyrix manifest request failed for %s: %s", embed_url, exc)
        else:
            if source:
                result = _zephyrix_result(source.replace("\\/", "/"))
                if result:
                    return result

    return {"direct_stream_error": "Could not extract direct stream link from Zephyrix"}


def resolve_direct_stream(embed_url: str) -> dict:
    """Resolve one authorized direct stream URL, or return an explicit failure."""
    if not _enabled():
        return {}
    valid, validation_error = _validate_url(embed_url)
    if not valid:
        return {"direct_stream_error": validation_error}

    try:
        result = _direct_format(_extract_info(embed_url))
    except (OSError, StreamResolutionError, ValueError) as exc:
        logger.warning("Direct stream resolution failed for %s: %s", embed_url, exc)
        return {"direct_stream_error": "The authorized source did not provide a direct stream"}

    if not result:
        return {"direct_stream_error": "No direct HLS or MP4 stream was provided"}
    direct_url, stream_type = result
    return {
        "direct_stream_url": direct_url,
        "direct_stream_type": stream_type,
    }


def resolve_first_direct_stream(urls: list[str]) -> dict:
    """Return the first direct stream from an authorized list of source URLs."""
    for url in urls:
        result = resolve_direct_stream(url)
        if result.get("direct_stream_url"):
            return result
    if _enabled():
        return {"direct_stream_error": "No direct HLS or MP4 stream was provided"}
    return {}
