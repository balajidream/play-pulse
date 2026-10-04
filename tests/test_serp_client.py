import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.config import Settings
from app.serp_client import SerpApiError, SerpClient, dedupe_by_product_id
from app.models import PlayApp

FIX = Path(__file__).parent / "fixtures"


def _settings(**kwargs):
    base = dict(
        api_key="test-key-not-real",
        base_url="https://serpapi.example/search.json",
        hl="en",
        gl="in",
        max_play_searches=3,
        max_product_lookups=5,
        max_google_searches=1,
    )
    base.update(kwargs)
    return Settings(**base)


def test_missing_key_raises():
    with pytest.raises(SerpApiError, match="SERPAPI_API_KEY"):
        SerpClient(_settings(api_key=None))


def test_search_play_parses_items_and_caps():
    payload = json.loads((FIX / "play_search.json").read_text())
    mock_get = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload
    mock_get.return_value = mock_resp

    client = SerpClient(_settings(max_play_searches=1), get=mock_get)
    apps = client.search_play("bus parking")
    assert len(apps) == 2
    assert apps[0].product_id == "com.jam.bus"
    assert mock_get.call_args.kwargs["params"]["engine"] == "google_play"
    assert mock_get.call_args.kwargs["params"]["q"] == "bus parking"
    assert mock_get.call_args.kwargs["params"]["hl"] == "en"
    assert mock_get.call_args.kwargs["params"]["gl"] == "in"

    assert client.search_play("again") == []
    assert mock_get.call_count == 1


def test_chart_games_params():
    payload = json.loads((FIX / "play_games_chart.json").read_text())
    mock_get = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload
    mock_get.return_value = mock_resp

    client = SerpClient(_settings(), get=mock_get)
    apps = client.chart_games("topselling_free")
    assert len(apps) == 3
    assert apps[0].chart == "topselling_free"
    params = mock_get.call_args.kwargs["params"]
    assert params["engine"] == "google_play_games"
    assert params["chart"] == "topselling_free"
    assert params["games_category"] == "GAME"


def test_play_call_budget_shared_across_engines():
    payload = json.loads((FIX / "play_games_chart.json").read_text())
    mock_get = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload
    mock_get.return_value = mock_resp

    client = SerpClient(_settings(max_play_searches=2), get=mock_get)
    assert client.chart_games("topselling_free")
    assert client.chart_games("movers_shakers")
    assert client.search_play("puzzle") == []
    assert mock_get.call_count == 2


def test_enrich_product_params():
    payload = json.loads((FIX / "play_product.json").read_text())
    mock_get = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload
    mock_get.return_value = mock_resp

    client = SerpClient(_settings(), get=mock_get)
    app = client.enrich_product("com.jam.bus")
    assert app is not None
    assert app.title == "Bus Jam - Traffic Puzzle"
    assert app.ratings_count == 150000
    assert app.genre == "Puzzle"
    params = mock_get.call_args.kwargs["params"]
    assert params["engine"] == "google_play_product"
    assert params["product_id"] == "com.jam.bus"
    assert params["store"] == "apps"


def test_search_google_organic():
    payload = json.loads((FIX / "google_search.json").read_text())
    mock_get = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload
    mock_get.return_value = mock_resp

    client = SerpClient(_settings(), get=mock_get)
    hits = client.search_google("bus parking mobile game")
    assert len(hits) == 2
    assert hits[0].title.startswith("The rise")
    assert mock_get.call_args.kwargs["params"]["engine"] == "google"


def test_api_error_surface():
    mock_get = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"error": "Invalid API key."}
    mock_get.return_value = mock_resp
    client = SerpClient(_settings(), get=mock_get)
    with pytest.raises(SerpApiError, match="Invalid API key"):
        client.search_play("x")


def test_dedupe():
    apps = [
        PlayApp(product_id="a", title="One"),
        PlayApp(product_id="a", title="One again"),
        PlayApp(product_id="b", title="Two"),
    ]
    out = dedupe_by_product_id(apps)
    assert [a.product_id for a in out] == ["a", "b"]


def _page(ids, token=""):
    items = [
        {
            "title": f"Game {pid}",
            "product_id": pid,
            "rating": 4.2,
            "author": "Dev",
            "description": "puzzle",
            "thumbnail": "https://example.com/icon.png",
        }
        for pid in ids
    ]
    data = {"organic_results": [{"items": items}]}
    if token:
        data["serpapi_pagination"] = {"next_page_token": token}
    return data


def test_search_play_pages_follows_next_page_token_not_start():
    pages = [
        _page(["a1", "a2"], token="PAGE2"),
        _page(["a2", "a3"], token="PAGE3"),
        _page(["a4"]),
    ]
    mock_get = MagicMock()
    responses = []
    for payload in pages:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = payload
        responses.append(resp)
    mock_get.side_effect = responses

    client = SerpClient(_settings(max_play_searches=6, max_play_pages=3, max_unique_per_loop=40), get=mock_get)
    apps, first_only = client.search_play_pages("block blast")
    assert first_only is False
    assert [a.product_id for a in apps] == ["a1", "a2", "a3", "a4"]
    assert mock_get.call_count == 3
    first_params = mock_get.call_args_list[0].kwargs["params"]
    assert first_params["engine"] == "google_play"
    assert "start" not in first_params
    assert "next_page_token" not in first_params
    second = mock_get.call_args_list[1].kwargs["params"]
    assert second["next_page_token"] == "PAGE2"
    third = mock_get.call_args_list[2].kwargs["params"]
    assert third["next_page_token"] == "PAGE3"


def test_search_play_pages_first_page_only_when_no_token():
    mock_get = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = _page(["only"])
    mock_get.return_value = resp
    client = SerpClient(_settings(max_play_searches=6), get=mock_get)
    apps, first_only = client.search_play_pages("bus jam")
    assert first_only is True
    assert len(apps) == 1
    assert mock_get.call_count == 1


def test_search_play_pages_caps_unique_titles():
    pages = [
        _page([f"p{i}" for i in range(10)], token="N"),
        _page([f"q{i}" for i in range(10)], token="N2"),
        _page([f"r{i}" for i in range(10)]),
    ]
    mock_get = MagicMock()
    responses = []
    for payload in pages:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = payload
        responses.append(resp)
    mock_get.side_effect = responses
    client = SerpClient(
        _settings(max_play_searches=6, max_play_pages=3, max_unique_per_loop=12),
        get=mock_get,
    )
    apps, first_only = client.search_play_pages("tile")
    assert len(apps) == 12
    assert first_only is False
