from datetime import date, timedelta
from urllib.parse import quote

from alphaview_integrations.connectors import google_oauth
from alphaview_integrations.connectors.base import Capability, Connector, ConnectorError, KeywordMetrics, raise_for
from alphaview_integrations.schemas import FieldSpec

API = "https://www.googleapis.com/webmasters/v3/sites"


class GoogleSearchConsole(Connector):
    id = "gsc"
    name = "Google Search Console"
    description = "Real Google impressions and clicks for queries matching each opportunity."
    auth_type = "oauth2"
    capabilities = [Capability.OWNED_SITE, Capability.SEARCH_VOLUME]
    config_fields = [
        FieldSpec(key="site_url", label="Site URL", help="e.g. https://example.com/ or sc-domain:example.com")
    ]
    oauth_scopes = ["https://www.googleapis.com/auth/webmasters.readonly"]

    def available(self) -> bool:
        return google_oauth.is_configured()

    def _site(self, config: dict) -> str:
        site = config.get("site_url", "").strip()
        if not site:
            raise ConnectorError("site_url is required")
        return quote(site, safe="")

    async def test(self, client, creds, config) -> None:
        token = await google_oauth.access_token(client, creds)
        resp = await client.get(f"{API}/{self._site(config)}", headers={"Authorization": f"Bearer {token}"})
        raise_for(resp, "Search Console")

    async def enrich(self, client, creds, config, keywords) -> KeywordMetrics:
        token = await google_oauth.access_token(client, creds)
        site = self._site(config)
        end = date.today()
        start = end - timedelta(days=90)
        out: KeywordMetrics = {}
        for kw in keywords:
            resp = await client.post(
                f"{API}/{site}/searchAnalytics/query",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "startDate": start.isoformat(),
                    "endDate": end.isoformat(),
                    "dimensions": ["query"],
                    "dimensionFilterGroups": [
                        {"filters": [{"dimension": "query", "operator": "contains", "expression": kw}]}
                    ],
                    "rowLimit": 250,
                },
            )
            raise_for(resp, "Search Console")
            rows = resp.json().get("rows", [])
            out[kw] = {
                "owned_impressions": float(sum(r.get("impressions", 0) for r in rows)),
                "owned_clicks": float(sum(r.get("clicks", 0) for r in rows)),
            }
        return out
