# Research Implementation Status

## Phase A: Evidence Foundation

Implemented:

- Discovery-owned PostgreSQL storage for research state, candidate provenance, documents, passages, fetch outcomes, claims and report versions. Deep operations now use these tables.
- Alembic revisions `0001_quick_baseline`, `0002_research_evidence` and `0003_deep_operations`. Startup upgrades run under a PostgreSQL advisory lock. Existing Quick rows are adopted without being removed. Downgrading to the baseline leaves Quick data intact.
- Explicit source outcomes on new Quick runs, including blocked, rate-limited, failed, unsupported, extraction-failed, duplicate and successful empty results. Metadata records the latest idempotent outcome for a source/query/URL; retry-by-retry accounting is not implemented yet.
- Persisted Quick signal snapshots and overlapping passages with deterministic document/passage IDs. Quick snapshots are labelled truncated; Deep extracts bounded reference documents separately.
- Workspace isolation in API queries and composite database foreign keys for documents/passages and run-owned research records. No shared-content cache is enabled.
- Read-only research details and lexical evidence search on the run page, including source, publication-date and document-type filters. Unknown publication dates remain unknown and are excluded by publication-date filters.
- PostgreSQL `plainto_tsquery('simple', ...)`, `ts_rank_cd`, and a stored `tsvector` with a GIN index. This is native PostgreSQL lexical ranking, **not BM25**, vector retrieval or semantic reranking.
- Existing Quick source searches and gap-score calculation remain available. A Temporal patch marker preserves the legacy crawl activity calls for already-started workflow histories.

## Deep Workflow

Deep mode is available through the Discovery mode selector and API. It uses a deterministic six-question plan: customer workflows, existing solutions, buying/pricing, customer experience, market context and counter-evidence. It searches connected SerpApi/DataForSEO tools and explicit HTTPS seeds. Community adapters remain in Quick; Investigate further can reuse their existing evidence.

The workflow is `plan -> search -> read -> assess -> targeted follow-up -> verify -> report`. Search results retain question/query/provider/position/title/snippet/retrieval provenance. Snippets are not evidence. A persistent frontier favors unresolved questions, source novelty, lexical relevance and preferred domains. Same-site pricing/documentation links can be followed to depth two. Page/domain/redirect/size limits remain bounded.

Each search/read reserves capacity under a PostgreSQL row lock. Network requests, including robots/redirect requests, also require a one-use, operation-scoped permit immediately before execution. Cancellation, deadline and continuation epoch are rechecked at permission time. No provider key or full document body is placed in the Deep workflow history: the crawler saves through scoped ingestion and returns document IDs.

Operation keys and coordinator decision keys are persisted. A lost-response retry returns its committed decision without reserving again. Ambiguous external operations are recorded as interrupted and retain their reservations; paid calls are not automatically retried. Reservation counters are conservative safety accounting, not an invoice or a claim of successful fetches.

Default Deep ceilings are 600 seconds, 15 reads, 12 queries, 12 paid search calls, 3 rounds and 120 network requests. They are configurable per run. The deadline stops new permissions, not metadata finalization; an already-authorized bounded request can finish. Quick preserves its legacy behavior and scoring rather than pretending its historic limits are enforced.

Deep stops on sufficient independent-domain coverage, diminishing useful evidence, exhausted frontier or a configured ceiling. Report completeness also requires supported contextual quotations per required question. Unresolved questions and stop reasons are persisted. Root-domain grouping is conservative; it is not a credibility certificate.

Deep reference extraction supports articles, product/pricing/documentation pages, canonical URLs, relevant tables and up to 64,000 characters split into stable passages. Undated references remain eligible and retain unknown dates. Robots, public-network checks, paywall/challenge handling and response restrictions are enforced. Static HTML only: browser rendering is not enabled.

## Claims and Versions

Deep reports use retrieved passages, not engagement-ranked excerpts. Every claim has an ID, document/passage IDs, exact quotation, source URL, research question and verification status. Validation checks source identity, stored passage offset/content, quotation membership, topical/question context and the narrow attribution claim itself. Unsupported generalizations remain partial/unverified; Deep does not invent market size, growth, competitors or willingness to pay.

