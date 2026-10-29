PY_SERVICES := identity integrations discovery crawler nlp strategist
.PHONY: up down restart logs status test lint dev-infra dev-identity dev-integrations dev-integrations-worker \
	dev-discovery dev-discovery-worker dev-crawler dev-nlp dev-strategist dev-web

up:        ## build + start all microservices in Docker
	./start.sh up
down:
	./start.sh stop
restart:
	./start.sh restart
logs:
	./start.sh logs
status:
	./start.sh status

test:
	uv run pytest -q
	uv run ruff check packages services
	npm run typecheck --workspace @alphaview/web

lint:
	uv run ruff check --fix packages services

# --- native development (infra in Docker, services on the host) ---
dev-infra:
	docker compose -f infra/docker-compose.yml --env-file .env -p alphaview up -d postgres redis clickhouse temporal temporal-ui
dev-identity:
	uv run --package alphaview-identity uvicorn alphaview_identity.main:app --reload --port 8001
dev-integrations:
	uv run --package alphaview-integrations uvicorn alphaview_integrations.main:app --reload --port 8002
dev-integrations-worker:
	uv run --package alphaview-integrations python -m alphaview_integrations.worker
dev-discovery:
	uv run --package alphaview-discovery uvicorn alphaview_discovery.main:app --reload --port 8003
dev-discovery-worker:
	uv run --package alphaview-discovery python -m alphaview_discovery.worker
dev-crawler:
	uv run --package alphaview-crawler python -m alphaview_crawler.worker
dev-nlp:
	uv run --package alphaview-nlp python -m alphaview_nlp.worker
dev-strategist:
	uv run --package alphaview-strategist python -m alphaview_strategist.worker
dev-web:
	npm run dev --workspace @alphaview/web
