"""Orchestrate SerpApi pulls into trend scans and idea briefs."""

from __future__ import annotations

from .analyzer import analyze
from .config import Settings, get_settings
from .models import Brief, GameIdea, PlayApp, WebHit
from .query_planner import plan_coverage_query, plan_queries
from .serp_client import SerpApiError, SerpClient, dedupe_by_product_id
from .market import MarketReport, story_for


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
        try:
            detail = client.enrich_product(app.product_id)
        except SerpApiError:
            detail = None
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


# Preset shelves for a market scan that does not need an idea.
# Two Play searches leave room for product lookups + one web search (~8 calls).
MARKET_PROBES = (
    ("bus / parking sort", "bus jam parking puzzle"),
    ("tile blast", "block blast puzzle"),
)


def _query_for_loop(loop: str) -> tuple[str, str]:
    text = (loop or "").strip().lower()
    if any(w in text for w in ("bus", "parking", "jam")):
        return "bus / parking sort", "bus jam parking puzzle"
    if any(w in text for w in ("blast", "tile", "block")):
        return "tile blast", "block blast puzzle"
    if "survivor" in text or ".io" in text or " io" in text:
        return "survivor.io style", "survivor.io game"
    if "merge" in text:
        return "merge", "merge mansion puzzle"
    if "idle" in text or "tycoon" in text:
        return "idle tycoon", "idle tycoon game"
    name = (loop or "").strip() or "this loop"
    return name, name


def _enrich(client: SerpClient, apps: list[PlayApp], limit: int) -> list[PlayApp]:
    """Product lookups for the likely hit and a few copies only."""
    ranked = sorted(
        apps,
        key=lambda a: (
            -(a.downloads_hint or 0),
            -(a.ratings_count or 0),
            -(a.rating or 0),
            a.title.lower(),
        ),
    )
    out: list[PlayApp] = []
    seen: set[str] = set()
    for app in ranked:
        if len(out) >= limit or client.calls["google_play_product"] >= client.settings.max_product_lookups:
            break
        if app.product_id in seen:
            continue
        try:
            detail = client.enrich_product(app.product_id)
        except SerpApiError:
            detail = None
        if detail is None:
            out.append(app)
            seen.add(app.product_id)
            continue
        detail.source_query = app.source_query
        if not detail.description:
            detail.description = app.description
        if not detail.thumbnail:
            detail.thumbnail = app.thumbnail
        if not detail.developer:
            detail.developer = app.developer
        if detail.rating is None:
            detail.rating = app.rating
        out.append(detail)
        seen.add(app.product_id)
    for app in apps:
        if app.product_id not in seen:
            out.append(app)
            seen.add(app.product_id)
    return out


def run_market_scan(settings: Settings | None = None) -> MarketReport:
    """Scan two known loops. No idea required. No game-chart engine."""
    settings = settings or get_settings()
    client = SerpClient(settings)
    stories = []
    for name, query in MARKET_PROBES:
        if client.play_calls >= settings.max_play_searches:
            break
        remaining = settings.max_product_lookups - client.calls["google_play_product"]
        per_loop = min(3, remaining)
        apps, first_only = client.search_play_pages(query)
        apps = _enrich(client, apps, per_loop)
        story = story_for(name, apps, first_page_only=first_only)
        if story:
            stories.append(story)
    web_hits = client.search_google("Google Play bus jam OR block blast puzzle")
    return MarketReport(
        stories=stories,
        sample_mode=False,
        market=settings.gl,
        focus="",
        api_calls_used=dict(client.calls),
        web_hits=web_hits,
    )


def run_loop_scan(loop: str, settings: Settings | None = None) -> MarketReport:
    """One loop the developer might build. Two query shapes max."""
    settings = settings or get_settings()
    name, query = _query_for_loop(loop)
    client = SerpClient(settings)
    apps, first_only = client.search_play_pages(query)
    apps = _enrich(client, apps, settings.max_product_lookups)
    story = story_for(name, apps, first_page_only=first_only)
    web_hits = client.search_google(f"Google Play {name} game")
    return MarketReport(
        stories=[story] if story else [],
        sample_mode=False,
        market=settings.gl,
        focus=name,
        api_calls_used=dict(client.calls),
        web_hits=web_hits,
    )


def run_trend_scan(settings: Settings | None = None) -> MarketReport:
    return run_market_scan(settings)


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


def sample_trend_scan() -> MarketReport:
    """SAMPLE shelves: one big tile-blast hit plus two copies, and a full bus-sort pile.

    Icons are local placeholders so the page stays visual without a network call.
    """
    icon = "/static/placeholder.svg"

    def app(pid, title, dev, rating, count, desc, loop):
        return PlayApp(
            product_id=pid,
            title=title,
            developer=dev,
            rating=rating,
            ratings_count=count,
            description=desc,
            genre="Puzzle",
            thumbnail=icon,
            link=f"https://play.google.com/store/apps/details?id={pid}",
            source_query=loop,
        )

    tile = [
        app("com.sample.blockblast", "Block Blast!", "Hungry Studio", 4.6, 20_000_000,
            "Blast wooden blocks off the board.", "tile"),
        app("com.sample.wood", "Wood Block Puzzle", "Tripledot", 4.5, 800_000,
            "Wood blocks, then blast full lines.", "tile"),
        app("com.sample.blockpuz", "Block Puzzle Blast", "Easy Fun", 4.2, 90_000,
            "Another block blast copy.", "tile"),
    ]
    bus = [
        app("com.sample.bus1", "Bus Jam Out", "Ivy Games", 4.5, 900_000,
            "Unblock buses stuck in a parking jam.", "bus"),
        app("com.sample.bus2", "Parking Jam 3D", "Rollic", 4.4, 700_000,
            "Sort cars out of a parking jam.", "bus"),
        app("com.sample.bus3", "Traffic Jam Bus Puzzle", "Easybrain", 4.3, 500_000,
            "Clear a bus traffic jam.", "bus"),
        app("com.sample.bus4", "Car Jam Parking", "Rollic", 4.2, 420_000,
            "Parking jam with cars.", "bus"),
        app("com.sample.bus5", "Bus Sort Puzzle", "Ivy Games", 4.1, 310_000,
            "Sort buses out of the lot.", "bus"),
    ]
    stories = [
        story_for("tile blast", tile),
        story_for("bus / parking sort", bus),
    ]
    return MarketReport(
        stories=[s for s in stories if s],
        sample_mode=True,
        market="in",
        focus="",
        api_calls_used={"google_play": 0, "google_play_product": 0, "google": 0},
        web_hits=[
            WebHit(
                title="SAMPLE: tile blast still has one giant and a few copies",
                link="https://example.com/sample-trends",
                snippet="Writers contrast one block-blast hit with a crowded bus-jam shelf.",
                source="example.com",
            )
        ],
    )



__all__ = [
    "run_brief",
    "run_market_scan",
    "run_loop_scan",
    "run_trend_scan",
    "sample_brief",
    "sample_trend_scan",
    "SerpApiError",
]
