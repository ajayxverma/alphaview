import asyncio

from temporalio import activity

from alphaview_common import contracts
from alphaview_common.temporal import run_worker
from alphaview_strategist.agent import synthesize


@activity.defn(name=contracts.SYNTHESIZE_STRATEGY)
async def synthesize_strategy(query: str, cluster: dict, scored: dict) -> dict:
    return (await synthesize(query, cluster, scored)).model_dump()


async def main() -> None:
    await run_worker(contracts.STRATEGIST_QUEUE, [synthesize_strategy], max_concurrent_activities=20)


if __name__ == "__main__":
    asyncio.run(main())
