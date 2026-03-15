## Standard Review Cycle

**Hard gate:** A phase is NOT complete until the review cycle reaches
the Completion section below. The mandatory sequence is:
Pass 1 -> Pass 2 -> Challenge Gate (if applicable) -> Completion.
Skipping passes is never valid. A fix cycle after Pass 1 does not
constitute completion — Pass 2 must still run on the revised artifact.

Review depth determined by risk level. Default: MEDIUM.

### Risk Level Classification

| | LOW | MEDIUM | HIGH |
|---|---|---|---|
| **Research** | Single fact, 1-2 sources | Multi-source, competing approaches. **Default** | Novel strategy, risk model changes, foundational |
| **Design** | Config, docs, single module | Multi-module, new interfaces, integration claims. **Default** | Money path, broker API, shared state, invariant-adjacent |
| **Plan** | Few steps, single module | Multi-module, step dependencies, risk sequencing. **Default** | Money path steps, broker integration, invariant-adjacent |
| **Execute** | Single-module, clear spec, no shared state | Multi-module, new interfaces, test-covered. **Default** | Money path, broker API, shared state mutations, invariant-adjacent |

### Risk-Based Review Depth

| | LOW | MEDIUM | HIGH |
|---|---|---|---|
| **Research** | External (LOW), Pass 2 | External (MEDIUM) + internal, Pass 2 | External (HIGH) + internal, Pass 2 + external challenge |
| **Design** | External (LOW) + codebase verification, Pass 2 | External (MEDIUM) + internal (parallel), Pass 2 | External (HIGH) + internal (parallel), Pass 2 + external challenge |
| **Plan** | External (LOW) + codebase verification, Pass 2 | External (MEDIUM) + internal (parallel), Pass 2 | External (HIGH) + internal (parallel), Pass 2 + external challenge |
| **Execute** | External (LOW), Pass 2 | External (MEDIUM) + internal (parallel), Pass 2 | External (HIGH) + internal (parallel), Pass 2 + external challenge |

The risk level in parentheses is passed to `--risk`. Script selects
models from roster automatically. Use `--mode review` for non-code,
`--mode code` for execute phase.

### Cyclical Restart

After Pass 2, if ANY pass had fixes during this cycle -> restart
from Pass 1. Continues until a full cycle has zero fixes.
**Maximum 3 cyclical restarts per phase.** If the 3rd restart still
produces fixes, halt and move task to review/ for human intervention.

Example (MEDIUM):
- Pass 1 fixes -> Pass 2 clean
- Pass 1 had fixes -> restart -> all clean -> done

Example (LOW):
- Pass 1 fixes -> Pass 2 clean
- Pass 1 had fixes -> restart -> all clean -> done

### Pre-Review: Freshness & Context Check

Before starting Pass 1 (Design / Plan / Execute phases):

1. **Freshness check:** `git log --since=<artifact creation date>` on
   CLAUDE.md, referenced source files, and related modules. If any
   changed — read the diffs and flag as review context. Concurrent
   tasks may have added invariants, changed interfaces, or updated
   conventions that invalidate assumptions in the artifact.
2. **In-flight task scan:** Check `phasebook/tasks/progress/` and
   recent `completed/` for tasks touching the same modules or subsystems.
   Cross-reference their artifacts for conflicts or dependencies.

### Pre-Assembled Interface Context (Design / Plan phases)

When artifact claims integration with existing code:
1. Scan artifact for integration claims (function names, classes, hook points)
2. Read each referenced source file once
3. Build context bundle (signatures, `__init__`, methods, attributes with ~5-10 lines surrounding context)
4. Pass to: External reviewers, Internal reviewers (Codebase Verification), Pass 2 Interface Verification

When no integration claims: skip.
On fix cycle introducing NEW integration claims: extend the bundle before restart.

### Pass 1: Reviewers

MEDIUM/HIGH: Launch External + Internal in parallel.
LOW: External only (no internal panel). Design/Plan LOW:
also run Codebase Verification role solo (not full internal panel).

**External:** `.claude/scripts/external_review.py` per `/review` skill.
Pass `--risk` and `--mode` (review or code). Never delegate to Task
subagents. Include pre-assembled interface context via `--files`.

