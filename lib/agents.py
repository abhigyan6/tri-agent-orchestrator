"""
Agent CLI detection, version checking, and execution wrapper for Tri-Agent Orchestrator.
Supports Antigravity (agy), Claude Code (claude), and OpenAI Codex (codex).
"""

import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

DEFAULT_TIMEOUT = 600  # seconds per agent invocation


class AgentClient:
    def __init__(self, name: str, binary_name: str, timeout: int = DEFAULT_TIMEOUT):
        self.name = name
        self.binary_name = binary_name
        self.timeout = timeout
        self.path = shutil.which(binary_name)

    @property
    def is_available(self) -> bool:
        return self.path is not None

    def get_version(self) -> str:
        if not self.is_available:
            return "Not Installed"
        try:
            res = subprocess.run(
                [self.binary_name, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            out = (res.stdout or res.stderr).strip().split("\n")[0]
            return out if out else "Unknown"
        except Exception:
            return "Installed"

    def build_command(self, prompt: str, non_interactive: bool = True) -> Optional[List[str]]:
        """Return the argv used to invoke this agent, or None for an unknown agent."""
        if self.binary_name == "agy":
            flag = "--print" if non_interactive else "--prompt-interactive"
            return [self.binary_name, flag, prompt]
        if self.binary_name == "claude":
            if non_interactive:
                return [self.binary_name, "--print", prompt]
            return [self.binary_name, prompt]
        if self.binary_name == "codex":
            if non_interactive:
                return [self.binary_name, "exec", prompt]
            return [self.binary_name, prompt]
        return None

    def run_prompt(
        self,
        prompt: str,
        non_interactive: bool = True,
        cwd: Optional[str] = None,
    ) -> Tuple[int, str]:
        """
        Execute a prompt against the agent CLI.
        Returns (exit_code, output). Output is stdout on success, otherwise stderr (or stdout).
        """
        if not self.is_available:
            return 1, f"Error: Agent CLI '{self.binary_name}' is not installed or not in PATH."

        cmd = self.build_command(prompt, non_interactive)
        if cmd is None:
            return 1, f"Unknown agent: {self.binary_name}"

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=self.timeout,
            )
            output = res.stdout if res.returncode == 0 else (res.stderr or res.stdout)
            return res.returncode, output
        except subprocess.TimeoutExpired:
            return 124, f"Execution timed out after {self.timeout}s for agent '{self.name}'"
        except Exception as e:
            return 1, f"Failed to execute agent '{self.name}': {e}"


def get_all_agents(timeout: int = DEFAULT_TIMEOUT) -> Dict[str, AgentClient]:
    return {
        "agy": AgentClient("Google Antigravity", "agy", timeout),
        "claude": AgentClient("Anthropic Claude Code", "claude", timeout),
        "codex": AgentClient("OpenAI Codex", "codex", timeout),
    }
