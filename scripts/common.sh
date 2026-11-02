# Shared helpers for start.sh / stop.sh / reset.sh. Source this file; do not execute it.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PROJECT="alphaview"
COMPOSE_FILE="infra/docker-compose.yml"

die() { echo "error: $*" >&2; exit 1; }

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    # Docker Desktop may install its CLI outside PATH (e.g. "user" install location on macOS).
    local dir
    for dir in "$HOME/.docker/bin" /Applications/Docker.app/Contents/Resources/bin /usr/local/bin /opt/homebrew/bin; do
      if [[ -x "$dir/docker" ]]; then export PATH="$dir:$PATH"; break; fi
    done
  fi
  command -v docker >/dev/null 2>&1 || die "Docker is not installed. Install Docker Desktop: https://docs.docker.com/get-docker/"
  docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required (docker compose ...)."
  docker info >/dev/null 2>&1 || die "Docker daemon is not running. Start Docker Desktop and retry."
}

compose() {
  if [[ -f .env ]]; then
    docker compose -f "$COMPOSE_FILE" --env-file .env -p "$PROJECT" "$@"
  else
    # Teardown without .env: compose still requires these variables to parse the file.
    JWT_SECRET="${JWT_SECRET:-teardown-placeholder-not-a-real-secret}" ENCRYPTION_KEY="${ENCRYPTION_KEY:-unused}" \
      docker compose -f "$COMPOSE_FILE" -p "$PROJECT" "$@"
  fi
}
