import asyncio

from alphaview_common.geo import REGION_MAX_KM
from alphaview_integrations.connectors.base import Capability, Connector, KeywordMetrics, growth_ratio, raise_for
from alphaview_integrations.schemas import FieldSpec

API = "https://serpapi.com"


class SerpApi(Connector):
    id = "serpapi"
    name = "SerpApi (Google Trends + SERP)"
    description = "Google Trends interest-over-time and SERP result counts as a supply-density proxy."
    auth_type = "api_key"
    capabilities = [Capability.TREND, Capability.SERP_COMPETITION]
    credential_fields = [FieldSpec(key="api_key", label="API Key", secret=True)]
    config_fields = [FieldSpec(key="geo", label="Trends geo", required=False, help="e.g. US; blank = worldwide")]

    async def test(self, client, creds, config) -> None:
        resp = await client.get(f"{API}/account.json", params={"api_key": creds["api_key"]})
        raise_for(resp, "SerpApi")

    async def _one(self, client, creds, config, kw: str, geo=None) -> dict[str, float]:
        trends_params = {
            "engine": "google_trends",
            "q": kw,
            "data_type": "TIMESERIES",
            "date": "today 12-m",
            "api_key": creds["api_key"],
        }
        serp_params = {"engine": "google", "q": kw, "num": 10, "api_key": creds["api_key"]}
        if geo and geo.get("country_code"):
            trends_params["geo"] = geo["country_code"]
            serp_params["gl"] = geo["country_code"].lower()
            if geo.get("radius_km", 0) <= REGION_MAX_KM and geo.get("label"):
                # Localised SERP: results as seen by a searcher in that place.
                serp_params["location"] = geo["label"]
        elif config.get("geo"):
            trends_params["geo"] = config["geo"]

        trends, serp = await asyncio.gather(
            client.get(f"{API}/search.json", params=trends_params),
            client.get(f"{API}/search.json", params=serp_params),
        )
        raise_for(trends, "SerpApi")
        raise_for(serp, "SerpApi")

        timeline = trends.json().get("interest_over_time", {}).get("timeline_data", [])
        series = [float(p["values"][0].get("extracted_value") or 0) for p in timeline if p.get("values")]
        total = serp.json().get("search_information", {}).get("total_results") or 0
        return {"trend_growth": growth_ratio(series), "serp_results": float(total)}

    async def enrich(self, client, creds, config, keywords, geo=None) -> KeywordMetrics:
        results = await asyncio.gather(*(self._one(client, creds, config, kw, geo) for kw in keywords))
        return dict(zip(keywords, results, strict=True))
