from abc import ABC, abstractmethod
from enum import StrEnum
from typing import ClassVar, Literal

import httpx

from alphaview_integrations.schemas import FieldSpec

KeywordMetrics = dict[str, dict[str, float]]


class Capability(StrEnum):
    SEARCH_VOLUME = "search_volume"
    TREND = "trend"
    SERP_COMPETITION = "serp_competition"
    OWNED_SITE = "owned_site"


class ConnectorError(Exception):
    pass


class Connector(ABC):
    """Plugin contract for external analytics tools.

    `enrich` must return metrics keyed by keyword using the normalized names:
    search_volume, cpc, competition (0-1), trend_growth (ratio, 0 = flat),
    serp_results, owned_impressions, owned_clicks, owned_site_searches.
    """

    id: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]
    auth_type: ClassVar[Literal["api_key", "oauth2"]]
    capabilities: ClassVar[list[Capability]]
    credential_fields: ClassVar[list[FieldSpec]] = []
    config_fields: ClassVar[list[FieldSpec]] = []
    oauth_scopes: ClassVar[list[str]] = []

    def available(self) -> bool:
        return True

    @abstractmethod
    async def test(self, client: httpx.AsyncClient, creds: dict, config: dict) -> None:
        """Raise ConnectorError when credentials or config are invalid."""

    @abstractmethod
    async def enrich(
        self, client: httpx.AsyncClient, creds: dict, config: dict, keywords: list[str]
    ) -> KeywordMetrics: ...


def growth_ratio(series: list[float]) -> float:
    """Relative change between the mean of the last and first quarter of a series."""
    values = [v for v in series if v is not None]
    if len(values) < 4:
        return 0.0
    q = max(1, len(values) // 4)
    head = sum(values[:q]) / q
    tail = sum(values[-q:]) / q
    if head <= 0:
        return 1.0 if tail > 0 else 0.0
    return round((tail - head) / head, 4)


def raise_for(resp: httpx.Response, provider: str) -> None:
    if resp.status_code >= 400:
        raise ConnectorError(f"{provider} returned HTTP {resp.status_code}: {resp.text[:200]}")
