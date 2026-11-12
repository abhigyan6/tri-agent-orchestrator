"""
Core Orchestrator Logic for Tri-Agent Orchestrator.
"""

import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .agents import get_all_agents
from .templates import render_template

# Entries never copied when the skill is installed as a directory copy.
_COPY_IGNORE = shutil.ignore_patterns(".git", "__pycache__", "tmp", "*.pyc", ".pytest_cache")

_META_RE = re.compile(r"^- \*\*(?P<key>[^:*]+):\*\*\s*(?P<value>.*?)\s*$")
_CHECK_RE = re.compile(r"^- \[(?P<mark>[ xX])\] (?P<text>.+?)\s*$", re.MULTILINE)


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def slugify(text: str, max_words: int = 6) -> str:
    """Turn free text into a short kebab-case slug, e.g. 'Build auth middleware' -> 'build-auth-middleware'."""
    words = re.findall(r"[a-z0-9]+", text.lower())[:max_words]
    return "-".join(words) or "new-feature"


def diagnose_environment() -> Dict[str, Any]:
    agents = get_all_agents()
    tools = {
        "git": shutil.which("git"),
        "gh": shutil.which("gh"),
        "python3": shutil.which("python3"),
        "node": shutil.which("node"),
    }

    return {
        "agents": {
            k: {"name": v.name, "path": v.path, "version": v.get_version(), "ready": v.is_available}
            for k, v in agents.items()
        },
        "tools": {k: {"path": v, "ready": v is not None} for k, v in tools.items()},
        "all_agents_ready": all(v.is_available for v in agents.values()),
    }


def _backup_path(target: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return target.with_name(f"{target.name}.bak-{stamp}")


def install_skills_globally(verbose: bool = True) -> List[str]:
    """
    Link (or, if symlinks are unavailable, copy) this repository into each agent's skills directory.

    A pre-existing real directory at a target is renamed to a timestamped .bak sibling
    rather than deleted, so nothing a user placed there is lost.
    """
    home = Path.home()
    source_skill_dir = get_repo_root()

    target_locations = [
        home / ".agents" / "skills" / "tri-agent-orchestrator",
        home / ".claude" / "skills" / "tri-agent-orchestrator",
        home / ".codex" / "skills" / "tri-agent-orchestrator",
    ]

    installed_paths = []
    for target in target_locations:
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.is_symlink():
            target.unlink()
        elif target.exists():
            backup = _backup_path(target)
            target.rename(backup)
            if verbose:
                print(f"  ↪ Existing directory moved to backup: {backup}")

        try:
            target.symlink_to(source_skill_dir, target_is_directory=True)
            mode = "Linked"
        except OSError as e:
            shutil.copytree(source_skill_dir, target, ignore=_COPY_IGNORE)
            mode = f"Copied (symlink unavailable: {e})"

        installed_paths.append(str(target))
        if verbose:
            print(f"✓ {mode} skill at: {target}")

    return installed_paths


def create_handoff_contract(
    feature_name: str,
    completed_by: str,
    next_agent: str,
    current_phase: str,
    summary_done: List[str],
    artifacts: List[str],
    constraints: List[str],
    checklist: List[str],
    output_path: Optional[Path] = None,
) -> Path:
    out = output_path or Path.cwd() / "HANDOFF.md"
    now = datetime.now(timezone.utc)
    workflow_id = f"wf-{now.strftime('%Y%m%d%H%M')}-{uuid.uuid4().hex[:6]}"

    content = render_template(
        "HANDOFF.template.md",
        {
            "WORKFLOW_ID": workflow_id,
            "FEATURE_NAME": feature_name,
            "CURRENT_PHASE": current_phase,
            "COMPLETED_BY": completed_by,
            "NEXT_AGENT": next_agent,
            "TIMESTAMP": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "SUMMARY_DONE": _bullets(summary_done, "Phase initialized."),
            "ARTIFACTS": _bullets(artifacts, "None yet."),
            "CONSTRAINTS": _bullets(constraints, "Adhere to repository conventions."),
            "CHECKLIST": "\n".join(f"- [ ] {item}" for item in checklist)
            if checklist
            else "- [ ] Execute assigned tasks.",
        },
    )

    out.write_text(content, encoding="utf-8")
    return out


def _bullets(items: List[str], empty: str) -> str:
    return "\n".join(f"- {item}" for item in items) if items else f"- {empty}"


def read_handoff_contract(path: Optional[Path] = None) -> Optional[str]:
    target = path or Path.cwd() / "HANDOFF.md"
    if target.exists():
        return target.read_text(encoding="utf-8")
    return None


def parse_handoff(text: str) -> Dict[str, Any]:
    """
    Extract the metadata fields and checklist state from a HANDOFF.md document.

    Returns a dict with ``metadata`` (key -> value, backticks stripped) and
    ``checklist`` (a list of {"text": str, "done": bool}).
    """
    metadata: Dict[str, str] = {}
    for line in text.splitlines():
        m = _META_RE.match(line)
        if m:
            metadata[m.group("key").strip()] = m.group("value").strip("` ").strip()

    checklist = [
        {"text": m.group("text"), "done": m.group("mark").lower() == "x"}
        for m in _CHECK_RE.finditer(text)
    ]
    return {"metadata": metadata, "checklist": checklist}
