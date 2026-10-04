"""Orchestrate SerpApi pulls into trend scans and idea briefs."""

from __future__ import annotations

from .analyzer import analyze
from .config import Settings, get_settings
from .models import Brief, GameIdea, PlayApp, WebHit
from .query_planner import plan_coverage_query, plan_queries
from .serp_client import SerpApiError, SerpClient, dedupe_by_product_id
from .trend_analyzer import analyze_trends


def run_brief(idea: GameIdea, settings: Settings | None = None) -> Brief:
    settings = settings or get_settings()
    queries = plan_queries(idea, max_queries=settings.max_play_searches)
    client = SerpClient(settings)

    collected: list[PlayApp] = []
    for q in queries:
        collected.extend(client.search_play(q))
    unique = dedupe_by_product_id(collected)

    ranked = _rank_for_enrichment(idea, unique)
    enriched: list[PlayApp] = []
    for app in ranked[: settings.max_product_lookups]:
        detail = client.enrich_product(app.product_id)
        if detail is None:
            enriched.append(app)
            continue
        detail.source_query = app.source_query
        detail.chart = app.chart
        if not detail.description and app.description:
            detail.description = app.description
        if not detail.genre and app.genre:
            detail.genre = app.genre
        enriched.append(detail)

    enriched_ids = {a.product_id for a in enriched}
    for app in ranked:
        if app.product_id not in enriched_ids:
            enriched.append(app)
        if len(enriched) >= 12:
            break

    coverage_q = plan_coverage_query(idea)
    web_hits = client.search_google(coverage_q)

    return analyze(
        idea=idea,
        queries=queries + [f"[web] {coverage_q}"],
        apps=enriched,
        web_hits=web_hits,
        api_calls_used=dict(client.calls),
        sample_mode=False,
    )


def run_trend_scan(settings: Settings | None = None):
    """Live scan: trending charts → room → build recommendation.

    Budget (~9 calls): 2 game charts + up to 5 product lookups + 1 Google web.
    """
    settings = settings or get_settings()
    client = SerpClient(settings)
    sources: list[str] = []

    topselling = client.chart_games("topselling_free")
    if topselling or client.calls["google_play_games"]:
        sources.append("topselling_free")
    movers = client.chart_games("movers_shakers")
    if movers or client.calls["google_play_games"] >= 2:
        sources.append("movers_shakers")

    # Optional third play call: casual shelf probe if budget remains.
    if client.play_calls < settings.max_play_searches:
        probe = client.search_play("casual puzzle game")
        if probe:
            sources.append("q:casual puzzle game")
        combined = topselling + movers + probe
    else:
        combined = topselling + movers

    unique = dedupe_by_product_id(combined)

    # Prefer enriching a mix of movers + topsellers.
    ranked = _rank_for_trend_enrichment(unique)
    enriched: list[PlayApp] = []
    for app in ranked[: settings.max_product_lookups]:
        detail = client.enrich_product(app.product_id)
        if detail is None:
            enriched.append(app)
            continue
        detail.source_query = app.source_query
        detail.chart = app.chart
        if not detail.genre and app.genre:
            detail.genre = app.genre
        if not detail.description and app.description:
            detail.description = app.description
        enriched.append(detail)

    enriched_ids = {a.product_id for a in enriched}
    for app in ranked:
        if app.product_id not in enriched_ids:
            enriched.append(app)
        if len(enriched) >= 20:
            break

    web_q = "\"Google Play\" trending mobile games puzzle OR casual"
    web_hits = client.search_google(web_q)

    return analyze_trends(
        apps=enriched,
        sources=sources or ["charts"],
        web_hits=web_hits,
        api_calls_used=dict(client.calls),
        sample_mode=False,
        market=settings.gl,
    )


def _rank_for_enrichment(idea: GameIdea, apps: list[PlayApp]) -> list[PlayApp]:
    from .query_planner import distinctive_tokens, tokenize

    idea_toks = set(distinctive_tokens(idea.title, idea.keywords, idea.pitch))

    def score(app: PlayApp) -> tuple:
        title_toks = set(tokenize(app.title))
        overlap = len(idea_toks & title_toks)
        rating = app.rating or 0.0
        return (-overlap, -rating, app.title.lower())

    return sorted(apps, key=score)


