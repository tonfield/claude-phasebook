## Task Decomposition Protocol

Fan-out/fan-in pattern for phases that exceed single-context capacity.
The orchestrator holds the overview; subagents explore in isolated contexts
with full tool access. Only structured summaries return to the orchestrator.

Three quality-protection layers prevent decomposition-induced information
loss: shared context map (before), dependency contracts (during), and
integration verification (after).

### When to Decompose vs Split

During prompt optimization, assess scope before decomposability:

**Step 1 — Scope check (split vs decompose):**

| Signal | Action |
|--------|--------|
| Sub-areas share no domain context, terminology, or constraints | **Recommend split** — these are separate tasks bundled together |
| Sub-areas are facets of one coherent topic | Continue to decomposition assessment |

Split = separate pipeline tasks that can run through the full pipeline
independently. Downstream phases (design, plan) reference the split
tasks' artifacts via the `depends:` field in the task file.

**When recommending a split:**
1. Write recommendation in the task file's Notes section:
   `SPLIT RECOMMENDED: This task contains N independent topics.
   Suggested tasks: <slug-a>, <slug-b>, <slug-c>.
   Reason: <why these are independent>.
   Downstream: create a design/plan task with depends: <all slugs>.`
2. Return task to review/ (worker cannot create tasks — user decides).
3. User creates the split tasks via `/add` and a synthesis task that
   references them. User archives or repurposes the original.

**Step 2 — Decomposition assessment (for coherent tasks):**

| Condition | Action |
|-----------|--------|
| 3+ independent sub-areas identified | Decompose |
| Sub-areas have cross-dependencies requiring back-and-forth | Do NOT decompose |
| Task touches a single tightly-coupled module | Do NOT decompose |
| Uncertain | Do NOT decompose — single context is the safe default |

"Independent" = a subagent can complete its sub-area without results
from other sub-areas. Shared read-only context (research findings,
CLAUDE.md, codebase) is fine. Shared write state is not.

**Independence check:** For each pair of sub-areas, verify they don't
share writable surfaces (same DB table, same config section, same file
for modifications). Shared writable targets → merge or sequence.

### Decomposition Step

Insert after prompt optimization, before drafting the artifact.

**Layer 1 — Shared Context Map (before fan-out):**

1. **Quick orientation** in the main context. Read the task, scan relevant
   areas (Grep/Glob, skim key files), identify relationships between
   sub-areas. Budget: ~5 min, no deep investigation.
2. **Produce a shared context map.** Format varies by phase:

   **Research — Domain Map:**
   - Sub-areas with IDs (`SA1`, `SA2`, ...) and 1-sentence scope each.
   - Shared terminology and domain definitions (ensure all subagents
     use consistent language for the same concepts).
   - Known cross-cutting themes (topics that span multiple sub-areas).
   - Shared constraints (invariants, design constraints from CLAUDE.md).
   - Open questions that span multiple sub-areas.

   **Design — Interface Skeleton:**
   - Sub-areas with IDs and 1-sentence scope each.
   - **Shared interfaces** between sub-areas: function signatures, data
     schemas, class APIs in pseudo-code. If SA1 produces data that SA2
     consumes, define the contract here. Subagents design *against*
     these interfaces, not independently.
   - Shared constraints (invariants, design constraints from CLAUDE.md).
   - Open questions that span multiple sub-areas.

   **Plan — Change Surface Map:**
   - Sub-areas with IDs and 1-sentence scope each.
   - Files/modules owned by each sub-area (no overlaps).
   - Shared interfaces that cross sub-area boundaries (from design).
   - Shared constraints (invariants, design constraints from CLAUDE.md).

   Budget: ~500 tokens base + ~100 per sub-area. Use structured tables
   for interfaces/surfaces; they don't count toward the prose budget.

3. The shared context map becomes input for every subagent briefing.

**Layer 2 — Fan-out with dependency contracts:**

4. **Classify independence.** For each pair: does A need B's output? If
   yes → merge or sequence them. Only truly independent sub-areas fan out.
5. **Build briefings.** One per sub-area (see Briefing Template). Include
   the shared context map in every briefing.
6. **Dispatch.** Launch Agent subagents in parallel (all independent ones
   in a single tool-call block). Use `subagent_type: general-purpose`.
7. **Collect.** Each subagent returns a structured deliverable including
   mandatory dependency contract and cross-reference sections.

**Synthesis:**

8. **Validate dependency contracts.** Walk each subagent's dependency
   table. Check against other subagents' findings and the shared context
   map. Mismatches → investigate (orchestrator reads the relevant
   file/source directly, or dispatches a targeted follow-up subagent
   for a specific question).
9. **Synthesize.** Orchestrator combines deliverables into the phase
   artifact. Write the integration layer connecting sub-areas.
   Identify cross-cutting concerns, contradictions, and gaps.
   The orchestrator writes the artifact — subagents do not.

**Layer 3 — Integration Verification (after synthesis):**

