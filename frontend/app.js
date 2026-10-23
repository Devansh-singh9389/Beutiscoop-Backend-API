const API = "http://127.0.0.1:8000/api";
const app = document.querySelector("#app");
const searchForm = document.querySelector("#search-form");
const searchInput = document.querySelector("#search-input");

const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
}[char]));

const slugFromRoute = route => route?.split("/").filter(Boolean).pop();
const image = (src, title) => src
  ? `<img src="${escapeHtml(src)}" alt="${escapeHtml(title)}" loading="lazy" onerror="this.parentElement.innerHTML='<span class=&quot;muted&quot;>No image</span>'">`
  : `<span class="muted">No image</span>`;
const routeFor = item => item.route || `/${item.media_type || "series"}/${slugFromRoute(item.url)}`;
const card = item => `<article class="card"><a class="poster" href="#${routeFor(item)}">${image(item.image || item.poster || item.thumbnail, item.title)}</a><div class="card-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</div><div class="tag">${escapeHtml(item.media_type || "watch now")}</div></article>`;
const cards = items => `<div class="cards">${(items || []).map(card).join("") || `<div class="message">No titles found.</div>`}</div>`;

async function get(path) {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) {
    let detail = "Could not load this page.";
    try { detail = (await response.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return response.json();
}

function loading() {
  app.innerHTML = `<div class="loading"><span></span><span></span><span></span> Loading...</div>`;
}

function showError(error) {
  app.innerHTML = `<div class="message"><h2>Something went wrong</h2><p>${escapeHtml(error.message)}</p><a class="chip" href="#/">Try again</a></div>`;
}

function section(title, items, more) {
  return `<section class="section"><div class="section-head"><h2>${escapeHtml(title)}</h2>${more ? `<a href="#${more}">See all →</a>` : ""}</div>${cards(items)}</section>`;
}

async function home() {
  const data = await get("/home");
  const sections = [
    ["New anime arrivals", data.new_anime_arrivals, "/category/anime"],
    ["Just in cartoon", data.just_in_cartoon_series, "/category/cartoon"],
    ["Most watched shows", data.most_watched_shows],
    ["Latest anime movies", data.latest_anime_movies, "/movies"]
  ];
  app.innerHTML = `<section class="hero"><div><div class="eyebrow">Your next favorite watch</div><h1>Stories worth staying up for.</h1><p>Explore fresh movies, series, anime and cartoons in one beautiful place.</p></div></section>${sections.map(item => section(...item)).join("")}`;
}

async function listing(path, title) {
  const data = await get(path);
  app.innerHTML = `<section class="section"><div class="section-head"><h2>${escapeHtml(data.title || title)}</h2><span class="muted">${data.total_items || 0} titles</span></div>${cards(data.items)}</section>`;
}

async function search(query) {
  const data = await get(`/search?q=${encodeURIComponent(query)}`);
  app.innerHTML = `<section class="section"><div class="section-head"><h2>Results for “${escapeHtml(query)}”</h2><span class="muted">${data.total_results} found</span></div>${cards(data.results)}</section>`;
}

function detailMarkup(data) {
  const chips = [...(data.genres || []), ...(data.languages || [])]
    .map(item => `<span class="chip">${escapeHtml(item)}</span>`).join("");
  return `<div class="details"><a class="poster">${image(data.poster, data.title)}</a><div><div class="eyebrow">${escapeHtml(data.type)}</div><h1>${escapeHtml(data.title)}</h1><div class="chips">${chips}</div><p class="muted">${escapeHtml(data.synopsis || "No description available.")}</p>${data.release_year ? `<p class="muted">${escapeHtml(data.release_year)} ${data.duration ? `• ${escapeHtml(data.duration)}` : ""}</p>` : ""}</div></div>`;
}

async function details(type, slug) {
  const data = await get(`/${type}/${encodeURIComponent(slug)}`);
  let html = detailMarkup(data);
  if (type === "series") {
    const episodeLinks = (data.seasons || []).flatMap(season => season.episodes || [])
      .map(episode => `<a class="episode" href="#${episode.route}">${escapeHtml(episode.title || episode.episode_code)}</a>`).join("");
    html += `<section class="section"><h2>Episodes</h2><div class="episode-list">${episodeLinks || `<p class="muted">No episodes available.</p>`}</div></section>`;
  }
  app.innerHTML = html;
}

async function episode(slug) {
  const data = await get(`/episode/${encodeURIComponent(slug)}`);
  const servers = (data.streaming_servers || []).filter(server => server.embed_url);
  const first = servers[0]?.embed_url || "";
  app.innerHTML = `<div class="player"><a class="muted" href="${data.navigation?.series_route ? `#${data.navigation.series_route}` : "#/"}">← Back to series</a><h1>${escapeHtml(data.episode_title || "Watch episode")}</h1><div id="server-buttons" class="servers">${servers.map((server, index) => `<button class="${index === 0 ? "active" : ""}" data-url="${escapeHtml(server.embed_url)}">${escapeHtml(server.server_name || `Server ${index + 1}`)}</button>`).join("")}</div>${first ? `<iframe id="video" src="${escapeHtml(first)}" allowfullscreen></iframe>` : `<div class="message">No playable server is available.</div>`}</div>`;
  document.querySelectorAll("#server-buttons button").forEach(button => button.addEventListener("click", () => {
    document.querySelector("#video").src = button.dataset.url;
    document.querySelectorAll("#server-buttons button").forEach(item => item.classList.remove("active"));
    button.classList.add("active");
  }));
}

async function render() {
  loading();
  const parts = location.hash.slice(1).split("/").filter(Boolean);
  document.querySelectorAll("nav a").forEach(link => link.classList.toggle("active", link.getAttribute("href") === `#/${parts.join("/")}`));
  try {
    if (!parts.length) return home();
    if (parts[0] === "search") return search(decodeURIComponent(parts[1] || ""));
    if (parts[0] === "movies") return parts[1] ? listing(`/movies?page=${parts[1]}`, "Movies") : listing("/movies", "Movies");
    if (parts[0] === "series") return parts[1] ? details("series", parts[1]) : listing("/series", "Series");
    if (parts[0] === "category") return parts[2] ? listing(`/category/${parts[1]}/${parts[2]}`, parts[1]) : listing(`/category/${parts[1]}`, parts[1]);
    if (parts[0] === "movie") return details("movie", parts[1]);
    if (parts[0] === "episode") return episode(parts[1]);
    return home();
  } catch (error) {
    showError(error);
  }
}

searchForm.addEventListener("submit", event => {
  event.preventDefault();
  const query = searchInput.value.trim();
  if (query) location.hash = `#/search/${encodeURIComponent(query)}`;
});
window.addEventListener("hashchange", render);
render();
