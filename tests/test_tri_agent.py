"""
Unit tests for Tri-Agent Orchestrator. Standard library only; no agent CLI is invoked.

Run from the repository root:
    python3 -m unittest discover -s tests -v
"""

import itertools
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lib import workflows  # noqa: E402
from lib.agents import AgentClient  # noqa: E402
from lib.orchestrator import (  # noqa: E402
    LockError,
    create_handoff_contract,
    install_skills_globally,
    parse_handoff,
    run_lock,
    slugify,
)
from lib.templates import render_template  # noqa: E402

TASK = "Build upload endpoint"
_counter = itertools.count(1)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

def handoff_text(completed: str, next_agent: str, stamp: int) -> str:
    return (
        "# Tri-Agent Handoff Contract\n\n## Metadata\n"
        f"- **Workflow ID:** `wf-test`\n- **Active Feature:** `test`\n"
        f"- **Current Phase:** `test`\n- **Completed By:** `{completed}`\n"
        f"- **Next Agent:** `{next_agent}`\n- **Timestamp:** `{stamp}`\n\n"
        "## Verification Checklist for Next Agent\n- [ ] check\n"
    )


def obedient(plan_by_prompt):
    """An effect that does exactly what each step's contract asks for."""
    def effect(prompt: str, root: Path) -> None:
        step = plan_by_prompt[prompt]
        for rel in step.artifacts:
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# produced\nSome content.\n", encoding="utf-8")
        if step.handoff_completed:
            (root / "HANDOFF.md").write_text(
                handoff_text(step.handoff_completed, step.handoff_next, next(_counter)),
                encoding="utf-8",
            )
    return effect


class FakeAgent:
    """Stands in for AgentClient: records calls and applies an optional effect to the workspace."""

    def __init__(self, binary: str, calls: list, effect=None, code: int = 0):
        self.binary_name = binary
        self.name = binary
        self.is_available = True
        self._calls = calls
        self._effect = effect
        self._code = code

    def build_command(self, prompt, non_interactive=True, access="edit"):
        return [self.binary_name, "--print", prompt]

    def run_prompt(self, prompt, non_interactive=True, cwd=None, access="edit"):
        self._calls.append(self.binary_name)
        if self._code == 0 and self._effect is not None:
            self._effect(prompt, Path(cwd))
        return (self._code, "agent exploded" if self._code else "ok")


def make_agents(workflow, effects, calls, failing=()):
    """effects: dict binary -> callable(prompt, root). failing: binaries that exit 1."""
    agents = {}
    for name in ("agy", "claude", "codex"):
        agents[name] = FakeAgent(name, calls, effects.get(name), code=1 if name in failing else 0)
    return agents


def plan_index(workflow):
    return {s.prompt: s for stage in workflows.plan_workflow(workflow, TASK) for s in stage}


def run(workflow, agents, root, dry_run=False):
    lines = []
    with mock.patch.object(workflows, "get_all_agents", lambda timeout=None: agents):
        ok = workflows.run_workflow(workflow, TASK, dry_run=dry_run, root=root, out=lines.append)
    return ok, "\n".join(lines)


def git_init(path: Path) -> bool:
    if shutil.which("git") is None:
        return False
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)
    return True


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class SlugifyTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify("Build Auth Middleware!"), "build-auth-middleware")

    def test_truncates_to_six_words(self):
        self.assertEqual(slugify("one two three four five six seven eight"), "one-two-three-four-five-six")

    def test_empty_falls_back(self):
        self.assertEqual(slugify("!!!"), "new-feature")


