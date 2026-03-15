# Research Phase

## Setup
- Read CLAUDE.md.
- Find task file by slug across `phasebook/tasks/{inbox,queue,progress,completed}/`.
- Read `phasebook/research/external/` for reference material.
- Load existing artifact (`phasebook/research/*-<slug>.md`) if present:
  - Has `>>` markers → **revise mode**: address feedback, preserve structure.
    Update status line to `REOPENED for >> feedback`.
  - No `>>` → **fresh mode**: existing = reference only

## Gate
None — research can start from task file alone.

## Principles
- Evidence over intuition. Never invent information.
- Primary sources first. Track versions and dates.
- Separate FINDING from INFERENCE.
- "Unknown — needs verification" is valid.
- Verify early: write `scripts/verify_*.py` for testable assumptions.

## Process
1. **Optimize prompt** per `prompt-optimization.md` research framing.
2. **Clarify**: restate objective, break into sub-questions, check existing work.
3. **Investigate**:
   - **WebSearch** for external facts. Default to searching, not recalling.
   - **WebFetch** for specific docs, changelogs, specs.
   - **Bash** (`scripts/verify_*.py`) for testable assumptions.
   - Codebase: Grep/Glob/Read for internal facts.
   - Tag: `[VERIFIED]`, `[INFERRED]`, or `[UNVERIFIED]`.
4. **Draft** to `phasebook/research/<date>-<HHMM>-<slug>.md`.
   Track claims and assumptions per `obligation-ledger.md`.
5. **Compact**: `/compact` after writing draft.
6. **Check >> markers** per `human-feedback.md`.
7. **Review** per `review-cycle.md`.
8. **Finalize**: remove `[!QA]` blocks, set status line, commit:
   `research(<task>): approved brief`

## Review
- Default risk: MEDIUM. Mode: `review`.
- Fix cycle: revise document, add `[!DELTA]` block.

## Rules
- READ ONLY. No project source modifications.
- Recurring findings → Opus decides.
