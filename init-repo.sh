#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

echo "=========================================================="
echo " 🚀 Initializing Git Repository: tri-agent-orchestrator"
echo "=========================================================="

# 1. Initialize Git if not already initialized
if [ ! -d ".git" ]; then
  git init -b main
  echo "✓ Initialized empty Git repository in $REPO_DIR"
else
  echo "✓ Git repository already initialized."
  git branch -M main || true
fi

# 2. Stage all files
git add .
echo "✓ Staged files for commit."

# 3. Commit if there are changes
if git diff --cached --quiet; then
  echo "✓ Working tree clean, nothing to commit."
else
  git commit -m "feat: initial release of tri-agent-orchestrator (Antigravity x Claude Code x Codex)"
  echo "✓ Created initial commit."
fi

# 4. Check GitHub CLI status
echo ""
echo "Checking GitHub authentication..."
if command -v gh &> /dev/null; then
  if gh auth status &> /dev/null; then
    GH_USER=$(gh api user --jq .login 2>/dev/null || echo "user")
    echo "✓ Logged in to GitHub as: $GH_USER"
    
    # Prompt or auto-create remote
    if [[ "${1:-}" == "--push" ]] || [[ "${AUTO_PUSH:-}" == "true" ]]; then
      echo "Pushing directly to GitHub..."
      if ! git remote get-url origin &>/dev/null; then
        gh repo create "tri-agent-orchestrator" --public --source=. --remote=origin --description "Multi-agent orchestration framework & skill coordinating Google Antigravity, Anthropic Claude Code, and OpenAI Codex." --push
      else
        git push -u origin main
      fi
      echo "🎉 Successfully published to GitHub!"
    else
      echo ""
      echo "To publish this repository directly to your GitHub, run:"
      echo "  gh repo create tri-agent-orchestrator --public --source=. --remote=origin --push"
      echo "Or re-run this script with --push:"
      echo "  ./init-repo.sh --push"
    fi
  else
    echo "⚠️  GitHub CLI is installed but not authenticated. Run 'gh auth login' to authenticate."
  fi
else
  echo "⚠️  GitHub CLI (gh) is not installed. You can set the remote manually with:"
  echo "  git remote add origin https://github.com/<your-username>/tri-agent-orchestrator.git"
  echo "  git push -u origin main"
fi

echo ""
echo "✅ Local repository initialization complete!"
