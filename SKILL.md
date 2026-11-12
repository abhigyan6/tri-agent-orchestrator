---
name: tri-agent-orchestrator
description: Coordinate complex engineering workflows across Google Antigravity (agy), Anthropic Claude Code (claude), and OpenAI Codex (codex). Orchestrates specialized research, architecture, implementation, adversarial auditing, testing, and deployment pipelines using standardized inter-agent handoffs.
---

# Tri-Agent Orchestrator: Antigravity × Claude Code × Codex

The **Tri-Agent Orchestrator** skill enables seamless coordination across the three industry-leading coding agent CLIs:
1. **Google Antigravity (`agy`)** – Architecture, multimodal analysis, deep research, and adversarial auditing.
2. **Anthropic Claude Code (`claude`)** – Domain modeling, high-taste implementation, nuanced refactoring, and clean diffs.
3. **OpenAI Codex (`codex`)** – Rapid scaffolding, test suite generation, terminal task execution, and deployment verification.

When this skill is active, any participating agent acts according to its core specializations and produces standardized handoff contracts (`HANDOFF.md`) so the next agent can immediately resume with zero loss of context.

---

## 1. Agent Specialization Matrix

| Agent | Primary Role | Core Strengths | Best Assigned Tasks |
| :--- | :--- | :--- | :--- |
| **Antigravity (`agy`)** | **Chief Architect & Auditor** | Multimodal/visual reasoning, broad codebase mapping, security review, complex system design | • Architectural specifications<br>• API design & RFC generation<br>• Adversarial edge-case discovery<br>• Multimodal UI/UX visual validation |
| **Claude Code (`claude`)** | **Lead Software Craftsman** | Contextual subtlety, clean idiomatic code, complex refactoring, high architectural taste | • Domain logic & core algorithms<br>• Clean component & API implementation<br>• Technical debt refactoring<br>• PR summary & documentation |
| **OpenAI Codex (`codex`)** | **Reliability & Execution Engineer** | Fast execution, test generation, bash/terminal automation, build & deploy pipelines | • Unit, integration, & e2e test harnesses<br>• Scaffolding boilerplate<br>• Git operations, CI/CD, Dockerfiles<br>• Build & lint verification |

---

## 2. Core Workflow Protocols

### Protocol A: The Relay Pipeline (Default)
Ideal for end-to-end features requiring deep planning, high-quality code, and exhaustive testing.

```
[Phase 1: Research & Spec] ────► [Phase 2: Core Build] ────► [Phase 3: Test & Deploy]
       Antigravity                       Claude Code                    Codex
   Outputs: SPEC.md                 Outputs: Source Code           Outputs: Test Suite &
      & HANDOFF.md                     & HANDOFF.md                   Deployment PR
```

1. **Step 1 (Antigravity)**: Research requirements, explore relevant repository files, evaluate trade-offs, and draft `docs/tri-agent/SPEC-<feature>.md`. Write a summary handoff in `HANDOFF.md`.
2. **Step 2 (Claude Code)**: Ingest `SPEC-<feature>.md` and `HANDOFF.md`. Implement production code cleanly, adhering strictly to the architectural constraints. Update `HANDOFF.md`.
3. **Step 3 (Codex)**: Ingest updated source files and `HANDOFF.md`. Generate comprehensive tests (unit, edge-case, integration), execute linting/test runners, fix any regressions, and stage the commit/PR.

---

### Protocol B: Architecture Debate & Consensus
Ideal for high-stakes technical decisions (database selection, state management, migration strategies).

1. **Antigravity** drafts Proposal A focusing on scalability, security, and ecosystem compatibility.
2. **Claude Code** drafts Proposal B focusing on developer ergonomic simplicity, maintainability, and clean abstractions.
3. **Codex** benchmarks or simulates both approaches via test scripts and generates a trade-off scorecard.
4. The winning consensus is logged into an Architecture Decision Record (`docs/adr/ADR-xxx.md`).

---

### Protocol C: Adversarial Red-Team Audit
Ideal for security-critical logic (authentication, payment processing, file uploads, permissions).

1. **Claude Code or Codex** writes the initial implementation.
2. **Antigravity** acts as the Adversarial Red-Team:
   - Inspects attack vectors (IDOR, race conditions, path traversal, injection, unhandled promise rejections).
   - Generates reproduction steps or failing test specs.
3. **Claude Code** fixes the vulnerabilities.
4. **Codex** verifies all security regression tests pass.

---

## 3. Standard Inter-Agent Handoff Contract (`HANDOFF.md`)

Whenever an agent finishes its phase in a multi-agent workflow, it must write or update `HANDOFF.md` in the workspace root with this exact schema. The `tri-agent run` pipeline checks `Completed By` and `Next Agent` after each phase and stops if they are wrong or unchanged, so a handoff that names the wrong successor halts the run:

```markdown
# Tri-Agent Handoff Contract

## Metadata
- **Workflow ID:** `<unique-task-id>`
- **Active Feature:** `<feature-name>`
- **Current Phase:** `[Phase 1: Spec | Phase 2: Build | Phase 3: Verify]`
- **Completed By:** `<agy | claude | codex>`
- **Next Agent:** `<agy | claude | codex>`
- **Timestamp:** `<ISO-8601>`

## What Was Done
- Brief bullet points of files created, modified, or researched.

## Key Files & Artifacts
- Specification: `path/to/spec.md`
- Source Files: `path/to/code.ts`
- Tests: `path/to/test.ts`

## Critical Constraints & Decisions
- Specific requirements or patterns the next agent must strictly preserve.

## Verification Checklist for Next Agent
- [ ] Task 1
- [ ] Task 2
- [ ] Run test command: `<command>`
```

---

## 4. CLI Helper Integration

When executing from terminal or scripts, use the bundled `tri-agent` CLI tool:

```bash
# Verify all agents are installed and healthy
tri-agent doctor

# Run an automated workflow: relay (default), debate, or audit
tri-agent run --workflow relay --prompt "Build modern auth middleware with JWT rotation"
tri-agent run --workflow debate --prompt "Choose a session store for the cart"
tri-agent run --workflow audit --feature uploads --prompt "Harden the file upload endpoint"

# Preview the exact commands without invoking any agent
tri-agent run --workflow relay --prompt "Build file upload component" --dry-run

# Generate a handoff document
tri-agent handoff create --completed agy --next claude --feature "auth-middleware"

# Summarize the current workspace handoff state (add --raw for the full file)
tri-agent handoff status
```

---

## 5. Agent Instructions When This Skill Is Triggered

When a user prompts you with a tri-agent task:
1. **Identify your current persona** (`agy`, `claude`, or `codex`).
2. **Check for existing `HANDOFF.md`** in the repository root:
   - If `HANDOFF.md` exists and you are the `Next Agent`, resume execution according to the checklist.
   - If no `HANDOFF.md` exists, you are the initiating agent. Begin Phase 1.
3. **Execute your scoped role** without overstepping into future phases unless explicitly instructed.
4. **Update `HANDOFF.md`** before concluding your turn and state clearly to the user what command to run next (e.g., `claude "Continue tri-agent workflow for auth middleware"` or `codex exec "..."`).
