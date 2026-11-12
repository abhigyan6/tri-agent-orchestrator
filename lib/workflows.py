"""
Workflow planning, verification, and execution for Tri-Agent Orchestrator.

A workflow is a list of *stages*. Stages run in order; the steps inside one stage run
concurrently (for example, two architects producing competing proposals).

After each stage, the orchestrator checks that the agents honoured the contract:
  - every expected artifact exists and is non-empty;
  - HANDOFF.md was rewritten by the step, with the expected "Completed By" and "Next Agent";
  - steps with a write scope changed nothing outside it (checked with git).

If any stage fails, the pipeline stops before later agents build on broken output.
"""

import hashlib
import shlex
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .agents import DEFAULT_TIMEOUT, get_all_agents
from .orchestrator import LockError, parse_handoff, run_lock, slugify

WORKFLOWS = ("relay", "debate", "audit")
_PROMPT_PREVIEW = 90
_STATE_DIR = Path("tmp/tri-agent")
_LOCK_FILE = _STATE_DIR / "run.lock"
_RUNS_DIR = _STATE_DIR / "runs"
_HANDOFF = "HANDOFF.md"


@dataclass(frozen=True)
class Step:
    agent: str                                  # "agy" | "claude" | "codex"
    title: str                                  # label shown in progress output
    prompt: str
    access: str = "edit"                        # passed to the agent CLI; see agents.ACCESS_MODES
    artifacts: Tuple[str, ...] = ()             # must exist and be non-empty after the step
    handoff_completed: Optional[str] = None     # HANDOFF.md "Completed By" must equal this
    handoff_next: Optional[str] = None          # HANDOFF.md "Next Agent" must equal this
    writable: Optional[Tuple[str, ...]] = None  # if set, git-visible changes must stay inside these paths


Stage = List[Step]


def plan_workflow(workflow: str, task: str, feature: Optional[str] = None) -> List[Stage]:
    """Build the ordered stages for a workflow. Pure function: no agents are invoked."""
    if workflow not in WORKFLOWS:
        raise ValueError(f"Unknown workflow '{workflow}'. Choose from: {', '.join(WORKFLOWS)}")

    slug = slugify(feature or task)
    if workflow == "relay":
        return _relay(task, f"docs/tri-agent/SPEC-{slug}.md")
    if workflow == "debate":
        return _debate(task, slug)
    return _audit(task, slug)


def _relay(task: str, spec: str) -> List[Stage]:
    return [
        [Step(
            agent="agy",
            title="Phase 1: Architecture & Specification (Antigravity)",
            prompt=(
                "You are the Chief Architect in a tri-agent workflow (Antigravity x Claude Code x Codex).\n"
                f"Task: {task}\n"
                f"Research the existing codebase, then write an architecture specification to {spec}. "
                "Do not write implementation code.\n"
                "Then create or update HANDOFF.md following the handoff contract in SKILL.md, with "
                "Completed By: agy and Next Agent: claude."
            ),
            artifacts=(spec,),
            handoff_completed="agy",
            handoff_next="claude",
        )],
        [Step(
            agent="claude",
            title="Phase 2: Implementation (Claude Code)",
            prompt=(
                "You are the Lead Software Craftsman in a tri-agent workflow.\n"
                f"Read {spec} and HANDOFF.md, then implement the specification with clean, idiomatic code. "
                "Do not silently change its architectural decisions; if one is infeasible, record the "
                "conflict under 'Critical Constraints & Decisions' in HANDOFF.md.\n"
                "When finished, update HANDOFF.md with Completed By: claude, Next Agent: codex, and a list "
                "of every file you created or changed."
            ),
            handoff_completed="claude",
            handoff_next="codex",
        )],
        [Step(
            agent="codex",
            title="Phase 3: Verification (Codex)",
            prompt=(
                "You are the Reliability Engineer in a tri-agent workflow.\n"
                f"Read {spec} and HANDOFF.md, then review the files listed there. Write tests covering the "
                "specification, run the test suite and linters, and fix regressions.\n"
                "Summarize the results in HANDOFF.md with Completed By: codex and Next Agent: none."
            ),
            handoff_completed="codex",
            handoff_next="none",
        )],
    ]


