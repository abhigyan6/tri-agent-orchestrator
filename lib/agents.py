"""
Agent CLI detection, version checking, and execution wrapper for Tri-Agent Orchestrator.
Supports Antigravity (agy), Claude Code (claude), and OpenAI Codex (codex).
"""

import shutil
import subprocess
from typing import Dict, Optional, Tuple


class AgentClient:
    def __init__(self, name: str, binary_name: str):
        self.name = name
        self.binary_name = binary_name
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
                timeout=5
            )
            out = (res.stdout or res.stderr).strip().split("\n")[0]
            return out if out else "Unknown"
        except Exception:
            return "Installed"

    def run_prompt(
        self,
        prompt: str,
        non_interactive: bool = True,
        cwd: Optional[str] = None
    ) -> Tuple[int, str]:
        """
        Executes a prompt against the agent CLI.
        """
        if not self.is_available:
            return 1, f"Error: Agent CLI '{self.binary_name}' is not installed or not in PATH."

        cmd = []
        if self.binary_name == "agy":
            if non_interactive:
                cmd = [self.binary_name, "--print", prompt]
            else:
                cmd = [self.binary_name, "--prompt-interactive", prompt]
        elif self.binary_name == "claude":
            if non_interactive:
                cmd = [self.binary_name, "--print", prompt]
            else:
                cmd = [self.binary_name, prompt]
        elif self.binary_name == "codex":
            if non_interactive:
                cmd = [self.binary_name, "exec", prompt]
            else:
                cmd = [self.binary_name, prompt]
        else:
            return 1, f"Unknown agent: {self.binary_name}"

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=600
            )
            output = res.stdout if res.returncode == 0 else (res.stderr or res.stdout)
            return res.returncode, output
        except subprocess.TimeoutExpired:
            return 124, f"Execution timed out for agent '{self.name}'"
        except Exception as e:
            return 1, f"Failed to execute agent '{self.name}': {str(e)}"


def get_all_agents() -> Dict[str, AgentClient]:
    return {
        "agy": AgentClient("Google Antigravity", "agy"),
        "claude": AgentClient("Anthropic Claude Code", "claude"),
        "codex": AgentClient("OpenAI Codex", "codex"),
    }