class TemplateTests(unittest.TestCase):
    def test_renders_all_placeholders(self):
        out = render_template("HANDOFF.template.md", {
            "WORKFLOW_ID": "wf-1", "FEATURE_NAME": "f", "CURRENT_PHASE": "p",
            "COMPLETED_BY": "agy", "NEXT_AGENT": "claude", "TIMESTAMP": "t",
            "SUMMARY_DONE": "- a", "ARTIFACTS": "- b", "CONSTRAINTS": "- c", "CHECKLIST": "- [ ] d",
        })
        self.assertNotIn("{{", out)
        self.assertIn("**Next Agent:** `claude`", out)

    def test_missing_value_raises(self):
        with self.assertRaises(ValueError):
            render_template("HANDOFF.template.md", {"WORKFLOW_ID": "x"})

    def test_values_are_not_reinterpreted(self):
        values = {k: "" for k in ("WORKFLOW_ID", "FEATURE_NAME", "CURRENT_PHASE", "COMPLETED_BY",
                                  "NEXT_AGENT", "TIMESTAMP", "SUMMARY_DONE", "ARTIFACTS",
                                  "CONSTRAINTS", "CHECKLIST")}
        values["FEATURE_NAME"] = "{{NEXT_AGENT}} and {braces}"
        out = render_template("HANDOFF.template.md", values)
        self.assertIn("{{NEXT_AGENT}} and {braces}", out)


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_create_then_parse_round_trip(self):
        path = create_handoff_contract(
            feature_name="rate-limiter",
            completed_by="agy",
            next_agent="claude",
            current_phase="Phase 1: Spec",
            summary_done=["Designed token bucket"],
            artifacts=["docs/tri-agent/SPEC-rate-limiter.md"],
            constraints=["No new dependencies"],
            checklist=["Implement limiter", "Add tests"],
            output_path=self.dir / "HANDOFF.md",
        )
        parsed = parse_handoff(path.read_text(encoding="utf-8"))
        self.assertEqual(parsed["metadata"]["Active Feature"], "rate-limiter")
        self.assertEqual(parsed["metadata"]["Completed By"], "agy")
        self.assertEqual(parsed["metadata"]["Next Agent"], "claude")
        self.assertTrue(parsed["metadata"]["Timestamp"].endswith("Z"))
        self.assertEqual(len(parsed["checklist"]), 2)
        self.assertFalse(any(item["done"] for item in parsed["checklist"]))

    def test_parse_counts_checked_items(self):
        text = (
            "- **Next Agent:** `codex`\n\n## Verification Checklist for Next Agent\n"
            "- [x] Implement\n- [X] Document\n- [ ] Test\n"
        )
        parsed = parse_handoff(text)
        self.assertEqual(parsed["metadata"]["Next Agent"], "codex")
        self.assertEqual([i["done"] for i in parsed["checklist"]], [True, True, False])


class BuildCommandTests(unittest.TestCase):
    def test_edit_access_grants_file_writes(self):
        self.assertEqual(AgentClient("agy", "agy").build_command("hi"),
                         ["agy", "--mode", "accept-edits", "--print", "hi"])
        self.assertEqual(AgentClient("claude", "claude").build_command("hi"),
                         ["claude", "--permission-mode", "acceptEdits", "--print", "hi"])
        self.assertEqual(AgentClient("codex", "codex").build_command("hi"),
                         ["codex", "exec", "--sandbox", "workspace-write", "hi"])

    def test_read_access_requests_plan_or_read_only(self):
        self.assertEqual(AgentClient("agy", "agy").build_command("hi", access="read"),
                         ["agy", "--mode", "plan", "--print", "hi"])
        self.assertEqual(AgentClient("claude", "claude").build_command("hi", access="read"),
                         ["claude", "--permission-mode", "plan", "--print", "hi"])
        self.assertEqual(AgentClient("codex", "codex").build_command("hi", access="read")[2:4],
                         ["--sandbox", "read-only"])

    def test_agy_prompt_is_the_last_argument(self):
        # agy's --print consumes the following argument as the prompt, so flags must precede it.
        argv = AgentClient("agy", "agy").build_command("prompt text")
        self.assertEqual(argv[-1], "prompt text")
        self.assertEqual(argv[-2], "--print")

    def test_invalid_access_rejected(self):
        with self.assertRaises(ValueError):
            AgentClient("agy", "agy").build_command("hi", access="root")

    def test_unknown_agent_has_no_command(self):
        self.assertIsNone(AgentClient("other", "other").build_command("hi"))


