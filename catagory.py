from scraper_utils import absolute_url, fetch_soup, BASE_URL, pagination_data


def _parse_listing(soup, page_url: str, label: str, current_page: int):
    items = []
    for li in soup.select("ul.post-lst > li"):
        card = li.find("article", class_="post")
        link = card.find("a", class_="lnk-blk") if card else None
        title = card.find(["h2", "h3"], class_="entry-title") if card else None
        if not link or not title:
            continue
        url = absolute_url(link.get("href"))
        media_type = "movie" if "/movies/" in url else "series"
        image = card.find("img")
        items.append({
            "id": li.get("id", "").removeprefix("post-") or None,
            "title": title.get_text(strip=True),
            "media_type": media_type,
            "route": f"/{media_type}/{url.rstrip('/').split('/')[-1]}",
            "url": url,
            "image": absolute_url(image.get("src") or image.get("data-src")) if image else None,
        })
    return {
        "type": "listing",
        "title": label,
        "url": page_url,
        "total_items": len(items),
        "items": items,
        "pagination": pagination_data(soup, current_page),
    }


def get_listing_data(section: str, page: int = 1):
    paths = {
        "series": ("/series/", "Series"),
        "movies": ("/movies/", "Movies"),
        "anime": ("/category/anime/", "Anime"),
        "cartoon": ("/category/cartoon/", "Cartoon"),
    }
    if section not in paths:
        raise ValueError("Unsupported listing section")
    if page < 1:
        raise ValueError("Page must be at least 1")
    path, label = paths[section]
    page_path = path if page == 1 else f"{path.rstrip('/')}/page/{page}/"
    page_url = f"{BASE_URL}{page_path}"
    return _parse_listing(fetch_soup(page_url), page_url, label, page)


def get_category_data(category_type: str, slug: str, page: int = 1):
    if page < 1:
        raise ValueError("Page must be at least 1")
    category_path = f"/category/{category_type}/{slug}/"
    page_path = category_path if page == 1 else f"{category_path.rstrip('/')}/page/{page}/"
    category_url = f"{BASE_URL}{page_path}"
    soup = fetch_soup(category_url)
    title_el = soup.find("h1", class_="section-title")
    result = _parse_listing(
        soup,
        category_url,
        title_el.get_text(strip=True) if title_el else slug,
        page,
    )
    return {
        **result,
        "category": title_el.get_text(strip=True) if title_el else slug,
        "category_type": category_type,
        "slug": slug,
    }
