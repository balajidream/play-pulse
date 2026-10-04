"""Hit-then-clones shelf read. Size is ratings count, never an invented launch date."""

from __future__ import annotations

from dataclasses import dataclass, field

from .loops import GENERIC, classify_loop, loop_name
from .models import PlayApp, WebHit
from .query_planner import STOPWORDS, tokenize

# A "giant" incumbent. Below this, a small cluster can still look early.
GIANT_RATINGS = 500_000
# Hit is "much larger" when it has at least this multiple of the next title.
SIZE_GAP = 5
# More copies than this means the shelf is filled.
FILLED_CLONES = 4
# A shelf needs the hit plus at least this many copies.
MIN_COPIES = 3
MAX_SHELVES = 20


@dataclass
class ShelfStory:
    loop_name: str
    label: str  # "Early" or "Filled"
    hit: PlayApp
    clones: list[PlayApp]
    size_note: str
    seen_count: int = 0
    more_count: int = 0
    first_page_only: bool = False

    def to_dict(self) -> dict:
        shown = self.clones[:4]
        return {
            "loop_name": self.loop_name,
            "label": self.label,
            "hit": self.hit,
            "clones": shown,
            "size_note": self.size_note,
            "seen_count": self.seen_count,
            "more_count": self.more_count,
            "first_page_only": self.first_page_only,
        }


@dataclass
class MarketReport:
    stories: list[ShelfStory]
    sample_mode: bool = False
    market: str = "in"
    focus: str = ""
    api_calls_used: dict[str, int] = field(default_factory=dict)
    web_hits: list[WebHit] = field(default_factory=list)
    qualified_count: int = 0

    def to_template_dict(self) -> dict:
        return {
            "stories": [s.to_dict() for s in self.stories],
            "sample_mode": self.sample_mode,
            "market": self.market,
            "focus": self.focus,
            "api_calls_used": self.api_calls_used,
            "web_hits": self.web_hits[:3],
            "qualified_count": self.qualified_count,
            "shown_count": len(self.stories),
        }


def _ratings(app: PlayApp) -> int:
    return app.ratings_count if app.ratings_count is not None else -1


def rank_by_size(apps: list[PlayApp]) -> list[PlayApp]:
    """Largest ratings count first. Missing counts sort last. Not launch order."""
    return sorted(apps, key=lambda a: (-_ratings(a), a.title.lower()))


def shelf_label(apps: list[PlayApp]) -> str:
    if not apps:
        return "Filled"
    ranked = rank_by_size(apps)
    clones = ranked[1:]
    hit_n = max(_ratings(ranked[0]), 0)
    second = max(_ratings(clones[0]), 0) if clones else 0
    much_larger = hit_n > 0 and (not clones or hit_n >= SIZE_GAP * max(second, 1))
    few = len(clones) < FILLED_CLONES
    no_giant = hit_n < GIANT_RATINGS
    if len(clones) >= FILLED_CLONES:
        return "Filled"
    if few and much_larger:
        return "Early"
    if few and no_giant and len(ranked) >= 2:
        return "Early"
    if few and len(clones) == 0:
        return "Early"
    return "Filled"


def size_note(apps: list[PlayApp], label: str) -> str:
    ranked = rank_by_size(apps)
    n_copies = max(len(ranked) - 1, 0)
    copies = f"{n_copies} {'copy' if n_copies == 1 else 'copies'}"
    return f"Biggest by ratings, not launch date. {copies}. {label}."


def story_for(
    loop_name: str, apps: list[PlayApp], first_page_only: bool = False
) -> ShelfStory | None:
    unique: list[PlayApp] = []
    seen: set[str] = set()
    for app in apps:
        if not app.product_id or app.product_id in seen:
            continue
        seen.add(app.product_id)
        unique.append(app)
    if not unique:
        return None
    ranked = rank_by_size(unique)
    label = shelf_label(ranked)
    shown = ranked[1:5]
    more = max(len(ranked) - 1 - len(shown), 0)
    return ShelfStory(
        loop_name=loop_name,
        label=label,
        hit=ranked[0],
        clones=shown,
        size_note=size_note(ranked, label),
        seen_count=len(ranked),
        more_count=more,
        first_page_only=first_page_only,
    )



# Title words that must not name a shelf or glue unrelated games together.
CLUSTER_SKIP = STOPWORDS | GENERIC | frozenset(
    {"game", "games", "puzzle", "free", "3d", "hd", "pro", "online", "offline", "new", "best"}
)


def _title_tokens(app: PlayApp) -> set[str]:
    return {tok for tok in tokenize(app.title) if tok not in CLUSTER_SKIP and len(tok) >= 3}


def _shelf_name(apps: list[PlayApp], seed: str) -> str:
    sets = [_title_tokens(a) for a in apps]
    if not sets:
        return seed
    common = set.intersection(*sets)
    if seed not in common:
        common.add(seed)
    ordered = sorted(common, key=lambda tok: (tok != seed, -len(tok), tok))
    return " ".join(ordered[:3])


def cluster_unnamed(apps: list[PlayApp], first_page_only: bool = False) -> list[ShelfStory]:
    """Group titles that missed a known loop by a shared distinctive title token.

    Each title is used once. A cluster needs the hit plus at least 3 other titles.
    The shelf name is the tokens those titles all share. No invented titles.
    """
    index: dict[str, list[PlayApp]] = {}
    for app in apps:
        for tok in _title_tokens(app):
            index.setdefault(tok, []).append(app)
    candidates = [tok for tok, group in index.items() if len(group) >= MIN_COPIES + 1]
    # Smaller pools first so a tight token is not swallowed by a broader one.
    candidates.sort(key=lambda tok: (len(index[tok]), tok))
    used: set[str] = set()
    stories: list[ShelfStory] = []
    for tok in candidates:
        group = [a for a in index[tok] if a.product_id not in used]
        if len(group) < MIN_COPIES + 1:
            continue
        name = _shelf_name(group, tok)
        story = story_for(name, group, first_page_only=first_page_only)
        if story is None or story.seen_count < MIN_COPIES + 1:
            continue
        stories.append(story)
        for app in group:
            used.add(app.product_id)
    return stories


def discover_shelves(apps: list[PlayApp], first_page_only: bool = False) -> list[ShelfStory]:
    """Group titles with the loop classifier. Drop groups with fewer than 3 copies.

    Order is fewest copies first (the opportunity order). At most 20 shelves.
    """
    buckets: dict[str, list[PlayApp]] = {}
    seen: set[str] = set()
    deduped: list[PlayApp] = []
    for app in apps:
        if not app.product_id or app.product_id in seen:
            continue
        seen.add(app.product_id)
        deduped.append(app)
        loop_id = classify_loop(app)
        if not loop_id:
            continue
        buckets.setdefault(loop_id, []).append(app)
    stories: list[ShelfStory] = []
    for loop_id, group in buckets.items():
        if len(group) < MIN_COPIES + 1:
            continue
        story = story_for(loop_name(loop_id), group, first_page_only=first_page_only)
        if story is None or story.seen_count < MIN_COPIES + 1:
            continue
        stories.append(story)
    leftover = [app for app in deduped if app.product_id not in {a.product_id for g in buckets.values() for a in g}]
    stories.extend(cluster_unnamed(leftover, first_page_only=first_page_only))
    stories.sort(key=lambda s: (s.seen_count - 1, s.loop_name.lower()))
    return stories
