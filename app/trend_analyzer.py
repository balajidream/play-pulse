"""Deterministic trend / room / build-next analysis — no LLM.

Groups chart apps into gameplay loops (bus/parking sort, tile blast, …)
from title + description tokens, then cites those titles in the copy.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from .analyzer import HEAVY_REVIEWS, token_frequency
from .loops import GENERIC, classify_loop, loop_name, loop_twist
from .models import GenreStat, Opportunity, PlayApp, TrendScan, WebHit
from .query_planner import tokenize

# A loop is "crowded" once two or more chart apps land in it,
# or one app already has heavy review mass.
CROWDED_COUNT = 2


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


def _fmt_app(app: PlayApp) -> str:
    bits = [f"“{app.title}”"]
    if app.developer:
        bits.append(f"by {app.developer}")
    if app.rating is not None and app.ratings_count is not None:
        bits.append(f"({app.rating:.1f}★, {app.ratings_count:,} ratings)")
    elif app.rating is not None:
        bits.append(f"({app.rating:.1f}★)")
    elif app.ratings_count is not None:
        bits.append(f"({app.ratings_count:,} ratings)")
    return " ".join(bits)


def _cite(apps: list[PlayApp], limit: int = 3) -> str:
    if not apps:
        return "none"
    return "; ".join(_fmt_app(a) for a in apps[:limit])


def _is_heavy(app: PlayApp) -> bool:
    return app.ratings_count is not None and app.ratings_count >= HEAVY_REVIEWS


def worn_title_words(apps: list[PlayApp], limit: int = 4) -> list[str]:
    """Words that repeat across titles in this loop — not generic filler."""
    if len(apps) < 2:
        # Single listing: words in its title that are loop-ish, still useful to avoid.
        counts: Counter = Counter()
        for tok in set(tokenize(apps[0].title)) if apps else []:
            if tok not in GENERIC and len(tok) >= 3:
                counts[tok] += 1
        return [t for t, _ in counts.most_common(limit)]
    counts = Counter()
    for app in apps:
        for tok in set(tokenize(app.title)):
            if tok in GENERIC or len(tok) < 3:
                continue
            counts[tok] += 1
    repeated = [(t, c) for t, c in counts.items() if c >= 2]
    repeated.sort(key=lambda pair: (-pair[1], -len(pair[0]), pair[0]))
    return [t for t, _ in repeated[:limit]]


def cluster_apps(apps: list[PlayApp]) -> dict[str, list[PlayApp]]:
    groups: dict[str, list[PlayApp]] = defaultdict(list)
    for app in apps:
        loop_id = classify_loop(app)
        if loop_id:
            groups[loop_id].append(app)
    return groups


def _crowded(apps: list[PlayApp]) -> bool:
    if len(apps) >= CROWDED_COUNT:
        return True
    return len(apps) == 1 and _is_heavy(apps[0])


def find_opportunities(apps: list[PlayApp]) -> list[Opportunity]:
    """Room = a recognizable loop that is on the chart but not a clone pile.

    Evidence always names the apps. If every matched loop is crowded, the
    list is empty and the copy says so instead of inventing a genre.
    """
    groups = cluster_apps(apps)
    opps: list[Opportunity] = []
    for loop_id, group in groups.items():
        if _crowded(group):
            continue
        name = loop_name(loop_id)
        worn = worn_title_words(group)
        worn_bit = (
            f" Title words already in use: {', '.join(worn)}."
            if worn
            else ""
        )
        # Higher room when the loop is merely visible (1 light app).
        heavy = sum(1 for a in group if _is_heavy(a))
        room = 1.0 - (0.25 * len(group)) - (0.4 * heavy)
        opps.append(
            Opportunity(
                label=name,
                kind="loop",
                evidence=f"Only {_cite(group)}.{worn_bit} Twist that would still be new: {loop_twist(loop_id)}.",
                room_score=round(room, 3),
            )
        )
    opps.sort(key=lambda o: (-o.room_score, o.label))
    return opps[:4]


def trending_summary_text(apps: list[PlayApp], sources: list[str]) -> str:
    if not apps:
        return (
            "No chart apps returned for this market — check the SerpApi key, "
            "credits, and gl/hl settings."
        )
    groups = cluster_apps(apps)
    named = [_fmt_app(a) for a in apps[:4]]
    bits = [
        f"This pull has {len(apps)} Play games ({', '.join(sources)}).",
        "Named on the charts: " + "; ".join(named) + ".",
    ]
    if groups:
        loop_bits = []
        for loop_id, group in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            loop_bits.append(f"{loop_name(loop_id)} ({len(group)}: {_cite(group, 2)})")
        bits.append("Loops in this pull: " + "; ".join(loop_bits) + ".")
    else:
        bits.append(
            "None of these titles matched a known casual loop (bus/parking sort, "
            "tile blast, survivor.io, merge, idle tycoon) — read the named games, "
            "do not invent a genre from the Play category label."
        )
    return " ".join(bits)


def room_summary_text(apps: list[PlayApp], opportunities: list[Opportunity]) -> str:
    groups = cluster_apps(apps)
    crowded = [(lid, g) for lid, g in groups.items() if _crowded(g)]
    if not groups:
        cited = _cite(apps, 3)
        return (
            f"No recognizable loop cluster in this pull ({cited}). "
            "That is not a green light — the shelf may just be big-brand charts. "
            "Do not treat a Play category like Casual as an open genre."
        )
    if not opportunities:
        # Everything we recognized is crowded. Name the closest (smallest) gap.
        crowded.sort(key=lambda pair: (len(pair[1]), -sum(1 for a in pair[1] if _is_heavy(a))))
        lid, group = crowded[0]
        worn = worn_title_words(group)
        worn_bit = ", ".join(worn) if worn else "the words already in those titles"
        return (
            f"The shelf is crowded. Closest gap is still {loop_name(lid)}, "
            f"and it is not open: {_cite(group)}. "
            f"Worn title words: {worn_bit}. "
            f"A build only makes sense if the twist is {loop_twist(lid)}."
        )
    parts = []
    for o in opportunities[:3]:
        parts.append(f"{o.label} — {o.evidence}")
    return "Still has room (visible, not a clone pile): " + " ".join(parts)


def build_recommendation_text(apps: list[PlayApp], opportunities: list[Opportunity]) -> str:
    if not apps:
        return (
            "Worth building next: nothing, until a chart pull actually returns games. "
            "Do not pick a genre slogan from an empty scan."
        )
    groups = cluster_apps(apps)
    if opportunities:
        pick = opportunities[0]
        return (
            f"Worth building next: a {pick.label} prototype, but only with this twist — "
            f"{pick.evidence}"
        )
    if not groups:
        return (
            "Worth building next: not a genre slogan. "
            f"These charts are {_cite(apps, 3)}. "
            "The shelf looks like big-brand or unmatched titles, not an open casual loop. "
            "Closest honest read: pick one of those named games and change the fantasy, "
            "or run idea-check on a specific title before building."
        )
    # Crowded shelf — closest gap is the smallest crowded loop.
    ranked = sorted(groups.items(), key=lambda kv: (len(kv[1]), kv[0]))
    lid, group = ranked[0]
    worn = worn_title_words(group)
    worn_bit = ", ".join(worn) if worn else "the repeated title words"
    return (
        f"Worth building next: not another {loop_name(lid)} clone. "
        f"The shelf is crowded — closest gap is {loop_name(lid)} "
        f"({_cite(group)}), and the worn words are {worn_bit}. "
        f"Only build it if the twist is {loop_twist(lid)}."
    )


def crowded_loop_notes(apps: list[PlayApp]) -> list[Opportunity]:
    """Crowded loops, cited, so the UI can list worn words + real titles."""
    notes: list[Opportunity] = []
    for loop_id, group in cluster_apps(apps).items():
        if not _crowded(group):
            continue
        worn = worn_title_words(group)
        worn_bit = ", ".join(worn) if worn else "no repeated title word beyond the brand"
        notes.append(
            Opportunity(
                label=loop_name(loop_id),
                kind="crowded_loop",
                evidence=(
                    f"Worn title words: {worn_bit}. "
                    f"Seen here: {_cite(group)}."
                ),
                room_score=0.0,
            )
        )
    notes.sort(key=lambda o: o.label)
    return notes


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
    room_opps = find_opportunities(apps)
    # UI list: room first, then crowded notes (kind distinguishes them).
    opps = room_opps + crowded_loop_notes(apps)
    web_hits = web_hits or []
    trending = trending_summary_text(apps, sources)
    room = room_summary_text(apps, room_opps)
    build = build_recommendation_text(apps, room_opps)
    if web_hits:
        first = web_hits[0]
        trending += (
            f" Separate from the store, web coverage includes “{first.title}”."
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
