from functools import lru_cache

from alphaview_common.settings import CommonSettings


class Settings(CommonSettings):
    research_ingest_url: str = "http://discovery-api:8000"
    crawler_user_agent: str = "alphaview-bot/0.1 (+https://alphaview.local/bot)"
    crawler_lookback_days: int = 90


@lru_cache
def get_settings() -> Settings:
    return Settings()