10. **Dispatch integration verifier.** A single Agent subagent with a
    dedicated mandate. **Input:** the synthesized artifact, the shared
    context map, AND all raw subagent structured outputs. Hunt for:
    - **Fidelity:** Did the orchestrator accurately represent each
      subagent's findings? Compare artifact sections against raw outputs.
    - **Contradictions:** Between sections originating from different
      sub-areas that the orchestrator may have smoothed over.
    - **Dropped information:** Findings in raw outputs that don't appear
      in the artifact. Blockers a subagent flagged that the artifact ignores.
    - **Contract violations** (Design/Plan): Deviations from the interface
      skeleton that weren't flagged as intentional.
    - **Lost context:** Information in the shared context map that was
      lost during synthesis.
    - Terminology or convention inconsistencies across sections.
    Return: list of BLOCKING / ADVISORY findings.
11. **Resolve blocking findings** per Remediation Protocol below.
12. **Re-verify** if blocking fixes touched cross-area sections.
    Loop max twice, then escalate per remediation protocol.

The standard review cycle (external + internal + gaps) then runs on the
verified artifact as usual. It remains the strongest quality net — the
three layers above reduce the work the review cycle needs to catch.

### Remediation Protocol

When integration verifier returns BLOCKING findings:

1. **Classify the failure:**

| Failure Type | Description | Resolution |
|-------------|-------------|------------|
| Assumption mismatch | One subagent's assumption contradicts another's findings | Targeted follow-up subagent to resolve the specific question |
| Missing integration | Sub-areas don't connect properly at boundaries | Orchestrator patches integration layer using raw outputs |
| Lost information | Artifact missing key findings from a subagent | Orchestrator re-reads relevant raw output, amends artifact |
| Contract violation | Subagent deviated from interface skeleton (Design/Plan) | Orchestrator rewrites section to match contract, or updates contract if deviation was correct |
| Decomposition failure | Sub-areas weren't actually independent | Re-decompose with different boundaries (see below) |

2. **Apply fix.** One fix cycle per round.
3. **Re-verify** if fix touched cross-area content (dispatch verifier
   again with updated artifact + same raw outputs).
4. **Max 2 remediation loops.** If still blocking → escalate.

**Escalation for decomposition failure:**

