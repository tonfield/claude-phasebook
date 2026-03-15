---
name: phasebook
description: Start worker loop to process tasks from queue. Use /phasebook stop to halt.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, Task
user-invocable: true
---

## Parse Arguments

- No args → Worker Loop
- `stop` → Stop Signal

---

## Stop Signal

1. Create file `phasebook/.phasebook-stop` (empty).
2. Report: "Stop signal created. Workers will stop after their current phase."

---

## Worker Loop

### Conventions

All instances run on `main` in the same working directory.
No worktrees, no branches, no remote push.

Commits use pathspec to avoid index contamination between instances:

```
git add <specific-files> && git commit -m "..."
```

If commit fails (another instance committed, index lock, HEAD moved), retry once.
Different tasks produce slug-namespaced files — no merge conflicts.

---

### Step 0: Startup

**0a. Clear stale stop signal:**
Delete `phasebook/.phasebook-stop` if it exists.

---

### Steps 1-10: Main Loop

**Step 1. Check stop signal:**
Check if `phasebook/.phasebook-stop` exists.
If found → exit with session summary.

**Step 2. Scan queue:**
List files in `phasebook/tasks/queue/` using `ls` on the filesystem.
Do not rely on git status — it may be stale from session start.
Parse per queue-protocol.md filename convention.
Sort by priority (ascending), then slug (alphabetical).
Skip dotfiles. Invalid filenames → notify `"lost & found: <filename> in queue/"` and skip.

**Step 3. Pick first task:**
Select first file from sorted list.

Execute serialization: if the picked task's next phase is Execute
(strip positions 0-2 are uppercase, position 3 is `-` or `+`), check
`phasebook/tasks/progress/` for any file whose strip matches `RDP[-+]`
(also about to execute). If found → skip this task **and all other
execute-ready tasks** in the queue. Pick the next non-execute task.
If no non-execute tasks available → idle, exit. This prevents busy-wait
loops where a blocked execute task is repeatedly picked and returned.

**Step 4. No work available:**
If no eligible tasks → send notification:
`python3 scripts/phasebook_notify.py "worker idle, no tasks in queue"`
Exit with session summary.

**Step 5. Claim task:**
1. Write `.phasebook-task` with the task slug (single line, no JSON).
   This is BEFORE the commit (gitignored, for token tracking only).
2. Run /clear.
3. `git mv phasebook/tasks/queue/<file> phasebook/tasks/progress/<file>`
4. If `git mv` fails: check if file exists on disk. If gone → re-scan
   queue (step 2). If present but untracked → `mv` then proceed.
5. Stage only the specific files involved in the move:
   ```
   git add phasebook/tasks/queue/<old-file> phasebook/tasks/progress/<new-file> && git commit -m "claim(<slug>): move to progress"
   ```
   If a prior review/ copy exists for this slug, also stage its removal:
   `git add phasebook/tasks/review/*<slug>*`
   **Never `git add phasebook/tasks/`** — directory-level staging captures
   other workers' file operations.
6. If commit fails → retry once.

**Step 5b. Prior-phase feedback gate:**
Before determining which phase to run, scan all **completed**
prior-phase artifacts for unresolved `>>` markers (per
`human-feedback.md`). Phase-to-artifact mapping:

| Position | Artifact glob |
|----------|---------------|
| 0 (R) | `phasebook/research/*-<slug>.md` |
| 1 (D) | `phasebook/designs/*-<slug>.md` |
| 2 (P) | `phasebook/plans/*-<slug>.md` |

For each completed position (uppercase in strip) before the current
phase, grep the artifact for `>>`. If any artifact has unresolved
`>>` markers:
1. Revert the **earliest** affected position from uppercase back to `-`.
2. Rename the task file with the updated strip (stay in progress/).
3. `git add phasebook/tasks/progress/<old-file> phasebook/tasks/progress/<new-file> && git commit -m "revert(<slug>): >> feedback found in <phase> artifact"`
4. Send notification:
   `python3 scripts/phasebook_notify.py "<slug>: >> feedback in <phase>, reverting to resolve"`
5. Fall through to Step 6 — the reverted position is now the first
   non-uppercase, so the correct phase runs in revise mode.

**Step 6. Run phase:**
Determine next phase from strip (first non-uppercase position):
- Position 0 → `Read .claude/phases/research.md` → follow instructions
- Position 1 → `Read .claude/phases/design.md` → follow instructions
- Position 2 → `Read .claude/phases/plan.md` → follow instructions
- Position 3 → `Read .claude/phases/execute.md` → follow instructions
- All uppercase → `Read .claude/phases/learn.md` → follow instructions

Execute gate (final): if the phase about to run is Execute, check
`phasebook/tasks/progress/` for any OTHER file whose strip matches
`RDP[-+]`. If found → move this task back to queue/ (keep current
strip), commit with pathspec (`git add phasebook/tasks/progress/<file>
phasebook/tasks/queue/<file>`), send notification `"<slug>: execute
blocked, returned to queue"`, go to step 1. This is the definitive
last check — it catches TOCTOU races between Step 3 and Step 5.

