"""Thin SerpApi HTTP client for Play charts/search, Play product, and Google web.

Parameter names match official docs:
- google_play: engine, q, hl, gl, api_key, next_page_token
  (no start offset; serpapi_pagination.next_page_token continues the search)
- google_play_games: engine, chart, games_category, hl, gl, api_key
  (verified at https://serpapi.com/google-play-games — used for mobile game charts)
- google_play_product: engine, product_id, store, hl, gl, api_key
- google: engine, q, hl, gl, api_key
"""

from __future__ import annotations

from typing import Any, Callable

import requests

from .config import Settings
from .models import PlayApp, WebHit


class SerpApiError(Exception):
    """Raised when SerpApi returns an error or the key is missing."""


class SerpClient:
    def __init__(
        self,
        settings: Settings,
        session: requests.Session | None = None,
        get: Callable[..., Any] | None = None,
    ) -> None:
        if not settings.has_api_key:
            raise SerpApiError(
                "SERPAPI_API_KEY is missing. Copy .env.example to .env and add your key "
                "from https://serpapi.com/users/sign_up"
            )
        self.settings = settings
        self.session = session or requests.Session()
        self._get = get or self.session.get
        self.calls = {
            "google_play": 0,
            "google_play_games": 0,
            "google_play_product": 0,
            "google": 0,
        }

    @property
    def play_calls(self) -> int:
        return self.calls["google_play"] + self.calls["google_play_games"]

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "api_key": self.settings.api_key,
            "hl": self.settings.hl,
            "gl": self.settings.gl,
            **params,
        }
        try:
            resp = self._get(self.settings.base_url, params=payload, timeout=45)
        except requests.RequestException as exc:
            raise SerpApiError(f"Network error calling SerpApi: {exc}") from exc
        try:
            data = resp.json()
        except ValueError as exc:
            raise SerpApiError(
                f"SerpApi returned non-JSON (HTTP {resp.status_code})"
            ) from exc
        if resp.status_code >= 400:
            msg = data.get("error") or data.get("message") or resp.text[:200]
            raise SerpApiError(f"SerpApi HTTP {resp.status_code}: {msg}")
        if isinstance(data, dict) and data.get("error"):
            raise SerpApiError(str(data["error"]))
        return data

    def _parse_play_items(
        self, data: dict[str, Any], source_label: str, chart: str = ""
    ) -> list[PlayApp]:
        apps: list[PlayApp] = []
        for block in data.get("organic_results") or []:
            for item in block.get("items") or []:
                pid = item.get("product_id") or ""
                if not pid:
                    link = item.get("link") or ""
                    if "id=" in link:
                        pid = link.split("id=", 1)[1].split("&", 1)[0]
                if not pid:
                    continue
                apps.append(
                    PlayApp(
                        product_id=pid,
                        title=item.get("title") or "",
                        developer=item.get("author") or "",
                        rating=_as_float(item.get("rating")),
                        ratings_count=None,
                        description=item.get("description") or "",
                        genre=item.get("category") or "",
                        link=item.get("link")
                        or f"https://play.google.com/store/apps/details?id={pid}",
                        thumbnail=item.get("thumbnail") or item.get("icon") or "",
                        source_query=source_label,
                        chart=chart,
                        downloads_hint=_downloads(item.get("downloads")),
                    )
                )
        return apps

    def search_play(self, query: str) -> list[PlayApp]:
        """engine=google_play — organic_results[].items[] with product_id."""
        if self.play_calls >= self.settings.max_play_searches:
            return []
        data = self._request({"engine": "google_play", "q": query})
        self.calls["google_play"] += 1
        return self._parse_play_items(data, source_label=query)

    def search_play_pages(
        self, query: str, max_pages: int | None = None, max_unique: int | None = None
    ) -> tuple[list[PlayApp], bool]:
        """Page a Play search with next_page_token.

        Returns (unique apps, first_page_only). first_page_only is True when
        the first response has no next_page_token, so the UI must not claim
        the shelf was exhausted beyond page 1.
        """
        pages_cap = max_pages if max_pages is not None else self.settings.max_play_pages
        unique_cap = max_unique if max_unique is not None else self.settings.max_unique_per_loop
        collected: list[PlayApp] = []
        token = ""
        pages = 0
        saw_next = False
        while pages < pages_cap and len(dedupe_by_product_id(collected)) < unique_cap:
            if self.play_calls >= self.settings.max_play_searches:
                break
            params: dict[str, Any] = {"engine": "google_play", "q": query}
            if token:
                params["next_page_token"] = token
            try:
                data = self._request(params)
            except SerpApiError:
                # A later page often errors even when page 1 was real.
                # Keep the titles already collected instead of failing the scan.
                if not collected:
                    raise
                break
            self.calls["google_play"] += 1
            pages += 1
            collected.extend(self._parse_play_items(data, source_label=query))
            token = ((data.get("serpapi_pagination") or {}).get("next_page_token") or "").strip()
            if token:
                saw_next = True
            else:
                break
        unique = dedupe_by_product_id(collected)[:unique_cap]
        first_page_only = pages <= 1 and not saw_next
        return unique, first_page_only

    def chart_games(
        self, chart: str, games_category: str = "GAME"
    ) -> list[PlayApp]:
        """engine=google_play_games — top charts for mobile games.

        Docs: chart (e.g. topselling_free, movers_shakers), games_category=GAME.
        """
        if self.play_calls >= self.settings.max_play_searches:
            return []
        params: dict[str, Any] = {
            "engine": "google_play_games",
            "chart": chart,
            "games_category": games_category,
        }
        data = self._request(params)
        self.calls["google_play_games"] += 1
        label = f"chart:{chart}"
        return self._parse_play_items(data, source_label=label, chart=chart)

    def enrich_product(self, product_id: str) -> PlayApp | None:
        """engine=google_play_product — product_info + about_this_app."""
        if self.calls["google_play_product"] >= self.settings.max_product_lookups:
            return None
        data = self._request(
            {
                "engine": "google_play_product",
                "product_id": product_id,
                "store": "apps",
            }
        )
        self.calls["google_play_product"] += 1
        info = data.get("product_info") or {}
        about = data.get("about_this_app") or {}
        categories = data.get("categories") or []
        genre = ""
        if categories:
            genre = categories[0].get("name") or ""
        authors = info.get("authors") or []
        developer = ""
        if authors:
            developer = authors[0].get("name") or ""
        if not developer:
            developer = about.get("offered_by") or ""
        return PlayApp(
            product_id=product_id,
            title=info.get("title") or "",
            developer=developer,
            rating=_as_float(info.get("rating")),
            ratings_count=_as_int(info.get("reviews")),
            description=(about.get("snippet") or "")[:500],
            genre=genre,
            link=f"https://play.google.com/store/apps/details?id={product_id}",
            thumbnail=info.get("thumbnail") or info.get("icon") or "",
        )

    def search_google(self, query: str, num: int = 8) -> list[WebHit]:
        """engine=google — organic_results for coverage / what people write."""
        if self.calls["google"] >= self.settings.max_google_searches:
            return []
        data = self._request({"engine": "google", "q": query})
        self.calls["google"] += 1
        hits: list[WebHit] = []
        for row in (data.get("organic_results") or [])[:num]:
            hits.append(
                WebHit(
                    title=row.get("title") or "",
                    link=row.get("link") or "",
                    snippet=row.get("snippet") or "",
                    source=row.get("source") or row.get("displayed_link") or "",
                )
            )
        return hits


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip().upper().replace(",", "")
    mult = 1
    if text.endswith("K"):
        mult = 1_000
        text = text[:-1]
    elif text.endswith("M"):
        mult = 1_000_000
        text = text[:-1]
    elif text.endswith("B"):
        mult = 1_000_000_000
        text = text[:-1]
    try:
        return int(float(text) * mult)
    except (TypeError, ValueError):
        return None


def _downloads(value: Any) -> int | None:
    """Parse Play download strings like '500,000,000+' into an int hint."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).upper().replace(",", "").replace("+", "").strip()
    mult = 1
    if text.endswith("K"):
        mult = 1_000
        text = text[:-1]
    elif text.endswith("M"):
        mult = 1_000_000
        text = text[:-1]
    elif text.endswith("B"):
        mult = 1_000_000_000
        text = text[:-1]
    try:
        return int(float(text) * mult)
    except (TypeError, ValueError):
        return None


def dedupe_by_product_id(apps: list[PlayApp]) -> list[PlayApp]:
    seen: set[str] = set()
    out: list[PlayApp] = []
    for app in apps:
        if app.product_id in seen:
            continue
        seen.add(app.product_id)
        out.append(app)
    return out
