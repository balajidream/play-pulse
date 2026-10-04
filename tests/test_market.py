
from app.market import shelf_label, story_for
from app.models import PlayApp
from app.service import sample_trend_scan


def _app(pid, title, count):
    return PlayApp(product_id=pid, title=title, ratings_count=count, rating=4.5, developer="Dev")


def test_early_when_one_hit_and_few_copies():
    apps = [
        _app("a", "Block Blast!", 20_000_000),
        _app("b", "Wood Block Puzzle", 800_000),
        _app("c", "Block Puzzle Blast", 90_000),
    ]
    assert shelf_label(apps) == "Early"
    story = story_for("tile blast", apps)
    assert story.hit.title == "Block Blast!"
    assert len(story.clones) == 2
    assert "not launch date" in story.size_note


def test_filled_when_many_copies():
    apps = [_app(str(i), f"Bus Jam {i}", 400_000 - i) for i in range(5)]
    assert shelf_label(apps) == "Filled"


def test_sample_tells_both_stories():
    report = sample_trend_scan()
    assert report.sample_mode is True
    names = [s.loop_name for s in report.stories]
    assert names == ["tile blast", "bus / parking sort"]
    assert "merge" not in names
    assert report.stories[0].seen_count - 1 == 3
    assert report.stories[1].seen_count - 1 == 4
    assert report.stories[0].hit.thumbnail.startswith("/static/")
    assert report.qualified_count == 2


def test_seen_count_and_more():
    apps = [_app(str(i), f"Title {i}", 1_000_000 - i) for i in range(10)]
    story = story_for("tile blast", apps, first_page_only=True)
    assert story.seen_count == 10
    assert story.more_count == 10 - 1 - len(story.clones)
    assert story.more_count > 0
    assert story.first_page_only is True
    assert story.hit.title == "Title 0"


def test_discover_drops_thin_groups_and_sorts_by_copies():
    from app.market import discover_shelves

    apps = []
    # 4 tile-blast titles → 3 copies (kept, fewer)
    apps.append(PlayApp(product_id="t0", title="Block Blast!", description="blast blocks", ratings_count=9_000_000))
    apps.append(PlayApp(product_id="t1", title="Wood Block Puzzle", description="blast lines", ratings_count=100_000))
    apps.append(PlayApp(product_id="t2", title="Tile Blast Rush", description="blast", ratings_count=50_000))
    apps.append(PlayApp(product_id="t3", title="Block Puzzle Blast", description="blast", ratings_count=20_000))
    # 6 match-3 titles → 5 copies (kept, later)
    for i in range(6):
        apps.append(PlayApp(product_id=f"m{i}", title=f"Match Story {i}", description="match 3", ratings_count=10_000))
    # 2 merge titles → dropped
    apps.append(PlayApp(product_id="g1", title="Merge Mansion", description="merge", ratings_count=1000))
    apps.append(PlayApp(product_id="g2", title="Merge Garden", description="merge", ratings_count=500))
    stories = discover_shelves(apps)
    assert [s.loop_name for s in stories] == ["tile blast", "match-3"]
    assert stories[0].seen_count - 1 < stories[1].seen_count - 1
