"""Market scan must discover loops from broad results, not two preset queries."""

from unittest.mock import MagicMock

from app.config import Settings
from app.models import PlayApp
from app.serp_client import SerpApiError
from app.service import run_market_scan


def _settings():
    return Settings(
        api_key="test-key-not-real",
        max_play_searches=6,
        max_play_pages=3,
        max_unique_per_loop=40,
        max_product_lookups=5,
        max_google_searches=1,
    )


def _blast(i, count):
    return PlayApp(
        product_id=f"b{i}",
        title=f"Block Blast {i}",
        description="blast blocks",
        rating=4.5,
        ratings_count=count,
        thumbnail="https://example.com/icon.png",
    )


def test_market_scan_uses_broad_queries_and_drops_thin(monkeypatch):
    queries = []

    class Fake:
        def __init__(self, settings):
            self.settings = settings
            self.calls = {
                "google_play": 0,
                "google_play_games": 0,
                "google_play_product": 0,
                "google": 0,
            }
            self.play_calls = 0

        def chart_games(self, chart, games_category="GAME"):
            assert chart == "topselling_free"
            assert games_category == "GAME"
            self.calls["google_play_games"] += 1
            self.play_calls += 1
            # Only two match-3 titles: must be dropped.
            return [
                PlayApp(product_id="m1", title="Match Story", description="match 3", ratings_count=1000),
                PlayApp(product_id="m2", title="Matching Village", description="match", ratings_count=800),
            ]

        def search_play_pages(self, query, max_pages=None, max_unique=None):
            queries.append(query)
            self.calls["google_play"] += 1
            self.play_calls += 1
            if query == "puzzle game":
                return [_blast(i, 1_000_000 - i * 1000) for i in range(4)], False
            return [], True

        def enrich_product(self, product_id):
            self.calls["google_play_product"] += 1
            return None

        def search_google(self, query):
            self.calls["google"] += 1
            return []

    monkeypatch.setattr("app.service.SerpClient", Fake)
    report = run_market_scan(_settings())
    assert "bus jam parking puzzle" not in queries
    assert "block blast puzzle" not in queries
    assert "puzzle game" in queries
    assert "casual game" in queries
    assert report.qualified_count == 1
    assert report.stories[0].loop_name == "tile blast"
    assert report.stories[0].seen_count >= 4
    assert report.api_calls_used["google_play_product"] <= 5


def test_later_page_error_keeps_titles(monkeypatch):
    class Fake:
        def __init__(self, settings):
            self.settings = settings
            self.calls = {"google_play": 1, "google_play_games": 0, "google_play_product": 0, "google": 0}
            self.play_calls = 1

        def chart_games(self, chart, games_category="GAME"):
            raise SerpApiError("chart down")

        def search_play_pages(self, query, max_pages=None, max_unique=None):
            if query == "casual game":
                raise SerpApiError("page failed")
            if query != "puzzle game":
                return [], True
            return [_blast(i, 500_000 - i) for i in range(4)], True

        def enrich_product(self, product_id):
            return None

        def search_google(self, query):
            return []

    monkeypatch.setattr("app.service.SerpClient", Fake)
    report = run_market_scan(_settings())
    assert report.qualified_count == 1
    assert report.stories[0].hit.title.startswith("Block Blast")
