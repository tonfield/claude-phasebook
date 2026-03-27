---
description: Enforces phased workflow
---

## Workflow Protocol

### Phases

| Phase | Purpose | Instructions | Artifact |
|-------|---------|-------------|----------|
| Research | Investigate, gather evidence | `.claude/phases/research.md` | `phasebook/research/<date>-<slug>.md` |
| Design | Architecture, alternatives, decisions | `.claude/phases/design.md` | `phasebook/designs/<date>-<slug>.md` |
| Plan | Step-by-step implementation plan | `.claude/phases/plan.md` | `phasebook/plans/<date>-<slug>.md` |
| Execute | Implement code per plan steps | `.claude/phases/execute.md` | Code changes + `phasebook/executions/` |
| Learn | Update system knowledge, docs | `.claude/phases/learn.md` | `phasebook/learnings/<date>-<slug>.md` |

Each phase reads its instructions from `.claude/phases/<phase>.md`.

### Flow

```
Research -> Design -> Plan -> Execute -> Learn
```

- Scale by adjusting depth, not removing phases.
- Previous phase artifacts loaded as context when available, not required.
- Exception: Execute requires a plan with PLANNED steps (hard gate).
- Research, Design, Plan can run in parallel across sessions. Execute is sequential.

### Task Strip

User controls which phases run via the 4-position strip in the task filename
(see `queue-protocol.md` for filename format, `strip-semantics.md` for
`+`/`-` behavior):

| Position | Phase | `-` = pause for review | `+` = auto-advance | Done |
|----------|-------|----------------------|--------------------|------|
| 0 | Research | `-` | `+` | `R` |
| 1 | Design | `-` | `+` | `D` |
| 2 | Plan | `-` | `+` | `P` |
| 3 | Execute | `-` | `+` | `E` |

### Per-Phase Steps

Each phase follows this general pattern (details in phase file):

1. **Optimize prompt** per `prompt-optimization.md`
2. **Load context** from previous phase artifacts
3. **Draft** the artifact, tracking obligations per `obligation-ledger.md`
4. **Check >> markers** per `human-feedback.md`
5. **Review cycle** per `review-cycle.md`
6. **Commit** per `git-integration.md`

Large phases may be decomposed per `task-decomposition.md` (fan-out/fan-in).

### Contract Check

Before declaring any phase complete (before review cycle):

1. Re-read the task file's Requirements and Anti-goals sections.
2. Walk each requirement — met with evidence, or explicitly deferred with reason.
3. Walk each anti-goal — any violated.
4. If the phase shifted the objective, update Enriched Context with:
   `INTENT DRIFT: <original> -> <new>. Reason: <why>`
5. Fix gaps before entering review.
