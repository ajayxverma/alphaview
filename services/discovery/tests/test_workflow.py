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
GEO = {"label": "Austin, Texas, United States", "lat": 30.27, "lon": -97.74, "radius_km": 25, "country_code": "US"}


def make_activities(calls: list[str], web: bool = False):
    @activity.defn(name=c.GET_RUN)
    async def get_run(run_id: str) -> dict:
        return {"query": "q", "sources": ["reddit", "web"] if web else ["reddit"],
            "workspace_id": str(uuid.uuid4()), "geo": GEO}

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
    async def crawl(run_id: str, query: str, sources: list, geo: dict | None, web_urls: list | None = None,
                    collect_outcomes: bool = False) -> int | dict:
        assert geo == GEO
        assert web_urls == (["https://example.com/blog"] if web else None)
        return {"count": 42, "attempts": []} if collect_outcomes else 42

    @activity.defn(name=c.RECORD_RESEARCH_CRAWL)
    async def record(run_id: str, result: dict) -> list[str]:
        assert result["count"] == 42
        return []

    @activity.defn(name=c.DISCOVER_WEB_URLS)
    async def discover_urls(workspace_id: str, query: str, geo: dict | None) -> list[str]:
        assert web and geo == GEO
        return ["https://example.com/blog"]

    @activity.defn(name=c.ANALYZE_SIGNALS)
    async def analyze(run_id: str, query: str) -> list:
        return [CLUSTER, CLUSTER]

    @activity.defn(name=c.ENRICH_KEYWORDS)
    async def enrich(workspace_id: str, keywords: list, geo: dict | None) -> dict:
        assert keywords == ["k1", "k2"]
        assert geo == GEO
        return {"kw_metrics": {}, "connectors_used": []}

    @activity.defn(name=c.SYNTHESIZE_STRATEGY)
    async def synth(workspace_id: str, query: str, cluster: dict, scored: dict) -> dict:
        uuid.UUID(workspace_id)
        assert "Austin" in query and "25 km" in query
        return {"title": "t"}

    return {
        c.DISCOVERY_QUEUE: [get_run, set_status, rank, persist, record],
        c.CRAWLER_QUEUE: [crawl],
        c.NLP_QUEUE: [analyze],
        c.INTEGRATIONS_QUEUE: [enrich, discover_urls],
        c.STRATEGIST_QUEUE: [synth],
    }


@pytest.mark.parametrize("web", [False, True])
async def test_workflow_routes_across_queues(web):
    calls: list[str] = []
    try:
        env = await WorkflowEnvironment.start_time_skipping()
    except RuntimeError as exc:  # test server binary download unavailable (offline)
        pytest.skip(f"Temporal test server unavailable: {exc}")
    async with env, AsyncExitStack() as stack:
        for q, acts in make_activities(calls, web).items():
            wfs = [DiscoveryWorkflow] if q == c.DISCOVERY_QUEUE else []
            await stack.enter_async_context(Worker(env.client, task_queue=q, activities=acts, workflows=wfs))
        result = await env.client.execute_workflow(
            c.DISCOVERY_WORKFLOW, str(uuid.uuid4()), id="wf-test", task_queue=c.DISCOVERY_QUEUE
        )
    assert result == 2
    assert calls == ["crawling", "analyzing", "enriching", "synthesizing", "completed"]
