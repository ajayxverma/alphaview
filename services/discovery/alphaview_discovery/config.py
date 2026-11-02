from functools import lru_cache

from alphaview_common.settings import CommonSettings


class Settings(CommonSettings):
    max_runs_per_hour: int = 20
    max_opportunities: int = 6
    # Nominatim-compatible geocoder (public OSM by default; self-host for production volume).
    geocoder_url: str = "https://nominatim.openstreetmap.org"
    geocoder_user_agent: str = "alphaview/0.1 (market-intelligence; contact: admin@alphaview.local)"


@lru_cache
def get_settings() -> Settings:
    return Settings()
