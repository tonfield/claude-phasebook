# phasebook

A phased workflow framework for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Structures AI-driven work into five phases — **Research, Design, Plan, Execute, Learn** — with built-in review cycles, external model reviews, and task tracking.

## What it does

Phasebook turns Claude Code into a disciplined engineering workflow. Each task moves through phases, with review gates between them. You control the pace: auto-advance phases you trust, pause for review on phases that need human judgment.

```
Research → Design → Plan → Execute → Learn
```

**Key features:**
- Task queue with priority and per-phase review gates
- Multi-model external review panel (Gemini, GPT, Grok, etc.)
- Internal review panel with specialist roles
- Obligation ledger for tracking claims and assumptions
- Token cost tracking per task and per phase
- Multiple workers can process tasks concurrently on main

## Install

```bash
git clone <repo-url> ~/projects/phasebook
cd ~/projects/phasebook
pip install -e .
```

## Quick start

```bash
# In your project directory
cd ~/projects/my-project
git init  # if not already a git repo

# Initialize phasebook
phasebook init

# Create your first task (in Claude Code)
/draft add user authentication

# View the task index
/index

# Start processing
/phasebook
```

## How it works

### Tasks

A task is a markdown file that moves through folders:

```
phasebook/tasks/
├── drafts/       ← create and edit tasks here
├── queue/        ← ready for processing
├── progress/     ← worker is actively processing
├── review/       ← waiting for human review
├── completed/    ← all phases done
└── archived/     ← long-term storage
```

Task filenames encode metadata: `<priority>.<strip>.<slug>.md`

- **Priority** (1-9): lower = processed first
- **Strip** (4 chars): controls per-phase review gates
- **Slug**: kebab-case identifier

Example: `1.--++.add-auth.md` — priority 1, review Research and Design, auto-advance Plan and Execute.

### The strip

The strip is 4 characters, one per phase (R D P E). Each position is either:

| Char | Meaning |
|------|---------|
| `-` | Pause for human review after this phase |
| `+` | Auto-advance to next phase |
| `R/D/P/E` | Phase completed |

Both `-` and `+` get the same review cycle. The difference is whether a human gates the transition.

Common patterns:
```
----    Review everything (safest)
--++    Review research + design, auto plan + execute
++++    Full auto (use with caution)
+++-    Auto early phases, review execute
```

### Phases

| Phase | Purpose | Artifact |
|-------|---------|----------|
| **Research** | Investigate, gather evidence | `phasebook/research/<date>-<slug>.md` |
| **Design** | Architecture, alternatives, decisions | `phasebook/designs/<date>-<slug>.md` |
| **Plan** | Step-by-step implementation plan | `phasebook/plans/<date>-<slug>.md` |
| **Execute** | Implement code per plan steps | Code changes + `phasebook/executions/` |
| **Learn** | Update system knowledge, docs | `phasebook/learnings/<date>-<slug>.md` |

### Review cycle

Every phase goes through a review cycle before completion:

1. **Pass 1** — External models (via `external_review.py`) + internal specialist panel
2. **Pass 2** — Gap analysis + self-review + invariant sweep
3. **Challenge gate** — Adversarial review (HIGH risk or both passes clean)
4. Fix cycles restart the sequence until clean

Review depth scales with risk level (LOW / MEDIUM / HIGH).

### Feedback

Add `>>` to any file in `phasebook/` to leave feedback. The worker reads intent from context — feedback, question, approval, or override — and resolves markers in the next revision.

```markdown
>> This assumption about the API seems wrong, check the docs
>> Why not use WebSocket instead of polling?
>> Approved, move forward
```

## CLI commands

```bash
# Project setup
phasebook init              # Initialize phasebook in current project
phasebook update            # Update managed framework files to latest version
phasebook update --check    # Dry-run: show what would change

# Task index and status
phasebook index             # Overview of all tasks across folders
phasebook status <slug>     # Detailed status of a specific task

# Task management
phasebook submit <slug>     # drafts/ → queue/
phasebook approve <slug>    # review/ → queue/
phasebook pause <slug>      # queue/ → drafts/
phasebook archive <slug>    # completed/ → archived/
phasebook reprioritize <slug> <N>   # Change priority (1-9)
phasebook strip <slug> <strip>      # Change strip (e.g. --++)

# Validation and costs
phasebook lint              # Validate filenames, structure, find orphans
phasebook costs             # Token usage breakdown by task and phase
```

## Claude Code slash commands

Use these inside Claude Code conversations:

| Command | Purpose |
|---|---|
| `/draft <task>` | Create a task with smart enrichment and review |
| `/phasebook` | Start the worker loop — processes tasks from queue |
| `/phasebook stop` | Stop the worker after the current phase completes |
| `/index` | Show the task index (calls `phasebook index`) |
| `/status <slug>` | Executive overview of a task (calls `phasebook status`) |
| `/review` | Run external + internal review panel on an artifact |
| `/optimize <topic>` | Optimize a prompt, then execute it |

## External reviews

Phasebook can call external AI models to review artifacts. Configure models in `.claude/scripts/review_models.json` and API keys in `.claude/scripts/api_keys.json` (gitignored).

Supported providers:
- **Gemini** (native SDK with thinking)
- **OpenAI-compatible** (Kilocode/OpenRouter, Z.AI, or any compatible endpoint)

```bash
# Install review dependencies
pip install -e ".[review]"

# Check available models
python3 .claude/scripts/external_review.py --list-models
```

## Project structure after `phasebook init`

```
your-project/
├── CLAUDE.md                    ← Project context (you edit this)
├── .claude/
│   ├── rules/                   ← 10 behavioral rules (managed)
│   ├── phases/                  ← 5 phase instructions (managed)
│   ├── agents/                  ← 2 review agents (managed)
│   ├── skills/                  ← 6 slash commands (managed)
│   ├── scripts/                 ← review, notify, context, tokens (managed)
│   ├── references/
│   │   └── reference-data.md    ← Patterns, gotchas, decisions (you edit)
│   ├── settings.json            ← Hooks config (you edit)
│   └── .phasebook-version
└── phasebook/
    ├── tasks/
    │   ├── drafts/
    │   ├── queue/
    │   ├── progress/
    │   ├── review/
    │   ├── completed/
    │   └── archived/
    ├── research/
    ├── designs/
    ├── plans/
    ├── executions/
    ├── learnings/
    ├── reviews/
    ├── obligations/
    ├── tokens/                  ← Per-task cost tracking
    └── token-usage.json         ← Lifetime cost aggregate
```

**Managed files** are overwritten by `phasebook update`. **User files** (CLAUDE.md, reference-data.md, settings.json, review_models.json, api_keys.json) are never touched by updates.

## Updating

When phasebook is updated, run `phasebook update` in your project to get the latest framework files:

```bash
cd ~/projects/phasebook && git pull
cd ~/projects/my-project
phasebook update --check   # See what changed
phasebook update           # Apply updates
```

## Requirements

- Python 3.11+
- Git
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- Optional: `openai` and `google-genai` packages for external reviews
