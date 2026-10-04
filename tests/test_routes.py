from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models import GameIdea
from app.service import sample_brief, sample_trend_scan


client = TestClient(app)


def test_home_ok():
    r = client.get("/")
    assert r.status_code == 200
    assert "Play Pulse" in r.text
    assert "Scan the market" in r.text
    assert "bus parking sort" in r.text


def test_sample_trends_marked_not_live():
    r = client.get("/sample/trends")
    assert r.status_code == 200
    assert "SAMPLE PREVIEW" in r.text
    assert "NOT LIVE" in r.text
    assert "Early" in r.text
    assert "Filled" in r.text
    assert "Block Blast!" in r.text
    assert "/static/placeholder.svg" in r.text


def test_sample_alias_and_idea():
    r = client.get("/sample")
    assert r.status_code == 200
    assert "SAMPLE PREVIEW" in r.text
    r2 = client.get("/sample/idea")
    assert r2.status_code == 200
    assert "Rush Bay" in r2.text
    assert "SAMPLE PREVIEW" in r2.text


def test_trends_without_key_shows_setup_error():
    from app.config import Settings

    with patch("app.main.get_settings", return_value=Settings(api_key=None)):
        r = client.post("/trends")
    assert r.status_code == 503
    assert "Setup required" in r.text or "no SerpApi key" in r.text


def test_analyze_without_key_shows_setup_error():
    from app.config import Settings

    with patch("app.main.get_settings", return_value=Settings(api_key=None)):
        r = client.post(
            "/analyze",
            data={
                "title": "Rush Bay",
                "pitch": "bus parking sort puzzle",
                "keywords": "bus",
            },
        )
    assert r.status_code == 503
    assert "Setup required" in r.text or "no SerpApi key" in r.text


def test_trends_with_mocked_run():
    from app.config import Settings

    scan = sample_trend_scan()
    scan.sample_mode = False
    with patch("app.main.get_settings", return_value=Settings(api_key="fake")):
        with patch("app.main.run_market_scan", return_value=scan):
            r = client.post("/trends")
    assert r.status_code == 200
    assert "Block Blast!" in r.text
    assert "SAMPLE PREVIEW" not in r.text
    assert "Early" in r.text or "Filled" in r.text


def test_analyze_with_mocked_run():
    from app.config import Settings

    idea = GameIdea(title="Rush Bay", pitch="bus parking", keywords="sort")
    brief = sample_brief(idea)
    brief.sample_mode = False

    with patch("app.main.get_settings", return_value=Settings(api_key="fake")):
        with patch("app.main.run_brief", return_value=brief):
            r = client.post(
                "/analyze",
                data={
                    "title": "Rush Bay",
                    "pitch": "bus parking",
                    "keywords": "sort",
                },
            )
    assert r.status_code == 200
    assert "Live shelf brief" in r.text
    assert "SAMPLE PREVIEW" not in r.text


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
