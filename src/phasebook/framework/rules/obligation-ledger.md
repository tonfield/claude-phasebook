## Obligation Ledger Protocol

Structural enforcement during drafting. Tracks claims, assumptions, and
traces as explicit obligations that must be resolved before completion.
Reduces review cycle load by catching incomplete follow-through at source.

Does NOT substitute for design review, domain review, or runtime
validation. Purpose: reduce avoidable factual and follow-through errors
before external review.

### When Active

All phases: Research, Design, Plan, Execute.
Also: fix cycles (any phase), decomposed subagent work.

### Storage

Write ledger to disk: `phasebook/obligations/<slug>.ledger.md`.
Do not maintain in-context only — context decay drops entries silently.
Overwrite on each update.

**Deletion timing:** Delete AFTER all three conditions are met:
1. Phase review cycle is clean (both passes, no cyclical restart).
2. Promoted items (per Phase Handoff) are written to next phase's ledger.
3. Artifact is committed.

### Ledger Lifetime

The ledger persists across review rounds within a phase.

- **Initial draft** -> obligations accumulate during drafting.
- **Fix cycle** -> fixes add new obligations (FIX_IMPACT, REFERENCE).
  Walk before exiting the fix cycle.
- **Next round** -> new obligations from the fix carry forward.
  VERIFIED entries stay resolved unless code changed (see Staleness).
  Walk again at next Contract Check.
- **Phase complete** -> promote unresolved items per Phase Handoff.
  Delete the ledger file.

### Staleness

VERIFIED entries go STALE when their evidence basis changes:

- File cited in evidence was modified since verification.
- Symbol cited was renamed, moved, or deleted.
- A fix cycle changed code in the same module.

STALE entries must be re-verified at next Contract Check.
When walking the ledger, check modification times of evidence files
against verification round. Changed -> mark STALE.

### Phase Handoff

Not everything is discarded at phase boundaries.

| Status at phase end | Action |
|---------------------|--------|
| VERIFIED | Discard |
| STALE | Re-verify or promote |
| `[UNVERIFIED]` ASSUMPTION | Promote to next phase's ledger |
| `[UNVERIFIED]` CLAIM | Must resolve before phase completes — cannot promote |
| PARTIAL TRACE | Promote unverified hops |

Promoted items appear in the next phase's ledger with origin
`[carried from <phase>]`. The next phase must resolve or re-defer.

### Obligation Types

| Type | Trigger | Resolution |
|------|---------|------------|
| CLAIM | Assert existing code behavior ("X calls Y") | Read source, verify signature/behavior |
| NEGATION | Assert absence ("no other callers", "only X depends on Y") | Exhaustive grep; document search scope and result count |
| ASSUMPTION | Take something as true without evidence | Test, verify, or flag `[UNVERIFIED]` |
| TRACE | Assert data/control flow across boundaries | Verify each hop in the chain |
| REFERENCE | Same value/name appears in multiple sections | Check all instances after any change |
| FIX_IMPACT | Fix changes X that has dependents | Check each dependent (callers, consumers, other sections) |

NEGATION obligations require documenting the search scope (which
directories/patterns were searched) because absence is harder to prove
than presence.

### Implicit Triggers

These patterns create obligations without explicit declaration:

| Pattern in artifact/code | Obligation created |
|--------------------------|--------------------|
| "integrates with X()" / "calls X()" | CLAIM: verify X exists with matching signature |
| "field Y available from Z" | CLAIM: verify Y in Z's schema/output |
| "no other callers" / "only X uses Y" / "nothing else writes Z" | NEGATION: exhaustive grep with documented scope |
| "assuming ..." / "should work" | ASSUMPTION: verify or flag |
| Changed value in one location | REFERENCE: find all other references to same value |
| Added/changed function parameter | FIX_IMPACT: trace all callers, including internal |
| Added field to dataclass/Protocol | FIX_IMPACT: check all constructors and implementations |
| Mentioned alternative without evaluating | Must evaluate or explicitly defer with reason |
| "step N creates/updates row" | CLAIM: verify SQL is INSERT/UPSERT, not UPDATE-only |

### Ledger Format

```
| # | Type | Origin | Obligation | Status | Evidence |
|---|------|--------|------------|--------|----------|
| 1 | CLAIM | §3.2 | calculate_threshold() called from scanner.py | VERIFIED ✓ | `grep -n "calculate_threshold" scanner/scanner.py` -> line 142: `result = calculate_threshold(...)` |
| 2 | NEGATION | §2.4 | no other callers of _rebuild_cache() | VERIFIED ✓ | `grep -rn "_rebuild_cache" .` -> 2 hits: definition + 1 caller (state/db.py:88) |
| 3 | ASSUMPTION | §2.1 | FlexQuery has access to exit_rule | [UNVERIFIED] | attempted: grep in flexquery output — field not found. Deferred: needs live test |
| 4 | TRACE | §4.1 | entry_cost: transform -> db -> dashboard | PARTIAL 2/3 | hops 1-2: grep confirmed. hop 3: dashboard read pending |
```

