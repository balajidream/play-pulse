"""Hit-then-clones shelf read. Size is ratings count, never an invented launch date."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import PlayApp, WebHit

# A "giant" incumbent. Below this, a small cluster can still look early.
GIANT_RATINGS = 500_000
# Hit is "much larger" when it has at least this multiple of the next title.
SIZE_GAP = 5
# More copies than this means the shelf is filled.
FILLED_CLONES = 4


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

    def to_template_dict(self) -> dict:
        return {
            "stories": [s.to_dict() for s in self.stories],
            "sample_mode": self.sample_mode,
            "market": self.market,
            "focus": self.focus,
            "api_calls_used": self.api_calls_used,
            "web_hits": self.web_hits[:3],
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
