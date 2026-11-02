from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from alphaview_common import contracts as c


@workflow.defn(name=c.DEEP_WORKFLOW)
class DeepResearchWorkflow:
    @workflow.run
    async def run(self, run_id: str, expected_epoch: int | None = None) -> int:
        async def local(name, *args):
            return await workflow.execute_activity(name, args=list(args), task_queue=c.DISCOVERY_QUEUE,
                start_to_close_timeout=timedelta(minutes=2), retry_policy=RetryPolicy(maximum_attempts=3))

        step = 0
        while True:
            action = await local(c.DEEP_NEXT, run_id, f"{workflow.info().run_id}:{step}", expected_epoch)
            step += 1
            if action["kind"] == "stop":
                return await local(c.DEEP_FINISH, run_id, action["reason"], expected_epoch)
            if action["kind"] == "checkpoint":
                continue
            try:
                if action["kind"] == "search":
                    result = await workflow.execute_activity(c.DEEP_SEARCH,
                        args=[action["workspace_id"], action["question"], action["options"], action["geo"], action["id"], run_id],
                        task_queue=c.INTEGRATIONS_QUEUE, start_to_close_timeout=timedelta(seconds=45),
                        schedule_to_close_timeout=timedelta(seconds=60), retry_policy=RetryPolicy(maximum_attempts=1))
                else:
                    result = await workflow.execute_activity(c.DEEP_READ,
                        args=[action["id"], run_id, action["workspace_id"], action["url"], action["options"]],
                        task_queue=c.CRAWLER_QUEUE, start_to_close_timeout=timedelta(seconds=90),
                        heartbeat_timeout=timedelta(seconds=60),
                        schedule_to_close_timeout=timedelta(seconds=120), retry_policy=RetryPolicy(maximum_attempts=1))
            except ActivityError:
                result = {"outcome": "interrupted", "detail": "External operation failed or timed out; reservation retained to avoid duplicate spend"}
            await local(c.DEEP_RECORD, run_id, action["id"], result)