#!/bin/bash
# hub/setup.sh — DEPRECATED entry point, kept for muscle memory.
#
# The canonical one-time board setup is the repo-root setup.sh. This wrapper
# used to carry its own (now stale) copy of the steps — it wrote a raw `type hw`
# ~/.asoundrc that causes an ALSA underrun storm, and told you to hand-download
# sound files that are now committed to the repo. Both are fixed in the root
# script, so just delegate to it.
set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "hub/setup.sh is deprecated — running $REPO_ROOT/setup.sh instead."
exec "$REPO_ROOT/setup.sh" "$@"
