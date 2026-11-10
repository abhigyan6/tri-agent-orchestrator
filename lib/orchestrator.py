"""
Core Orchestrator Logic for Tri-Agent Orchestrator.
"""

import json
import os
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .agents import get_all_agents
from .templates import HANDOFF_TEMPLATE, SPEC_TEMPLATE


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def diagnose_environment() -> Dict[str, Any]:
    agents = get_all_agents()
    tools = {
        "git": shutil.which("git"),
        "gh": shutil.which("gh"),
        "python3": shutil.which("python3"),
        "node": shutil.which("node"),
    }
    
    report = {
        "agents": {k: {"name": v.name, "path": v.path, "version": v.get_version(), "ready": v.is_available} for k, v in agents.items()},
        "tools": {k: {"path": v, "ready": v is not None} for k, v in tools.items()},
        "all_agents_ready": all(v.is_available for v in agents.values())
    }
    return report


def install_skills_globally(verbose: bool = True) -> List[str]:
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
        # Create symlink or directory copy
        if target.is_symlink() or target.exists():
            if target.is_symlink():
                target.unlink()
            else:
                shutil.rmtree(target)
        try:
            target.symlink_to(source_skill_dir, target_is_directory=True)
            installed_paths.append(str(target))
            if verbose:
                print(f"✓ Linked skill to: {target}")
        except Exception as e:
            # Fallback to copy
            shutil.copytree(source_skill_dir, target)
            installed_paths.append(str(target))
            if verbose:
                print(f"✓ Copied skill to: {target} (fallback: {e})")
                
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
    workflow_id = f"wf-{datetime.utcnow().strftime('%Y%m%d%H%M')}-{uuid.uuid4().hex[:6]}"
    
    content = HANDOFF_TEMPLATE.format(
        workflow_id=workflow_id,
        feature_name=feature_name,
        current_phase=current_phase,
        completed_by=completed_by,
        next_agent=next_agent,
        timestamp=datetime.utcnow().isoformat() + "Z",
        summary_done="\n".join(f"- {item}" for item in summary_done) if summary_done else "- Phase initialized.",
        artifacts="\n".join(f"- {item}" for item in artifacts) if artifacts else "- None yet.",
        constraints="\n".join(f"- {item}" for item in constraints) if constraints else "- Adhere to repository conventions.",
        checklist="\n".join(f"- [ ] {item}" for item in checklist) if checklist else "- [ ] Execute assigned tasks."
    )
    
    out.write_text(content, encoding="utf-8")
    return out


def read_handoff_contract(path: Optional[Path] = None) -> Optional[str]:
    target = path or Path.cwd() / "HANDOFF.md"
    if target.exists():
        return target.read_text(encoding="utf-8")
    return None
