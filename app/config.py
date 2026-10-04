"""Runtime configuration. Requires SERPAPI_API_KEY for live searches."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

SERPAPI_BASE_URL = "https://serpapi.com/search.json"

# Cap SerpApi usage (~10 calls) so a free 250-credit account can demo.
MAX_PLAY_SEARCHES = 3  # charts + optional q on google_play / google_play_games
MAX_PRODUCT_LOOKUPS = 5
MAX_GOOGLE_SEARCHES = 1

# Localization: English results, India market bias for an India hackathon.
DEFAULT_HL = "en"
DEFAULT_GL = "in"


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    base_url: str = SERPAPI_BASE_URL
    hl: str = DEFAULT_HL
    gl: str = DEFAULT_GL
    max_play_searches: int = MAX_PLAY_SEARCHES
    max_product_lookups: int = MAX_PRODUCT_LOOKUPS
    max_google_searches: int = MAX_GOOGLE_SEARCHES

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key and self.api_key.strip())


def get_settings() -> Settings:
    return Settings(api_key=os.getenv("SERPAPI_API_KEY"))
