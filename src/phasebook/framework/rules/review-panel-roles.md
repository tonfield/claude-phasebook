## Reviewer Panel Roles

3-5 roles per review, selected by artifact type and content.

### Role Catalog

| Role | Focus | When to Include |
|------|-------|-----------------|
| **Plan Compliance** | Output matches spec? Signatures, scope, completeness. | Always (execute) |
| **Logical Consistency** | Contradictions, circular reasoning, edge cases, races. | Always |
| **Completeness** | Missing paths, unhandled errors, gaps, missing alternatives. | Always |
| **Codebase Verification** | Read every file referenced in the artifact. Verify every claimed function signature, return type, attribute name, and hook point against actual source. Flag "new work disguised as hook insertion" — where the artifact says "hook into existing X" but X doesn't exist or works differently. | Always (design, plan) |
| **Domain Accuracy** | Domain knowledge correct? Spawns named specialists. | Domain-specific content |
| **Risk & Assumptions** | Unstated assumptions, fragile deps, failure modes, security. Performance: quantify resource cost (background tasks, threads, event loop time, memory). External services: for every runtime dependency on a third-party service, verify startup behavior when unreachable, degradation mode, rate/quota limits, and disable path. | MEDIUM+ risk |
| **Verification Coverage** | Test coverage, assertion quality, evidence, reproducibility. | Tests or evidence produced |
| **Testability** | Is the design testable? Identify what needs mocking (external APIs, timers, background tasks). Flag components that are hard to isolate. Verify the artifact addresses test strategy for non-trivial behavior (rate limiting, quiet hours, timeouts, fire-and-forget patterns). | Design / Plan |
| **Integration Impact** | Cross-module deps, upstream/downstream effects. | Shared interface changes |

### Domain Specialists

Spawned by Domain Accuracy based on content.
See reference-data.md for the lookup table.
Create others as needed.

### Rules

1. Minimum 3, maximum 5 roles.
2. Always: Logical Consistency + Completeness.
3. Design / Plan: + Codebase Verification (mandatory — reads actual source).
4. Design / Plan: + Testability (mandatory). When at cap (5) with Domain Accuracy, domain accuracy wins for domain-heavy artifacts, testability wins otherwise.
5. Execute: + Plan Compliance.
6. Specialized knowledge: + Domain Accuracy.
7. MEDIUM+: + Risk & Assumptions.
8. Shared interfaces: + Integration Impact.
9. Tests/evidence: + Verification Coverage.
