"""Workflow test using Temporal's time-skipping env with mocked remote services."""

import uuid
from contextlib import AsyncExitStack

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from alphaview_common import contracts as c
from alphaview_discovery.workflow import DiscoveryWorkflow

CLUSTER = {"label": "a", "keywords": ["k1", "k2"], "evidence": []}


def make_activities(calls: list[str]):
    @activity.defn(name=c.GET_RUN)
    async def get_run(run_id: str) -> dict:
        return {"query": "q", "sources": ["reddit"], "workspace_id": str(uuid.uuid4())}

    @activity.defn(name=c.SET_STATUS)
    async def set_status(run_id: str, status: str, error: str | None, count: int | None) -> None:
        calls.append(status)

    @activity.defn(name=c.RANK_CLUSTERS)
    async def rank(clusters: list, enrichment: dict) -> list:
        return [{"cluster": cl, "scored": {"gap_score": 50}} for cl in clusters]

    @activity.defn(name=c.PERSIST_OPPORTUNITIES)
    async def persist(run_id: str, ranked: list, strategies: list) -> int:
        assert len(ranked) == len(strategies)
        return len(ranked)

    @activity.defn(name=c.CRAWL_SOURCES)
    async def crawl(run_id: str, query: str, sources: list) -> int:
        return 42

    @activity.defn(name=c.ANALYZE_SIGNALS)
    async def analyze(run_id: str, query: str) -> list:
        return [CLUSTER, CLUSTER]

    @activity.defn(name=c.ENRICH_KEYWORDS)
    async def enrich(workspace_id: str, keywords: list) -> dict:
        assert keywords == ["k1", "k2"]
        return {"kw_metrics": {}, "connectors_used": []}

    @activity.defn(name=c.SYNTHESIZE_STRATEGY)
    async def synth(query: str, cluster: dict, scored: dict) -> dict:
        return {"title": "t"}

    return {
        c.DISCOVERY_QUEUE: [get_run, set_status, rank, persist],
        c.CRAWLER_QUEUE: [crawl],
        c.NLP_QUEUE: [analyze],
        c.INTEGRATIONS_QUEUE: [enrich],
        c.STRATEGIST_QUEUE: [synth],
    }


async def test_workflow_routes_across_queues():
    calls: list[str] = []
    try:
        env = await WorkflowEnvironment.start_time_skipping()
    except RuntimeError as exc:  # test server binary download unavailable (offline)
        pytest.skip(f"Temporal test server unavailable: {exc}")
    async with env, AsyncExitStack() as stack:
        for q, acts in make_activities(calls).items():
            wfs = [DiscoveryWorkflow] if q == c.DISCOVERY_QUEUE else []
            await stack.enter_async_context(Worker(env.client, task_queue=q, activities=acts, workflows=wfs))
        result = await env.client.execute_workflow(
            c.DISCOVERY_WORKFLOW, str(uuid.uuid4()), id="wf-test", task_queue=c.DISCOVERY_QUEUE
        )
    assert result == 2
    assert calls == ["crawling", "analyzing", "enriching", "synthesizing", "completed"]