Send notification before starting:
`python3 scripts/phasebook_notify.py "<slug>: starting <phase>"`

**Step 7. Phase complete — advance:**
Commit phase artifacts: `git add <slug-specific-files> && git commit -m "<phase message>"`.
If commit fails, retry once.

Record the strip character at the completed position (`-` or `+`)
before replacing it with the uppercase letter.

Then determine next action:

**7a. Phase failed** (stop condition, error, review loop exceeded):
Move task to review/ (unchanged filename — strip NOT updated).
`git add phasebook/tasks/progress/<file> phasebook/tasks/review/<file> && git commit -m "fail(<slug>): <phase> failed, moved to review"`
Send notification:
`python3 scripts/phasebook_notify.py "<slug>: <phase> failed, moved to review"`
Go to step 1.

**7b. Cancel detection:**
Check if task file exists in `phasebook/tasks/progress/` on local filesystem.
If file missing → user cancelled. Discard uncommitted changes. Go to step 1.

**7c. Position was `-` (review):**
Replace position with uppercase letter in filename.
`git mv` from progress/ to review/.
Commit with pathspec: `git add phasebook/tasks/progress/<old-file> phasebook/tasks/review/<new-file> && git commit -m "<phase>(<slug>): complete, moved to review"`
Send notification:
`python3 scripts/phasebook_notify.py "<slug>: <phase> complete, moved to review"`
Go to step 1.

**7d. Position was `+` (auto) + more phases remain:**
Replace position with uppercase letter in filename. Stay in progress/.
`git add phasebook/tasks/progress/<old-file> phasebook/tasks/progress/<new-file> && git commit -m "<phase>(<slug>): complete, continuing"`

Execute serialization (auto-advance): if the NEXT phase is Execute
(positions 0-2 are now uppercase, position 3 is `-` or `+`), check
`phasebook/tasks/progress/` for any OTHER file whose strip matches
`RDP[-+]`. If found → move this task back to queue/ (revert filename
to use the NEW strip with completed phases), commit with pathspec
(`git add phasebook/tasks/progress/<file> phasebook/tasks/queue/<file>`),
send notification `"<slug>: execute blocked, returned to queue"`,
go to step 1.

Continue to step 6.

**7e. All 4 positions now uppercase (RDPE):**

Learn concurrency check: scan `phasebook/tasks/progress/` for any
OTHER file whose strip is also all uppercase (RDPE). If found → send
warning notification:
`python3 scripts/phasebook_notify.py "<slug>: WARN — concurrent Learn with <other-slug>, shared files may conflict"`
Proceed anyway (Learn is additive), but the warning alerts the user
to check for git commit failures on shared files (reference-data.md,
CLAUDE.md).

Run Learn phase. Then rename to `<slug>.md`.
`git mv` to completed/.
`git add phasebook/tasks/progress/<old-file> phasebook/tasks/completed/<slug>.md && git commit -m "done(<slug>): all phases complete"`
Send notification:
`python3 scripts/phasebook_notify.py "<slug>: done"`
Go to step 1.

**Step 8.** Go to step 1.

---

### Session Summary

```
Worker session: <start> — <end>

Tasks processed:
  <slug> — <phase> → <outcome>

Remaining in queue:
  <count> tasks
```

---

### Notifications

**MUST send** at every event below. Run synchronously (not `&`).
Notification failure is non-fatal — log and continue.

```
python3 scripts/phasebook_notify.py "<message>"
```

| Event | Message |
|-------|---------|
| Phase starting | `<slug>: starting <phase>` |
| Phase complete (auto) | `<slug>: <phase> complete, starting <next>` |
| Phase complete (review) | `<slug>: <phase> complete, moved to review` |
| Phase failed | `<slug>: <phase> failed, moved to review` |
| Task done | `<slug>: done` |
| Execute blocked | `<slug>: execute blocked, returned to queue` |
| Prior feedback found | `<slug>: >> feedback in <phase>, reverting to resolve` |
| Learn concurrency | `<slug>: WARN — concurrent Learn with <other-slug>, shared files may conflict` |
| Worker idle | `worker idle, no tasks in queue` |
| Lost & found | `lost & found: <filename> in <folder>/` |

---

## Rules

- Commit with pathspec only — never `git add .` or `git add -A`.
- If `git mv` fails during claim (file gone), re-scan queue.
- If commit fails, retry once with `git add <files> && git commit`.
- `.phasebook-task` written at claim for token tracking (gitignored, best-effort).
- Execute serialization: only one execute task in progress/ at a time. Three checkpoints: claim (step 3), execute gate (step 6), and auto-advance (step 7d). The step 6 gate is the definitive last check before execution begins.
- No remote push. User pushes when ready.
- Never modify task file human-authored sections.
- Never skip review cycle within phase skills.
- Never adopt tasks already in `progress/`. Only work on tasks you
  successfully moved from `queue/` to `progress/` in this session.
  Orphaned tasks in `progress/` from prior sessions are the user's
  responsibility — skip them silently.
