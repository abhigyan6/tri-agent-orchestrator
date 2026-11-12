#!/usr/bin/env bash
# Register tri-agent-orchestrator with Antigravity, Claude Code, and Codex.
# Delegates to `tri-agent install-skill` so there is a single implementation.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ python3 (3.9+) is required." >&2
  exit 1
fi

exec python3 "$SCRIPT_DIR/bin/tri-agent" install-skill
