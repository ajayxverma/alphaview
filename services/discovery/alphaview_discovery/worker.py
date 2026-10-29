import asyncio

from alphaview_common import contracts
from alphaview_common.db import init_schema
from alphaview_common.temporal import run_worker
from alphaview_discovery.activities import LOCAL_ACTIVITIES
from alphaview_discovery.models import SCHEMA, Base, engine
from alphaview_discovery.workflow import DiscoveryWorkflow


async def main() -> None:
    await init_schema(engine, Base, SCHEMA)
    await run_worker(contracts.DISCOVERY_QUEUE, LOCAL_ACTIVITIES, workflows=[DiscoveryWorkflow])


if __name__ == "__main__":
    asyncio.run(main())
