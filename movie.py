# import base64
# import json
# import urllib.parse

# from scraper_utils import absolute_url, fetch_soup, BASE_URL
# from stream_resolver import resolve_first_direct_stream


# def get_movie_data(slug: str):
#     if not slug:
#         raise ValueError("Movie slug is required")
#     movie_url = f"{BASE_URL}/movies/{slug.strip('/')}/"
#     soup = fetch_soup(movie_url)
#     title_el = soup.find("h1", class_="entry-title")
#     poster = soup.select_one(".dfxb > div img")
#     duration = soup.select_one(".duration .overviewCss")
#     year = soup.select_one(".year .overviewCss")
#     post_id = soup.select_one("#comment_post_ID")
#     servers = []
#     labels = {}
#     for tab in soup.select(".aa-tbs-video li a"):
#         target = tab.get("href", "").removeprefix("#")
#         number = tab.find("span")
#         name = tab.find("span", class_="server")
#         labels[target] = f"Server {number.get_text(strip=True) if number else ''} - {name.get_text(strip=True) if name else ''}".strip()
#     for video in soup.select("aside.video-player div.video"):
#         iframe = video.find("iframe")
#         if not iframe:
#             continue
#         embed = absolute_url(iframe.get("src") or iframe.get("data-src"))
#         decoded = None
#         if embed and "data=" in embed:
#             try:
#                 raw = urllib.parse.parse_qs(urllib.parse.urlparse(embed).query)["data"][0]
#                 decoded = json.loads(base64.b64decode(raw + "=" * (-len(raw) % 4)))
#             except (KeyError, ValueError, TypeError):
#                 decoded = None
#         server = {
#             "server_id": video.get("id"),
#             "server_name": labels.get(video.get("id"), video.get("id")),
#             "embed_url": embed,
#             "decoded_streams": decoded,
#         }
#         source_urls = [embed] if embed else []
#         source_urls.extend(
#             stream.get("link")
#             for stream in decoded or []
#             if stream.get("link")
#         )
#         server.update(resolve_first_direct_stream(source_urls))
#         servers.append(server)
#     recommendations = []
#     for card in soup.select(".owl-carousel article.post"):
#         link = card.find("a", class_="lnk-blk")
#         title = card.find(["h2", "h3"], class_="entry-title")
#         if not link or not title:
#             continue
#         url = absolute_url(link.get("href"))
#         recommendations.append({
#             "title": title.get_text(strip=True),
#             "url": url,
#             "route": f"/movie/{url.rstrip('/').split('/')[-1]}",
#             "poster": absolute_url(card.find("img").get("src")) if card.find("img") else None,
#         })
#     vlc_result = next(
#         (
#             {
#                 "direct_stream_url": server["direct_stream_url"],
#                 "direct_stream_type": server.get("direct_stream_type"),
#             }
#             for server in servers
#             if server.get("direct_stream_url")
#         ),
#         {},
#     )
#     return {
#         "type": "movie",
#         "slug": slug,
#         "title": title_el.get_text(strip=True) if title_el else None,
#         "post_id": post_id.get("value") if post_id else None,
#         "url": movie_url,
#         "route": f"/movie/{slug}",
#         "poster": absolute_url(poster.get("src")) if poster else None,
#         "synopsis": (soup.select_one(".description p").get_text(strip=True)
#                      if soup.select_one(".description p") else None),
#         "duration": duration.get_text(strip=True) if duration else None,
#         "release_year": year.get_text(strip=True) if year else None,
#         "genres": [a.get_text(strip=True) for a in soup.select("p.genres a")],
#         "languages": [a.get_text(strip=True) for a in soup.select("p.loadactor a")],
#         "streaming_servers": servers,
#         "vlc_url": vlc_result.get("direct_stream_url"),
#         "vlc_stream_type": vlc_result.get("direct_stream_type"),
#         **(
#             {"vlc_error": vlc_result["direct_stream_error"]}
#             if vlc_result.get("direct_stream_error")
#             else {}
#         ),
#         "downloads": [],
#         "recommended_movies": recommendations,
#     }







import base64
import json
import urllib.parse

