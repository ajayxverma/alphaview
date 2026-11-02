import asyncio

from alphaview_common import contracts
from alphaview_common.temporal import run_worker
from alphaview_discovery.activities import LOCAL_ACTIVITIES
from alphaview_discovery.deep import DEEP_ACTIVITIES
from alphaview_discovery.deep_workflow import DeepResearchWorkflow
from alphaview_discovery.models import init_db
from alphaview_discovery.workflow import DiscoveryWorkflow


async def main() -> None:
    await init_db()
    await run_worker(contracts.DISCOVERY_QUEUE, LOCAL_ACTIVITIES + DEEP_ACTIVITIES, workflows=[DiscoveryWorkflow, DeepResearchWorkflow])


if __name__ == "__main__":
    asyncio.run(main())
