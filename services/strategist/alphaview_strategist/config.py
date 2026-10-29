from functools import lru_cache

from alphaview_common.settings import CommonSettings


class Settings(CommonSettings):
    llm_model: str = "gpt-4o-mini"


@lru_cache
def get_settings() -> Settings:
    return Settings()
