# phasebook

Phased workflow framework for Claude Code.

## Install

```bash
pip install -e .
```

## Usage

```bash
# Initialize a project
phasebook init

# Show index of all tasks
phasebook index

# Task status
phasebook status <slug>

# Task management
phasebook submit <slug>     # drafts/ → queue/
phasebook approve <slug>    # review/ → queue/
phasebook pause <slug>      # queue/ → drafts/
phasebook archive <slug>    # completed/ → archived/

# Validation
phasebook lint

# Token costs
phasebook costs

# Update framework files
phasebook update --check
phasebook update
```

## Claude Code slash commands

| Command | Purpose |
|---|---|
| `/draft <task>` | Create task in drafts |
| `/phasebook` | Start processing queue |
| `/phasebook stop` | Stop after current phase |
| `/index` | Show task index |
| `/status <slug>` | Executive overview of a task |
| `/review` | Run external review panel |
| `/optimize <topic>` | Optimize a prompt |
