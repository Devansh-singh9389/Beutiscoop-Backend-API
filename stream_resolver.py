import logging
import os
import re
import time
import json
from urllib.parse import urlparse
import requests

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth 

logger = logging.getLogger("beutiscoop.stream_resolver")

class StreamResolutionError(RuntimeError):
    pass

# --- PERSISTENT CACHE SETUP ---
CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "stream_cache.json")
CACHE_TTL = 7200  # 2 hours in seconds

_stream_cache = {}

def _load_cache():
    """Load the cache from the JSON file on startup."""
    global _stream_cache
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                _stream_cache = json.load(f)
        except (json.JSONDecodeError, IOError) as exc:
            logger.warning("Failed to load cache file, starting fresh: %s", exc)
            _stream_cache = {}

def _save_cache():
    """Save the cache to the JSON file, purging expired entries first."""
    current_time = time.time()
    
    # Remove expired items to prevent the JSON file from growing endlessly
    expired_keys = [
        url for url, data in _stream_cache.items() 
        if current_time - data.get("timestamp", 0) >= CACHE_TTL
    ]
    for key in expired_keys:
        del _stream_cache[key]
        
    try:
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
        with open(CACHE_FILE, "w") as f:
            json.dump(_stream_cache, f, indent=4)
    except IOError as exc:
        logger.warning("Failed to save cache file: %s", exc)

# Initialize cache into memory when this module is imported
_load_cache()

def get_cached_stream(url: str) -> dict | None:
    if url in _stream_cache:
        data = _stream_cache[url]
        timestamp = data.get("timestamp", 0)
        if time.time() - timestamp < CACHE_TTL:
            return data.get("result")
    return None

def set_cached_stream(url: str, result: dict):
    _stream_cache[url] = {
        "result": result,
        "timestamp": time.time()
    }
    _save_cache()
# ------------------------------

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


def _playwright_fallback(embed_url: str) -> dict | None:
    start_time = time.time()
    logger.info("Starting Playwright fallback for: %s", embed_url)
    
    try:
        with Stealth().use_sync(sync_playwright()) as p:
            browser = p.chromium.launch(
                headless=False,
                args=[
                    "--window-position=-32000,-32000",
                    "--mute-audio",
                    "--autoplay-policy=no-user-gesture-required"
                ]
            )
            
            context = browser.new_context(
                user_agent=_ZEPHYRIX_HEADERS["User-Agent"],
                extra_http_headers={"Referer": "https://watchanimeworld.one/"}
            )
            
            main_page = context.new_page()
            
            def close_popups(new_page):
                if new_page != main_page:
                    logger.debug("[!] Blocked a popup tab.")
                    new_page.close()
                    
            context.on("page", close_popups)
            
            found_m3u8 = {"value": None}

            def intercept_request(request):
                if "master.m3u8" in request.url and not found_m3u8["value"]:
                    logger.info("[+] Master .m3u8 Link Found Automatically!")
                    found_m3u8["value"] = request.url
                    
            main_page.on("request", intercept_request)
            main_page.goto(embed_url)
            main_page.wait_for_timeout(4000) 
            
            viewport = main_page.viewport_size
            center_x = viewport['width'] / 2 if viewport else 400
            center_y = viewport['height'] / 2 if viewport else 300
            
            logger.info("Bypassing ad overlays and 'verify human' checks...")
            
            for i in range(6):
                if found_m3u8["value"]:
                    break
                logger.debug(f"[*] Simulating click {i+1} at center...")
                main_page.mouse.click(x=center_x, y=center_y)
                main_page.wait_for_timeout(2000) 
                
            for _ in range(10):
                if found_m3u8["value"]:
                    break
                main_page.wait_for_timeout(1000)
                
            browser.close()
            
            execution_time = time.time() - start_time
            logger.info(f"Playwright fallback execution time: {execution_time:.2f} seconds")

            if found_m3u8["value"]:
                return {
                    "direct_stream_url": found_m3u8["value"],
                    "direct_stream_type": "hls"
                }
    except Exception as exc:
        logger.error("Playwright fallback error: %s", exc)
        
    return None


def resolve_direct_stream(embed_url: str) -> dict:
    if not _enabled():
        return {}
        
    valid, validation_error = _validate_url(embed_url)
    if not valid:
        return {"direct_stream_error": validation_error}

    # 1. Check Cache
    cached_result = get_cached_stream(embed_url)
    if cached_result:
        logger.info("Serving direct stream from JSON cache for: %s", embed_url)
        return cached_result

    # 2. Try yt-dlp first
    result = None
    try:
        result = _direct_format(_extract_info(embed_url))
    except (OSError, StreamResolutionError, ValueError) as exc:
        logger.warning("Direct stream resolution failed for %s: %s", embed_url, exc)
    
    # 3. If yt-dlp fails, ONLY trigger Playwright fallback for bysewihe.com
    if not result:
        parsed = urlparse(embed_url)
        if parsed.hostname and "bysewihe.com" in parsed.hostname:
            fallback_result = _playwright_fallback(embed_url)
            if fallback_result:
                set_cached_stream(embed_url, fallback_result)
                return fallback_result
        return {"direct_stream_error": "The authorized source did not provide a direct stream"}
        
    # 4. Return and Cache yt-dlp result
    direct_url, stream_type = result
    final_result = {
        "direct_stream_url": direct_url,
        "direct_stream_type": stream_type,
    }
    set_cached_stream(embed_url, final_result)
    return final_result


def resolve_first_direct_stream(urls: list[str]) -> dict:
    for url in urls:
        result = resolve_direct_stream(url)
        if result.get("direct_stream_url"):
            return result
    if _enabled():
        return {"direct_stream_error": "No direct HLS or MP4 stream was provided"}
    return {}