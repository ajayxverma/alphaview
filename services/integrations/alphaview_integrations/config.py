from functools import lru_cache

from alphaview_common.settings import CommonSettings


class Settings(CommonSettings):
    google_client_id: str = ""
    google_client_secret: str = ""
    oauth_redirect_url: str = "http://localhost:8000/connections/oauth/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()
