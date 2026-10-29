#!/usr/bin/env bash
# Start every alphaview microservice with Docker Compose.
# Usage: ./start.sh [up|stop|restart|logs [service]|status]
set -euo pipefail

cd "$(dirname "$0")"
COMPOSE=(docker compose -f infra/docker-compose.yml --env-file .env -p alphaview)
GATEWAY_HEALTH="http://localhost:8000/health"

die() { echo "error: $*" >&2; exit 1; }

require_docker() {
  command -v docker >/dev/null 2>&1 || die "Docker is not installed. Install Docker Desktop: https://docs.docker.com/get-docker/"
  docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required (docker compose ...)."
  docker info >/dev/null 2>&1 || die "Docker daemon is not running. Start Docker Desktop and retry."
}

rand_b64() {
  if command -v openssl >/dev/null 2>&1; then openssl rand -base64 "$1"; else head -c "$1" /dev/urandom | base64; fi
}

ensure_env() {
  [[ -f .env ]] && return
  echo "Creating .env with freshly generated secrets..."
  local jwt key
  jwt=$(rand_b64 48 | tr -d '\n=+/')
  # Fernet key: urlsafe base64 of 32 random bytes.
  key=$(rand_b64 32 | tr -d '\n' | tr '+/' '-_')
  awk -v jwt="$jwt" -v key="$key" '
    /^JWT_SECRET=/     { print "JWT_SECRET=" jwt; next }
    /^ENCRYPTION_KEY=/ { print "ENCRYPTION_KEY=" key; next }
    { print }
  ' .env.example > .env
  chmod 600 .env
}

wait_for_gateway() {
  echo -n "Waiting for services to become healthy"
  for _ in $(seq 1 100); do
    if curl -fsS "$GATEWAY_HEALTH" >/dev/null 2>&1; then echo " ready."; return 0; fi
    echo -n "."
    sleep 3
  done
  echo
  "${COMPOSE[@]}" ps
  die "gateway did not become healthy in time. Inspect with: ./start.sh logs"
}

up() {
  ensure_env
  "${COMPOSE[@]}" up -d --build --remove-orphans
  wait_for_gateway
  cat <<EOF

alphaview is running
  Web app      http://localhost:3000
  API gateway  http://localhost:8000
  Temporal UI  http://localhost:8080

Stop with: ./start.sh stop   |   Logs: ./start.sh logs [service]
EOF
}

require_docker
case "${1:-up}" in
  up|start) up ;;
  stop|down) "${COMPOSE[@]}" down ;;
  restart) "${COMPOSE[@]}" down; up ;;
  logs) shift; "${COMPOSE[@]}" logs -f --tail=100 "$@" ;;
  status|ps) "${COMPOSE[@]}" ps ;;
  *) die "unknown command '$1'. Use: up | stop | restart | logs [service] | status" ;;
esac
