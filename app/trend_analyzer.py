"""Deterministic trend / room / build-next analysis — no LLM."""

from __future__ import annotations

from collections import Counter, defaultdict

from .analyzer import HEAVY_REVIEWS, token_frequency
from .models import GenreStat, Opportunity, PlayApp, TokenStat, TrendScan, WebHit

# Title tokens that often signal a crowded casual template.
TEMPLATE_TOKENS = frozenset(
    {
        "jam",
        "sort",
        "merge",
        "idle",
        "tycoon",
        "rush",
        "master",
        "go",
        "io",
        "puzzle",
        "blast",
        "match",
        "3d",
        "online",
        "battle",
        "war",
        "legends",
        "survivor",
        "survival",
        "park",
        "parking",
        "bus",
        "car",
        "water",
        "color",
        "colour",
        "tile",
        "block",
        "ball",
        "shooter",
        "runner",
        "race",
        "racing",
        "farm",
        "city",
        "craft",
    }
)


def genre_stats(apps: list[PlayApp], limit: int = 10) -> list[GenreStat]:
    if not apps:
        return []
    by_genre: dict[str, list[PlayApp]] = defaultdict(list)
    for app in apps:
        g = (app.genre or "Unknown").strip() or "Unknown"
        by_genre[g].append(app)
    n = len(apps)
    stats: list[GenreStat] = []
    for genre, group in by_genre.items():
        ratings = [a.ratings_count for a in group if a.ratings_count is not None]
        avg = round(sum(ratings) / len(ratings), 1) if ratings else None
        heavy = sum(1 for r in ratings if r >= HEAVY_REVIEWS)
        stats.append(
            GenreStat(
                genre=genre,
                count=len(group),
                share=round(len(group) / n, 3),
                avg_ratings=avg,
                heavy_count=heavy,
            )
        )
    stats.sort(key=lambda s: (-s.count, s.genre.lower()))
    return stats[:limit]


def find_opportunities(
    apps: list[PlayApp],
    genres: list[GenreStat],
    tokens: list[TokenStat],
) -> list[Opportunity]:
    """Visible-but-not-saturated genres and title patterns."""
    opps: list[Opportunity] = []
    n = len(apps) or 1

    for g in genres:
        if g.genre == "Unknown":
            continue
        # Visible: at least 2 apps. Not saturated: share under 35% OR few heavies.
        if g.count >= 2 and (g.share < 0.35 or g.heavy_count <= 1):
            avg_bit = (
                f", avg ~{int(g.avg_ratings):,} ratings among enriched"
                if g.avg_ratings is not None
                else ""
            )
            room = (1.0 - g.share) * (1.0 if g.heavy_count <= 1 else 0.7)
            opps.append(
                Opportunity(
                    label=g.genre,
                    kind="genre",
                    evidence=(
                        f"{g.count}/{n} chart apps ({int(g.share * 100)}%) in {g.genre}; "
                        f"{g.heavy_count} heavy-review incumbents{avg_bit}"
                    ),
                    room_score=round(room + (0.15 if g.count >= 2 else 0), 3),
                )
            )

    for t in tokens:
        if t.token not in TEMPLATE_TOKENS:
            continue
        # Pattern shows up but is not everywhere.
        if 2 <= t.count <= max(3, int(n * 0.35)):
            room = 1.0 - t.share
            opps.append(
                Opportunity(
                    label=t.token,
                    kind="title_pattern",
                    evidence=(
                        f"“{t.token}” appears in {t.count}/{n} titles "
                        f"({int(t.share * 100)}%) — visible on charts, not universal"
                    ),
                    room_score=round(room * 0.9, 3),
                )
            )

    # Prefer genres slightly over raw tokens; stable tie-break.
    opps.sort(key=lambda o: (-o.room_score, 0 if o.kind == "genre" else 1, o.label))
    # Dedupe by label
    out: list[Opportunity] = []
    seen: set[str] = set()
    for o in opps:
        key = f"{o.kind}:{o.label.lower()}"
        if key in seen:
            continue
        seen.add(key)
        out.append(o)
    return out[:6]


def _top_titles(apps: list[PlayApp], limit: int = 5) -> str:
    names = [f"“{a.title}”" for a in apps[:limit] if a.title]
    if not names:
        return "no titles"
    return ", ".join(names)


