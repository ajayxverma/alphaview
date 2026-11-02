from functools import lru_cache

from alphaview_common.settings import CommonSettings


class Settings(CommonSettings):
    # Server-wide fallback used when a workspace has not configured its own AI provider.
    llm_model: str = "gpt-4o-mini"
    # Allows http:// and private-network endpoints (e.g. local Ollama). Keep off for multi-tenant deployments.
    allow_private_llm_endpoints: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
