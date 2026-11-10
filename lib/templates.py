"""
Markdown and Contract Templates for Tri-Agent Orchestration.
"""

from datetime import datetime

HANDOFF_TEMPLATE = """# Tri-Agent Handoff Contract

## Metadata
- **Workflow ID:** {workflow_id}
- **Active Feature:** {feature_name}
- **Current Phase:** {current_phase}
- **Completed By:** {completed_by}
- **Next Agent:** {next_agent}
- **Timestamp:** {timestamp}

## What Was Done
{summary_done}

## Key Files & Artifacts
{artifacts}

## Critical Constraints & Architectural Guidelines
{constraints}

## Verification Checklist for Next Agent
{checklist}
"""

SPEC_TEMPLATE = """# Architecture Specification: {feature_name}

**Author (Architect):** Google Antigravity (`agy`)
**Date:** {date}
**Status:** Ready for Implementation

---

## 1. Executive Summary & Goals
{summary}

## 2. Architecture & Component Diagram
```mermaid
flowchart TD
    Client --> API_Gateway
    API_Gateway --> Service
    Service --> Storage
```

## 3. Data Models & Interface Contracts
- API Routes / Types:
- Invariants & Constraints:

## 4. Implementation Directives for Claude Code (`claude`)
- File locations:
- Idiomatic patterns to follow:
- Error handling policies:

## 5. Reliability & Test Directives for OpenAI Codex (`codex`)
- Edge cases to cover:
- Test frameworks to use:
- Verification commands:
"""

AUDIT_TEMPLATE = """# Adversarial Security & Quality Audit: {feature_name}

**Auditor:** Google Antigravity (`agy`)
**Date:** {date}
**Target Implementation:** {target_files}

---

## Findings Matrix
| ID | Severity | File & Location | Vulnerability / Issue | Recommended Fix |
| :--- | :--- | :--- | :--- | :--- |
| SEC-01 | High | ... | ... | ... |

## Attack Vectors Evaluated
- [ ] Authentication & Authorization Bypass
- [ ] Injection & Unsanitized Input
- [ ] Concurrency & Race Conditions
- [ ] Resource Exhaustion & Denial of Service

## Action Items for Claude Code
- [ ] Patch SEC-01
- [ ] Patch SEC-02
"""
