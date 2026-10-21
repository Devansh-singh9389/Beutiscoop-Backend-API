import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from requests import HTTPError, RequestException, Timeout
import logging

from catagory import get_category_data, get_listing_data
from home import get_home_data
from movie import get_movie_data
from search import search_anime
from series import get_series_data
from series_ep import get_episode_data
from scraper_utils import set_scraper_api_enabled


app = FastAPI(title="Beutiscoop API", version="1.0.0")
logger = logging.getLogger("beutiscoop.api")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _read_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(
        f"{name} must be one of: true, false, 1, 0, yes, no, on, off"
    )


use_ScraperAPI = _read_bool_env("USE_SCRAPER_API")
set_scraper_api_enabled(use_ScraperAPI)


def run_scraper(scraper, *args):
    try:
        return scraper(*args)
    except Timeout as exc:
        logger.warning("Upstream timeout in %s: %s", scraper.__name__, exc)
        raise HTTPException(
            status_code=504,
            detail="The content provider took too long to respond",
        ) from exc
    except HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        logger.warning(
            "Upstream HTTP error in %s: status=%s url=%s",
            scraper.__name__,
            status_code,
            exc.request.url if exc.request is not None else "unknown",
        )
        raise HTTPException(
            status_code=502,
            detail="The content provider returned an unavailable response",
        ) from exc
    except RequestException as exc:
        logger.warning("Upstream connection error in %s: %s", scraper.__name__, exc)
        raise HTTPException(status_code=502, detail="Upstream content is unavailable") from exc
    except RuntimeError as exc:
        logger.error("Scraper configuration error in %s: %s", scraper.__name__, exc)
        raise HTTPException(status_code=503, detail="The content provider is not configured") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/home")
def home(page: int = Query(default=1, ge=1)):
    return run_scraper(get_home_data, page)


@app.get("/api/search")
def search(q: str = Query(min_length=1, max_length=100)):
    return run_scraper(search_anime, q)


@app.get("/api/series")
def series_listing(page: int = Query(default=1, ge=1)):
    return run_scraper(get_listing_data, "series", page)


@app.get("/api/movies")
def movie_listing(page: int = Query(default=1, ge=1)):
    return run_scraper(get_listing_data, "movies", page)


@app.get("/api/category/{category_type}")
def category_listing(category_type: str, page: int = Query(default=1, ge=1)):
    if category_type not in {"anime", "cartoon"}:
        raise HTTPException(status_code=400, detail="Unsupported category listing")
    return run_scraper(get_listing_data, category_type, page)


@app.get("/api/movie/{slug}")
def movie(slug: str):
    return run_scraper(get_movie_data, slug)


@app.get("/api/series/{slug}")
def series(slug: str):
    return run_scraper(get_series_data, slug)


@app.get("/api/episode/{slug}")
def episode(slug: str):
    return run_scraper(get_episode_data, slug)


@app.get("/api/category/{category_type}/{slug}")
def category(category_type: str, slug: str, page: int = Query(default=1, ge=1)):
    if category_type not in {"franchise", "genre", "language", "anime", "cartoon"}:
        raise HTTPException(status_code=400, detail="Unsupported category type")
    return run_scraper(get_category_data, category_type, slug, page)
