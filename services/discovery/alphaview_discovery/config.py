from functools import lru_cache

from alphaview_common.settings import CommonSettings


class Settings(CommonSettings):
    max_runs_per_hour: int = 20
    max_opportunities: int = 6


@lru_cache
def get_settings() -> Settings:
    return Settings()
