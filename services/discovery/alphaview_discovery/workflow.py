import asyncio
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from alphaview_common import contracts as c

QUICK = {"start_to_close_timeout": timedelta(seconds=30), "task_queue": c.DISCOVERY_QUEUE}
HEAVY = {
    "start_to_close_timeout": timedelta(minutes=15),
    "retry_policy": RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=5)),
}


@workflow.defn(name=c.DISCOVERY_WORKFLOW)
class DiscoveryWorkflow:
    """Orchestrates crawler -> nlp -> integrations -> discovery scoring -> strategist across task queues."""

    async def _status(self, run_id: str, status: str, error: str | None = None, count: int | None = None) -> None:
        await workflow.execute_activity(c.SET_STATUS, args=[run_id, status, error, count], **QUICK)

    async def _remote(self, name: str, queue: str, *args: Any) -> Any:
        return await workflow.execute_activity(name, args=list(args), task_queue=queue, **HEAVY)

    @workflow.run
    async def run(self, run_id: str) -> int:
        try:
            run = await workflow.execute_activity(c.GET_RUN, run_id, **QUICK)
            query, geo = run["query"], run.get("geo")
            # The strategist sees the market scope as part of the theme.
            theme = f"{query} (market: {geo['label']}, within {geo['radius_km']} km)" if geo else query

            await self._status(run_id, "crawling")
            record_evidence = workflow.patched("research_evidence_v1")
            web_urls = None
            if "web" in run["sources"]:
                web_urls = await self._remote(c.DISCOVER_WEB_URLS, c.INTEGRATIONS_QUEUE, run["workspace_id"], query, geo)
            if record_evidence:
                result = await self._remote(c.CRAWL_SOURCES, c.CRAWLER_QUEUE, run_id, query, run["sources"], geo, web_urls, True)
                await self._remote(c.RECORD_RESEARCH_CRAWL, c.DISCOVERY_QUEUE, run_id, result)
                count = result["count"]
                failures = [attempt for attempt in result.get("attempts", []) if attempt["outcome"] not in ("fetched", "no_results", "duplicate")]
            elif web_urls is not None:
                count = await self._remote(c.CRAWL_SOURCES, c.CRAWLER_QUEUE, run_id, query, run["sources"], geo, web_urls)
            else:
                count = await self._remote(c.CRAWL_SOURCES, c.CRAWLER_QUEUE, run_id, query, run["sources"], geo)
            if count == 0:
                detail = "Sources were blocked or failed; no demand conclusion is supported." if record_evidence and failures else "No signals returned in this bounded Quick pass; this does not establish absent demand."
                await self._status(run_id, "completed", detail, 0)
                return 0

            await self._status(run_id, "analyzing", None, count)
            clusters = await self._remote(c.ANALYZE_SIGNALS, c.NLP_QUEUE, run_id, query)

            await self._status(run_id, "enriching")
            keywords = sorted({kw for cl in clusters for kw in cl["keywords"][:3]})
            enrichment = await self._remote(
                c.ENRICH_KEYWORDS, c.INTEGRATIONS_QUEUE, run["workspace_id"], keywords, geo
            )

            await self._status(run_id, "synthesizing")
            ranked = await self._remote(c.RANK_CLUSTERS, c.DISCOVERY_QUEUE, clusters, enrichment)
            strategies = await asyncio.gather(
                *(
                    self._remote(
                        c.SYNTHESIZE_STRATEGY, c.STRATEGIST_QUEUE, run["workspace_id"], theme, r["cluster"], r["scored"]
                    )
                    for r in ranked
                )
            )
            n = await self._remote(c.PERSIST_OPPORTUNITIES, c.DISCOVERY_QUEUE, run_id, ranked, list(strategies))

            await self._status(run_id, "completed")
            return n
        except ActivityError as err:
            cause = err.cause.message if err.cause else str(err)
            await self._status(run_id, "failed", cause[:500])
            raise
