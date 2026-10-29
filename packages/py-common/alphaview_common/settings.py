from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CommonSettings(BaseSettings):
    """Settings shared by every service; services subclass this for their own fields."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    service_name: str = "alphaview"
    database_url: str = "postgresql+asyncpg://alphaview:alphaview@localhost:5432/alphaview"
    redis_url: str = "redis://localhost:6379/0"

    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_database: str = "alphaview"

    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"

    jwt_secret: str = "change-me-in-production-please-32b"
    jwt_ttl_minutes: int = 720
    # Fernet key (urlsafe base64, 32 bytes).
    encryption_key: str = ""

    frontend_url: str = "http://localhost:3000"
    cors_origins: list[str] = ["http://localhost:3000"]

    @field_validator("jwt_secret")
    @classmethod
    def _strong_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return v


@lru_cache
def get_common_settings() -> CommonSettings:
    return CommonSettings()