Single-context fallback is not available (the task was too large for
single context — that's why we decomposed). Instead:

1. **Re-decompose:** Draw different sub-area boundaries. Merge the
   coupled sub-areas into one, split elsewhere if needed. Restart
   Layer 1 with new boundaries.
2. **Sequence:** If two sub-areas are coupled, run them sequentially
   instead of in parallel. SA1 completes first, its findings feed into
   SA2's briefing as input context.
3. **Staged depth:** If the scope is too interconnected for any
   parallel split, switch to iterative refinement:
   a. **Shallow pass** (single context): Cover the entire scope at low
      resolution. Establish the framework — key findings, architecture,
      major decisions, section structure. Write to disk as a draft.
   b. **Compact.**
   c. **Deep passes** (targeted subagents): Each subagent takes one
      section of the framework and fills in details. The framework
      provides coherence; the subagent adds depth.
   d. **Integration pass** (single context): Read the framework + deep
      pass returns, finalize the artifact.
   This preserves coherence (shallow pass sees everything) while
   managing context (deep work is isolated per section).

### Briefing Template

```
## Sub-Area Brief: <SA_ID> — <title>

**Phase:** Research | Design | Plan
**Parent task:** <slug>
**Objective:** <1-2 sentences — what this subagent must produce>

### Shared Context Map
<paste from Layer 1 — domain map / interface skeleton / change surface>

### Scope
- IN: <what to investigate/design/map>
- OUT: <what is NOT this subagent's responsibility>

### Input Context
- Task requirements: <relevant subset>
- Prior artifacts: <file paths to read — research findings, design docs>
- Codebase entry points: <file paths to start reading>
- Constraints: <relevant invariants, design constraints from CLAUDE.md>

### Output Format
<phase-specific structured format — see below>

### Tool Guidance
- Use Read/Grep/Glob for codebase exploration
- Use WebSearch/WebFetch for external research
- Use Bash for verification scripts
- Do NOT modify any project files
- Do NOT commit

### Rules
- Read-only. No edits, no writes to project files.
- Stay within scope. Flag out-of-scope discoveries as cross-references.
- Tag evidence: [VERIFIED], [INFERRED], [UNVERIFIED].
- Track obligations per `obligation-ledger.md`. Walk ledger before
  returning output.
- If you discover something that fundamentally changes another sub-area's
  scope or invalidates the shared context map, flag it as URGENT in
  Cross-References. Do not silently absorb it.
- Return ONLY the structured output format. No preamble.
```

### Phase-Specific Output Formats

**Research sub-area return:**
```
## Findings: <SA_ID> — <sub-area title>

**Summary:** <2-3 sentences>

### Key Findings
1. <finding> [VERIFIED|INFERRED|UNVERIFIED]
   Evidence: <source>
2. ...

### Recommendations
- <recommendation with rationale>

### Dependency Contract
| Target SA | Assumption | Impact if Wrong | Evidence |
|-----------|------------|-----------------|----------|
| SA2 | <specific assumption> | <what breaks> | <source or UNVERIFIED> |
| — | No dependency | — | — |

Every other sub-area must appear in this table. Use "No dependency"
with justification for sub-areas with no interaction.

### Cross-References
- <things other sub-areas or the orchestrator should know>
- Prefix URGENT if it changes another sub-area's scope

### Blockers
- <anything preventing completion — empty if none>
```

**Design sub-area return:**
```
## Design: <SA_ID> — <sub-area title>

**Summary:** <2-3 sentences>

### Proposed Design
<module/component design — data flow, interfaces, key decisions>

### Interface Contracts
- <function signatures, class interfaces this sub-area exposes or consumes>
- <verified against actual source: YES/NO with file:line>

### Contract Compliance
- Adheres to interface skeleton: YES / NO
- Deviations (if any): <what and why — technical reality required it>

### Alternatives Considered
- <alternative>: <why rejected>

### Dependency Contract
| Target SA | Assumption | Impact if Wrong | Evidence |
|-----------|------------|-----------------|----------|
| SA1 | <specific assumption> | <what breaks> | <source or UNVERIFIED> |

### Cross-References
- <dependencies on other sub-areas, shared concerns>
- Prefix URGENT if it changes another sub-area's scope

### Blockers
- <empty if none>
```

**Plan sub-area return (codebase mapping):**
```
## Mapping: <SA_ID> — <sub-area title>

**Summary:** <2-3 sentences>

### Affected Files
| File | Changes needed | Risk | Lines (~) |
|------|---------------|------|-----------|
| path | description | LOW/MED/HIGH | est |

### Current Interfaces
- <function signatures, class APIs that will change — copied from source>

### Callers / Consumers
- <who calls the interfaces above — file:line>

### Test Coverage
- <existing tests that cover this area>

### Dependency Contract
| Target SA | Assumption | Impact if Wrong | Evidence |
|-----------|------------|-----------------|----------|
| SA2 | <specific assumption about their changes> | <what breaks> | <source> |

### Cross-References
- <how this module's changes affect other modules in the task>
- Prefix URGENT if it changes another sub-area's scope

### Risks
- <specific risks for this sub-area>
```

### Synthesis Rules

The orchestrator — not a subagent — writes the final artifact.

1. Read all structured returns (they're compact — ~1-2k tokens each).
2. **Dependency contract validation:** Walk each subagent's dependency
   table. Cross-check every assumption against the target sub-area's
   actual findings. Mismatches → investigate directly or dispatch
   targeted follow-up.
3. **Contract compliance check** (Design/Plan): Where subagents flagged
   deviations from the interface skeleton, decide: update the skeleton
   or rewrite the section to comply. Do not leave conflicting interfaces
   in the artifact.
4. **URGENT cross-reference triage:** Any URGENT flags → assess whether
   decomposition is still valid. If a discovery invalidates the shared
   context map, consider re-decomposition or sequencing.
5. **Gap check:** Walk the original task requirements. Is every
   requirement covered by at least one sub-area's findings? Missing
   coverage → orchestrator fills the gap inline or notes it.
6. **Integration layer** (Design/Plan): Write the integration section
   that connects sub-area outputs. Sub-areas design components;
   the orchestrator designs how they fit together.
7. Draft the artifact in the standard phase format. Sub-area structure
   may or may not be preserved — use whatever organization best serves
   the artifact's purpose.
8. **Dispatch integration verifier** (Layer 3) with: artifact + shared
   context map + all raw subagent outputs.
9. Resolve blocking findings per Remediation Protocol. Then proceed to
   review cycle.

### Model Routing

Subagents inherit the phase's model routing. Research/Design/Plan
subagents use Opus (judgment work). Override only if a sub-area is
purely mechanical (e.g., codebase mapping → Sonnet is sufficient).
Integration verifier always uses Opus.

### Cost Awareness

Decomposition shifts work from the orchestrator to subagents — the
sub-area research/design is not additional cost, it's transferred cost.
The net overhead is: shared context map + dependency contract validation
+ integration verifier + remediation loops.

Estimate ~1.5-2x total cost vs a hypothetical successful single-context
run. But if single context would fail (context exhaustion), the
comparison is decomposition vs. no output.

A 2-sub-area split is rarely worth it — the overhead approaches the
savings. 3+ sub-areas is the threshold.

### What NOT to Decompose

- Review cycles (already have their own fan-out via review panel)
- Execute steps (already dispatched to subagents per step)
- Learn phase (single-pass synthesis, reads artifacts not source)
- Prompt optimization (lightweight by design)
- Tightly coupled designs where sub-areas would need each other's
  output to make decisions
