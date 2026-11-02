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
RECORD_RESEARCH_CRAWL = "discovery.record_research_crawl"
DEEP_WORKFLOW = "DeepResearchWorkflow"
DEEP_NEXT = "discovery.deep_next"
DEEP_RECORD = "discovery.deep_record"
DEEP_FINISH = "discovery.deep_finish"
DEEP_SEARCH = "integrations.deep_search"
DEEP_READ = "crawler.deep_read"
# crawler-q: (run_id, query, sources, geo | None) -> signal count
CRAWL_SOURCES = "crawler.crawl_sources"
# nlp-q: (run_id, query) -> list[cluster]
ANALYZE_SIGNALS = "nlp.analyze_signals"
# integrations-q: (workspace_id, keywords, geo | None) -> {"kw_metrics": {...}, "connectors_used": [...]}
ENRICH_KEYWORDS = "integrations.enrich_keywords"
DISCOVER_WEB_URLS = "integrations.discover_web_urls"
# strategist-q: (workspace_id, query, cluster, scored) -> strategy dict
SYNTHESIZE_STRATEGY = "strategist.synthesize_strategy"

SOURCES: dict[str, str] = {
    "reddit": "Reddit",
    "hackernews": "Hacker News",
    "stackexchange": "Stack Exchange",
    "mastodon": "Mastodon (mastodon.social)",
    "github": "GitHub Issues",
    "devto": "DEV Community",
    "web": "Web & Blogs",
}
