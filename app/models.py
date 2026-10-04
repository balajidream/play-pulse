"""Typed shapes for trend scans and competitive briefs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GameIdea:
    title: str
    pitch: str
    keywords: str = ""


@dataclass
class PlayApp:
    product_id: str
    title: str
    developer: str = ""
    rating: float | None = None
    ratings_count: int | None = None
    description: str = ""
    genre: str = ""
    link: str = ""
    thumbnail: str = ""
    source_query: str = ""
    chart: str = ""


@dataclass
class WebHit:
    title: str
    link: str
    snippet: str = ""
    source: str = ""


@dataclass
class TokenStat:
    token: str
    count: int
    share: float  # 0..1 of apps mentioning it


@dataclass
class GenreStat:
    genre: str
    count: int
    share: float
    avg_ratings: float | None = None
    heavy_count: int = 0


@dataclass
class Opportunity:
    label: str
    kind: str  # "genre" | "title_pattern"
    evidence: str
    room_score: float  # higher = more room


@dataclass
class Brief:
    idea: GameIdea
    queries: list[str]
    apps: list[PlayApp]
    web_hits: list[WebHit]
    token_stats: list[TokenStat]
    close_title_matches: int
    heavy_review_apps: int
    pitch_overlap: list[str]
    saturation_label: str
    saturation_detail: str
    findings: list[str]
    cautions: list[str]
    api_calls_used: dict[str, int] = field(default_factory=dict)
    sample_mode: bool = False

    def to_template_dict(self) -> dict[str, Any]:
        return {
            "idea": self.idea,
            "queries": self.queries,
            "apps": self.apps,
            "web_hits": self.web_hits,
            "token_stats": self.token_stats,
            "close_title_matches": self.close_title_matches,
            "heavy_review_apps": self.heavy_review_apps,
            "pitch_overlap": self.pitch_overlap,
            "saturation_label": self.saturation_label,
            "saturation_detail": self.saturation_detail,
            "findings": self.findings,
            "cautions": self.cautions,
            "api_calls_used": self.api_calls_used,
            "sample_mode": self.sample_mode,
        }


@dataclass
class TrendScan:
    """Answers: what's trending, what has room, what to build next."""

    sources: list[str]
    trending_apps: list[PlayApp]
    genre_stats: list[GenreStat]
    token_stats: list[TokenStat]
    opportunities: list[Opportunity]
    trending_summary: str
    room_summary: str
    build_recommendation: str
    web_hits: list[WebHit] = field(default_factory=list)
    api_calls_used: dict[str, int] = field(default_factory=dict)
    sample_mode: bool = False
    market: str = "in"

    def to_template_dict(self) -> dict[str, Any]:
        return {
            "sources": self.sources,
            "trending_apps": self.trending_apps,
            "genre_stats": self.genre_stats,
            "token_stats": self.token_stats,
            "opportunities": self.opportunities,
            "trending_summary": self.trending_summary,
            "room_summary": self.room_summary,
            "build_recommendation": self.build_recommendation,
            "web_hits": self.web_hits,
            "api_calls_used": self.api_calls_used,
            "sample_mode": self.sample_mode,
            "market": self.market,
        }
