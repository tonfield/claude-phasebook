# CLAUDE.md

Project context for Claude Code.

## Stack & Tooling

## Workflow

Phases: Research → Design → Plan → Execute → Learn
Each phase: draft → review → `>>` feedback → revise → approve → commit

## Commands

**Slash commands:**

| Command | Purpose |
|---|---|
| `/draft <task>` | Create task in drafts |
| `/phasebook` | Start processing queue |
| `/phasebook stop` | Stop after current phase |
| `/index` | Show task index |
| `/status <slug>` | Executive overview of a task |
| `/optimize <topic>` | Optimize a prompt |

## >> Feedback

Add `>>` comments to any `phasebook/` file. Claude reads intent from context (feedback, question, approval, or override) and resolves all markers in the next revision.

## Coding Conventions

## Architectural Invariants

## Key File Locations

## Design Constraints

## Testing

## Reference Data (read on demand)

Failure patterns, documentation map, known patterns, known gotchas, and
key decisions are in `.claude/references/reference-data.md`. Read when
needed for debugging, /learn updates, or prompt optimization context injection.
