from scraper_utils import absolute_url, fetch_soup, BASE_URL


def search_anime(query: str):
    query = query.strip()
    soup = fetch_soup(f"{BASE_URL}/?s={query}")
    results = []
    for li in soup.select("ul.post-lst > li"):
        card = li.find("article", class_="post")
        link = card.find("a", class_="lnk-blk") if card else None
        title = card.find(["h2", "h3"], class_="entry-title") if card else None
        if not link or not title:
            continue
        url = absolute_url(link.get("href"))
        media_type = "movie" if "/movies/" in url else "series"
        results.append({
            "id": li.get("id", "").removeprefix("post-") or None,
            "title": title.get_text(strip=True),
            "media_type": media_type,
            "route": f"/{media_type}/{url.rstrip('/').split('/')[-1]}",
            "url": url,
            "image": absolute_url(
                (card.find("img").get("src") or card.find("img").get("data-src"))
            ) if card.find("img") else None,
            "categories": [
                value.removeprefix("category-")
                for value in li.get("class", [])
                if value.startswith("category-")
            ],
        })
    title_el = soup.find("h1", class_="section-title")
    return {
        "query": title_el.get_text(strip=True) if title_el else query,
        "search_url": f"{BASE_URL}/?s={query}",
        "total_results": len(results),
        "results": results,
    }
