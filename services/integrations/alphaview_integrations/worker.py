import asyncio
import uuid

from temporalio import activity

from alphaview_common import contracts
from alphaview_common.db import init_schema
from alphaview_common.temporal import run_worker
from alphaview_integrations.enrichment import enrich_keywords
from alphaview_integrations.models import SCHEMA, Base, SessionLocal, engine


@activity.defn(name=contracts.ENRICH_KEYWORDS)
async def enrich_keywords_activity(workspace_id: str, keywords: list[str]) -> dict:
    async with SessionLocal() as session:
        kw_metrics, used = await enrich_keywords(session, uuid.UUID(workspace_id), keywords)
    return {"kw_metrics": kw_metrics, "connectors_used": used}


async def main() -> None:
    await init_schema(engine, Base, SCHEMA)
    await run_worker(contracts.INTEGRATIONS_QUEUE, [enrich_keywords_activity])


if __name__ == "__main__":
    asyncio.run(main())
