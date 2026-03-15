---
name: review
description: Run external + internal review panel on an artifact via .claude/scripts/external_review.py.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, Agent
user-invocable: true
---

## Usage

```bash
python3 .claude/scripts/external_review.py <artifact> --mode <MODE> --risk <LEVEL> [--files <context>...] -v
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `<artifact>` | Yes | Primary file to review |
| `--mode` | Yes | `review`, `code`, or `challenge` |
| `--risk` | Yes (except challenge) | `LOW`, `MEDIUM`, or `HIGH` |
| `--files` | No | Additional context files |
| `--prompt` | No | Custom prompt (overrides mode prompt, skips structured output) |
| `-v` | No | Verbose logging to stderr |

### Modes

| Mode | Use |
|------|-----|
| `review` | Research, Design, Plan phases |
| `code` | Execute phase (code review) |
| `challenge` | Adversarial challenge gate (fixed model, no `--risk`) |

### Risk Levels

| Risk | Scope |
|------|-------|
| LOW | Single module, clear scope, no shared state |
| MEDIUM | Multi-module, new interfaces, integration claims. **Default when uncertain** |
| HIGH | Money path, broker API, shared state, invariant-adjacent |

Each tier progressively adds more models, cheapest first.
Model roster: `.claude/scripts/review_models.json`

---

## Output

Script returns JSON to stdout. Logs go to stderr.

```json
{
  "reviews": [
    {
      "model_alias": "gemini3.1",
      "model_name": "gemini-3.1-pro-preview",
      "provider": "gemini",
      "response": "## Grade: B+\n## BLOCKING Findings\n...",
      "error": null,
      "duration_s": 42.3,
      "tokens": {"input": 5000, "output": 3000}
    }
  ],
  "skipped": [{"alias": "glm5", "reason": "Won't fit: ~50000 > 45000 budget"}],
  "files": [{"path": "/path/to/artifact.md", "tokens_est": 5000}],
  "config": {"mode": "review", "risk": "MEDIUM", "models_succeeded": 4, "models_failed": 1},
  "total_duration_s": 85.2
}
```

**Parsing**: For each entry in `reviews[]`:
- `error` non-null → model failed, continue with successes
- `response` contains structured sections: `## Grade:`, `## BLOCKING Findings`,
  `## ADVISORY Findings`, `## Summary`
- Models may not follow the format — fall back to extracting findings from prose
- If ALL models failed → abort the review

---

## Step 1: External Reviews

Run the script with `--mode` and `--risk`. All models call in parallel.

**Design / Plan integration context**: pass source snippets via `--files`.
**Execute scope briefing**: use `--prompt` to specify scope and line ranges.

---

## Step 2: Internal Panel

| Risk | Internal Panel |
|------|---------------|
| LOW (Design/Plan) | Codebase Verification only |
| LOW (other) | Skip |
| MEDIUM / HIGH | Full panel per `.claude/rules/review-panel-roles.md` |

Run internal and external in parallel where possible.

---

## Step 3: Synthesize Findings

Extract each model's artifact grade from `## Grade:` and findings from
`## BLOCKING Findings` / `## ADVISORY Findings`. Classify as BLOCKING or ADVISORY.
Flag cross-model and external vs internal disagreements.

### Per Reviewer

```markdown
#### <Name> — <Type>

| # | Severity | Finding | Verdict | Resolution |
|---|----------|---------|---------|------------|
| 1 | BLOCKING | <description> | Accepted | <resolution> |
| 2 | ADVISORY | <description> | Rejected | `BY_DESIGN` |

N findings · B blocking · A accepted · R rejected · Grade: X
```

**Rejection codes:** `PRE_EXISTING` (out of scope), `OUT_OF_SCOPE` (future work),
`BY_DESIGN` (intentional), `ALREADY_ADDRESSED` (fixed this round), `FALSE_PREMISE` (misread).

### Per Round

```markdown
| Tier | Reviewers | Findings | Blocking | Accepted | Rejected |
|------|-----------|----------|----------|----------|----------|
| External | <models> | N | B | A | R |
| Internal | <roles> | N | B | A | R |
| **Total** | | **N** | **B** | **A** | **R** |

Fix cycles triggered: <list or "None">
Cyclical restart: Yes / No
```

End with: `EXTERNAL — Models: N/K | Grade: <per model> | BLOCKING: B | ADVISORY: A`

If the same finding recurs across rounds, flag to human.

---

## Step 4: Challenge Gate (HIGH risk, or both passes clean)

```bash
python3 .claude/scripts/external_review.py <artifact> --mode challenge -v
```

No `--risk` needed. Blocking findings → treat as Pass 2 (fix → restart check).

---

## Step 5: Determine Outcome

**BLOCKING findings** → signal cyclical restart or report actions.
**No BLOCKING** → report clean with ADVISORY summary.

---

## Output Location

- Phasebook: `phasebook/reviews/<date>-<HHMM>-<slug>[-step<N>]-r<R>.md`
- Standalone: display inline

Follow the synthesis format in Step 3 above.
