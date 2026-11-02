#!/usr/bin/env bash
# Stop all alphaview containers. Data volumes and images are kept; start again with ./start.sh.
set -euo pipefail
source "$(dirname "$0")/scripts/common.sh"

require_docker
echo "Stopping alphaview..."
compose down --remove-orphans
cat <<EOF

alphaview stopped. Your data is preserved.
  Start again:      ./start.sh
  Wipe everything:  ./reset.sh
EOF
