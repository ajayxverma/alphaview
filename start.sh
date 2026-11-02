#!/usr/bin/env bash
# Start every alphaview microservice with Docker Compose.
# Usage: ./start.sh [up|stop|restart|logs [service]|status]
set -euo pipefail
source "$(dirname "$0")/scripts/common.sh"

GATEWAY_HEALTH="http://localhost:8000/health"

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
  compose ps
  die "gateway did not become healthy in time. Inspect with: ./start.sh logs"
}

up() {
  ensure_env
  compose up -d --build --remove-orphans
  wait_for_gateway
  cat <<EOF

alphaview is running
  Web app      http://localhost:3000
  API gateway  http://localhost:8000
  Temporal UI  http://localhost:8080

Stop: ./stop.sh   |   Logs: ./start.sh logs [service]   |   Wipe everything: ./reset.sh
EOF
}

require_docker
ensure_env
case "${1:-up}" in
  up|start) up ;;
  stop|down) exec ./stop.sh ;;
  restart) compose down; up ;;
  logs) shift; compose logs -f --tail=100 "$@" ;;
  status|ps) compose ps ;;
  *) die "unknown command '$1'. Use: up | stop | restart | logs [service] | status" ;;
esac