def _rank_for_trend_enrichment(apps: list[PlayApp]) -> list[PlayApp]:
    def score(app: PlayApp) -> tuple:
        # Prefer movers, then missing genre (needs enrichment), then rating.
        movers = 0 if app.chart == "movers_shakers" else 1
        needs_genre = 0 if not app.genre else 1
        rating = app.rating or 0.0
        return (movers, needs_genre, -rating, app.title.lower())

    return sorted(apps, key=score)


def sample_brief(idea: GameIdea | None = None) -> Brief:
    """Clearly labeled SAMPLE preview — never presented as live SerpApi data."""
    idea = idea or GameIdea(
        title="Rush Bay",
        pitch="unblock colorful buses, match passengers, clear island parking bays",
        keywords="bus parking sort puzzle",
    )
    queries = plan_queries(idea)
    apps = [
        PlayApp(
            product_id="com.example.busjam",
            title="Bus Jam Color Sort",
            developer="Sample Studio",
            rating=4.6,
            ratings_count=120_000,
            description="Sort colorful buses and free the parking lot in this puzzle jam.",
            genre="Puzzle",
            link="https://play.google.com/store/apps/details?id=com.example.busjam",
            source_query=queries[0] if queries else "bus jam",
        ),
        PlayApp(
            product_id="com.example.parkingout",
            title="Parking Jam Out",
            developer="Demo Games",
            rating=4.4,
            ratings_count=85_000,
            description="Unblock cars and buses from crowded parking bays.",
            genre="Puzzle",
            link="https://play.google.com/store/apps/details?id=com.example.parkingout",
            source_query=queries[1] if len(queries) > 1 else "parking jam",
        ),
        PlayApp(
            product_id="com.example.colorsort",
            title="Water Color Sort Puzzle",
            developer="Fixture Labs",
            rating=4.7,
            ratings_count=500_000,
            description="Sort colored water — not a bus game, but shares sort/puzzle tokens.",
            genre="Puzzle",
            link="https://play.google.com/store/apps/details?id=com.example.colorsort",
            source_query=queries[-1] if queries else "color sort",
        ),
        PlayApp(
            product_id="com.example.islandpark",
            title="Island Bus Parking",
            developer="Harbor Soft",
            rating=4.1,
            ratings_count=12_400,
            description="Park buses on a tropical island and match passenger colors.",
            genre="Simulation",
            link="https://play.google.com/store/apps/details?id=com.example.islandpark",
            source_query=queries[0] if queries else "island bus",
        ),
    ]
    web_hits = [
        WebHit(
            title="SAMPLE: Why parking-jam puzzles keep topping casual charts",
            link="https://example.com/sample-parking-jam-article",
            snippet="Editors discuss the wave of bus and car unblock puzzles on Google Play.",
            source="example.com",
        ),
        WebHit(
            title="SAMPLE: Indie ASO notes for sort-puzzle hybrids",
            link="https://example.com/sample-aso-notes",
            snippet="Title tokens like jam, sort, and bus are heavily contested in 2025–2026.",
            source="example.com",
        ),
    ]
    return analyze(
        idea=idea,
        queries=queries + ["[web] SAMPLE coverage query"],
        apps=apps,
        web_hits=web_hits,
        api_calls_used={"google_play": 0, "google_play_product": 0, "google": 0},
        sample_mode=True,
    )


