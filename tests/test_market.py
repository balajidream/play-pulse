
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
    labels = {s.loop_name: s.label for s in report.stories}
    assert labels["tile blast"] == "Early"
    assert labels["bus / parking sort"] == "Filled"
    assert report.stories[0].hit.thumbnail.startswith("/static/")
