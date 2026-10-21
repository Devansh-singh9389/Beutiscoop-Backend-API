from scraper_utils import BASE_URL, absolute_url, fetch_soup, frontend_route, pagination_data


def _image(img):
    return absolute_url(img.get("src") or img.get("data-src")) if img else None


def _media_cards(container):
    if not container:
        return []
    items = []
    for article in container.find_all("article", class_="post"):
        title_el = article.find(["h2", "h3"], class_="entry-title")
        link_el = article.find("a", class_="lnk-blk")
        if not title_el or not link_el or not link_el.get("href"):
            continue
        url = absolute_url(link_el["href"])
        media_type = "movie" if "/movies/" in url else "series"
        slug = url.rstrip("/").split("/")[-1]
        year_el = article.find("span", class_="year")
        season_el = article.find("span", class_="post-ql")
        items.append({
            "title": title_el.get_text(strip=True),
            "url": url,
            "route": f"/{media_type}/{slug}",
            "media_type": media_type,
            "image": _image(article.find("img")),
            "season": season_el.get_text(strip=True) if season_el else None,
            "episodes_or_year": year_el.get_text(strip=True) if year_el else None,
        })
    return items


def _logo_slider(soup, slider_id):
    slider = soup.find("div", id=slider_id)
    if not slider:
        return []
    result = []
    for link in slider.find_all("a", href=True):
        img = link.find("img")
        name = (img.get("title") or img.get("alt")) if img else link.get_text(strip=True)
        url = absolute_url(link["href"])
        result.append({"name": name, "url": url, "route": frontend_route(url), "image": _image(img)})
    return result


def _trending(soup, section_id):
    section = soup.find("section", id=section_id)
    if not section:
        return []
    result = []
    for card in section.select(".top-picks__item .item__card"):
        image = card.find("img")
        url = absolute_url(card.get("href"))
        if url:
            result.append({
                "title": image.get("alt", "").replace("Image ", "").strip() if image else None,
                "url": url,
                "route": frontend_route(url),
                "image": _image(image),
            })
    return result


def get_home_data(page: int = 1):
    if page < 1:
        raise ValueError("Page must be at least 1")
    if page != 1:
        raise ValueError("The home page does not provide numbered pagination")
    page_url = BASE_URL
    soup = fetch_soup(page_url)
    return {
        "type": "home",
        "url": page_url,
        "pagination": pagination_data(soup, page),
        "navbar": [
            {
                "label": (
                    a.find("div", class_="textomenu").get_text(strip=True)
                    if a.find("div", class_="textomenu")
                    else a.get_text(strip=True)
                ).upper(),
                "url": absolute_url(a["href"]),
                "route": frontend_route(absolute_url(a["href"])),
            }
            for a in soup.select("ul.ulbotoes a.botao[href]")
        ],
        "big_titles_main": _logo_slider(soup, "gs_logo_area_2"),
        "newest_drops": _media_cards(soup.find("section", id="widget_list_episodes-5")),
        "networks": _logo_slider(soup, "gs_logo_area_3"),
        "stream_in_your_language": _logo_slider(soup, "gs_logo_area_4"),
        "most_watched_shows": _trending(soup, "torofilm_wdgt_popular-3"),
        "new_anime_arrivals": _media_cards(soup.find("section", id="widget_list_movies_series-2")),
        "just_in_cartoon_series": _media_cards(soup.find("section", id="widget_list_movies_series-8")),
        "most_watched_films": _trending(soup, "torofilm_wdgt_popular-5"),
        "latest_anime_movies": _media_cards(soup.find("section", id="widget_list_movies_series-4")),
        "fresh_cartoon_films": _media_cards(soup.find("section", id="widget_list_movies_series-11")),
    }
