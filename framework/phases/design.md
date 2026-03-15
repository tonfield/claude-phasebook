# Design Phase

## Setup
- Read CLAUDE.md.
- Find task file by slug across `phasebook/tasks/{inbox,queue,progress,completed}/`.
- Load `phasebook/research/*-<slug>.md` if exists — authoritative context.
- Load existing artifact (`phasebook/designs/*-<slug>.md`) if present:
  - Has `>>` markers → **revise mode**: address feedback, preserve structure.
    Update status line to `REOPENED for >> feedback`.
  - No `>>` → **fresh mode**: existing = reference only

## Gate
None — design can proceed from task file alone (research is optional context).

## Principles
- Interrogate before designing.
- Visualize with Mermaid diagrams.
- 2-3 alternatives for key decisions.
- Every decision traces to evidence (research, requirements, or domain knowledge).
- Verify early: write `scripts/verify_*.py` for external assumptions.

## Process
1. **Optimize prompt** per `prompt-optimization.md` design framing.
2. **Load context**: approved research, existing designs.
3. **Interrogate**: scale, security, failure modes, integration.
   Verify external assumptions via WebSearch/WebFetch or verification scripts.
4. **Explore 2-3 alternatives** with trade-offs.
5. **Consensus** on contested decisions: run `.claude/scripts/external_review.py`
   with `--mode challenge` for adversarial, `--mode review` for supportive.
   Skip if best approach is clear.
6. **Draft** to `phasebook/designs/<date>-<HHMM>-<slug>.md`.
   Track claims, integration assumptions per `obligation-ledger.md`.
7. **Compact**: `/compact` after writing draft.
8. **Check >> markers** per `human-feedback.md`.
9. **Review** per `review-cycle.md`.
10. **Finalize**: remove `[!QA]` blocks, set status line, commit:
    `design(<task>): approved architecture`

## Review
- Default risk: MEDIUM. Mode: `review`.
- Fix cycle: revise document, add `[!DELTA]` block.

## Rules
- No implementation code. Pseudocode and stubs only.
- Every decision references evidence.
- Recurring findings → Opus decides.
