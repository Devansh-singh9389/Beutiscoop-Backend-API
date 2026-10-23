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

Direct upstream requests are used by default. To route requests through
ScraperAPI, enable it in the environment and provide the API key:

```powershell
$env:USE_SCRAPER_API = "true"
$env:SCRAPER_API_KEY = "your-scraperapi-key"
```

Set `USE_SCRAPER_API` to `false`, `0`, `no`, or `off` to bypass ScraperAPI.
When it is unset, ScraperAPI is disabled. `SCRAPER_API_KEY` is required only
when ScraperAPI is enabled.

Do not commit the key to the repository. If a key was previously committed or
shared publicly, revoke it in ScraperAPI and create a replacement.

```powershell
python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

To enable direct HLS/MP4 resolution, set the resolver variables in the same
PowerShell session before starting Uvicorn. The embed host must be explicitly
authorized; for the `MultiCloud2` server shown by the episode endpoint:

```powershell
$env:RESOLVE_DIRECT_STREAMS = "true"
$env:DIRECT_STREAM_ALLOWED_HOSTS = "bysewihe.com"
python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

If Uvicorn is already running, stop and restart it after changing these
variables. Do not add a host unless you are authorized to access and resolve
its streams.

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

### Optional direct stream resolution

The API can optionally resolve one direct HLS or MP4 URL for an authorized
source using `yt-dlp`. This is disabled by default and does not change the
existing `embed_url` response or frontend behavior.

Only enable it for sources you own or are explicitly authorized to access. The
resolver does not bypass anti-bot, anti-debugging, authentication, DRM, or
other provider access controls. Configure an explicit host allowlist:

```powershell
$env:RESOLVE_DIRECT_STREAMS = "true"
$env:DIRECT_STREAM_ALLOWED_HOSTS = "media.example.com,player.example.com"
```

When enabled, episode servers may additionally contain:

```json
{
  "direct_stream_url": "https://media.example.com/video.m3u8",
  "direct_stream_type": "hls"
}
```

If the source does not provide a direct stream, the response includes
`direct_stream_error` and keeps the existing `embed_url`. The resolver is
bounded to one URL and does not crawl playlists.

Movie responses also include a single top-level `vlc_url` when a direct stream
is available:

```text
GET /api/movie/your-authorized-movie-slug
```

Open that `vlc_url` in VLC using **Media > Open Network Stream**. If it is
`null`, the source only supplied a browser player or a protected redirect; VLC
cannot play that page directly.

## Run the frontend

Start the API first, then serve the static files from the `frontend` folder
using Python's built-in static server:

```powershell
cd C:\Code\beutiscoop\frontend
python -m http.server 5500
```

Open `http://127.0.0.1:5500` in your browser. The frontend calls the API at
`http://127.0.0.1:8000`, so both the API and frontend servers must be running.

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