Evidence must include the **tool command and result**, not just a
file:line pointer. This allows reviewers to spot-check by re-running
the same command.

### Verification Responsibility

Three layers, each catching what the previous missed:

| Layer | Who | How | Catches |
|-------|-----|-----|---------|
| **Self-verification** | Drafting agent | Run grep/read tools. Evidence = tool output. | Untraced callers, wrong signatures, missing fields |
| **Codebase Verification** | Internal reviewer (Design/Plan) | Independent source reads per `review-panel-roles.md`. Audit capture: search for uncaptured claims, not just verify captured ones. | Self-verification errors, missed obligations, shallow checks |
| **External review** | 6 models via PAL | Logical/domain review of the artifact | Incorrect assumptions, design flaws, domain errors |

Self-verification is mandatory but not trusted as final. It shifts
easy catches left so reviewers focus on harder problems.

Reviewers must **audit the capture mechanism** (search for claims NOT
in the ledger) rather than only trusting captured entries.

### `[UNVERIFIED]` Budget

Not all phases tolerate the same level of unresolved obligations.

| Phase | Allowed `[UNVERIFIED]` | Blocked |
|-------|------------------------|---------|
| Research | ASSUMPTION: allowed with rationale. CLAIM: must resolve. | — |
| Design | ASSUMPTION about external behavior: allowed, bounded. CLAIM about existing code: must resolve. | Interface/signature CLAIMs |
| Plan | ASSUMPTION: bounded (max 3). All CLAIMs and TRACEs must resolve. | Caller/schema CLAIMs, full TRACEs |
| Execute | Zero tolerance. All obligations must resolve. | Everything |

To leave something `[UNVERIFIED]`, document what was attempted:
`"Attempted: grep -rn 'exit_rule' core/flexquery*. 0 results.
Cannot verify without live FlexQuery response. Deferred to Execute."`

### Completion Gate

Before declaring phase/step complete (runs as part of Contract Check):

1. Walk every ledger entry.
2. VERIFIED -> evidence includes tool command + result.
3. STALE -> re-verify (re-run the original command, check result).
4. UNVERIFIED -> resolve now. If cannot -> check phase budget above.
   If within budget -> mark `[UNVERIFIED]` in artifact with attempt log.
   If over budget -> must resolve before completing.
5. PARTIAL -> complete remaining hops or flag per budget.
6. **Artifact reconciliation:** Scan each artifact section for factual,
   causal, or dependency assertions not in the ledger. Add and resolve
   any found. This catches obligations the agent didn't create during
   drafting.

### Fix Cycle Obligations

Every fix creates FIX_IMPACT obligations automatically:

1. Changed a value -> REFERENCE: find all other mentions in artifact.
2. Changed a signature -> FIX_IMPACT: trace all callers (grep, not memory).
3. Added a field -> FIX_IMPACT: check all constructors/implementations.
4. Defined a new variable/term -> FIX_IMPACT: verify it's consumed by
   all formulas/sections that should reference it.

Walk fix-created obligations before exiting the fix cycle.
Mark any previously VERIFIED entries touching changed files as STALE.

### Execute Phase

**Subagent (implementing code):**

Track at the **per-function contract** level, not per-operator:

1. Each new/modified function -> CLAIM on its interface contract
   (signature, return type, side effects match design spec).
2. Cross-boundary calls -> CLAIM (verify target exists with matching
   signature).
3. Behaviorally significant defaults and conditions (design-specified
   values, thresholds, comparison semantics) -> CLAIM against design spec.
4. Compound scope ("implement X for Y and Z") -> TRACE (verify all
   paths implemented).
5. Walk ledger before returning output.

Do NOT create per-operator obligations for routine code. Focus on
design-spec deviations and cross-boundary contracts.

**Orchestrator (verifying step output):**

1. Each "step passes" assertion -> CLAIM (verify tests actually ran
   and cover the step's scope).
2. Each cross-step dependency -> TRACE (verify prior step's output
   is consumed correctly by current step).
3. Walk ledger before marking step VERIFIED.

### Decomposed Subagent Merge

When multiple subagents maintain ledgers (task decomposition):

1. Each subagent writes its ledger to disk per Storage rules.
2. Orchestrator reads all subagent ledgers during synthesis.
3. Cross-reference: if SA1 has a CLAIM that SA2's interface exists,
   check SA2's ledger for matching verification.
4. Merge into a single phase ledger. Conflicts -> investigate.

### Rules

- Ledger is a working tool, not artifact content. Do not ship it.
- Use grep/read tools to resolve — not memory. Memory-based resolution
  is the root cause of Category 2 failures.
- When in doubt about whether something is an obligation, track it.
  False positives cost seconds; false negatives cost review cycles.
- At Execute granularity, false positives cost more. Track contracts
  and design-specified values, not routine code.
