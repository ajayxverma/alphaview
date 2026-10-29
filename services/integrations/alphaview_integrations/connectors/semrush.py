from alphaview_integrations.connectors.base import Capability, Connector, ConnectorError, KeywordMetrics, raise_for
from alphaview_integrations.schemas import FieldSpec

API = "https://api.semrush.com/"


class Semrush(Connector):
    id = "semrush"
    name = "Semrush"
    description = "Keyword volume, CPC and competitive density from the Semrush Analytics API."
    auth_type = "api_key"
    capabilities = [Capability.SEARCH_VOLUME, Capability.SERP_COMPETITION]
    credential_fields = [FieldSpec(key="api_key", label="API Key", secret=True)]
    config_fields = [FieldSpec(key="database", label="Database", required=False, help="Default 'us'")]

    async def test(self, client, creds, config) -> None:
        resp = await client.get(
            "https://www.semrush.com/users/countapiunits.html", params={"key": creds["api_key"]}
        )
        raise_for(resp, "Semrush")
        if not resp.text.strip().isdigit():
            raise ConnectorError("Semrush key rejected")

    async def enrich(self, client, creds, config, keywords) -> KeywordMetrics:
        out: KeywordMetrics = {}
        for kw in keywords:
            resp = await client.get(
                API,
                params={
                    "type": "phrase_this",
                    "key": creds["api_key"],
                    "phrase": kw,
                    "export_columns": "Ph,Nq,Cp,Co",
                    "database": config.get("database") or "us",
                },
            )
            raise_for(resp, "Semrush")
            lines = [ln for ln in resp.text.strip().splitlines() if ln]
            # Semrush answers "ERROR 50 :: NOTHING FOUND" with HTTP 200 when there is no data.
            if len(lines) < 2 or lines[0].startswith("ERROR"):
                continue
            _, volume, cpc, comp = (lines[1].split(";") + ["0"] * 4)[:4]
            out[kw] = {
                "search_volume": float(volume or 0),
                "cpc": float(cpc or 0),
                "competition": float(comp or 0),
            }
        return out
