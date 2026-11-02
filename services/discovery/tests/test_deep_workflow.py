import uuid
from contextlib import AsyncExitStack

import pytest
from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from alphaview_common import contracts as c
from alphaview_discovery.deep_workflow import DeepResearchWorkflow


@pytest.mark.parametrize("interrupt", [False, True])
async def test_deep_search_read_assess_checkpoint_and_interruption(interrupt):
    calls = []
    actions = [{"kind": "search", "id": "search-op", "workspace_id": str(uuid.uuid4()),
                "question": {"id": "buying", "query": "invoice pricing"}, "options": {}, "geo": None},
               {"kind": "checkpoint"}, {"kind": "read", "id": "read-op", "workspace_id": str(uuid.uuid4()),
                "url": "https://example.com/pricing", "options": {}}, {"kind": "stop", "reason": "round_budget"}]

    @activity.defn(name=c.DEEP_NEXT)
    async def next_action(run_id: str, decision_id: str, expected_epoch: int | None) -> dict:
        assert decision_id
        return actions.pop(0)

    @activity.defn(name=c.DEEP_RECORD)
    async def record(run_id: str, operation_id: str, result: dict) -> None:
        calls.append((operation_id, result["outcome"]))

    @activity.defn(name=c.DEEP_FINISH)
    async def finish(run_id: str, reason: str, expected_epoch: int | None) -> int:
        assert reason == "round_budget"
        return 1

    @activity.defn(name=c.DEEP_SEARCH)
    async def search(workspace_id: str, question: dict, options: dict, geo: dict | None, operation_id: str, run_id: str) -> dict:
        assert question["id"] == "buying"
        return {"outcome": "fetched", "candidates": []}

    @activity.defn(name=c.DEEP_READ)
    async def read(operation_id: str, run_id: str, workspace_id: str, url: str, options: dict) -> dict:
        if interrupt:
            raise ApplicationError("Read interrupted", non_retryable=True)
        return {"outcome": "fetched", "document_id": str(uuid.uuid4())}

    try:
        env = await WorkflowEnvironment.start_time_skipping()
    except RuntimeError as exc:
        pytest.skip(f"Temporal test server unavailable: {exc}")
    async with env, AsyncExitStack() as stack:
        for queue, activities, workflows in [(c.DISCOVERY_QUEUE, [next_action, record, finish], [DeepResearchWorkflow]),
                                             (c.INTEGRATIONS_QUEUE, [search], []), (c.CRAWLER_QUEUE, [read], [])]:
            await stack.enter_async_context(Worker(env.client, task_queue=queue, activities=activities, workflows=workflows))
        result = await env.client.execute_workflow(c.DEEP_WORKFLOW, str(uuid.uuid4()), id=str(uuid.uuid4()), task_queue=c.DISCOVERY_QUEUE)
    assert result == 1
    assert calls == [("search-op", "fetched"), ("read-op", "interrupted" if interrupt else "fetched")]