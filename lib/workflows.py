"""
Workflow planning and execution for Tri-Agent Orchestrator.

A workflow is a list of *stages*. Stages run in order; the steps inside one stage
run concurrently (for example, two architects producing competing proposals). If any
step fails, the pipeline stops after its stage so later agents never build on broken output.
"""

import shlex
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

from .agents import DEFAULT_TIMEOUT, get_all_agents
from .orchestrator import slugify

WORKFLOWS = ("relay", "debate", "audit")
_PROMPT_PREVIEW = 90


@dataclass(frozen=True)
class Step:
    agent: str   # "agy" | "claude" | "codex"
    title: str   # human-readable label shown in progress output
    prompt: str


Stage = List[Step]


def plan_workflow(workflow: str, task: str, feature: Optional[str] = None) -> List[Stage]:
    """Build the ordered stages for a workflow. Pure function: no agents are invoked."""
    if workflow not in WORKFLOWS:
        raise ValueError(f"Unknown workflow '{workflow}'. Choose from: {', '.join(WORKFLOWS)}")

    slug = slugify(feature or task)
    spec = f"docs/tri-agent/SPEC-{slug}.md"

    if workflow == "relay":
        return _relay(task, spec)
    if workflow == "debate":
        return _debate(task, slug)
    return _audit(task, spec, slug)


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
                "trade-off scorecard, and consequences. Update HANDOFF.md with Next Agent: none."
            ),
        )],
    ]


def _audit(task: str, spec: str, slug: str) -> List[Stage]:
    audit_report = f"docs/tri-agent/AUDIT-{slug}.md"
    return [
        [Step(
            agent="claude",
            title="Build: Initial Implementation (Claude Code)",
            prompt=(
                "You are the Lead Software Craftsman in a tri-agent audit workflow.\n"
                f"Task: {task}\n"
                "Implement it with careful attention to authentication, authorization, input validation, and "
                "error handling. List every changed file in HANDOFF.md and set Next Agent: agy."
            ),
        )],
        [Step(
            agent="agy",
            title="Audit: Adversarial Red-Team Review (Antigravity)",
            prompt=(
                "You are the Adversarial Red-Team Auditor in a tri-agent workflow.\n"
                "Review the implementation listed in HANDOFF.md against the checklist in "
                "workflows/03-redteam-audit.md: authentication and session tampering, IDOR, injection, "
                "denial of service, sensitive data exposure, and race conditions.\n"
                f"Write findings to {audit_report} with an ID, severity, location, and recommended fix for "
                "each. Do not modify source code. Set Next Agent: claude in HANDOFF.md."
            ),
        )],
        [Step(
            agent="claude",
            title="Remediation: Patch Findings (Claude Code)",
            prompt=(
                f"Read {audit_report}. Patch every High and Medium finding in the source and add a regression "
                "check for each. Update HANDOFF.md with Next Agent: codex."
            ),
        )],
        [Step(
            agent="codex",
            title="Verification: Regression Testing (Codex)",
            prompt=(
                f"Read {audit_report} and HANDOFF.md. Confirm every finding is fixed: add regression tests for "
                "each, run the full test suite and linters, and list any remaining failures in HANDOFF.md "
                "with Next Agent: none."
            ),
        )],
    ]


def _preview(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= _PROMPT_PREVIEW else flat[:_PROMPT_PREVIEW] + "…"


def describe_plan(stages: Sequence[Stage]) -> List[str]:
    """Render a plan as the shell-like commands that would run, for --dry-run."""
    agents = get_all_agents()
    lines: List[str] = []
    for index, stage in enumerate(stages, start=1):
        parallel = " (parallel)" if len(stage) > 1 else ""
        lines.append(f"Stage {index}{parallel}:")
        for step in stage:
            argv = agents[step.agent].build_command(step.prompt, non_interactive=True) or [step.agent]
            display = [argv[0], *argv[1:-1], shlex.quote(_preview(argv[-1]))]
            lines.append(f"  [{step.title}]")
            lines.append(f"    {' '.join(display)}")
    return lines


def run_workflow(
    workflow: str,
    task: str,
    feature: Optional[str] = None,
    dry_run: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    out: Callable[[str], None] = print,
) -> bool:
    """Execute a workflow. Returns True only if every stage succeeds."""
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

    for index, stage in enumerate(stages, start=1):
        for step in stage:
            out(f"▶ {step.title}")

        if len(stage) == 1:
            results = [_execute(agents, stage[0])]
        else:
            with ThreadPoolExecutor(max_workers=len(stage)) as pool:
                results = list(pool.map(lambda s: _execute(agents, s), stage))

        failures = [(step, code, output) for step, (code, output) in zip(stage, results) if code != 0]
        for step, (code, _) in zip(stage, results):
            status = "✓" if code == 0 else f"✗ exit {code}"
            out(f"  {status}  {step.title}")

        if failures:
            for step, code, output in failures:
                tail = "\n".join(output.strip().splitlines()[-20:])
                out(f"\n--- {step.title} output (last 20 lines) ---\n{tail}\n")
            out(f"❌ Stage {index} failed; stopping before later agents run.")
            return False

    out("\n🎉 Tri-Agent Workflow Completed!")
    return True


def _execute(agents, step: Step):
    return agents[step.agent].run_prompt(step.prompt, non_interactive=True)
