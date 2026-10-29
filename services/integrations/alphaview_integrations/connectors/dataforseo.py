import httpx

from alphaview_integrations.connectors.base import Capability, Connector, KeywordMetrics, growth_ratio, raise_for
from alphaview_integrations.schemas import FieldSpec

API = "https://api.dataforseo.com/v3"


class DataForSEO(Connector):
    id = "dataforseo"
    name = "DataForSEO"
    description = "Google Ads keyword search volume, CPC, competition and 12-month volume trend."
    auth_type = "api_key"
    capabilities = [Capability.SEARCH_VOLUME, Capability.TREND, Capability.SERP_COMPETITION]
    credential_fields = [
        FieldSpec(key="login", label="API Login"),
        FieldSpec(key="password", label="API Password", secret=True),
    ]
    config_fields = [
        FieldSpec(key="location_code", label="Location code", required=False, help="Default 2840 (United States)")
    ]

    def _auth(self, creds: dict) -> httpx.BasicAuth:
        return httpx.BasicAuth(creds["login"], creds["password"])

    async def test(self, client, creds, config) -> None:
        resp = await client.get(f"{API}/appendix/user_data", auth=self._auth(creds))
        raise_for(resp, "DataForSEO")

    async def enrich(self, client, creds, config, keywords) -> KeywordMetrics:
        payload = [
            {
                "keywords": keywords[:1000],
                "location_code": int(config.get("location_code") or 2840),
                "language_code": "en",
            }
        ]
        resp = await client.post(
            f"{API}/keywords_data/google_ads/search_volume/live", json=payload, auth=self._auth(creds)
        )
        raise_for(resp, "DataForSEO")
        out: KeywordMetrics = {}
        for task in resp.json().get("tasks") or []:
            for item in task.get("result") or []:
                monthly = sorted(
                    item.get("monthly_searches") or [], key=lambda m: (m.get("year", 0), m.get("month", 0))
                )
                out[item["keyword"]] = {
                    "search_volume": float(item.get("search_volume") or 0),
                    "cpc": float(item.get("cpc") or 0),
                    "competition": float(item.get("competition_index") or 0) / 100,
                    "trend_growth": growth_ratio([float(m.get("search_volume") or 0) for m in monthly]),
                }
        return out
