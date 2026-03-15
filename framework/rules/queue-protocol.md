## Phasebook Protocol

The filesystem is the queue. Folders represent state, filenames encode
metadata, file movement is the user interface.

### Directory Structure

```
phasebook/tasks/
├── drafts/        <- user workspace: create, edit, prepare
├── queue/         <- workers pick from here
├── progress/      <- worker claimed — hands off
├── review/        <- worker returns reviewed tasks here
├── completed/     <- all phases complete
├── archived/      <- user moves completed tasks for long-term storage
```

| Folder | Managed by | Purpose |
|--------|-----------|---------|
| drafts/ | User | New tasks created by `/draft`. User edits before submitting. |
| queue/ | User | Move here when ready for processing. |
| progress/ | Worker | Claimed by worker. User can remove to cancel. |
| review/ | Worker + user | Worker returns tasks here after `-` phases. User reviews, then moves to queue/. |
| completed/ | Worker + user | Completed. User deletes when no longer needed. |
| archived/ | User | Long-term storage. Artifacts persist in phasebook/*/. |

### Filename Convention

```
<priority>.<strip>.<slug>.md
```

| Segment | Values | Purpose |
|---------|--------|---------|
| priority | 1-9 | Priority (lower = first) |
| strip | 4 chars, one per phase (RDPE) | Progress + review policy |
| slug | kebab-case (no underscores, no dots) | Task identifier |

**Strip characters** (each position = one phase: R D P E):

| Char | Meaning |
|------|---------|
| Uppercase letter (`R`/`D`/`P`/`E`) | Phase completed |
| `-` | Pending — will pause for review (safe default) |
| `+` | Pending — will auto-run (opt-in, no review) |

Position 0 = Research (`R`/`-`/`+`), Position 1 = Design (`D`/`-`/`+`),
Position 2 = Plan (`P`/`-`/`+`), Position 3 = Execute (`E`/`-`/`+`).

Examples:
```
1.----.exchange-timezone.md        # all review (safest)
1.--++.exchange-timezone.md        # review R+D, auto P+E
2.RD--.pushover-notifications.md   # R+D done, review P+E
2.RD+-.dashboard-redesign.md       # R+D done, auto P, review E
3.++++.low-risk-task.md            # full auto (intentional)
```

Parsing: strip `.md`, split on first two dots -> priority, strip, slug.
Validate strip: exactly 4 chars, each position matches `[<LETTER>+\-]`
where `<LETTER>` is the phase letter for that position.
Done phases must be sequential — no gaps (e.g., `R-D-` is invalid).
`completed/` files: just `<slug>.md` (no priority, no strip).

**Next phase:** first non-uppercase position in the strip.
All positions uppercase -> run Learn -> move to completed/.

**Invalid filenames:** Files that don't match the convention appear in
"Lost & Found" in `/index`. The worker skips them and sends a
notification: `"lost & found: <filename> in <folder>/"`.
Fix by renaming to a valid format.

### Task File Format

```markdown
# <slug>
**Completed:** YYYY-MM-DD   <!-- stamped by Learn phase -->

<description>

## Requirements
- <acceptance criteria>

## Anti-goals
<!-- Optional: scope boundaries -->

## References
- <links, docs>

## Data
<logs, measurements>

## Enriched Context
<!-- Updated by optimizer each phase -->

## Notes
<!-- Worker logs, completion report -->
```

Human-authored sections (Description, Requirements, References, Data)
are never modified by workers. Token data in sidecar files
(`phasebook/tokens/<slug>.json`), not in the task file.

### Priority System

Lower priority = picked first. No blocking between priority levels.

Workers sort by priority number, then alphabetically by slug. A free worker
picks priority 2 tasks if all priority 1 tasks are already claimed.

User manages dependencies manually: keep dependent tasks in inbox/
until prerequisites are in completed/.

### Mode System

See `strip-semantics.md` for the canonical definition of `+` and `-`.

**Worker decision after completing a phase:**

"Completing a phase" requires the review cycle to have reached the
Completion state per `review-cycle.md`. A phase with unfinished review
passes (e.g., Pass 1 done but Pass 2 not run) is not complete.

1. Replace the position's char with its uppercase letter (mark done).
2. All 4 positions now uppercase -> run Learn -> move to completed/.
3. Otherwise, if it was `-` -> return task to review/ (human review gate).
4. Otherwise, if it was `+` -> continue to next phase (auto-advance).

Learn runs automatically when all 4 phases are done — the `-`/`+` gate
does not apply. Learn always goes to completed/ (final phase, no gate needed).

### User Actions (file operations)

| Action | How |
|--------|-----|
| Approve/start | Move review/ -> queue/ (or drafts/ -> queue/) |
| Pause | Move queue/ -> drafts/ |
| Cancel | Delete the file |
| Reprioritize | Rename priority number |
| Redo a phase | Change uppercase letter back to `-` or `+` |
| Skip a phase | Change `-`/`+` to uppercase letter |
| Add review | Change `+` to `-` at that position |
| Remove review | Change `-` to `+` at that position |
| Rename slug | Also rename `phasebook/tokens/<slug>.json` |
| Archive | Delete from completed/ (artifacts persist in phasebook/*/) |
