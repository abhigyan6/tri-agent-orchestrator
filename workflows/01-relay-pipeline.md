# Workflow 01: The Relay Pipeline (Research → Build → Verify)

The **Relay Pipeline** is the standard end-to-end production workflow. Each agent handles the phase matching its greatest architectural and engineering strengths.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant AGY as Google Antigravity (Architect)
    participant CLAUDE as Claude Code (Builder)
    participant CODEX as OpenAI Codex (Tester & Ops)

    User->>AGY: Feature prompt & requirements
    Note over AGY: Phase 1: Reconnaissance & Architecture
    AGY->>AGY: Explore codebase & dependencies
    AGY->>AGY: Write docs/tri-agent/SPEC.md
    AGY->>CLAUDE: Produce HANDOFF.md (next: claude)

    Note over CLAUDE: Phase 2: Domain Implementation
    CLAUDE->>CLAUDE: Ingest SPEC.md & existing codebase
    CLAUDE->>CLAUDE: Implement modules & clean abstractions
    CLAUDE->>CODEX: Update HANDOFF.md (next: codex)

    Note over CODEX: Phase 3: Reliability & Verification
    CODEX->>CODEX: Generate comprehensive test suite
    CODEX->>CODEX: Execute tests, linters, typechecks
    CODEX->>CODEX: Fix edge-case failures & build PR
    CODEX-->>User: Complete verified PR ready for merge
```

---

## Phase Details

### Phase 1: Research, Architecture & Specification
- **Agent:** Google Antigravity (`agy`)
- **Key Actions:**
  - Map existing project architecture and identify affected modules.
  - Review best practices, security standards, and API boundaries.
  - Formulate the design document into `docs/tri-agent/SPEC.md`.
  - Initialize `HANDOFF.md` with strict invariants, type interfaces, and success criteria.

### Phase 2: Production Craftsmanship & Implementation
- **Agent:** Anthropic Claude Code (`claude`)
- **Key Actions:**
  - Read `docs/tri-agent/SPEC.md` and `HANDOFF.md`.
  - Implement idiomatic, clean, readable code with zero premature optimization.
  - Structure modules for high maintainability.
  - Update `HANDOFF.md` logging all created and modified source files.

### Phase 3: Test Suite Generation, Verification & Deployment
- **Agent:** OpenAI Codex (`codex`)
- **Key Actions:**
  - Read `HANDOFF.md` and examine new code.
  - Generate unit tests, integration tests, and edge-case mocks.
  - Execute test commands (`npm test`, `pytest`, `cargo test`, etc.).
  - Fix any syntax errors or test regressions.
  - Prepare git commit and GitHub PR summary.
