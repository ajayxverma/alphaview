from alphaview_integrations.connectors.base import Connector
from alphaview_integrations.connectors.dataforseo import DataForSEO
from alphaview_integrations.connectors.ga4 import GoogleAnalytics4
from alphaview_integrations.connectors.gsc import GoogleSearchConsole
from alphaview_integrations.connectors.semrush import Semrush
from alphaview_integrations.connectors.serpapi import SerpApi

REGISTRY: dict[str, Connector] = {
    c.id: c for c in (GoogleAnalytics4(), GoogleSearchConsole(), DataForSEO(), SerpApi(), Semrush())
}


def get_connector(provider: str) -> Connector | None:
    return REGISTRY.get(provider)