def trending_summary_text(
    apps: list[PlayApp], genres: list[GenreStat], sources: list[str]
) -> str:
    n = len(apps)
    if n == 0:
        return (
            "No chart apps returned for this market — check the SerpApi key, "
            "credits, and gl/hl settings."
        )
    top_g = genres[0].genre if genres else "mixed"
    movers = [a for a in apps if a.chart == "movers_shakers"]
    sellers = [a for a in apps if a.chart == "topselling_free"]
    bits = [
        f"Scanned {n} unique Google Play game chart apps ({', '.join(sources)}).",
        f"Largest genre slice: {top_g}"
        + (f" ({genres[0].count} apps, {int(genres[0].share * 100)}%)." if genres else "."),
    ]
    if sellers:
        bits.append(f"Top free examples: {_top_titles(sellers, 3)}.")
    if movers:
        bits.append(f"Movers & shakers examples: {_top_titles(movers, 3)}.")
    return " ".join(bits)


def room_summary_text(opportunities: list[Opportunity], tokens: list[TokenStat]) -> str:
    if not opportunities:
        saturated = ", ".join(f"“{t.token}”" for t in tokens[:4]) or "common title words"
        return (
            f"This sample looks tightly clustered around {saturated}. "
            "Room is limited unless you differentiate with a specific fantasy or constraint."
        )
    parts = []
    for o in opportunities[:3]:
        kind = "genre" if o.kind == "genre" else "title pattern"
        parts.append(f"{o.label} ({kind})")
    return (
        "Visible but not fully saturated: "
        + "; ".join(parts)
        + ". These show up on charts without owning every slot."
    )


def build_recommendation_text(
    opportunities: list[Opportunity],
    genres: list[GenreStat],
    tokens: list[TokenStat],
    apps: list[PlayApp],
) -> str:
    if not apps:
        return (
            "Worth building next: wait for a successful chart pull, then target a niche "
            "that appears on movers but is not the largest topselling genre."
        )
    pick = opportunities[0] if opportunities else None
    heavy = sum(
        1 for a in apps if a.ratings_count is not None and a.ratings_count >= HEAVY_REVIEWS
    )
    if pick and pick.kind == "genre":
        return (
            f"Worth building next: a small-scope game in {pick.label} that avoids the "
            f"most repeated title tokens "
            f"({', '.join(t.token for t in tokens[:3]) or 'jam/sort/idle'}). "
            f"Evidence: {pick.evidence}. "
            f"Among enriched titles, {heavy} already look review-heavy — win on a clear twist, "
            f"not a clone name."
        )
    if pick and pick.kind == "title_pattern":
        avoid = [t.token for t in tokens if t.share >= 0.35][:3]
        avoid_bit = (
            f" Avoid leading with {', '.join(avoid)} in the title."
            if avoid
            else ""
        )
        return (
            f"Worth building next: lean into the “{pick.label}” pattern that already charts "
            f"({pick.evidence}), but brand it with a unique proper noun so it is searchable."
            f"{avoid_bit}"
        )
    top = genres[0].genre if genres else "Puzzle"
    return (
        f"Worth building next: a focused {top} prototype with a memorable proper-noun title. "
        f"Charts are active ({len(apps)} apps sampled) but no clear under-served slice stood out — "
        f"differentiation matters more than genre-chasing."
    )


def analyze_trends(
    apps: list[PlayApp],
    sources: list[str],
    web_hits: list[WebHit] | None = None,
    api_calls_used: dict[str, int] | None = None,
    sample_mode: bool = False,
    market: str = "in",
) -> TrendScan:
    genres = genre_stats(apps)
    tokens = token_frequency(apps)
    opps = find_opportunities(apps, genres, tokens)
    web_hits = web_hits or []
    trending = trending_summary_text(apps, genres, sources)
    room = room_summary_text(opps, tokens)
    build = build_recommendation_text(opps, genres, tokens, apps)
    if web_hits:
        trending += (
            f" Web coverage added {len(web_hits)} recent articles/posts about mobile games "
            "(separate from the store shelf)."
        )
    return TrendScan(
        sources=sources,
        trending_apps=apps,
        genre_stats=genres,
        token_stats=tokens,
        opportunities=opps,
        trending_summary=trending,
        room_summary=room,
        build_recommendation=build,
        web_hits=web_hits,
        api_calls_used=api_calls_used or {},
        sample_mode=sample_mode,
        market=market,
    )
