# Architecture Specification: {{FEATURE_NAME}}

- **Architect:** Google Antigravity (`agy`)
- **Target Builder:** Anthropic Claude Code (`claude`)
- **Target Tester:** OpenAI Codex (`codex`)
- **Status:** Approved for Implementation

---

## 1. System Overview & Problem Statement
Explain why this feature is needed and its high-level objectives.

## 2. Architecture & Data Flow
Include a mermaid diagram of components, data pipelines, and network interactions.

## 3. Public Interfaces & TypeScript Types
```typescript
export interface FeatureConfig {
  id: string;
  enabled: boolean;
}
```

## 4. Implementation Directives for Claude Code
- File paths:
- Patterns and error boundaries:
- Security practices:

## 5. Test Directives for OpenAI Codex
- Positive test cases:
- Negative & boundary test cases:
- Load or concurrency scenarios:
