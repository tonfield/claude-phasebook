# Execute Phase

## Setup
- Read CLAUDE.md.
- Find task file by slug across `phasebook/tasks/{inbox,queue,progress,completed}/`.
- Load `phasebook/plans/*-<slug>.md` — identify steps.
- Read relevant source files.

## Gate
Plan must exist with at least one PLANNED step.
Scan plan for STATUS markers:
- All VERIFIED → "All steps verified. Next: /learn"
- First PLANNED or FAILED → current step

## Principles
- Match existing conventions.
- Tests alongside code, not after.
- If ambiguous: HALT.
- Only current step.
- All implementation delegated to Task subagents.

## Process

For each PLANNED step:

1. **Load step context**: scope, changes, verification, risk from plan.
   Re-read source files. Apply `prompt-optimization.md` execute framing.
2. **Check >> markers** per `human-feedback.md`.
3. **Build implementation brief** (see template below).
4. **Dispatch subagent** (see Subagent Dispatch below).
5. **Review** per `review-cycle.md` at step's risk level.
6. **Check stop conditions**. If triggered → STATUS: FAILED, halt.
7. **Auto-commit**: `step(<task>): N - <description>`
   Pathspec only — files from plan step + review/execution artifacts.
8. **Mark STATUS: VERIFIED**.
9. **Check stop signal**: if `phasebook/.phasebook-stop` exists → return.
10. **Compact**: `/compact`, then next step.

### Completion
Print summary: steps completed/failed, review paths, plan path.

## Subagent Dispatch

| Risk | Model |
|------|-------|
| LOW / MEDIUM | `sonnet` |
| HIGH | `opus` |

1. Build implementation brief from plan step + CLAUDE.md conventions.
2. Spawn `general-purpose` Task subagent with routed model.
3. Subagent: read files → implement → write tests → run tests → verify → report.
4. Fix cycles: same dispatch + reviewer findings.
5. All green → proceed to review. Blockers → stop condition.

Before fix dispatch, `/compact` if 3+ reviewer outputs accumulated.

## Implementation Brief Template

```
## Implementation Brief

**Step:** N — <title>
**Risk Level:** <level>
**Task:** <task>

### Specification
<plan step's Scope section>

### TODOCLAUDE
<plan step's TODOCLAUDE section, if present>

### Files to Modify
<file paths from plan step>

### Coding Conventions
- Type hints on every function. Prefer `X | None` over `Optional[X]`.
- Async: `async def` with `await`.
- Imports: stdlib, third-party, local, separated by blank lines. Absolute.
- <step-specific conventions from CLAUDE.md>

### Verification Criteria
<from plan step>

### Fix Findings (fix cycles only)
<reviewer findings with severity>

### Instructions
Read only listed files. Implement exactly — no extras. Write tests.
Run `pytest -x`. All tests + verification must pass.
Track interface contracts per `obligation-ledger.md`.
If ambiguous, STOP and report.

### Report Back
1. Files changed (one-line each)
2. Lines +N / -N
3. Test results
4. Verification criteria: PASS/FAIL each
5. Blockers (if any)
```

## Review
- Risk level from plan step. Mode: `code`.
- Fix cycle: subagent dispatch with reviewer findings.
- Scope briefing required: use `--prompt` to specify scope and line ranges.

## Stop Conditions
1. **Test failure loop**: Same failure after 3 fix attempts.
2. **Review restart loop**: 3+ cyclical restarts on one step.
3. **Ambiguity**: Decision not in plan or CLAUDE.md.
4. **Step contradiction**: Conflicts with previous step or invariant.
5. **Subagent failure**: Unresolvable blockers or persistent test failures.

On halt: STATUS: FAILED, report to user, do not continue.

## Resume
1. **Retry**: `/execute` — re-attempts PLANNED/FAILED step.
2. **Edit**: User modifies plan step, then `/execute`.
3. **Skip**: User marks step VERIFIED manually, then `/execute`.

## Rules
- Only current step. All verification must pass.
- Tests green before returning to review.
- Auto-commit without confirmation. Halt on stop conditions.
- Recurring findings → Opus decides.
