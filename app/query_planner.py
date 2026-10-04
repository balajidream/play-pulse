"""Turn a game pitch into distinct Google Play search queries.

No LLM: extract distinctive tokens, drop stopwords, and build 2–3 queries
that cover title, mechanic keywords, and genre-style phrasing.
"""

from __future__ import annotations

import re
from collections import Counter

from .models import GameIdea

STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "you",
        "your",
        "we",
        "our",
        "they",
        "their",
        "i",
        "me",
        "my",
        "into",
        "over",
        "under",
        "again",
        "further",
        "then",
        "once",
        "here",
        "there",
        "when",
        "where",
        "why",
        "how",
        "all",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "also",
        "about",
        "up",
        "out",
        "off",
        "down",
        "make",
        "making",
        "get",
        "got",
        "like",
        "new",
        "free",
        "game",
        "games",
        "app",
        "apps",
        "play",
        "mobile",
        "fun",
        "best",
        "cool",
        "awesome",
        "one",
        "line",
        "pitch",
    }
)

# Tokens that often signal puzzle / sim mechanics — keep even if short.
MECHANIC_HINTS = frozenset(
    {
        "bus",
        "sort",
        "parking",
        "unblock",
        "match",
        "puzzle",
        "jam",
        "rush",
        "bay",
        "color",
        "colour",
        "colorful",
        "colourful",
        "passenger",
        "passengers",
        "island",
        "clear",
        "merge",
        "idle",
        "tycoon",
        "sim",
        "simulator",
        "runner",
        "tower",
        "defense",
        "defence",
        "rpg",
        "fps",
        "card",
        "solitaire",
        "word",
        "trivia",
        "racing",
        "race",
        "park",
        "slot",
        "candy",
        "water",
        "sort",
        "stack",
        "slide",
        "swipe",
        "tap",
        "idle",
    }
)

TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text or "")]


def distinctive_tokens(*parts: str, min_len: int = 3) -> list[str]:
    """Ordered unique tokens, preferring longer / mechanic-hint words."""
    seen: set[str] = set()
    ordered: list[str] = []
    for part in parts:
        for tok in tokenize(part):
            if tok in STOPWORDS and tok not in MECHANIC_HINTS:
                continue
            if len(tok) < min_len and tok not in MECHANIC_HINTS:
                continue
            if tok not in seen:
                seen.add(tok)
                ordered.append(tok)
    return ordered


def _rank_tokens(tokens: list[str]) -> list[str]:
    """Prefer mechanic hints and longer tokens for query construction."""
    counts = Counter(tokens)

    def sort_key(pair: tuple[int, str]) -> tuple:
        idx, t = pair
        return (
            0 if t in MECHANIC_HINTS else 1,  # hints first
            -len(t),
            -counts[t],
            idx,
        )

    indexed = list(enumerate(tokens))
    indexed.sort(key=sort_key)
    out: list[str] = []
    seen: set[str] = set()
    for _, t in indexed:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def plan_queries(idea: GameIdea, max_queries: int = 3) -> list[str]:
    """Build 2–3 Google Play search queries from title, pitch, and keywords.

    Never returns only the raw pitch sentence.
    """
    title = (idea.title or "").strip()
    pitch = (idea.pitch or "").strip()
    keywords = (idea.keywords or "").strip()

    title_tokens = distinctive_tokens(title)
    pitch_tokens = distinctive_tokens(pitch)
    keyword_tokens = distinctive_tokens(keywords)
    ranked = _rank_tokens(title_tokens + keyword_tokens + pitch_tokens)

    queries: list[str] = []

    # 1) Title as a Play query (exact working title check).
    if title:
        queries.append(title)

    # 2) Mechanic / keyword cluster (not the raw sentence).
    mechanic = [t for t in ranked if t not in {x.lower() for x in title_tokens}]
    if not mechanic:
        mechanic = ranked[:4]
    if mechanic:
        q2 = " ".join(mechanic[:4])
        if q2.lower() != title.lower() and q2 not in queries:
            queries.append(q2)

    # 3) Genre-style phrase: top tokens + "game" for Play store recall.
    if ranked:
        core = " ".join(ranked[:3])
        q3 = f"{core} puzzle game" if "puzzle" not in ranked[:5] else f"{core} game"
        # Avoid near-duplicates of query 2.
        if all(q3.lower() != q.lower() for q in queries):
            # Also skip if it's literally the same token set as q2 plus fluff.
            q3_tokens = set(tokenize(q3)) - {"game", "puzzle"}
            q2_tokens = set(tokenize(queries[1])) if len(queries) > 1 else set()
            if q3_tokens != q2_tokens:
                queries.append(q3)

    # Ensure at least 2 queries when we have any signal.
    if len(queries) < 2 and ranked:
        fallback = " ".join(ranked[:3])
        if fallback and fallback not in queries:
            queries.append(fallback)
    if len(queries) < 2 and title and pitch:
        # Last resort: first few distinctive pitch tokens as a second query.
        pt = distinctive_tokens(pitch)[:3]
        if pt:
            queries.append(" ".join(pt))

    # Cap and drop empties.
    cleaned = [q.strip() for q in queries if q and q.strip()]
    # Deduplicate case-insensitively while preserving order.
    final: list[str] = []
    seen_q: set[str] = set()
    for q in cleaned:
        key = q.lower()
        if key not in seen_q:
            seen_q.add(key)
            final.append(q)
    return final[:max_queries]


def plan_coverage_query(idea: GameIdea, tokens: list[str] | None = None) -> str:
    """One Google web query for recent genre / market coverage writing."""
    ranked = tokens or _rank_tokens(
        distinctive_tokens(idea.title, idea.keywords, idea.pitch)
    )
    core = " ".join(ranked[:3]) if ranked else (idea.title or "mobile puzzle game")
    return f"{core} mobile game Google Play 2025 OR 2026"
