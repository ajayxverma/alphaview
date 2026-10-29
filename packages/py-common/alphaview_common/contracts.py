"""Cross-service contracts: Temporal task queues, activity names and crawl sources."""

DISCOVERY_QUEUE = "discovery-q"
CRAWLER_QUEUE = "crawler-q"
NLP_QUEUE = "nlp-q"
INTEGRATIONS_QUEUE = "integrations-q"
STRATEGIST_QUEUE = "strategist-q"

DISCOVERY_WORKFLOW = "DiscoveryWorkflow"

# discovery-q
GET_RUN = "discovery.get_run"
SET_STATUS = "discovery.set_status"
RANK_CLUSTERS = "discovery.rank_clusters"
PERSIST_OPPORTUNITIES = "discovery.persist_opportunities"
# crawler-q: (run_id, query, sources) -> signal count
CRAWL_SOURCES = "crawler.crawl_sources"
# nlp-q: (run_id, query) -> list[cluster]
ANALYZE_SIGNALS = "nlp.analyze_signals"
# integrations-q: (workspace_id, keywords) -> {"kw_metrics": {...}, "connectors_used": [...]}
ENRICH_KEYWORDS = "integrations.enrich_keywords"
# strategist-q: (query, cluster, scored) -> strategy dict
SYNTHESIZE_STRATEGY = "strategist.synthesize_strategy"

SOURCES: dict[str, str] = {
    "reddit": "Reddit",
    "hackernews": "Hacker News",
    "stackexchange": "Stack Exchange",
}
