from app.models import PlayApp
from app.loops import classify_loop
from app.trend_analyzer import analyze_trends, find_opportunities, genre_stats


def _apps():
    return [
        PlayApp(
            product_id="1",
            title="Block Blast!",
            developer="Hungry Studio",
            genre="Puzzle",
            description="Blast wooden blocks.",
            chart="topselling_free",
            rating=4.6,
            ratings_count=2_000_000,
        ),
        PlayApp(
            product_id="2",
            title="Bus Jam Out",
            developer="Ivy",
            genre="Puzzle",
            description="Unblock buses in a parking jam.",
            chart="topselling_free",
            rating=4.5,
            ratings_count=800_000,
        ),
        PlayApp(
            product_id="3",
            title="Parking Jam 3D",
            developer="Rollic",
            genre="Puzzle",
            description="Sort cars out of a parking jam.",
            chart="topselling_free",
            rating=4.4,
            ratings_count=400_000,
        ),
        PlayApp(
            product_id="4",
            title="Merge Mansion",
            developer="Metacore",
            genre="Puzzle",
            description="Merge items to restore a mansion.",
            chart="movers_shakers",
            rating=4.5,
            ratings_count=22_000,
        ),
        PlayApp(
            product_id="5",
            title="Survivor.io",
            developer="Habby",
            genre="Action",
            description="Survivor horde arena.",
            chart="movers_shakers",
            rating=4.4,
            ratings_count=1_200_000,
        ),
    ]


def test_classify_known_loops():
    apps = _apps()
    assert classify_loop(apps[0]) == "tile_blast"
    assert classify_loop(apps[1]) == "bus_parking_sort"
    assert classify_loop(apps[2]) == "bus_parking_sort"
    assert classify_loop(apps[3]) == "merge"
    assert classify_loop(apps[4]) == "survivor_io"


def test_genre_stats_still_counts_play_labels():
    genres = genre_stats(_apps())
    assert genres[0].genre == "Puzzle"
    assert genres[0].count == 4


def test_room_is_a_named_loop_not_a_genre_slogan():
    opps = find_opportunities(_apps())
    assert opps
    assert all(o.kind == "loop" for o in opps)
    assert any(o.label == "merge" for o in opps)
    assert "Merge Mansion" in opps[0].evidence or any("Merge Mansion" in o.evidence for o in opps)


def test_analyze_trends_cites_titles_and_worn_words():
    scan = analyze_trends(
        apps=_apps(),
        sources=["topselling_free", "movers_shakers"],
        web_hits=[],
    )
    blob = " ".join([scan.trending_summary, scan.room_summary, scan.build_recommendation])
    assert "Bus Jam Out" in blob or "Parking Jam 3D" in blob
    assert "bus / parking sort" in blob or "merge" in blob
    assert "Worth building next" in scan.build_recommendation
    assert "Casual" not in scan.build_recommendation
    crowded = [o for o in scan.opportunities if o.kind == "crowded_loop"]
    assert crowded
    bus = next(o for o in crowded if o.label == "bus / parking sort")
    assert "jam" in bus.evidence
    assert "Bus Jam Out" in bus.evidence
    assert scan.sample_mode is False


def test_description_words_do_not_invent_a_loop():
    math = PlayApp(
        product_id="m",
        title="Crossmath - Math Puzzle Games",
        description="Race against the clock in this crossword number puzzle.",
        ratings_count=882_000,
    )
    numbers = PlayApp(
        product_id="n",
        title="2248 - Numbers Game 2048",
        description="Merge number blocks in this 2048 matching puzzle.",
        ratings_count=875_000,
    )
    assert classify_loop(math) is None
    assert classify_loop(numbers) is None
