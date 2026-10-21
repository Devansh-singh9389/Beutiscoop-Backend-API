# Beutiscoop Backend API

This project provides a request-driven FastAPI backend for Beutiscoop content.
The frontend sends the page or item the user selected, and the backend fetches
only that requested content from the upstream source and returns JSON.

The backend does not crawl every page at startup.

## Requirements

- Python 3.10+
- Internet access to the upstream content provider

## Installation

From the project directory:

```powershell
cd C:\Code\beutiscoop
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Start the API

Set the ScraperAPI key in the environment before starting the API:

```powershell
$env:SCRAPER_API_KEY = "your-scraperapi-key"
```

Do not commit the key to the repository. If a key was previously committed or
shared publicly, revoke it in ScraperAPI and create a replacement.

```powershell
python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

The API base URL is:

```text
http://127.0.0.1:8000
```

Interactive API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

## API endpoints

### Health

```http
GET /api/health
```

Response:

```json
{
  "status": "ok"
}
```

### Home data

```http
GET /api/home
```

Returns the home page sections, navigation, media cards, networks, languages,
and trending content.

The home page currently has no numbered upstream pages. `GET /api/home?page=1`
is supported; requesting another page returns `400`.

### Series listing

```http
GET /api/series
```

### Movie listing

```http
GET /api/movies
```

### Anime listing

```http
GET /api/category/anime
```

### Cartoon listing

```http
GET /api/category/cartoon
```

All numbered listings accept a `page` query parameter:

```http
GET /api/movies?page=2
GET /api/series?page=2
GET /api/category/anime?page=2
GET /api/category/cartoon?page=2
```

The response includes pagination metadata:

```json
{
  "pagination": {
    "current_page": 2,
    "total_pages": 11,
    "pages": [
      {
        "page": 1,
        "route": "/movies"
      },
      {
        "page": 2,
        "route": "/movies/page/2"
      }
    ],
    "previous_route": "/movies",
    "next_route": "/movies/page/3"
  }
}
```

Listing responses use this shape:

```json
{
  "type": "listing",
  "title": "Series",
  "url": "https://watchanimeworld.one/series/",
  "total_items": 10,
  "items": [
    {
      "id": "123",
      "title": "Example Series",
      "media_type": "series",
      "route": "/series/example-series",
      "url": "https://watchanimeworld.one/series/example-series/",
      "image": "https://example.com/image.jpg"
    }
  ]
}
```

### Search

```http
GET /api/search?q=ben
```

The `q` parameter is required and must contain between 1 and 100 characters.

### Movie details

```http
GET /api/movie/{slug}
```

Example:

```http
GET /api/movie/ben-10-vs-the-universe-the-movie
```

### Series details

```http
GET /api/series/{slug}
```

Example:

```http
GET /api/series/arifureta-from-commonplace-to-worlds-strongest
```

The response includes seasons and episodes. Each episode contains a frontend
route:

```json
{
  "season_number": 1,
  "episodes": [
    {
      "episode_code": "1",
      "title": "Episode 1",
      "route": "/episode/example-series-1x1",
      "url": "https://watchanimeworld.one/episode/example-series-1x1/"
    }
  ]
}
```

### Episode details and streaming servers

```http
GET /api/episode/{slug}
```

Example:

```http
GET /api/episode/arifureta-from-commonplace-to-worlds-strongest-1x1
```

The response contains the available player servers:

```json
{
  "type": "episode",
  "episode_title": "Example Episode",
  "streaming_servers": [
    {
      "server_id": "options-0",
      "server_name": "Play",
      "audio": "Multi-Audio",
      "embed_url": "https://player.example.com/video/123"
    }
  ],
  "navigation": {
    "series_route": "/series/example-series",
    "previous_episode_route": null,
    "next_episode_route": "/episode/example-series-1x2"
  }
}
```

The frontend should display each `embed_url` in an iframe. It should not fetch
the upstream website directly.

### Category details

```http
GET /api/category/{category_type}/{slug}
```

Supported category types include:

- `franchise`
- `genre`
- `language`
- `anime`
- `cartoon`

Example:

```http
GET /api/category/franchise/ben-10
```

## Frontend integration

The frontend should use the backend API as the only data source.

### 1. Request a listing

```javascript
const response = await fetch("/api/series");
const data = await response.json();
```

Render each item using its `route`:

```javascript
function openItem(item) {
  window.history.pushState({}, "", item.route);
  loadPage(item.route);
}
```

### 2. Convert frontend routes to API requests

Frontend routes are navigation routes. They are not upstream URLs.

```javascript
function apiPathFromRoute(route) {
  const parts = route.split("/").filter(Boolean);

  if (parts.length === 0) {
    return "/api/home";
  }

  if (["movie", "series", "episode"].includes(parts[0])) {
    return `/api/${parts[0]}/${encodeURIComponent(parts[1])}`;
  }

  if (parts[0] === "category" && parts.length >= 3) {
    return `/api/category/${encodeURIComponent(parts[1])}/${encodeURIComponent(parts[2])}`;
  }

  return "/api/home";
}
```

### 3. Load the selected page

```javascript
async function loadPage(frontendRoute) {
  const apiPath = apiPathFromRoute(frontendRoute);
  const response = await fetch(apiPath);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "API request failed");
  }

  return response.json();
}
```

### 4. Load a selected video server

```javascript
function playServer(server) {
  const iframe = document.querySelector("#video-player");
  iframe.src = server.embed_url;
}
```

The frontend should use the `navigation` routes from an episode response for
previous, next, and series navigation:

```javascript
openItem({ route: episode.navigation.next_episode_route });
```

Do not send arbitrary external URLs to the backend. Send a known route or slug,
for example:

```text
/movie/ben-10-vs-the-universe-the-movie
/series/arifureta-from-commonplace-to-worlds-strongest
/episode/arifureta-from-commonplace-to-worlds-strongest-1x1
```

## Error responses

### Invalid request

```text
400 Bad Request
```

Returned for invalid values such as an unsupported category type.

### Upstream unavailable

```text
502 Bad Gateway
```

Returned when the upstream provider returns an unavailable response or cannot
be reached.

### Upstream timeout

```text
504 Gateway Timeout
```

Returned when the upstream provider does not respond within the configured
timeout.

Example error:

```json
{
  "detail": "The content provider took too long to respond"
}
```

The backend retries temporary upstream failures and uses connection/read
timeouts. A frontend should display the `detail` value to the user instead of
assuming a successful JSON payload.

## Project files

- [api.py](./api.py): FastAPI routes and error handling
- [scraper_utils.py](./scraper_utils.py): shared upstream HTTP session, retries, and URL helpers
- [home.py](./home.py): home page parser
- [catagory.py](./catagory.py): listing and category parser
- [search.py](./search.py): search parser
- [movie.py](./movie.py): movie details parser
- [series.py](./series.py): series and season parser
- [series_ep.py](./series_ep.py): episode and streaming server parser
- [requirements.txt](./requirements.txt): Python dependencies
