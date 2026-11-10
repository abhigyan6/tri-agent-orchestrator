# Workflow 03: Adversarial Red-Team Audit

Use this workflow for security-critical logic, financial calculations, encryption routines, and authorization middlewares.

```mermaid
flowchart LR
    Dev[Claude Code: Build Initial Implementation] --> Audit[Antigravity: Adversarial Red-Team Audit]
    Audit -->|Attack vectors & failed tests| Fix[Claude Code: Patch Vulnerabilities]
    Fix --> Verify[OpenAI Codex: Regression Testing & CI Validation]
    Verify --> Release[Safe Production Merge]
```

## Security Audit Checklist (Antigravity Role)
- [ ] Authentication & Session tampering (JWT replay, algorithmic confusion).
- [ ] Authorization & IDOR (accessing resources without tenant ownership check).
- [ ] Injection attacks (SQL, NoSQL, Command, Template, Header injection).
- [ ] Denial of Service & Resource exhaustion (unbounded loop, uncompressed payload, memory leaks).
- [ ] Sensitive Data Exposure (API keys in logs, stack traces in production errors).
