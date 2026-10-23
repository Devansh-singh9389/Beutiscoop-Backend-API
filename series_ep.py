import re

from scraper_utils import absolute_url, fetch_soup, BASE_URL
from stream_resolver import resolve_direct_stream, resolve_zephyrix_stream


def get_episode_data(slug: str):
    episode_url = f"{BASE_URL}/episode/{slug.strip('/')}/"
    soup = fetch_soup(episode_url)
    servers = []
    labels = {}
    for tab in soup.select(".aa-tbs-video li a"):
        target = tab.get("href", "").removeprefix("#")
        name = tab.find("span", class_="server")
        labels[target] = name.get_text(strip=True) if name else target
    for video in soup.select("aside.video-player div.video"):
        iframe = video.find("iframe")
        if iframe:
            server = {
                "server_id": video.get("id"),
                "server_name": labels.get(video.get("id"), video.get("id")),
                "audio": "Multi-Audio",
                "embed_url": absolute_url(iframe.get("src") or iframe.get("data-src")),
            }
            if server["embed_url"]:
                if "play.zephyrix.org" in server["embed_url"]:
                    server.update(resolve_zephyrix_stream(server["embed_url"], episode_url))
                else:
                    server.update(resolve_direct_stream(server["embed_url"]))
            servers.append(server)
    tracking = soup.find(string=re.compile(r"addToWatchHistory"))
    metadata = {}
    if tracking:
        for key in ("postID", "title", "season", "episode", "image"):
            match = re.search(rf'let {key} = "([^"]*)";', tracking)
            metadata[key] = match.group(1) if match else None
    nav = soup.select_one(".epsdsnv")
    series_route = next_route = previous_route = None
    if nav:
        for link in nav.find_all("a", href=True):
            url = absolute_url(link["href"])
            if "/series/" in url:
                series_route = f"/series/{url.rstrip('/').split('/')[-1]}"
            elif "/episode/" in url:
                route = f"/episode/{url.rstrip('/').split('/')[-1]}"
                text = link.get_text(" ", strip=True).lower()
                if "next" in text:
                    next_route = route
                elif "prev" in text:
                    previous_route = route
    return {
        "type": "episode",
        "episode_title": soup.select_one("aside.video-player > div").get_text(strip=True) if soup.select_one("aside.video-player > div") else None,
        "series_title": metadata.get("title"),
        "current_url": episode_url,
        "slug": slug,
        "post_id": metadata.get("postID"),
        "season": int(metadata["season"]) if metadata.get("season", "").isdigit() else None,
        "episode": int(metadata["episode"]) if metadata.get("episode", "").isdigit() else None,
        "poster": absolute_url(metadata.get("image")),
        "navigation": {
            "series_route": series_route,
            "previous_episode_route": previous_route,
            "next_episode_route": next_route,
        },
        "streaming_servers": servers,
    }
