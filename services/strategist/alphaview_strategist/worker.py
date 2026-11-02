import asyncio
import logging
import uuid

from temporalio import activity

from alphaview_common import contracts
from alphaview_common.db import init_schema
from alphaview_common.netguard import UnsafeEndpointError
from alphaview_common.temporal import run_worker
from alphaview_strategist.agent import synthesize
from alphaview_strategist.credentials import resolve_llm
from alphaview_strategist.models import SCHEMA, Base, engine

log = logging.getLogger(__name__)


@activity.defn(name=contracts.SYNTHESIZE_STRATEGY)
async def synthesize_strategy(workspace_id: str, query: str, cluster: dict, scored: dict) -> dict:
    try:
        llm = await resolve_llm(uuid.UUID(workspace_id))
    except UnsafeEndpointError as exc:
        log.warning("workspace %s AI endpoint rejected: %s", workspace_id, exc)
        llm = None
    return (await synthesize(query, cluster, scored, llm)).model_dump()


async def main() -> None:
    await init_schema(engine, Base, SCHEMA)
    await run_worker(contracts.STRATEGIST_QUEUE, [synthesize_strategy], max_concurrent_activities=20)


if __name__ == "__main__":
    asyncio.run(main())
