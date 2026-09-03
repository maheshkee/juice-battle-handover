#!/bin/bash
# hub/deploy.sh — DEPRECATED entry point, kept for muscle memory.
# The canonical redeploy script is the repo-root deploy.sh, which also re-syncs
# the systemd unit files (this copy did not, letting the installed units drift).
set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "hub/deploy.sh is deprecated — running $REPO_ROOT/deploy.sh instead."
exec "$REPO_ROOT/deploy.sh" "$@"