**Internal:** Generate panel per review-panel-roles.md, spawn specialists.
Pass pre-assembled interface context to Codebase Verification role.

Collect ALL findings into one pool.
Single synthesis: BLOCKING / ADVISORY. Flag cross-reviewer disagreements
(external vs internal). Cross-reference against prior artifacts and CLAUDE.md.
Accepted findings -> **single fix cycle** -> Pass 2.

### Pass 2: Validation (Gaps & Self-Review)

1. Run review-gaps agent (reads all Pass 1 findings — External + Internal combined).
2. Self-review: correctness, completeness, domain risks.
3. **Interface verification (Design / Plan phases):** Use pre-assembled
   interface context. Only re-read source for claims added during fix
   cycles. Verify: function exists, signature matches, return type
   matches, attributes exist on the class, hook point works as described.
   Codebase Verification findings from Pass 1 are inputs, but Pass 2
   must independently re-check any integration claim not already verified.
4. **Invariant sweep (Design / Plan phases):** Walk every Invariant and
   Design Constraint in CLAUDE.md. For each one, confirm the artifact
   does not violate it. Not "scan for relevant ones" — check the full
   list. Flag any tension, even if the artifact doesn't directly violate
   but introduces patterns that could lead to violation.
5. **Documentation consistency (Design / Plan phases):** Check the
   artifact against `docs/ARCHITECTURE.md` for contradictions. Note
   which doc files will need updating after execution. Record these in
   the review synthesis as a **Doc Update** list — not blocking, but
   tracked for the Learn phase.
6. **External service resilience (when artifact adds external
   dependencies):** For each new runtime dependency — verify: (a) engine
   starts cleanly when service is unreachable, (b) failure is
   fire-and-forget or gracefully degraded, (c) free tier / rate limits
   documented, (d) kill switch exists to disable without code change.
7. **Contract verification:** Walk the task file's Requirements and
   Anti-goals. Confirm the phase output satisfies each requirement.
   Flag any deferred criteria. Flag any anti-goal violations.
8. **Obligation ledger:** Walk all entries per `obligation-ledger.md`.
   Verify VERIFIED entries, resolve UNVERIFIED, check phase budget.
9. Produce findings table.
10. Accepted findings -> **fix cycle** -> check cyclical restart.

### Challenge Gate

Triggers: (1) both passes return 0 blocking, or (2) HIGH risk always.
Run `.claude/scripts/external_review.py <artifact> --mode challenge`.
Blocking findings -> treat as Pass 2 (fix -> restart check).

### Fix Cycle

| Phase | Fix Cycle |
|-------|-----------|
| Research / Design / Plan | Revise document |
| Execute | Subagent: implement fixes -> tests -> verify all green |

Must complete fully before continuing.
**Artifact checkpoint:** Write the revised artifact to disk after every fix cycle.
**Obligations:** Fixes create FIX_IMPACT obligations per `obligation-ledger.md`.
**Human feedback:** Handle `>>` markers, `[!DELTA]`, `[!ACTION]` per `human-feedback.md`.

### Completion

When both passes are clean and no cyclical restart:
1. Run micro-learn
2. Write review synthesis to review file
3. Include **Doc Update** list from Pass 2 in the review synthesis
   (carried forward to Learn phase for execution)
4. Add `[!ACTION]` block if human input needed
5. Present results
6. **Commit gating per `strip-semantics.md`:** `-` positions wait for
   human approval before committing. `+` positions commit automatically
   after review passes clean. Both receive the same review cycle.

### Micro-Learn

After each review round, scan accepted findings for persistable insights:
- Reusable pattern -> append to CLAUDE.md Known Patterns
- Pitfall -> append to CLAUDE.md Known Gotchas
- Only accepted AND fixed AND generalizable. 1-2 lines max.

### Review File Location

`phasebook/reviews/<date>-<HHMM>-<topic-slug>[-step<N>]-r<R>.md` — run `date +%Y-%m-%d-%H%M` for the prefix.

One file per round. `-step<N>` only for execute phase.

---

Output format: per `/review` skill synthesis format (Step 3 in `.claude/skills/review/SKILL.md`).