class ScopeHelperTests(unittest.TestCase):
    def test_within_matches_directories_and_exact_files_only(self):
        allowed = ("docs/tri-agent", "HANDOFF.md")
        self.assertTrue(workflows._within("docs/tri-agent/AUDIT-x.md", allowed))
        self.assertTrue(workflows._within("HANDOFF.md", allowed))
        self.assertFalse(workflows._within("docs/tri-agent-evil/x.md", allowed))
        self.assertFalse(workflows._within("HANDOFF.md.bak", allowed))
        self.assertFalse(workflows._within("src/app.py", allowed))

    def test_out_of_scope_ignores_pre_existing_changes(self):
        before = {"src/app.py": "abc", "docs/tri-agent/x.md": None}
        after = {"src/app.py": "abc", "docs/tri-agent/x.md": "new", "src/other.py": "zzz"}
        self.assertEqual(workflows._out_of_scope(before, after, ("docs/tri-agent",)), ["src/other.py"])


class PlanTests(unittest.TestCase):
    def test_relay_is_three_sequential_stages(self):
        stages = workflows.plan_workflow("relay", "Build auth middleware")
        self.assertEqual([[s.agent for s in st] for st in stages], [["agy"], ["claude"], ["codex"]])
        self.assertIn("docs/tri-agent/SPEC-build-auth-middleware.md", stages[0][0].prompt)
        self.assertEqual(stages[0][0].artifacts, ("docs/tri-agent/SPEC-build-auth-middleware.md",))

    def test_debate_runs_two_proposals_in_parallel_then_codex(self):
        stages = workflows.plan_workflow("debate", "Pick a database")
        self.assertEqual([[s.agent for s in st] for st in stages], [["agy", "claude"], ["codex"]])
        self.assertEqual(len({s.artifacts for s in stages[0]}), 2)

    def test_audit_has_four_stages_and_scoped_auditor(self):
        stages = workflows.plan_workflow("audit", "Harden upload endpoint")
        self.assertEqual([[s.agent for s in st] for st in stages],
                         [["claude"], ["agy"], ["claude"], ["codex"]])
        auditor = stages[1][0]
        self.assertIsNotNone(auditor.writable)
        self.assertNotIn("src", " ".join(auditor.writable))

    def test_feature_overrides_slug(self):
        stages = workflows.plan_workflow("relay", "long prompt text here", feature="uploads")
        self.assertIn("SPEC-uploads.md", stages[0][0].prompt)

    def test_unknown_workflow_rejected(self):
        with self.assertRaises(ValueError):
            workflows.plan_workflow("nope", "x")

    def test_describe_plan_shows_real_commands(self):
        with mock.patch.object(workflows, "get_all_agents", lambda timeout=None: {
            "agy": AgentClient("Google Antigravity", "agy"),
            "claude": AgentClient("Anthropic Claude Code", "claude"),
            "codex": AgentClient("OpenAI Codex", "codex"),
        }):
            joined = "\n".join(workflows.describe_plan(workflows.plan_workflow("relay", "x")))
        self.assertIn("agy --mode accept-edits --print", joined)
        self.assertIn("claude --permission-mode acceptEdits --print", joined)
        self.assertIn("codex exec --sandbox workspace-write", joined)


# ---------------------------------------------------------------------------
# Workflow execution and contract enforcement
# ---------------------------------------------------------------------------

class RunWorkflowTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_relay_success_runs_every_agent_and_writes_logs(self):
        plan = plan_index("relay")
        calls = []
        agents = make_agents("relay", {b: obedient(plan) for b in ("agy", "claude", "codex")}, calls)
        ok, output = run("relay", agents, self.root)
        self.assertTrue(ok, output)
        self.assertEqual(calls, ["agy", "claude", "codex"])
        logs = list((self.root / "tmp/tri-agent/runs").glob("*/*.log"))
        self.assertEqual(len(logs), 3)
        self.assertFalse((self.root / "tmp/tri-agent/run.lock").exists())

    def test_nonzero_exit_stops_pipeline(self):
        calls = []
        agents = make_agents("relay", {}, calls, failing=("agy",))
        ok, output = run("relay", agents, self.root)
        self.assertFalse(ok)
        self.assertEqual(calls, ["agy"])

    def test_missing_artifact_stops_before_next_agent(self):
        plan = plan_index("relay")
        good = obedient(plan)

        def lazy_architect(prompt, root):
            if "Chief Architect" in prompt:
                (root / "HANDOFF.md").write_text(handoff_text("agy", "claude", 1), encoding="utf-8")
                return
            good(prompt, root)

        calls = []
        agents = make_agents("relay", {"agy": lazy_architect}, calls)
        ok, output = run("relay", agents, self.root)
        self.assertFalse(ok)
        self.assertIn("expected artifact missing or empty", output)
        self.assertEqual(calls, ["agy"])

    def test_wrong_successor_in_handoff_is_rejected(self):
        plan = plan_index("relay")
        good = obedient(plan)

        def wrong_next(prompt, root):
            if "Chief Architect" in prompt:
                good(prompt, root)
                (root / "HANDOFF.md").write_text(handoff_text("agy", "codex", 2), encoding="utf-8")
                return
            good(prompt, root)

        calls = []
        agents = make_agents("relay", {"agy": wrong_next}, calls)
        ok, output = run("relay", agents, self.root)
        self.assertFalse(ok)
        self.assertIn("'Next Agent' is 'codex', expected 'claude'", output)
        self.assertEqual(calls, ["agy"])

    def test_stale_handoff_from_previous_run_is_rejected(self):
        plan = plan_index("relay")
        good = obedient(plan)
        # HANDOFF.md already says what this step should write, from some earlier run.
        (self.root / "HANDOFF.md").write_text(handoff_text("agy", "claude", 0), encoding="utf-8")

        def forgetful_architect(prompt, root):
            if "Chief Architect" in prompt:
                step = plan[prompt]
                (root / step.artifacts[0]).parent.mkdir(parents=True, exist_ok=True)
                (root / step.artifacts[0]).write_text("spec\n", encoding="utf-8")
                return
            good(prompt, root)

        calls = []
        agents = make_agents("relay", {"agy": forgetful_architect}, calls)
        ok, output = run("relay", agents, self.root)
        self.assertFalse(ok)
        self.assertIn("was not updated by this step", output)

    def test_debate_success(self):
        plan = plan_index("debate")
        good = obedient(plan)
        calls = []
        agents = make_agents("debate", {b: good for b in ("agy", "claude", "codex")}, calls)
        ok, output = run("debate", agents, self.root)
        self.assertTrue(ok, output)
        self.assertEqual(sorted(calls), ["agy", "claude", "codex"])
        self.assertEqual(calls[-1], "codex")

    def test_dry_run_invokes_nothing_and_writes_nothing(self):
        calls = []
        agents = make_agents("relay", {}, calls)
        ok, output = run("relay", agents, self.root, dry_run=True)
        self.assertTrue(ok)
        self.assertEqual(calls, [])
        self.assertIn("agy --print", output)
        self.assertFalse((self.root / "tmp").exists())

    def test_missing_agent_refuses_to_start(self):
        calls = []
        agents = make_agents("relay", {}, calls)
        agents["codex"].is_available = False
        ok, output = run("relay", agents, self.root)
        self.assertFalse(ok)
        self.assertIn("not found in PATH", output)
        self.assertEqual(calls, [])

    def test_live_lock_blocks_second_run(self):
        lock = self.root / "tmp/tri-agent/run.lock"
        lock.parent.mkdir(parents=True)
        lock.write_text(str(os.getpid()), encoding="ascii")  # this process is alive
        calls = []
        agents = make_agents("relay", {}, calls)
        ok, output = run("relay", agents, self.root)
        self.assertFalse(ok)
        self.assertIn("another tri-agent run is active", output)
        self.assertEqual(calls, [])
        self.assertTrue(lock.exists())  # not ours to delete

    def test_stale_lock_is_taken_over(self):
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        lock = self.root / "tmp/tri-agent/run.lock"
        lock.parent.mkdir(parents=True)
        lock.write_text(str(dead.pid), encoding="ascii")
        plan = plan_index("relay")
        calls = []
        agents = make_agents("relay", {b: obedient(plan) for b in ("agy", "claude", "codex")}, calls)
        ok, output = run("relay", agents, self.root)
        self.assertTrue(ok, output)
        self.assertFalse(lock.exists())

    def test_run_lock_context_releases_on_error(self):
        path = self.root / "lock"
        with self.assertRaises(KeyError):
            with run_lock(path):
                self.assertTrue(path.exists())
                raise KeyError("boom")
        self.assertFalse(path.exists())

    def test_lock_error_type(self):
        path = self.root / "lock"
        path.write_text(str(os.getpid()), encoding="ascii")
        with self.assertRaises(LockError):
            with run_lock(path):
                pass


class AuditScopeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        if not git_init(self.root):
            self.skipTest("git is not installed")

    def tearDown(self):
        self._tmp.cleanup()

    def _builder(self, plan):
        good = obedient(plan)

        def build(prompt, root):
            if "audit workflow" in prompt:
                (root / "src").mkdir(exist_ok=True)
                (root / "src/app.py").write_text("def upload(): pass\n", encoding="utf-8")
            good(prompt, root)
        return build

    def test_auditor_may_write_report_and_handoff(self):
        plan = plan_index("audit")
        good = self._builder(plan)
        calls = []
        agents = make_agents("audit", {b: good for b in ("agy", "claude", "codex")}, calls)
        ok, output = run("audit", agents, self.root)
        self.assertTrue(ok, output)
        self.assertEqual(calls, ["claude", "agy", "claude", "codex"])
        self.assertIn("src/app.py", output)  # the builder's change is visible in the summary

    def test_auditor_editing_source_is_caught_and_stops_run(self):
        plan = plan_index("audit")
        good = self._builder(plan)

        def tampering_auditor(prompt, root):
            if "Adversarial Red-Team" in prompt:
                good(prompt, root)
                (root / "src/app.py").write_text("def upload(): return 'patched by auditor'\n", encoding="utf-8")
                return
            good(prompt, root)

        calls = []
        agents = make_agents("audit", {"claude": good, "agy": tampering_auditor}, calls)
        ok, output = run("audit", agents, self.root)
        self.assertFalse(ok)
        self.assertIn("modified out-of-scope path: src/app.py", output)
        self.assertEqual(calls, ["claude", "agy"])  # remediation and verification never ran


class InstallSkillTests(unittest.TestCase):
    def test_existing_directory_is_backed_up_not_deleted(self):
        with tempfile.TemporaryDirectory() as home:
            existing = Path(home) / ".claude" / "skills" / "tri-agent-orchestrator"
            existing.mkdir(parents=True)
            (existing / "user-notes.txt").write_text("keep me", encoding="utf-8")

            with mock.patch.dict(os.environ, {"HOME": home}):
                installed = install_skills_globally(verbose=False)

            target = Path(installed[1])
            self.assertTrue(target.is_symlink())
            self.assertEqual(target.resolve(), REPO_ROOT.resolve())
            backups = list((Path(home) / ".claude" / "skills").glob("tri-agent-orchestrator.bak-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "user-notes.txt").read_text(encoding="utf-8"), "keep me")


if __name__ == "__main__":
    unittest.main()
