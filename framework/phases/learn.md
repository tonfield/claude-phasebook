# Learn Phase

## Setup
- Read CLAUDE.md.
- Find task file by slug across `phasebook/tasks/{inbox,queue,progress,completed}/`.
- Read all artifacts: research, design, plan, reviews, executions, learnings.

## Gate
At least one phase must be completed. Learn works with any completed phase —
not only execute.

## Principles
- Specific and actionable — no vague observations.
- Key Decisions is append-only (never modify existing entries).
- Docs reflect implementation, not design intent.

## Process
1. **Optimize prompt** per `prompt-optimization.md` learn framing.
2. **Review all artifacts**: what worked, what caused rework, reviewer accuracy.
3. **Draft learnings** to `phasebook/learnings/<date>-<HHMM>-<slug>.md`.
4. **Update system knowledge**:
   - `.claude/references/reference-data.md`: Known Patterns, Known Gotchas,
     Key Decisions (append only).
   - CLAUDE.md: Conventions, Invariants — only if new convention needed.
   - `.claude/rules/`: if a mistake must never recur.
5. **Update documentation**: bring affected docs (`docs/ARCHITECTURE.md`,
   `docs/USER_GUIDE.md`, etc.) current with what was built. Use the
   **Doc Update** list from reviews as starting point.
6. **Review panel effectiveness**: which reviewers found high-value issues,
   what gaps-reviewer caught. Document in learnings.
7. **Pattern extraction**: scan `generalizable: true` findings in review
   YAML blocks → candidates for Known Patterns or Known Gotchas.
8. **Quick review** via review-gaps agent.
9. **Finalize**: stamp `**Completed:** YYYY-MM-DD` after the `# <slug>` title
   line in the task file. Commit `learn(<task>): system updated`, move task
   to `completed/`.
10. **Completion card** (write to Notes section of task file):
    ```
    ### Completion (<date range>)
    <N> steps | <N> blocking fixed
    Decisions: <key decisions>
    CLAUDE.md: +<N> patterns, +<N> gotchas, +<N> decisions
    Attention: <anything needing operator awareness>
    ```

## Review
- No formal review cycle. Quick gaps review only (step 8).

## Rules
- Mandatory after features/milestones.
- Key Decisions is append-only.
