from datetime import date, timedelta

import httpx

from alphaview_integrations.connectors import google_oauth
from alphaview_integrations.connectors.base import Capability, Connector, ConnectorError, KeywordMetrics, raise_for
from alphaview_integrations.schemas import FieldSpec

API = "https://analyticsdata.googleapis.com/v1beta"


class GoogleAnalytics4(Connector):
    id = "ga4"
    name = "Google Analytics 4"
    description = "Owned-site demand: on-site search terms and engagement for your GA4 property."
    auth_type = "oauth2"
    capabilities = [Capability.OWNED_SITE]
    config_fields = [FieldSpec(key="property_id", label="GA4 Property ID", help="Numeric, e.g. 312345678")]
    oauth_scopes = ["https://www.googleapis.com/auth/analytics.readonly"]

    def available(self) -> bool:
        return google_oauth.is_configured()

    async def _report(self, client: httpx.AsyncClient, creds: dict, config: dict, body: dict) -> dict:
        prop = config.get("property_id", "").strip()
        if not prop.isdigit():
            raise ConnectorError("property_id must be numeric")
        token = await google_oauth.access_token(client, creds)
        resp = await client.post(
            f"{API}/properties/{prop}:runReport", json=body, headers={"Authorization": f"Bearer {token}"}
        )
        raise_for(resp, "GA4")
        return resp.json()

    async def test(self, client, creds, config) -> None:
        await self._report(
            client,
            creds,
            config,
            {"dateRanges": [{"startDate": "7daysAgo", "endDate": "today"}], "metrics": [{"name": "activeUsers"}]},
        )

    async def enrich(self, client, creds, config, keywords) -> KeywordMetrics:
        start = (date.today() - timedelta(days=90)).isoformat()
        out: KeywordMetrics = {}
        for kw in keywords:
            data = await self._report(
                client,
                creds,
                config,
                {
                    "dateRanges": [{"startDate": start, "endDate": "today"}],
                    "dimensions": [{"name": "searchTerm"}],
                    "metrics": [{"name": "eventCount"}],
                    "dimensionFilter": {
                        "filter": {
                            "fieldName": "searchTerm",
                            "stringFilter": {"matchType": "CONTAINS", "value": kw, "caseSensitive": False},
                        }
                    },
                    "limit": 100,
                },
            )
            total = sum(float(r["metricValues"][0]["value"]) for r in data.get("rows", []))
            out[kw] = {"owned_site_searches": total}
        return out
