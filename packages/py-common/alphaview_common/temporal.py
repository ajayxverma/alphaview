import asyncio
import logging
from collections.abc import Callable, Sequence

from temporalio.client import Client
from temporalio.worker import Worker

from alphaview_common.settings import get_common_settings

log = logging.getLogger(__name__)


async def connect(attempts: int = 30, delay: float = 2.0) -> Client:
    """Connect to Temporal, retrying while the server is still starting."""
    s = get_common_settings()
    for attempt in range(1, attempts + 1):
        try:
            return await Client.connect(s.temporal_host, namespace=s.temporal_namespace)
        except RuntimeError as exc:
            if attempt == attempts:
                raise
            log.info("Temporal not ready (%s), retry %d/%d", exc, attempt, attempts)
            await asyncio.sleep(delay)
    raise RuntimeError("unreachable")


async def run_worker(
    task_queue: str,
    activities: Sequence[Callable],
    workflows: Sequence[type] = (),
    max_concurrent_activities: int = 50,
) -> None:
    logging.basicConfig(level=logging.INFO)
    client = await connect()
    worker = Worker(
        client,
        task_queue=task_queue,
        activities=list(activities),
        workflows=list(workflows),
        max_concurrent_activities=max_concurrent_activities,
    )
    log.info("worker started queue=%s", task_queue)
    await worker.run()