The current claim generator is deterministic and deliberately narrow: `According to [source]: [quotation]`. Supported means that this source attribution is contextually grounded, **not that the quoted source is independently proven true**. Reports separately label interpretations and startup hypotheses. Pricing differences and counter-evidence are retained for review; automatic contradiction resolution is not claimed.

PostgreSQL native lexical retrieval uses `ts_rank_cd`, not BM25. Deep combines query terms lexically and caps passages per document to maintain diversity. No embeddings, semantic reranking or new model costs are silently enabled.

Cancellation retains evidence and existing report versions. Continuation requires explicit additional budgets, preserves completed work, increments a persisted epoch and prevents superseded workers from using new permits or overwriting reports. Each completed/cancelled research epoch creates an idempotent report version. Investigate further upgrades an existing opportunity's run to Deep without deleting its Quick opportunity/report.

## API

- `GET /discovery/{run_id}/research`: source outcomes, evidence count, current phase, stop reason and explicit limitations. The outcome list is bounded to the most recent 100 records.
- `GET /discovery/{run_id}/evidence?q=...`: bounded passage retrieval. Optional parameters: `source`, `document_type`, `language`, `date_from`, `date_to` (timezone-aware ISO timestamps).
- `POST /discovery`: accepts optional `research` with mode, budget, language, date range, preferred/excluded domains and seed URLs. Old payloads default to Quick.
- `POST /discovery/{run_id}/cancel`: request Deep cancellation without deletion.
- `POST /discovery/{run_id}/continue`: authorize `additional_budget` and resume evidence-backed work.
- `POST /opportunities/{id}/investigate`: reuse that run's evidence with additional authorized budget.
- Research details include budgets, counters, round, coverage, failures, versions and linked claims. User routes require workspace authentication. Internal request/document routes require short-lived, purpose/run/operation/epoch-scoped service tokens, not user access tokens.

## Evaluation

The current eight-topic benchmark is synthetic and provisionally labelled in tests. On these deliberately separable fixtures, lexical ordering gives precision@10 of 1.0 versus 0.0 for the engagement-ordering proxy. This is a regression result, **not an evaluation of live Quick versus Deep research**, and does not establish the requested 80% relevance or 95% factual-support goals.

Fixtures exercise pricing differences, reference text after character 4,000, date uncertainty, citation identity and a quote that does not support a broader market claim. More representative human-labelled topics, contradictory evidence and ranking judgements are still needed before tuning or reporting real-world improvements.

Focused tests:

```bash
uv run pytest -q services/discovery/tests services/crawler/tests
uv run ruff check services/discovery services/crawler
npm run typecheck --workspace @alphaview/web
```

PostgreSQL integration tests require an explicitly configured disposable database. The suite refuses database names that do not start with `alphaview_test_` and resets only that database's discovery schema:

```bash
ALPHAVIEW_TEST_DATABASE_URL=<disposable-postgresql-asyncpg-url> \
  uv run pytest -q services/discovery/tests/test_evidence_storage.py
```

The PostgreSQL suite verifies fresh/repeated migrations, old Quick data, idempotent documents/attempts/decisions, concurrent budget enforcement, one-use request permits, cancellation/continuation, report versions, unknown dates, grounded citations and workspace isolation. Temporal tests exercise Deep checkpoints and interrupted external operations without paid providers.

## Remaining Limitations

Live paid relevance/support benchmarks are not authorized or measured. The 80% relevance and 95% factual-support goals remain unproven on real research. Near-duplicate policy is evaluated on fixtures, not a large labelled syndication corpus. Multilingual/geographical relevance is approximate. Static extraction may miss permitted JS-only pages. Automated semantic truth/contradiction verification and model reranking remain disabled. Deep produces evidence reports, not unchecked LLM market forecasts. Existing Quick reports are retained, not retroactively rewritten.

## Operating Costs

Opting into Deep web searches authorizes bounded SerpApi/DataForSEO usage under the submitted paid-call budget; prices depend on the provider. Seed-only Deep runs can use zero paid calls. This implementation and its default tests do not add paid LLM calls. Live/paid benchmarks and substantial additional provider costs still require authorization.