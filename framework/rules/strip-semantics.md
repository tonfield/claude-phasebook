## Strip Semantics

Canonical definition of `+` and `-` in the task strip. All other files
reference this document — do not redefine these semantics elsewhere.

### What the strip controls

Each strip position controls **one thing**: whether the human gates
the phase-to-phase transition after the review cycle completes.

Both `+` and `-` receive the **same review cycle** (depth determined
by risk level per `review-cycle.md`, not by strip character).

| Char | Name | Review cycle | Commit | Transition |
|------|------|-------------|--------|------------|
| `-` | review | Full (risk-based) | Waits for human approval | Moves to review/ — human must move to queue/ to continue |
| `+` | auto | Full (risk-based) | Automatic after review passes clean | Stays in progress/ — advances to next phase |

### What the strip does NOT control

- Review depth (controlled by risk level)
- Whether external/internal reviewers run (controlled by risk level)
- Whether the challenge gate runs (controlled by risk level)
- Number of review rounds (controlled by findings)

### Setting `+` is pre-authorization

When a user sets `+` on a strip position, they are pre-authorizing
automatic commit and advancement for that phase. The review cycle
still runs in full — `+` trusts the review cycle's quality gates
instead of adding a manual gate on top.

### Default

`-` is the safe default. `+` requires explicit opt-in per phase.