def _debate(task: str, slug: str) -> List[Stage]:
    proposal_a = f"docs/tri-agent/PROPOSAL-{slug}-agy.md"
    proposal_b = f"docs/tri-agent/PROPOSAL-{slug}-claude.md"
    adr = f"docs/adr/ADR-{slug}.md"
    return [
        [
            Step(
                agent="agy",
                title="Proposal A: Scalability & Security (Antigravity)",
                prompt=(
                    "You are the Chief Architect in a tri-agent architecture debate.\n"
                    f"Decision to make: {task}\n"
                    f"Write Proposal A to {proposal_a}. Emphasize failure modes, security guarantees, and "
                    "behaviour at future scale. Cover the trade-offs and the risks you see in the alternatives. "
                    "Do not write implementation code."
                ),
                artifacts=(proposal_a,),
            ),
            Step(
                agent="claude",
                title="Proposal B: Simplicity & Developer Experience (Claude Code)",
                prompt=(
                    "You are the Lead Software Craftsman in a tri-agent architecture debate.\n"
                    f"Decision to make: {task}\n"
                    f"Write Proposal B to {proposal_b}. Emphasize simplicity, developer velocity, and "
                    "refactorability. Cover the trade-offs and the risks you see in the alternatives. "
                    "Do not write implementation code."
                ),
                artifacts=(proposal_b,),
            ),
        ],
        [Step(
            agent="codex",
            title="Synthesis: Benchmark & ADR (Codex)",
            prompt=(
                "You are the Reliability Engineer in a tri-agent architecture debate.\n"
                f"Read {proposal_a} and {proposal_b}. Benchmark or simulate both approaches where feasible, "
                "using throwaway scripts outside the codebase.\n"
                f"Write the consensus to {adr} as an Architecture Decision Record: context, decision, "
                "trade-off scorecard, and consequences. Update HANDOFF.md with Completed By: codex and "
                "Next Agent: none."
            ),
            artifacts=(adr,),
            handoff_completed="codex",
            handoff_next="none",
        )],
    ]


def _audit(task: str, slug: str) -> List[Stage]:
    report = f"docs/tri-agent/AUDIT-{slug}.md"
    return [
        [Step(
            agent="claude",
            title="Build: Initial Implementation (Claude Code)",
            prompt=(
                "You are the Lead Software Craftsman in a tri-agent audit workflow.\n"
                f"Task: {task}\n"
                "Implement it with careful attention to authentication, authorization, input validation, and "
                "error handling. List every changed file in HANDOFF.md with Completed By: claude and "
                "Next Agent: agy."
            ),
            handoff_completed="claude",
            handoff_next="agy",
        )],
        [Step(
            agent="agy",
            title="Audit: Adversarial Red-Team Review (Antigravity)",
            prompt=(
                "You are the Adversarial Red-Team Auditor in a tri-agent workflow.\n"
                "Review the implementation listed in HANDOFF.md against the checklist in "
                "workflows/03-redteam-audit.md: authentication and session tampering, IDOR, injection, "
                "denial of service, sensitive data exposure, and race conditions.\n"
                f"Write findings to {report} with an ID, severity, location, and recommended fix for each. "
                "Do NOT modify any source code or tests; your only writes are that report and HANDOFF.md. "
                "Set Completed By: agy and Next Agent: claude in HANDOFF.md."
            ),
            artifacts=(report,),
            handoff_completed="agy",
            handoff_next="claude",
            writable=("docs/tri-agent", _HANDOFF),
        )],
        [Step(
            agent="claude",
            title="Remediation: Patch Findings (Claude Code)",
            prompt=(
                f"Read {report}. Patch every High and Medium finding in the source and add a regression "
                "check for each. Update HANDOFF.md with Completed By: claude and Next Agent: codex."
            ),
            handoff_completed="claude",
            handoff_next="codex",
        )],
        [Step(
            agent="codex",
            title="Verification: Regression Testing (Codex)",
            prompt=(
                f"Read {report} and HANDOFF.md. Confirm every finding is fixed: add regression tests for "
                "each, run the full test suite and linters, and list any remaining failures in HANDOFF.md "
                "with Completed By: codex and Next Agent: none."
            ),
            handoff_completed="codex",
            handoff_next="none",
        )],
    ]


# ---------------------------------------------------------------------------
# Plan display
# ---------------------------------------------------------------------------

