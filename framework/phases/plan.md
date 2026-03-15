# Plan Phase

## Setup
- Read CLAUDE.md.
- Find task file by slug across `phasebook/tasks/{inbox,queue,progress,completed}/`.
- Load `phasebook/designs/*-<slug>.md` if exists — authoritative context.
- If not found, use task file and any research artifact.
- Map codebase to understand where changes land.
- Load existing artifact (`phasebook/plans/*-<slug>.md`) if present:
  - Has `>>` markers → **revise mode**: address feedback, preserve structure.
    Update status line to `REOPENED for >> feedback`.
  - No `>>` → **fresh mode**: existing = reference only

## Gate
None — plan can proceed from task file alone (design is optional context).

## Principles
- Step 0 = foundation (thinnest verifiable slice).
- Each step <= 1.5k lines.
- Each step independently verifiable with defined criteria.
- Plan is alive: updated after every execute cycle.

## Process
1. **Optimize prompt** per `prompt-optimization.md` plan framing.
2. **Load context**: approved design, codebase mapping.
3. **Step 0**: minimal slice proving the approach, with verification.
4. **Decompose**: per step define context, scope, changes, risk level
   (LOW/MEDIUM/HIGH), verification criteria, DoD, TODOCLAUDE.
5. **Draft** to `phasebook/plans/<date>-<HHMM>-<slug>.md`.
   Track scope claims, caller/consumer assumptions per `obligation-ledger.md`.
6. **Compact**: `/compact` after writing plan.
7. **Check >> markers** per `human-feedback.md`.
8. **Review** per `review-cycle.md`.
9. **Finalize**: remove `[!QA]` blocks, mark all STATUS: PLANNED, set status line,
   commit: `plan(<task>): approved plan with N steps`

## Verification Criteria
Every step defines explicit verification:
- Code steps: unit tests, full suite passes, type/lint checks.
- Non-code steps: consistency checks, cross-references, completeness.

## Review
- Default risk: MEDIUM. Mode: `review`.
- Fix cycle: revise plan, add `[!DELTA]` block.

## Rules
- No implementation — only planning.
- Split if > 1.5k lines.
- Recurring findings → Opus decides.
