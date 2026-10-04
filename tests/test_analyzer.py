from app.analyzer import (
    analyze,
    close_title_match_count,
    heavy_review_count,
    pitch_overlap_tokens,
    token_frequency,
)
from app.models import GameIdea, PlayApp, WebHit


def _idea():
    return GameIdea(
        title="Rush Bay",
        pitch="unblock colorful buses, match passengers, clear island parking bays",
        keywords="bus parking sort puzzle",
    )


def _apps():
    return [
        PlayApp(
            product_id="a",
            title="Bus Jam Color Sort",
            description="parking buses",
            ratings_count=120_000,
            rating=4.6,
        ),
        PlayApp(
            product_id="b",
            title="Parking Jam Out",
            description="unblock cars",
            ratings_count=80_000,
            rating=4.4,
        ),
        PlayApp(
            product_id="c",
            title="Island Bus Parking",
            description="match passengers on island bays",
            ratings_count=10_000,
            rating=4.1,
        ),
    ]


def test_token_frequency_counts_unique_per_title():
    stats = token_frequency(_apps())
    tokens = {s.token: s for s in stats}
    assert "bus" in tokens or "parking" in tokens or "jam" in tokens
    # "bus" appears in 2 of 3 titles
    if "bus" in tokens:
        assert tokens["bus"].count == 2


def test_close_matches_and_heavy_reviews():
    idea = _idea()
    apps = _apps()
    assert close_title_match_count(idea, apps) >= 1
    assert heavy_review_count(apps) == 2


def test_pitch_overlap():
    overlap = pitch_overlap_tokens(_idea(), _apps())
    assert any(t in overlap for t in ("bus", "parking", "island", "passengers", "sort"))


def test_analyze_returns_three_findings_and_cautions():
    brief = analyze(
        idea=_idea(),
        queries=["Rush Bay", "bus parking sort"],
        apps=_apps(),
        web_hits=[WebHit(title="t", link="https://x", snippet="s")],
    )
    assert len(brief.findings) == 3
    assert len(brief.cautions) == 3
    assert brief.saturation_label
    assert brief.sample_mode is False
