import re

from scraper_utils import absolute_url, fetch_soup, BASE_URL, HEADERS, HTTP_SESSION


def _episodes(element):
    result = []
    for card in element.select("article.episodes") if element else []:
        link = card.find("a", class_="lnk-blk")
        if not link:
            continue
        url = absolute_url(link.get("href"))
        result.append({
            "episode_code": (card.find("span", class_="num-epi").get_text(strip=True)
                             if card.find("span", class_="num-epi") else None),
            "title": (card.find("h2", class_="entry-title").get_text(strip=True)
                      if card.find("h2", class_="entry-title") else None),
            "url": url,
            "route": f"/episode/{url.rstrip('/').split('/')[-1]}",
            "thumbnail": absolute_url(card.find("img").get("src")) if card.find("img") else None,
        })
    return result


def get_series_data(slug: str):
    series_url = f"{BASE_URL}/series/{slug.strip('/')}/"
    soup = fetch_soup(series_url)
    post = soup.select_one(".choose-season a[data-post]")
    post_id = post.get("data-post") if post else None
    nonce_match = re.search(r'"nonce":\s*"([a-zA-Z0-9]+)"', str(soup))
    nonce = nonce_match.group(1) if nonce_match else None
    active = soup.select_one("ul#episode_by_temp")
    active_num = soup.select_one(".choose-season dt.n_s")
    active_num = active_num.get_text(strip=True) if active_num else None
    seasons = []
    for button in soup.select(".choose-season .sub-menu li a[data-season]"):
        number = button.get("data-season")
        episodes = _episodes(active) if number == active_num else []
        if not episodes and nonce and post_id:
            response = HTTP_SESSION.post(
                f"{BASE_URL}/wp-admin/admin-ajax.php",
                data={"action": "action_select_season", "season": number, "post": post_id, "nonce": nonce},
                headers={**HEADERS, "Referer": series_url, "X-Requested-With": "XMLHttpRequest"},
                timeout=(10, 30),
            )
            response.raise_for_status()
            from bs4 import BeautifulSoup
            episodes = _episodes(BeautifulSoup(response.text, "html.parser"))
        seasons.append({"season_name": button.get_text(strip=True), "season_number": int(number), "episodes": episodes, "episodes_count": len(episodes)})
    seasons.sort(key=lambda value: value["season_number"])
    title = soup.find("h1", class_="entry-title")
    poster = soup.select_one(".dfxb > div img")
    return {
        "type": "series",
        "slug": slug,
        "title": title.get_text(strip=True) if title else None,
        "url": series_url,
        "route": f"/series/{slug}",
        "poster": absolute_url(poster.get("src")) if poster else None,
        "synopsis": (soup.select_one(".description p").get_text(strip=True)
                     if soup.select_one(".description p") else None),
        "genres": [a.get_text(strip=True) for a in soup.select("p.genres a")],
        "languages": [a.get_text(strip=True) for a in soup.select("p.loadactor a")],
        "total_seasons": len(seasons),
        "seasons": seasons,
    }
