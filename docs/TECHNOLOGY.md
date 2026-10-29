# alphaview — Technology Document

## 1. Stack summary

| Layer | Technology | Version | Why it was chosen |
|---|---|---|---|
| Frontend | **Next.js (App Router) + React + TypeScript** | 15 / 19 / 5.7 | SSR/edge rendering, file-based routing, built-in BFF (route handlers), standalone container output |
| Styling | **Tailwind CSS v4** | 4.x | Zero-runtime CSS, design tokens via `@theme` |
| Client data | **TanStack Query** | 5.x | Caching, background polling of run status, mutation state |
| Charts | **Recharts** | 2.x | Declarative charts for gap-score components |
| Icons | lucide-react | — | Tree-shakeable icon set |
| Backend API | **Python + FastAPI** | 3.12 / 0.115+ | Async I/O, Pydantic validation, OpenAPI docs, best-in-class NLP/AI ecosystem |
| ORM | **SQLAlchemy 2 (async) + asyncpg** | 2.0 | Typed models, async pool, fastest Postgres driver |
| Workflow engine | **Temporal** | 1.25 server / temporalio SDK | Durable multi-stage pipelines with retries, timeouts and visibility (Temporal UI) |
| OLTP database | **PostgreSQL (pgvector image)** | 16 | Users, workspaces, connections, runs, opportunities; pgvector ready for semantic search |
| Analytics store | **ClickHouse** | 24.8 | Columnar store for high-volume crawled signals; sub-second aggregations at billions of rows |
| Cache / rate limiting | **Redis** | 7 | Fixed-window rate limits (auth, discovery runs); future response cache |
| NLP | **VADER sentiment, scikit-learn (TF-IDF + KMeans)** | — | Fast, CPU-only, deterministic baseline; swappable for embeddings |
| LLM | **LiteLLM** gateway | 1.50+ | One API for OpenAI, Anthropic, Azure, Bedrock, local models; model routing |
| Auth | FastAPI-native **Argon2id** password hashing + **JWT (HS256)**; httpOnly cookie in Next.js | — | No vendor lock-in; tokens never exposed to browser JS |
| Secrets at rest | **Fernet (AES-128-CBC + HMAC)** envelope for connector credentials | — | Swap to AWS KMS / Vault in production |
| HTTP client | **httpx** | 0.27+ | Async, HTTP/2-capable, used by crawlers and connectors |
| Python tooling | **uv workspace**, ruff, pytest | — | One lockfile for all Python services, per-service installs (`--package`) |
| JS tooling | npm workspaces + **Turborepo** | — | Monorepo task orchestration and caching |
| API gateway | **nginx** | 1.27 | Path-based routing to services, body-size limits, real-IP handling |
| Containers | Docker, docker-compose | — | Local parity; one shared Python image parameterised by `SERVICE`; images run as non-root |
| Production target | Kubernetes (EKS/GKE) + KEDA + Terraform + ArgoCD | — | Horizontal autoscaling of API and workers (see HLD) |

## 2. Repository layout

```
alphaview/
├─ start.sh / start.bat            # one-command start for macOS/Linux / Windows
├─ .env.example                    # secrets template (auto-filled by start scripts)
├─ pyproject.toml / uv.lock        # uv workspace root (all Python services)
├─ packages/
│  └─ py-common/alphaview_common/  # shared library
│     ├─ settings.py               # CommonSettings (env-driven)
│     ├─ security.py               # Argon2, JWT, Fernet
│     ├─ auth.py                   # stateless Principal from JWT (sub + ws claims)
│     ├─ db.py                     # engine factory + schema-per-service init
│     ├─ contracts.py              # Temporal queues, activity names, sources
│     ├─ temporal.py               # connect-with-retry, run_worker
│     ├─ clickhouse.py             # shared signal event store
│     ├─ signals.py / ratelimit.py / web.py
├─ services/
│  ├─ gateway/                     # nginx config + Dockerfile
│  ├─ identity/                    # users, workspaces, auth API
│  ├─ integrations/                # connectors, OAuth, connections API + enrichment worker
│  ├─ discovery/                   # runs/opportunities API, gap engine, workflow orchestrator worker
│  ├─ crawler/                     # source adapters worker
│  ├─ nlp/                         # sentiment/intent/clustering worker
│  └─ strategist/                  # LLM synthesis worker
│     (each: pyproject.toml, alphaview_<service>/, tests/)
├─ apps/web/                       # Next.js app (UI + BFF)
├─ infra/
│  ├─ docker-compose.yml           # full stack: infra + 12 app containers
│  └─ docker/python.Dockerfile     # shared Python image (ARG SERVICE)
├─ docs/
├─ Makefile
└─ package.json / turbo.json
```

## 3. Local setup

### One command (recommended)

Prerequisite: Docker Desktop (Compose v2).

```bash
./start.sh            # macOS / Linux
start.bat             # Windows
```

On first run the script creates `.env` from `.env.example` with freshly generated `JWT_SECRET` and Fernet `ENCRYPTION_KEY`, builds every image, starts all containers, waits for the gateway health check and prints the URLs:

| URL | What |
|---|---|
| http://localhost:3000 | Web app |
| http://localhost:8000 | API gateway |
| http://localhost:8080 | Temporal UI |

Other commands: `stop`, `restart`, `logs [service]`, `status`. Scale a worker: `docker compose -p alphaview -f infra/docker-compose.yml --env-file .env up -d --scale crawler-worker=4`.

### Native development of a single service (hot reload)

Prerequisites: Docker, Node 20+, [uv](https://docs.astral.sh/uv/). Infra ports are published on `127.0.0.1` for this mode.

```bash
./start.sh && ./start.sh stop      # first run only: generates .env
make dev-infra                     # Postgres, Redis, ClickHouse, Temporal
uv sync
make dev-discovery                 # e.g. discovery API on :8003 → http://localhost:8003/docs
make dev-discovery-worker          # any worker: dev-crawler, dev-nlp, dev-strategist, ...
```

For end-to-end UI testing use `./start.sh` (the gateway routes to container hostnames).

### Google OAuth (GA4 / Search Console)
1. Google Cloud Console → create OAuth client (Web).
2. Authorized redirect URI: `http://localhost:8000/connections/oauth/callback`.
3. Enable *Google Analytics Data API* and *Search Console API*.
4. Set `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` in `.env` and run `./start.sh restart`.

### LLM
Set `LLM_MODEL` (any LiteLLM model id, e.g. `gpt-4o-mini`, `anthropic/claude-3-5-sonnet-20241022`) and the provider key in `.env`. Without a key, a deterministic heuristic strategist is used.

## 4. Configuration reference

| Variable | Used by | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | identity, integrations, discovery | local Postgres | SQLAlchemy async URL (each service uses its own schema) |
| `REDIS_URL` | identity, discovery | `redis://localhost:6379/0` | Rate limiting |
| `CLICKHOUSE_*` | crawler, nlp | localhost:8123 | Signal event store |
| `TEMPORAL_HOST` | discovery + all workers | `localhost:7233` | Workflow engine (queues are fixed in `contracts.py`) |
| `JWT_SECRET` | all APIs | — (≥32 chars, validated) | Token signing/verification |
| `JWT_TTL_MINUTES` | identity | 720 | Session length |
| `ENCRYPTION_KEY` | integrations | — | Fernet key for connector credentials |
| `GOOGLE_CLIENT_ID/SECRET`, `OAUTH_REDIRECT_URL` | integrations | — | OAuth connectors |
| `FRONTEND_URL`, `CORS_ORIGINS` | all APIs | localhost:3000 | Redirects/CORS |
| `LLM_MODEL` + provider keys | strategist | `gpt-4o-mini` | Strategy synthesis |
| `MAX_OPPORTUNITIES` | discovery | 6 | Top-N clusters synthesized per run |
| `CRAWLER_LOOKBACK_DAYS` | crawler | 90 | Signal recency window |
| `MAX_RUNS_PER_HOUR` | discovery | 20 | Per-workspace discovery quota |

## 5. Quality gates

```bash
make test   # pytest + ruff + tsc
```

## 6. Security controls

- Argon2id password hashing; generic login errors; Redis rate limiting on login/register/discovery.
- JWT stored only in an `httpOnly`, `SameSite=Lax`, `Secure` (prod) cookie; browser never sees the token.
- Every data query is scoped by `workspace_id` (no IDOR).
- Connector credentials encrypted at rest, never returned by the API; secret inputs are `type=password`, `autocomplete=off`.
- OAuth `state` is a signed, 10-minute, purpose-bound JWT (CSRF protection).
- Login `next` redirect restricted to same-origin paths (no open redirect).
- LLM prompt treats crawled content as untrusted data (prompt-injection mitigation); LLM output validated by Pydantic and rendered without `dangerouslySetInnerHTML`.
- Security headers (`X-Frame-Options`, `nosniff`, `Referrer-Policy`); containers run as non-root.
- API trusts `X-Forwarded-For` only from the web BFF's fixed IP; in production terminate at the ingress and set `--forwarded-allow-ips` to the ingress CIDR.

## 7. Production roadmap (tech)

| Phase | Addition |
|---|---|
| Scale-out | Kubernetes + KEDA (scale workers on Temporal queue depth), HPA for API, Postgres read replicas (Aurora), ClickHouse Cloud cluster |
| Streaming | Kafka/Redpanda between crawler and NLP for continuous (non-run) ingestion |
| Data | Alembic migrations, pgvector/Qdrant embeddings, OpenSearch full-text over signals |
| Crawling | Playwright workers + rotating proxy pool for JS-heavy forums; more adapters (Product Hunt, G2, App Store, X, YouTube) |
| Connectors | Ahrefs, SimilarWeb, Exploding Topics, Crunchbase, Mixpanel/Amplitude |
| Secrets | AWS KMS envelope encryption / HashiCorp Vault, key rotation |
| Auth | Google/GitHub SSO, team invites, RBAC, refresh-token rotation |
| Observability | OpenTelemetry → Grafana Tempo/Loki/Prometheus, Sentry, Langfuse for LLM traces |
| Billing | Stripe metered plans tied to run quotas |
