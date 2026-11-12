"""
Unit tests for Tri-Agent Orchestrator. Standard library only.

Run from the repository root:
    python3 -m unittest discover -s tests -v
"""

import os
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
    create_handoff_contract,
    install_skills_globally,
    parse_handoff,
    slugify,
)
from lib.templates import render_template  # noqa: E402


class FakeAgent:
    """Stands in for AgentClient: records prompts and returns a canned exit code."""

    def __init__(self, binary: str, calls: list, code: int = 0):
        self.binary_name = binary
        self.name = binary
        self.is_available = True
        self._calls = calls
        self._code = code

    def build_command(self, prompt, non_interactive=True):
        return [self.binary_name, "--print", prompt]

    def run_prompt(self, prompt, non_interactive=True, cwd=None):
        self._calls.append((self.binary_name, prompt))
        return (self._code, "agent exploded" if self._code else "ok")


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
    def test_non_interactive_commands(self):
        cases = {
            "agy": ["agy", "--print", "hi"],
            "claude": ["claude", "--print", "hi"],
            "codex": ["codex", "exec", "hi"],
        }
        for binary, expected in cases.items():
            client = AgentClient(binary, binary)
            self.assertEqual(client.build_command("hi", non_interactive=True), expected)

    def test_unknown_agent_has_no_command(self):
        self.assertIsNone(AgentClient("other", "other").build_command("hi"))


class PlanTests(unittest.TestCase):
    def test_relay_is_three_sequential_stages(self):
        stages = workflows.plan_workflow("relay", "Build auth middleware")
        self.assertEqual([[s.agent for s in st] for st in stages], [["agy"], ["claude"], ["codex"]])
        self.assertIn("docs/tri-agent/SPEC-build-auth-middleware.md", stages[0][0].prompt)

    def test_debate_runs_two_proposals_in_parallel_then_codex(self):
        stages = workflows.plan_workflow("debate", "Pick a database")
        self.assertEqual([[s.agent for s in st] for st in stages], [["agy", "claude"], ["codex"]])
        proposal_paths = {s.prompt for s in stages[0]}
        self.assertEqual(len(proposal_paths), 2)

    def test_audit_has_four_stages(self):
        stages = workflows.plan_workflow("audit", "Harden upload endpoint")
        self.assertEqual([[s.agent for s in st] for st in stages],
                         [["claude"], ["agy"], ["claude"], ["codex"]])

    def test_feature_overrides_slug(self):
        stages = workflows.plan_workflow("relay", "long prompt text here", feature="uploads")
        self.assertIn("SPEC-uploads.md", stages[0][0].prompt)

    def test_unknown_workflow_rejected(self):
        with self.assertRaises(ValueError):
            workflows.plan_workflow("nope", "x")

    def test_describe_plan_shows_real_commands(self):
        lines = workflows.describe_plan(workflows.plan_workflow("relay", "x"))
        joined = "\n".join(lines)
        self.assertIn("agy --print", joined)
        self.assertIn("claude --print", joined)
        self.assertIn("codex exec", joined)


class RunWorkflowTests(unittest.TestCase):
    def _run(self, workflow, fail_binary=None):
        calls = []
        agents = {
            name: FakeAgent(name, calls, code=1 if name == fail_binary else 0)
            for name in ("agy", "claude", "codex")
        }
        with mock.patch.object(workflows, "get_all_agents", lambda timeout=None: agents):
            ok = workflows.run_workflow(workflow, "task", out=lambda _msg: None)
        return ok, [name for name, _ in calls]

    def test_relay_success_runs_every_agent_in_order(self):
        ok, order = self._run("relay")
        self.assertTrue(ok)
        self.assertEqual(order, ["agy", "claude", "codex"])

    def test_relay_stops_after_failing_stage(self):
        ok, order = self._run("relay", fail_binary="agy")
        self.assertFalse(ok)
        self.assertEqual(order, ["agy"])

    def test_audit_stops_before_verification_when_patch_fails(self):
        ok, order = self._run("audit", fail_binary="claude")
        self.assertFalse(ok)
        self.assertEqual(order, ["claude"])

    def test_dry_run_invokes_nothing(self):
        calls = []
        agents = {name: FakeAgent(name, calls) for name in ("agy", "claude", "codex")}
        lines = []
        with mock.patch.object(workflows, "get_all_agents", lambda timeout=None: agents):
            ok = workflows.run_workflow("relay", "task", dry_run=True, out=lines.append)
        self.assertTrue(ok)
        self.assertEqual(calls, [])
        self.assertTrue(any("agy --print" in line for line in lines))

    def test_missing_agent_refuses_to_start(self):
        calls = []
        agents = {name: FakeAgent(name, calls) for name in ("agy", "claude", "codex")}
        agents["codex"].is_available = False
        agents["codex"].binary_name = "codex"
        with mock.patch.object(workflows, "get_all_agents", lambda timeout=None: agents):
            ok = workflows.run_workflow("relay", "task", out=lambda _m: None)
        self.assertFalse(ok)
        self.assertEqual(calls, [])


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
