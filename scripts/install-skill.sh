#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "🛰️ Installing 'tri-agent-orchestrator' skill across coding agent environments..."

TARGETS=(
  "$HOME/.agents/skills/tri-agent-orchestrator"
  "$HOME/.claude/skills/tri-agent-orchestrator"
  "$HOME/.codex/skills/tri-agent-orchestrator"
)

for TARGET in "${TARGETS[@]}"; do
  PARENT_DIR="$(dirname "$TARGET")"
  mkdir -p "$PARENT_DIR"
  if [ -L "$TARGET" ] || [ -d "$TARGET" ]; then
    rm -rf "$TARGET"
  fi
  ln -sf "$SCRIPT_DIR" "$TARGET"
  echo "  ✓ Linked to $TARGET"
done

echo ""
echo "🎉 Tri-Agent Orchestrator skill is now active for Antigravity, Claude Code, and Codex!"
