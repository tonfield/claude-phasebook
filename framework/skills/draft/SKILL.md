---
name: draft
description: Draft a new task file in drafts/ with smart enrichment, prompt optimization, and review cycle.
allowed-tools: Read, Edit, Write, Grep, Glob, Agent, Bash
user-invocable: true
---

## Process

1. **Parse input:** Extract task name from arguments. If no args, ask.
   Generate slug: lowercase, hyphens only, no underscores, no dots.

2. **Check uniqueness:** Scan all six folders for files whose parsed
   slug exactly matches the new slug. Exact match only — `spx-migration`
   does NOT match `spx-migration-v2`.
   - `phasebook/tasks/drafts/` — parse filenames for slug (third dot-segment)
   - `phasebook/tasks/queue/` — parse filenames for slug
   - `phasebook/tasks/progress/` — parse filenames for slug
   - `phasebook/tasks/review/` — parse filenames for slug
   - `phasebook/tasks/completed/` — filename IS the slug (no priority/strip)
   - `phasebook/tasks/archived/` — filename IS the slug (no priority/strip)
   If found → report: "Task '<slug>' already exists in <folder>/."
   Ask whether to update existing or abort.

3. **Shape contract:** Ask for priority (default 1), description, requirements.
   Optional (don't block): references, data.
   Then before writing:
   - Tighten vague requirements into verifiable criteria (propose rewording, user approves)
   - **Generate acceptance criteria:** For each requirement, append a
     `[verify: <method>]` annotation describing HOW correctness is proven.
     Methods must be concrete and phase-appropriate:
     - Test: `[verify: test_budget_ceiling_enforced passes]`
     - Benchmark: `[verify: scanner batch ≤100 concurrent, measured in test]`
     - Script: `[verify: scripts/verify_X.py passes]`
     - Inspection: `[verify: no direct imports from engine/ in dashboard/]`
     Requirements without a verification method are incomplete.
   - Infer anti-goals from description and scope — propose them
   - Present shaped version for user approval before writing

4. **Risk classification:** Classify the task's risk level. This determines
   both the strip recommendation (step 5) and the review depth (step 8).

   | Level | Task Characteristics |
   |-------|---------------------|
   | LOW | Config, docs, single module, clear scope, no shared state |
   | MEDIUM | Multi-module, new interfaces, integration claims. **Default when uncertain** |
   | HIGH | Money path, broker API, shared state, invariant-adjacent |

   State the classification and rationale before proceeding.

5. **Recommend strip:** Default `----` (review all). Apply classification
   signals per phase to suggest `+` where safe. User can override any position.

   | Signal | `+` (auto) | `-` (review) |
   |--------|------------|--------------|
   | Ambiguity | Clear, one path | Trade-offs, open-ended |
   | Reversibility | Single revert | Shared state, hard to undo |
   | Domain risk | No money impact | Direct (orders, broker) |
   | Novelty | Strong precedent | No precedent |
   | Decision weight | No choices | Strategic |

   Common patterns:

   | Pattern | Strip | Behavior |
   |---------|-------|----------|
   | Review everything | `----` | Pause after every phase |
   | Review first, auto rest | `--++` | Review R+D, auto P+E |
   | Auto everything | `++++` | No pauses (requires intention) |
   | Review execute only | `+++-` | Auto R+D+P, review E |
   | Review early + code | `--+-` | Review R+D+E, auto P |

6. **Prompt optimization:** Apply all strategies per `prompt-optimization.md`,
   including Premise Challenge (Strategy 5). Write findings to Enriched
   Context section.

7. **Write draft file:** `phasebook/tasks/drafts/<priority>.<strip>.<slug>.md`

   ```markdown
   # <slug>

   <description>

   ## Requirements
   - <requirement> [verify: <method>]

   ## Anti-goals
   <!-- Optional: scope boundaries -->
   - <what we're explicitly NOT doing>

   ## References
   - <links, docs>

   ## Data
   <logs, measurements>

   ## Enriched Context
   <!-- Updated by optimizer each phase -->
   <enriched content from step 6>

   ## Notes
   <!-- Worker logs, completion report -->
   ```

8. **Review cycle:** Apply the standard review cycle to the task file.
   Review depth scales with the risk classification from step 4.

   ### Risk-Based Review Depth

   Lighter than phase-artifact reviews (task files are scope definitions,
   not analysis), but scaled with risk.

   | Risk | Review Depth |
   |------|-------------|
   | LOW | 4 external, Pass 2 |
   | MEDIUM | 3 external, Pass 2 |
   | HIGH | 3 external, Pass 2, challenge |

   ### Pass 1: External Review (MEDIUM+)

   Run `.claude/scripts/external_review.py` with the first available model from the
   external review protocol. Send the task file with this prompt:

   > Critically review this task specification for a pipeline system.
   > Evaluate: (1) Are requirements verifiable and complete? (2) Are
   > [verify:] methods concrete and phase-appropriate? (3) Are anti-goals
   > sufficient to prevent scope creep? (4) Is the scope right-sized or
   > should it be split? (5) Are there unstated assumptions or missing
   > requirements? (6) Is the task feasible within the described
   > architecture? Be harsh and specific. Grade A-F.

   Include CLAUDE.md invariants and design constraints as context when
   the task touches those areas.

   Normalize findings into BLOCKING / ADVISORY per `/review` skill synthesis format.

   ### Pass 2: Validation

   1. **Requirements audit:** Each requirement has a concrete `[verify:]`
      method. Methods are achievable in the stated phase. No circular
      verification (requirement verifies itself).
   2. **Anti-goals audit:** Scope boundaries sufficient. No obvious
      adjacent work that should be explicitly excluded.
   3. **Invariant compatibility:** Walk CLAUDE.md Architectural Invariants
      and Design Constraints. Flag any that the task could violate or
      that constrain how the task must be implemented.
   4. **Overlap detection:** Check `phasebook/tasks/progress/` and
      recent `completed/` for tasks touching the same modules or subsystems.
      Flag duplication or dependency that should be noted.
   5. **Enriched context accuracy:** References exist, prior art links
      are valid, constraint citations are correct.
   6. **Scope calibration:** Task is right-sized. Not so broad it needs
      splitting, not so narrow it's a subtask of something else.
   7. **Contract verification:** Requirements and anti-goals are internally
      consistent. No requirement contradicts an anti-goal.

   Produce findings table per `/review` skill synthesis format.
   Accepted findings → fix cycle → check cyclical restart.

   ### Cyclical Restart

   After Pass 2, if ANY pass had fixes during this cycle → restart from
   Pass 1. Continues until a full cycle has zero fixes.

   ### Challenge Gate (HIGH only)

   Triggers after both passes return 0 blocking, OR always for HIGH risk.
   Run `.claude/scripts/external_review.py <task-file> --mode challenge`.
   Blocking findings → treat as Pass 2 (fix → restart check).

   ### Fix Cycle

   Revise the task file on disk. Re-read before each revision.

   ### Completion

   When all passes are clean and no cyclical restart:
   1. Run micro-learn (scan accepted findings for persistable insights)
   2. Present final task file and review summary to user

9. **Report:** "Task '<slug>' created in drafts/. Move to queue/ when ready."
   Include risk classification and review summary.

## Rules

- Never modify human-written sections of existing task files.
- Slug must be kebab-case: lowercase letters, digits, hyphens only.
- Strip always starts with all positions as `-` or `+` (no phases done yet).
- File goes to drafts/, not queue/ — user moves when ready.
- Review file not written for task creation (review is inline, not a phase artifact).
- LOW tasks with clear scope may use lighter review (fewer external models).
