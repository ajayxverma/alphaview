#!/usr/bin/env bash
# Delete all alphaview containers, data volumes and built images so the project starts from scratch.
# Always asks for confirmation; refuses to run without an interactive terminal.
set -euo pipefail
source "$(dirname "$0")/scripts/common.sh"

ask_yes() {
  local answer
  read -r -p "$1 [y/N] " answer
  [[ "$answer" =~ ^[Yy]([Ee][Ss])?$ ]]
}

remove_app_images() {
  # Covers both naming styles compose uses: "alphaview/<svc>:local" and "alphaview-<svc>".
  { docker images -q --filter "reference=alphaview/*"; docker images -q --filter "reference=alphaview-*"; } \
    | sort -u | xargs docker image rm -f >/dev/null 2>&1 || true
}

[[ -t 0 ]] || die "reset.sh needs an interactive terminal for confirmation; refusing to run unattended."
require_docker

cat <<EOF
WARNING: this permanently deletes ALL alphaview data on this machine:
  - all alphaview containers and the alphaview network
  - database volumes: users, workspaces, connected tools, AI provider keys,
    discovery runs, opportunities and crawled signals
  - locally built alphaview images (rebuilt automatically by ./start.sh)

EOF
read -r -p "Type 'reset' to continue (anything else aborts): " answer
if [[ "$answer" != "reset" ]]; then
  echo "Aborted. Nothing was deleted."
  exit 1
fi

delete_env=false
delete_artifacts=false
ask_yes "Also delete .env (generated secrets and any server API keys you added)?" && delete_env=true
ask_yes "Also delete local build artifacts (.venv, node_modules, .next, caches)?" && delete_artifacts=true

echo "Removing containers, network and data volumes..."
compose down --volumes --remove-orphans

echo "Removing built alphaview images..."
remove_app_images

if $delete_env; then
  rm -f .env
  echo "Removed .env"
fi

if $delete_artifacts; then
  echo "Removing local build artifacts..."
  rm -rf .venv node_modules apps/web/node_modules apps/web/.next .turbo apps/web/.turbo .pytest_cache .ruff_cache
  find packages services -type d \( -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} +
fi

cat <<EOF

Reset complete. Run ./start.sh to rebuild and start a fresh alphaview.
EOF
