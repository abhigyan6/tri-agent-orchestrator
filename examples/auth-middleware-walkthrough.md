# Walkthrough: Modern Auth Middleware Pipeline

This end-to-end walkthrough demonstrates how the tri-agent workflow executes the prompt:
> *"Run the tri-agent workflow to research and build a modern auth middleware for my app."*

---

## Step 1: Antigravity Architect Phase
Run in terminal or prompt Antigravity:
```bash
agy -p "Act as Chief Architect in tri-agent workflow. Research and draft the architecture for a modern JWT authentication middleware with refresh token rotation and CSRF protection. Save spec to docs/tri-agent/SPEC-auth.md and create HANDOFF.md for Claude Code."
```

**What Antigravity produces:**
1. `docs/tri-agent/SPEC-auth.md` detailing:
   - Access token (15m expiry, RS256) + Refresh token (7d, database-backed rotation).
   - In-memory blacklisting cache and revoked token handling.
   - HTTP-only Secure SameSite=Strict cookies.
2. `HANDOFF.md` setting `Next Agent: claude`.

---

## Step 2: Claude Code Builder Phase
Run in terminal or prompt Claude Code:
```bash
claude "Read docs/tri-agent/SPEC-auth.md and HANDOFF.md. Implement the auth middleware in src/middleware/auth.ts with clean TypeScript types and zero external bloat. Update HANDOFF.md when done."
```

**What Claude Code produces:**
1. `src/middleware/auth.ts` containing the clean middleware logic.
2. `src/types/auth.ts` containing the UserTokenPayload and AuthRequest interfaces.
3. Updated `HANDOFF.md` setting `Next Agent: codex`.

---

## Step 3: OpenAI Codex Testing & Ops Phase
Run in terminal or prompt Codex:
```bash
codex exec "Read HANDOFF.md and src/middleware/auth.ts. Write complete Vitest/Jest unit tests in tests/auth.test.ts covering expired tokens, missing headers, signature tampering, and valid claims. Run tests and verify."
```

**What Codex produces:**
1. `tests/auth.test.ts` covering full edge-case matrix.
2. Runs the test suite via bash execution.
3. Stages the git commit or opens a GitHub PR.
