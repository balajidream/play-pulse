"""Deterministic competitive analysis — no LLM.

Computes title-token frequency, saturation, pitch overlap, findings, cautions.
"""

from __future__ import annotations

from collections import Counter

from .models import Brief, GameIdea, PlayApp, TokenStat, WebHit
from .query_planner import STOPWORDS, distinctive_tokens, tokenize

# Reviews at or above this count count as "heavy" incumbents.
HEAVY_REVIEWS = 50_000
# Token share across competitor titles to call it "saturated".
SATURATED_SHARE = 0.4


def _title_tokens_for_freq(apps: list[PlayApp]) -> Counter:
    counts: Counter = Counter()
    for app in apps:
        toks = [
            t
            for t in tokenize(app.title)
            if (t not in STOPWORDS and len(t) >= 3) or len(t) >= 4
        ]
        # Unique within one title so one app doesn't inflate a word.
        for t in set(toks):
            counts[t] += 1
    return counts


def token_frequency(apps: list[PlayApp], limit: int = 12) -> list[TokenStat]:
    if not apps:
        return []
    counts = _title_tokens_for_freq(apps)
    n = len(apps)
    stats = [
        TokenStat(token=tok, count=cnt, share=round(cnt / n, 3))
        for tok, cnt in counts.most_common(limit)
    ]
    return stats


def close_title_match_count(idea: GameIdea, apps: list[PlayApp]) -> int:
    """Count competitors whose titles share ≥2 distinctive tokens with the idea."""
    idea_toks = set(distinctive_tokens(idea.title, idea.keywords, idea.pitch))
    if not idea_toks:
        return 0
    close = 0
    for app in apps:
        app_toks = set(tokenize(app.title))
        if len(idea_toks & app_toks) >= 2:
            close += 1
    return close


def heavy_review_count(apps: list[PlayApp], threshold: int = HEAVY_REVIEWS) -> int:
    n = 0
    for app in apps:
        if app.ratings_count is not None and app.ratings_count >= threshold:
            n += 1
    return n


def pitch_overlap_tokens(idea: GameIdea, apps: list[PlayApp], limit: int = 10) -> list[str]:
    pitch_toks = set(distinctive_tokens(idea.title, idea.pitch, idea.keywords))
    if not pitch_toks or not apps:
        return []
    corpus = " ".join(
        f"{a.title} {a.description} {a.genre}" for a in apps
    ).lower()
    present = [t for t in distinctive_tokens(idea.title, idea.pitch, idea.keywords) if t in corpus]
    # Prefer tokens that appear in titles specifically.
    title_blob = " ".join(a.title for a in apps).lower()
    present.sort(key=lambda t: (0 if t in title_blob else 1, -len(t)))
    # Dedupe preserving order
    out: list[str] = []
    seen: set[str] = set()
    for t in present:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:limit]


def saturation_read(
    apps: list[PlayApp], close_matches: int, heavy: int
) -> tuple[str, str]:
    n = len(apps)
    if n == 0:
        return (
            "Sparse shelf",
            "No close Play results for these queries — either a niche gap or the queries need tuning.",
        )
    if close_matches >= 5 or (heavy >= 3 and close_matches >= 2):
        return (
            "Crowded shelf",
            f"{close_matches} titles look close to your wording and {heavy} already have "
            f"{HEAVY_REVIEWS:,}+ ratings. Expect discovery pressure unless positioning is sharp.",
        )
    if close_matches >= 2 or heavy >= 2:
        return (
            "Contested shelf",
            f"{n} competitors surfaced; {close_matches} close title matches and {heavy} heavy "
            f"review incumbents. Differentiating on theme or twist matters.",
        )
    return (
        "Openish shelf",
        f"{n} related apps found, but only {close_matches} close title matches and {heavy} "
        f"heavy-review players. Room to claim a clearer name and angle.",
    )