def sample_trend_scan():
    """SAMPLE trend layout — fixture charts, not live SerpApi.

    Descriptions are specific enough for loop classification (bus/parking sort,
    tile blast, and so on). The page banner still says SAMPLE, not live.
    """
    apps = [
        PlayApp(
            product_id="com.sample.blockblast",
            title="Block Blast!",
            developer="Hungry Studio",
            rating=4.6,
            ratings_count=20_000_000,
            genre="Puzzle",
            description="Blast wooden blocks off the board in this tile blast puzzle.",
            chart="topselling_free",
            source_query="chart:topselling_free",
            link="https://play.google.com/store/apps/details?id=com.sample.blockblast",
        ),
        PlayApp(
            product_id="com.sample.woodoku",
            title="Wood Block Puzzle",
            developer="Tripledot",
            rating=4.7,
            ratings_count=8_000_000,
            genre="Puzzle",
            description="Fit wood blocks, then blast full lines. A tile blast cousin of Block Blast.",
            chart="topselling_free",
            source_query="chart:topselling_free",
            link="https://play.google.com/store/apps/details?id=com.sample.woodoku",
        ),
        PlayApp(
            product_id="com.sample.busjam",
            title="Bus Jam Out",
            developer="Ivy Games",
            rating=4.5,
            ratings_count=800_000,
            genre="Puzzle",
            description="Unblock colorful buses stuck in a parking jam and clear the lot.",
            chart="topselling_free",
            source_query="chart:topselling_free",
            link="https://play.google.com/store/apps/details?id=com.sample.busjam",
        ),
        PlayApp(
            product_id="com.sample.parkingjam",
            title="Parking Jam 3D",
            developer="Rollic",
            rating=4.4,
            ratings_count=400_000,
            genre="Puzzle",
            description="Sort cars out of a crowded parking jam. Tap to unblock the exit.",
            chart="topselling_free",
            source_query="chart:topselling_free",
            link="https://play.google.com/store/apps/details?id=com.sample.parkingjam",
        ),
        PlayApp(
            product_id="com.sample.trafficbus",
            title="Traffic Jam Bus Puzzle",
            developer="Easybrain",
            rating=4.3,
            ratings_count=120_000,
            genre="Puzzle",
            description="Clear a bus traffic jam. Move buses until the parking bay is free.",
            chart="movers_shakers",
            source_query="chart:movers_shakers",
            link="https://play.google.com/store/apps/details?id=com.sample.trafficbus",
        ),
        PlayApp(
            product_id="com.sample.survivor",
            title="Survivor.io",
            developer="Habby",
            rating=4.4,
            ratings_count=1_200_000,
            genre="Action",
            description="Survivor horde game: auto-attack waves in an .io arena.",
            chart="movers_shakers",
            source_query="chart:movers_shakers",
            link="https://play.google.com/store/apps/details?id=com.sample.survivor",
        ),
        PlayApp(
            product_id="com.sample.merge",
            title="Merge Mansion",
            developer="Metacore",
            rating=4.5,
            ratings_count=22_000,
            genre="Puzzle",
            description="Merge items to restore a mansion. Not a jam or blast game.",
            chart="movers_shakers",
            source_query="chart:movers_shakers",
            link="https://play.google.com/store/apps/details?id=com.sample.merge",
        ),
        PlayApp(
            product_id="com.sample.idle",
            title="Idle Miner Tycoon",
            developer="Kolibri",
            rating=4.3,
            ratings_count=4_000_000,
            genre="Simulation",
            description="Idle tycoon: dig, upgrade shafts, and leave the mine running.",
            chart="topselling_free",
            source_query="chart:topselling_free",
            link="https://play.google.com/store/apps/details?id=com.sample.idle",
        ),
    ]
    web_hits = [
        WebHit(
            title="SAMPLE: Parking-jam puzzles and tile blast still own casual charts",
            link="https://example.com/sample-trends",
            snippet="Writers name Bus Jam clones and Block Blast as the two casual piles, with merge as a thinner slice.",
            source="example.com",
        )
    ]
    return analyze_trends(
        apps=apps,
        sources=["topselling_free", "movers_shakers"],
        web_hits=web_hits,
        api_calls_used={
            "google_play": 0,
            "google_play_games": 0,
            "google_play_product": 0,
            "google": 0,
        },
        sample_mode=True,
        market="in",
    )



__all__ = [
    "run_brief",
    "run_trend_scan",
    "sample_brief",
    "sample_trend_scan",
    "SerpApiError",
]