from scraper_utils import absolute_url, fetch_soup, BASE_URL
from stream_resolver import resolve_first_direct_stream, resolve_zephyrix_stream


def get_movie_data(slug: str):
    if not slug:
        raise ValueError("Movie slug is required")
    movie_url = f"{BASE_URL}/movies/{slug.strip('/')}/"
    soup = fetch_soup(movie_url)
    title_el = soup.find("h1", class_="entry-title")
    poster = soup.select_one(".dfxb > div img")
    duration = soup.select_one(".duration .overviewCss")
    year = soup.select_one(".year .overviewCss")
    post_id = soup.select_one("#comment_post_ID")

    servers = []
    labels = {}
    for tab in soup.select(".aa-tbs-video li a"):
        target = tab.get("href", "").removeprefix("#")
        number = tab.find("span")
        name = tab.find("span", class_="server")
        num_txt = number.get_text(strip=True) if number else ""
        name_txt = name.get_text(strip=True) if name else ""
        labels[target] = f"Server {num_txt} - {name_txt}".strip(" -")

    for video in soup.select("aside.video-player div.video"):
        iframe = video.find("iframe")
        if not iframe:
            continue
        embed = absolute_url(iframe.get("src") or iframe.get("data-src"))
        decoded = None
        if embed and "data=" in embed:
            try:
                raw = urllib.parse.parse_qs(urllib.parse.urlparse(embed).query)["data"][0]
                decoded = json.loads(base64.b64decode(raw + "=" * (-len(raw) % 4)))
            except (KeyError, ValueError, TypeError):
                decoded = None

        server = {
            "server_id": video.get("id"),
            "server_name": labels.get(video.get("id"), video.get("id")),
            "embed_url": embed,
            "decoded_streams": decoded,
        }

        # --- ROUTING LOGIC ---
        # Server 1: Custom Zephyrix resolution
        if embed and "play.zephyrix.org" in embed:
            server.update(resolve_zephyrix_stream(embed, movie_url))
        # Server 2 & others: Untouched, routed through existing resolve_first_direct_stream
        else:
            source_urls = [embed] if embed else []
            source_urls.extend(
                stream.get("link")
                for stream in decoded or []
                if stream.get("link")
            )
            server.update(resolve_first_direct_stream(source_urls))

        servers.append(server)

    recommendations = []
    for card in soup.select(".owl-carousel article.post"):
        link = card.find("a", class_="lnk-blk")
        title = card.find(["h2", "h3"], class_="entry-title")
        if not link or not title:
            continue
        url = absolute_url(link.get("href"))
        recommendations.append({
            "title": title.get_text(strip=True),
            "url": url,
            "route": f"/movie/{url.rstrip('/').split('/')[-1]}",
            "poster": absolute_url(card.find("img").get("src")) if card.find("img") else None,
        })

    vlc_result = next(
        (
            {
                "direct_stream_url": server["direct_stream_url"],
                "direct_stream_type": server.get("direct_stream_type"),
                "direct_stream_error": server.get("direct_stream_error"),
            }
            for server in servers
            if server.get("direct_stream_url")
        ),
        {},
    )

    return {
        "type": "movie",
        "slug": slug,
        "title": title_el.get_text(strip=True) if title_el else None,
        "post_id": post_id.get("value") if post_id else None,
        "url": movie_url,
        "route": f"/movie/{slug}",
        "poster": absolute_url(poster.get("src")) if poster else None,
        "synopsis": (
            soup.select_one(".description p").get_text(strip=True)
            if soup.select_one(".description p")
            else None
        ),
        "duration": duration.get_text(strip=True) if duration else None,
        "release_year": year.get_text(strip=True) if year else None,
        "genres": [a.get_text(strip=True) for a in soup.select("p.genres a")],
        "languages": [a.get_text(strip=True) for a in soup.select("p.loadactor a")],
        "streaming_servers": servers,
        "vlc_url": vlc_result.get("direct_stream_url"),
        "vlc_stream_type": vlc_result.get("direct_stream_type"),
        **(
            {"vlc_error": vlc_result["direct_stream_error"]}
            if vlc_result.get("direct_stream_error")
            else {}
        ),
        "downloads": [],
        "recommended_movies": recommendations,
    }