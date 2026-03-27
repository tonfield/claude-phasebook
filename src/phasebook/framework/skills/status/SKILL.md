---
name: status
description: Executive overview of a specific task's full history and current state.
allowed-tools: Bash
user-invocable: true
---

Run `phasebook status <slug>` (slug from arguments) and display the output to the user.
If no slug provided, ask the user which task they want to see.
If the command is not found, tell the user to install phasebook: `pip install -e ~/projects/phasebook`
