import asyncio
import uuid

from temporalio import activity

from alphaview_common import contracts
from alphaview_common.db import init_schema
from alphaview_common.temporal import run_worker
from alphaview_integrations.enrichment import enrich_keywords
from alphaview_integrations.models import SCHEMA, Base, SessionLocal, engine
from alphaview_integrations.web_search import deep_search, discover_web_urls


@activity.defn(name=contracts.ENRICH_KEYWORDS)
async def enrich_keywords_activity(workspace_id: str, keywords: list[str], geo: dict | None = None) -> dict:
    async with SessionLocal() as session:
        kw_metrics, used = await enrich_keywords(session, uuid.UUID(workspace_id), keywords, geo)
    return {"kw_metrics": kw_metrics, "connectors_used": used}


@activity.defn(name=contracts.DISCOVER_WEB_URLS)
async def discover_web_urls_activity(workspace_id: str, query: str, geo: dict | None = None) -> list[str]:
    return await discover_web_urls(workspace_id, query, geo)


@activity.defn(name=contracts.DEEP_SEARCH)
async def deep_search_activity(workspace_id: str, question: dict, options: dict, geo: dict | None, operation_id: str, run_id: str) -> dict:
    return await deep_search(workspace_id, question, options, geo, operation_id, run_id)


async def main() -> None:
    await init_schema(engine, Base, SCHEMA)
    await run_worker(contracts.INTEGRATIONS_QUEUE, [enrich_keywords_activity, discover_web_urls_activity, deep_search_activity])


if __name__ == "__main__":
    asyncio.run(main())