def build_findings(
    idea: GameIdea,
    apps: list[PlayApp],
    token_stats: list[TokenStat],
    close_matches: int,
    heavy: int,
    overlap: list[str],
    web_hits: list[WebHit],
) -> list[str]:
    findings: list[str] = []
    n = len(apps)

    # Finding 1: shelf size + heavy players
    if n == 0:
        findings.append(
            "Play returned no apps for the planned queries — treat as a signal to broaden "
            "keywords, not as proof the niche is empty."
        )
    else:
        top = apps[0]
        rating_bit = (
            f"{top.rating:.1f}★ / {top.ratings_count:,} ratings"
            if top.rating is not None and top.ratings_count is not None
            else (
                f"{top.rating:.1f}★"
                if top.rating is not None
                else "no rating yet in enrichment"
            )
        )
        findings.append(
            f"Shelf scan found {n} unique Play apps. Top enriched listing: "
            f"“{top.title}” by {top.developer or 'unknown'} ({rating_bit})."
        )

    # Finding 2: saturated title tokens
    saturated = [s for s in token_stats if s.share >= SATURATED_SHARE and s.count >= 2]
    if saturated:
        words = ", ".join(f"“{s.token}” ({s.count}/{n})" for s in saturated[:4])
        findings.append(
            f"Title-token saturation: {words} show up across many competitor titles — "
            f"those words alone will not differentiate “{idea.title}”."
        )
    elif token_stats:
        top_tok = token_stats[0]
        findings.append(
            f"Most common competitor title token is “{top_tok.token}” "
            f"({top_tok.count} of {n} apps). The cluster is not fully saturated yet."
        )
    else:
        findings.append(
            "Not enough competitor titles to compute token saturation."
        )

    # Finding 3: overlap + web coverage
    if overlap:
        findings.append(
            f"Your pitch already shares wording with live listings: "
            f"{', '.join(overlap[:6])}. "
            + (
                f"Web coverage also returned {len(web_hits)} articles/posts about this genre."
                if web_hits
                else "Little recent web coverage showed up for the genre query."
            )
        )
    else:
        findings.append(
            "Pitch words barely appear in competitor titles/descriptions — either a fresh "
            "angle or queries missed the real shelf. Cross-check the web hits."
            if not web_hits
            else f"Pitch overlap with store copy is low, but {len(web_hits)} web results "
            f"still discuss this genre — store and press language may diverge."
        )

    return findings[:3]


def build_cautions(
    idea: GameIdea,
    apps: list[PlayApp],
    token_stats: list[TokenStat],
    close_matches: int,
    overlap: list[str],
) -> list[str]:
    cautions: list[str] = []
    title_l = idea.title.lower()
    saturated_words = {s.token for s in token_stats if s.share >= SATURATED_SHARE}

    # Caution 1: title collision
    if close_matches >= 2:
        cautions.append(
            f"Working title “{idea.title}” sits near {close_matches} existing titles that "
            f"share multiple tokens — consider a more distinctive proper noun or setting."
        )
    elif any(t in title_l for t in saturated_words):
        hit = [t for t in saturated_words if t in title_l]
        cautions.append(
            f"Title leans on saturated shelf words ({', '.join(hit)}). Pair them with a "
            f"unique hook word players can remember and search."
        )
    else:
        cautions.append(
            f"“{idea.title}” does not collide hard with the current sample — still search "
            f"exact-match and trademark before shipping the icon."
        )

    # Caution 2: positioning vs incumbents
    heavy_names = [
        a.title
        for a in apps
        if a.ratings_count is not None and a.ratings_count >= HEAVY_REVIEWS
    ][:3]
    if heavy_names:
        hook = "/".join(overlap[:2] or ["puzzle"])
        names = ", ".join(f"“{n}”" for n in heavy_names)
        cautions.append(
            f"Do not position as another “{hook} game” next to incumbents like "
            f"{names} — lead with the twist (setting, constraint, or fantasy) in the subtitle."
        )
    else:
        cautions.append(
            "Incumbents in this sample are not review-heavy yet — still avoid a generic "
            "subtitle that only restates the mechanic words already in every listing."
        )

    # Caution 3: ASO / keyword stuffing
    if len(overlap) >= 4:
        cautions.append(
            "Pitch language mirrors the shelf closely ("
            + ", ".join(overlap[:5])
            + "). Useful for ASO keywords in the short description; risky if the store "
            "icon/title look interchangeable with the top five."
        )
    else:
        cautions.append(
            "Keep short-description keywords concrete (mechanic + fantasy), and reserve "
            "the title for a memorable brand — judges and players both skim titles first."
        )

    return cautions[:3]


def analyze(
    idea: GameIdea,
    queries: list[str],
    apps: list[PlayApp],
    web_hits: list[WebHit],
    api_calls_used: dict[str, int] | None = None,
    sample_mode: bool = False,
) -> Brief:
    token_stats = token_frequency(apps)
    close = close_title_match_count(idea, apps)
    heavy = heavy_review_count(apps)
    overlap = pitch_overlap_tokens(idea, apps)
    label, detail = saturation_read(apps, close, heavy)
    findings = build_findings(idea, apps, token_stats, close, heavy, overlap, web_hits)
    cautions = build_cautions(idea, apps, token_stats, close, overlap)
    return Brief(
        idea=idea,
        queries=queries,
        apps=apps,
        web_hits=web_hits,
        token_stats=token_stats,
        close_title_matches=close,
        heavy_review_apps=heavy,
        pitch_overlap=overlap,
        saturation_label=label,
        saturation_detail=detail,
        findings=findings,
        cautions=cautions,
        api_calls_used=api_calls_used or {},
        sample_mode=sample_mode,
    )
