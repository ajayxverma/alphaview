from functools import lru_cache

from alphaview_common.settings import CommonSettings


class Settings(CommonSettings):
    crawler_user_agent: str = "alphaview-bot/0.1 (+https://alphaview.local/bot)"
    crawler_lookback_days: int = 90


@lru_cache
def get_settings() -> Settings:
    return Settings()
