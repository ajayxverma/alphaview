# alphaview

**Market Intelligence & Trend Discovery Agent** — finds startup opportunities where consumer demand is surging but existing supply is weak, outdated or missing.

alphaview crawls what people are searching for, complaining about and wishing existed, clusters those signals into pain points, backs them with hard metrics from your own analytics tools, and turns the strongest gaps into investor-grade startup theses.

## What it does

| Capability | Description |
|---|---|
| **Targeted crawling** | Pulls demand signals from Reddit, Hacker News and Stack Exchange, expanded with intent phrases ("is there a tool", "alternative to", "I wish"…) |
| **Gap identification** | Classifies each signal (wish / complaint / alternative-seeking / solution), clusters pain points and scores every cluster 0–100 on **demand vs. supply asymmetry** |
| **Strategic synthesis** | An LLM strategist writes the thesis, value proposition, target audience, wedge, execution plan, GTM, moat, risks and kill criteria — grounded in the metrics and evidence |
| **Analytics integrations** | Users connect their own tools — **Google Analytics 4, Google Search Console, DataForSEO, SerpApi (Google Trends), Semrush** — to enrich every run with search volume, CPC, competition, trend growth and owned-site data |
| **Accounts & workspaces** | Register/login, connect tools via OAuth or API key (encrypted at rest), run ad-hoc keyword lookups, review ranked opportunities with linked evidence |

## Architecture

Microservices behind an nginx gateway; the discovery pipeline is orchestrated by Temporal across per-service task queues.

```
Browser ─▶ web (Next.js) ─▶ gateway (nginx :8000)
                               ├─ /auth/*            ─▶ identity
                               ├─ /connectors, /connections/* ─▶ integrations-api
                               └─ /discovery, /opportunities  ─▶ discovery-api ─▶ Temporal
                                                                                    │
            discovery-worker ◀─┬─ crawler-worker ─ nlp-worker ─ integrations-worker ─ strategist-worker
                               │
              PostgreSQL (schema per service) · ClickHouse (signals) · Redis (rate limits)
```

**Stack:** Next.js 15 · React 19 · Tailwind 4 · FastAPI · SQLAlchemy 2 · Temporal · PostgreSQL 16 · ClickHouse · Redis · LiteLLM · scikit-learn · Docker Compose · uv · Turborepo

## Quick start

**Prerequisite:** [Docker Desktop](https://docs.docker.com/get-docker/) (Compose v2) running.

```bash
git clone <repo-url> alphaview && cd alphaview

./start.sh        # macOS / Linux
start.bat         # Windows
```

The script generates `.env` with secure secrets on first run, builds and starts every service, waits until the stack is healthy and prints:

| URL | What |
|---|---|
| http://localhost:3000 | Web app — register an account here |
| http://localhost:8000 | API gateway |
| http://localhost:8080 | Temporal UI (pipeline runs) |

Other commands:

```bash
./stop.sh                    # stop everything (data is kept)
./reset.sh                   # DELETE all containers, data and built images (asks for confirmation)
./start.sh restart           # rebuild + restart
./start.sh logs [service]    # follow logs, e.g. ./start.sh logs crawler-worker
./start.sh status            # container status
```

(Windows: `stop.bat`, `reset.bat`, and `start.bat restart|logs|status`.)

`reset` asks you to type `reset` to confirm, then optionally also removes `.env` and local build artifacts. Run `./start.sh` afterwards for a completely fresh install.

## Configuration (optional)

Edit `.env` (created on first run from [.env.example](.env.example)), then `./start.sh restart`.

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GROQ_API_KEY` + `LLM_MODEL` | *Optional server-wide fallback* AI key. Normally each user adds their own provider key on the **AI Models** page. Without any key a heuristic summary is generated. |
| `ALLOW_PRIVATE_LLM_ENDPOINTS` | Set `true` to allow `http://` or private-network LLM servers (e.g. Ollama on your machine via `http://host.docker.internal:11434`). Keep `false` for shared deployments. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Enables the GA4 and Search Console connectors. Create a Google OAuth (Web) client with redirect URI `http://localhost:8000/connections/oauth/callback` and enable the *Google Analytics Data API* and *Search Console API*. |

API-key connectors (DataForSEO, SerpApi, Semrush) need no server config — users paste their keys on the **Integrations** page.

## Using the app

1. **Register** at http://localhost:3000.
2. *(Optional)* **AI Models** → add your own key for **OpenAI, Anthropic, Google Gemini, Groq, Mistral, DeepSeek, xAI, Cohere, Perplexity, Together AI, Fireworks, OpenRouter, Azure OpenAI, Ollama** or any OpenAI-compatible server, and pick the default model.
3. *(Optional)* **Integrations** → connect your analytics tools; use **Query** to look up keyword metrics directly.
4. **Discovery** → enter a niche or problem space (e.g. *"small accounting firms"*) and run.
5. Watch the run progress (crawl → analyze → enrich → synthesize), then open the ranked opportunities for metrics, gap-score breakdown, strategy and source evidence.

## Development

Requires [uv](https://docs.astral.sh/uv/) and Node 20+.

```bash
uv sync && npm install
make test                     # pytest (all services) + ruff + TypeScript check

make dev-infra                # Postgres, Redis, ClickHouse, Temporal in Docker
make dev-discovery            # run one service natively with hot reload (see Makefile for all targets)
```

## Repository layout

```
apps/web/              Next.js UI + BFF
services/
  gateway/             nginx routing
  identity/            users, workspaces, auth
  integrations/        connectors, OAuth, enrichment worker
  discovery/           runs, opportunities, gap engine, workflow orchestrator
  crawler/             source adapters
  nlp/                 sentiment, intent, clustering
  strategist/          LLM synthesis
packages/py-common/    shared contracts, auth, db, Temporal helpers
infra/                 docker-compose + shared Python Dockerfile
docs/                  detailed documentation
start.sh / start.bat   one-command start
stop.sh / stop.bat     stop all services (keeps data)
reset.sh / reset.bat   wipe containers, data and images (with confirmation)
```

## Documentation

The evidence-driven research upgrade is being delivered in testable phases. See [Research status](docs/RESEARCH.md) for implemented evidence storage/failure visibility, provisional benchmark results and remaining Deep-research work.

- [Functional specification](docs/FUNCTIONAL.md) — features, user journeys, business rules, gap-score formula
- [Technology](docs/TECHNOLOGY.md) — stack, setup, configuration, security controls, roadmap
- [High-level design](docs/HLD.md) — service architecture, pipeline, scaling strategy
- [Low-level design](docs/LLD.md) — data model, API spec, modules, workflow contracts, testing
