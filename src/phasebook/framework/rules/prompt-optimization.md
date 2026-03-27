## Prompt Optimization Protocol

Enrich a raw topic before proceeding with the phase. Replaces the raw
topic for all subsequent steps. If it adds nothing, proceed unchanged.

### Output Format

Include only non-empty sections. Omit sections with no content.

```
## Enriched Prompt: <topic>

**Objective:** <1-2 sentences>
**Sub-questions:** <numbered list>
**Relevant Context:** <Invariants, Gotchas, Patterns, Decisions by reference number>
**Prior Art:** <phasebook paths with relation>
**Constraints:** <applicable rules>
**Success Criteria:** <what done looks like>
**Phase-Specific Framing:** <see below>
```

### Universal Strategies

Apply all four. Skip any producing nothing.

**1. Context Injection**
Scan CLAUDE.md for relevant Invariants, Design Constraints, Extension Points.
Scan `.claude/references/reference-data.md` for relevant Gotchas, Patterns,
Decisions, Failure Patterns. Match by file paths, module names, concept names.

**2. Ambiguity Detection**
Flag vague input (no clear verb/outcome, nonexistent references,
multiple interpretations). Proceed with best interpretation, note assumption.

**3. Prior Art & Concurrent Work**
Search phasebook/research/, designs/, plans/, archived/, learnings/.
Scan phasebook/tasks/inbox/, queue/, progress/, completed/ for related task files.
Check `progress/` and recent `completed/` for tasks touching the same modules —
concurrent work may have changed interfaces, added invariants, or updated
conventions. Flag as context.

**4. Constraint Surfacing**
Extract from CLAUDE.md: Design Constraints, Editing Checklist, Testing
conventions, Extension Points.

### Phase-Specific Strategies

| Phase | Focus |
|-------|-------|
| Research | 3-5 sub-questions, evidence standards, external sources. "What do we need to KNOW before we can DESIGN?" |
| Design | Requirements from research, design dimensions, affected files. "What architectural decisions does this require?" |
| Plan | Scope from design, affected files (Glob/Grep), risk levels, dependencies. "Minimal sequence of verifiable steps?" |
| Execute | Current step context, coding conventions, applicable gotchas. "What conventions and gotchas apply to THIS step?" |
| Learn | All artifacts to review, CLAUDE.md sections to update, recurring findings. "What should persist?" |

### Task File Integration

Find the task file by slug across inbox/, queue/, progress/, completed/:
- Search `phasebook/tasks/{inbox,queue,progress,completed}/*.<slug>.md`
- Read Description, Requirements, References, Data for context
- Update "Enriched Context" section (accumulates across phases)
- Never modify human-written sections

### Scope Assessment

After enrichment, assess whether the phase needs decomposition per
`task-decomposition.md`. Signals: 3+ independent sub-areas, context
likely to exceed single window. If decomposition is needed, it runs
after prompt optimization and before drafting.

### Rules

- Lightweight — at most 30 seconds
- No external model calls
- No new files (exception: Enriched Context in existing task file)
