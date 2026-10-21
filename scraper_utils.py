import os
from urllib.parse import urljoin
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import cloudscraper
from dotenv import load_dotenv


BASE_URL = "https://watchanimeworld.one"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def create_http_session():
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        raise_on_status=False,
    )
    
    # Initialize cloudscraper instead of standard requests.Session
    session = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    session.headers.update(HEADERS)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


HTTP_SESSION = create_http_session()
load_dotenv()


def absolute_url(value: str | None) -> str | None:
    if not value:
        return None
    return urljoin(BASE_URL, value)


def frontend_route(url: str | None) -> str | None:
    if not url:
        return None
    path = urlparse(url).path.strip("/")
    if not path:
        return "/"
    parts = path.split("/")
    if parts[0] in {"movies", "series"} and len(parts) >= 3 and parts[1] == "page":
        return f"/{parts[0]}/page/{parts[2]}"
    if parts[0] in {"movies", "series", "episode"} and len(parts) > 1:
        media_type = {"movies": "movie", "series": "series", "episode": "episode"}[parts[0]]
        return f"/{media_type}/{parts[1]}"
    if parts[0] == "category" and len(parts) >= 4 and parts[2] == "page":
        return f"/category/{parts[1]}/page/{parts[3]}"
    if parts[0] == "category" and len(parts) >= 5 and parts[3] == "page":
        return f"/category/{parts[1]}/{parts[2]}/page/{parts[4]}"
    if parts[0] == "category" and len(parts) > 2:
        return f"/category/{parts[1]}/{parts[2]}"
    return f"/{path}"


def pagination_data(soup, current_page: int) -> dict:
    links = []
    next_url = None
    previous_url = None
    for link in soup.select("nav.pagination a[href]"):
        label = link.get_text(" ", strip=True)
        url = absolute_url(link.get("href"))
        if label.upper() == "NEXT":
            next_url = url
        elif label.upper() in {"PREV", "PREVIOUS"}:
            previous_url = url
        elif label.isdigit():
            links.append({"page": int(label), "url": url})
    total_pages = max((item["page"] for item in links), default=current_page)
    return {
        "current_page": current_page,
        "total_pages": total_pages,
        "pages": [
            {
                "page": item["page"],
                "url": item["url"],
                "route": frontend_route(item["url"]),
            }
            for item in links
        ],
        "previous_url": previous_url,
        "previous_route": frontend_route(previous_url),
        "next_url": next_url,
        "next_route": frontend_route(next_url),
    }


import urllib.parse
from bs4 import BeautifulSoup

def _scraper_api_url(url: str) -> str:
    scraper_api_key = os.getenv("SCRAPER_API_KEY")
    if not scraper_api_key:
        raise RuntimeError(
            "SCRAPER_API_KEY environment variable is not configured"
        )

    encoded_url = urllib.parse.quote(url)
    return (
        f"http://api.scraperapi.com?api_key={scraper_api_key}"
        f"&url={encoded_url}"
    )


def fetch_response(
    url: str,
    *,
    method: str = "GET",
    data: dict | None = None,
    headers: dict | None = None,
) -> requests.Response:
    response = HTTP_SESSION.request(
        method,
        _scraper_api_url(url),
        data=data,
        headers=headers,
        timeout=(15, 45),
    )
    response.raise_for_status()
    return response


def fetch_soup(url: str, referer: str | None = None):
    response = fetch_response(
        url,
        headers={"Referer": referer} if referer else None,
    )
    return BeautifulSoup(response.text, "html.parser")