## Knowledge Transfer

Mechanics for pushing findings to waiting tasks. Called by every phase
between review completion and commit.

### What to Extract

| Phase | Knowledge Types |
|-------|----------------|
| Research | Findings, corrected estimates, verified/disproven assumptions |
| Design | Architecture decisions, interface specs, new/removed fields, integration points |
| Plan | Risk levels, dependency discoveries, module scope, step sequences |
| Execute | Implementation facts (exact signatures, config defaults, file locations, behavioral changes) |
| Learn | Cross-artifact synthesis, final corrections |

### Find Affected Tasks

Search ALL active phasebook folders (drafts/, queue/, progress/, review/):

1. Grep for this task's slug in Enriched Context sections.
2. Grep for module names from changed/referenced files in References or
   Enriched Context sections. Read Enriched Context to confirm relevance.
3. Check for shared concepts: tasks referencing the same subsystem,
   config parameters, or domain topic even without explicit slug mention.

### Update Enriched Context

For each affected task, update its `## Enriched Context` section:

- Block exists for this slug → update in-place (add phase status, correct
  stale facts, add new findings).
- No block → append new:
  ```
  **<slug> Output — <status> (<date>):**
  - <relevant finding or fact>
  - Corrected: <old assumption> → <verified value>
  ```
- 3-10 bullets per block. Never modify human-written sections.
- Include ALL knowledge relevant to the receiving task's scope.

### Status Labels

| Phase Completed | Status |
|-----------------|--------|
| Research | "Research Complete" |
| Design | "Design Complete" |
| Plan | "Plan Complete" |
| Execute | "NOW IMPLEMENTED" |
| Learn | "NOW IMPLEMENTED (final)" |

### Stale Assumption Check

Check if artifacts referenced BY waiting tasks contain stale assumptions
this task corrected. Note corrections in Enriched Context block — don't
modify historical artifacts.

### Logging

Add to the phase artifact or learnings artifact:
```
## Knowledge Distribution
Updated N task(s):
- `<path>`: <one-line summary of what was pushed>
```
If none found: "No waiting tasks reference this task's slug or changed modules."