def _preview(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= _PROMPT_PREVIEW else flat[:_PROMPT_PREVIEW] + "…"


def describe_plan(stages: Sequence[Stage]) -> List[str]:
    """Render a plan as the commands that would run, for --dry-run."""
    agents = get_all_agents()
    lines: List[str] = []
    for index, stage in enumerate(stages, start=1):
        parallel = " (parallel)" if len(stage) > 1 else ""
        lines.append(f"Stage {index}{parallel}:")
        for step in stage:
            argv = agents[step.agent].build_command(step.prompt, non_interactive=True, access=step.access)
            argv = argv or [step.agent]
            display = [argv[0], *argv[1:-1], shlex.quote(_preview(argv[-1]))]
            lines.append(f"  [{step.title}]")
            lines.append(f"    {' '.join(display)}")
    return lines


# ---------------------------------------------------------------------------
# Verification helpers
# ---------------------------------------------------------------------------

def _digest(path: Path) -> Optional[str]:
    try:
        if path.is_file():
            return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        pass
    return None


def _git(root: Path, *args: str) -> Optional[bytes]:
    try:
        proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout if proc.returncode == 0 else None


def _snapshot_changes(root: Path) -> Optional[Dict[str, Optional[str]]]:
    """
    Map every git-visible changed path to a content digest (None = deleted).

    Keys are relative to ``root`` (the directory the run operates in), so they match the
    scope prefixes in Step.writable even when ``root`` is a subdirectory of the repository.
    Returns None when ``root`` is not inside a git work tree.
    """
    top_raw = _git(root, "rev-parse", "--show-toplevel")
    status = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if top_raw is None or status is None:
        return None
    top = Path(top_raw.decode("utf-8", "replace").strip())

    snapshot: Dict[str, Optional[str]] = {}
    tokens = status.split(b"\0")
    i = 0
    while i < len(tokens):
        token = tokens[i].decode("utf-8", "replace")
        i += 1
        if len(token) < 4:
            continue
        code, repo_path = token[:2], token[3:]
        if "R" in code or "C" in code:
            i += 1  # renames/copies carry the original path as the next token
        absolute = top / repo_path  # git reports paths relative to the repository top
        rel = absolute.relative_to(root) if absolute.is_relative_to(root) else Path(absolute)
        snapshot[rel.as_posix()] = _digest(absolute)
    return snapshot


def _within(path: str, allowed: Sequence[str]) -> bool:
    return any(path == a or path.startswith(a.rstrip("/") + "/") for a in allowed)


def _out_of_scope(before: Dict[str, Optional[str]], after: Dict[str, Optional[str]],
                  allowed: Sequence[str]) -> List[str]:
    """Paths whose content changed between snapshots outside ``allowed``.

    The orchestrator's own state (lock file, run logs) is never an agent write, so it is ignored.
    """
    violations = []
    for path in sorted(set(before) | set(after)):
        if _within(path, (_STATE_DIR.as_posix(),)):
            continue
        if before.get(path) != after.get(path) and not _within(path, allowed):
            violations.append(path)
    return violations


def _check_stage(stage: Stage, root: Path, handoff_before: Optional[str]) -> List[str]:
    problems: List[str] = []
    for step in stage:
        for rel in step.artifacts:
            target = root / rel
            if not target.is_file() or target.stat().st_size == 0:
                problems.append(f"[{step.title}] expected artifact missing or empty: {rel}")

        if step.handoff_completed is None and step.handoff_next is None:
            continue
        handoff_path = root / _HANDOFF
        if not handoff_path.is_file():
            problems.append(f"[{step.title}] {_HANDOFF} was not written")
            continue
        if _digest(handoff_path) == handoff_before:
            problems.append(f"[{step.title}] {_HANDOFF} was not updated by this step")
        meta = parse_handoff(handoff_path.read_text(encoding="utf-8"))["metadata"]
        if step.handoff_completed and meta.get("Completed By") != step.handoff_completed:
            problems.append(
                f"[{step.title}] {_HANDOFF} 'Completed By' is {meta.get('Completed By')!r}, "
                f"expected {step.handoff_completed!r}"
            )
        if step.handoff_next and meta.get("Next Agent") != step.handoff_next:
            problems.append(
                f"[{step.title}] {_HANDOFF} 'Next Agent' is {meta.get('Next Agent')!r}, "
                f"expected {step.handoff_next!r}"
            )
    return problems


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _execute(agents, step: Step, root: Path):
    return agents[step.agent].run_prompt(
        step.prompt, non_interactive=True, cwd=str(root), access=step.access
    )


def _write_log(run_dir: Path, index: int, step: Step, code: int, output: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / f"{index:02d}-{step.agent}.log"
    path.write_text(
        f"# {step.title}\nagent: {step.agent}\naccess: {step.access}\nexit: {code}\n\n"
        f"## Prompt\n{step.prompt}\n\n## Output\n{output}\n",
        encoding="utf-8",
    )


def run_workflow(
    workflow: str,
    task: str,
    feature: Optional[str] = None,
    dry_run: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    root: Optional[Path] = None,
    out: Callable[[str], None] = print,
) -> bool:
    """Execute a workflow in ``root`` (default: current directory). Returns True only if every stage passes."""
    root = Path(root or Path.cwd()).resolve()
    stages = plan_workflow(workflow, task, feature)

    out(f"🚀 Initiating Tri-Agent Workflow: {workflow.upper()}")
    out(f"  Task: {task}\n")

    if dry_run:
        out("[DRY RUN] Planned commands (nothing will be executed):")
        for line in describe_plan(stages):
            out(line)
        return True

    agents = get_all_agents(timeout)
    needed = {step.agent for stage in stages for step in stage}
    missing = [agents[k].binary_name for k in sorted(needed) if not agents[k].is_available]
    if missing:
        out(f"❌ Required agent CLI(s) not found in PATH: {', '.join(missing)}. Run `tri-agent doctor`.")
        return False

    try:
        with run_lock(root / _LOCK_FILE):
            return _execute_stages(stages, agents, root, feature or task, out)
    except LockError as e:
        out(f"❌ {e}")
        return False


def _execute_stages(stages, agents, root: Path, label: str, out) -> bool:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = root / _RUNS_DIR / f"{stamp}-{slugify(label)}"
    out(f"  Logs: {run_dir.relative_to(root)}/\n")

    for index, stage in enumerate(stages, start=1):
        for step in stage:
            out(f"▶ {step.title}")

        scoped = any(step.writable is not None for step in stage)
        scope_before = _snapshot_changes(root) if scoped else None
        handoff_before = _digest(root / _HANDOFF)

        if len(stage) == 1:
            results = [_execute(agents, stage[0], root)]
        else:
            with ThreadPoolExecutor(max_workers=len(stage)) as pool:
                results = list(pool.map(lambda s: _execute(agents, s, root), stage))

        for step, (code, output) in zip(stage, results):
            _write_log(run_dir, index, step, code, output)
            status = "✓" if code == 0 else f"✗ exit {code}"
            out(f"  {status}  {step.title}")

        failures = [(step, output) for step, (code, output) in zip(stage, results) if code != 0]
        if failures:
            for step, output in failures:
                tail = "\n".join(output.strip().splitlines()[-20:])
                out(f"\n--- {step.title} output (last 20 lines) ---\n{tail}\n")
            out(f"❌ Stage {index} failed; stopping before later agents run. Full logs in {run_dir.relative_to(root)}/")
            return False

        problems = _check_stage(stage, root, handoff_before)
        if scoped:
            scope_after = _snapshot_changes(root)
            if scope_after is None or scope_before is None:
                out("  ⚠️  Write-scope check skipped: not a git work tree.")
            else:
                for step in stage:
                    if step.writable is None:
                        continue
                    for path in _out_of_scope(scope_before, scope_after, step.writable):
                        problems.append(f"[{step.title}] modified out-of-scope path: {path}")

        if problems:
            for problem in problems:
                out(f"  ✗ contract: {problem}")
            out(f"❌ Stage {index} broke the handoff contract; stopping. Logs: {run_dir.relative_to(root)}/")
            return False

    _print_summary(root, run_dir, out)
    out("\n🎉 Tri-Agent Workflow Completed!")
    return True


def _print_summary(root: Path, run_dir: Path, out) -> None:
    changed = _snapshot_changes(root)
    if changed is None:
        out(f"\nLogs: {run_dir.relative_to(root)}/")
        return
    visible = sorted(p for p in changed if not p.startswith(str(_STATE_DIR)))
    out("\nGit-visible changes in the working tree after this run:" if visible
        else "\nNo git-visible changes in the working tree after this run.")
    for path in visible:
        out(f"  {path}")
    out(f"Logs: {run_dir.relative_to(root)}/")
