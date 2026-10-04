from app.models import PlayApp
from app.trend_analyzer import analyze_trends, find_opportunities, genre_stats


def _apps():
    return [
        PlayApp(product_id="1", title="Block Blast Puzzle", genre="Puzzle", chart="topselling_free", ratings_count=2_000_000),
        PlayApp(product_id="2", title="Bus Jam Traffic", genre="Puzzle", chart="topselling_free", ratings_count=800_000),
        PlayApp(product_id="3", title="Water Sort Puzzle", genre="Puzzle", chart="topselling_free", ratings_count=1_500_000),
        PlayApp(product_id="4", title="Idle Miner Tycoon", genre="Simulation", chart="movers_shakers", ratings_count=400_000),
        PlayApp(product_id="5", title="Farm City Sim", genre="Simulation", chart="movers_shakers", ratings_count=50_000),
        PlayApp(product_id="6", title="Car Race Master", genre="Racing", chart="movers_shakers", ratings_count=12_000),
        PlayApp(product_id="7", title="Car Park Rush", genre="Racing", chart="movers_shakers", ratings_count=8_000),
    ]


def test_genre_stats_and_opportunities():
    apps = _apps()
    genres = genre_stats(apps)
    assert genres[0].genre == "Puzzle"
    assert genres[0].count == 3
    from app.analyzer import token_frequency

    tokens = token_frequency(apps)
    opps = find_opportunities(apps, genres, tokens)
    assert any(o.kind in ("genre", "title_pattern") for o in opps)


def test_analyze_trends_three_answers():
    scan = analyze_trends(
        apps=_apps(),
        sources=["topselling_free", "movers_shakers"],
        web_hits=[],
    )
    assert "Google Play" in scan.trending_summary or "chart" in scan.trending_summary.lower() or "Scanned" in scan.trending_summary
    assert scan.room_summary
    assert scan.build_recommendation
    assert "Worth building" in scan.build_recommendation or "building next" in scan.build_recommendation.lower()
    assert scan.sample_mode is False
