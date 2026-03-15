---
name: optimize
description: Optimize a prompt, then execute it.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash, Task, WebFetch, WebSearch
user-invocable: true
---

## Process

1. Read the input. Silently improve it:
   - Add specificity where vague
   - Add structure where disorganized
   - Add context from CLAUDE.md and codebase where relevant
   - Remove ambiguity and noise
   - Surface intent (why this matters, not just what to do)
   - Add anti-goals where scope creep is likely
   - Make success criteria verifiable where vague
2. Show the optimized version in a quoted block
3. Immediately execute the optimized prompt — do not wait for confirmation

If the input is already clear and specific, say so and execute it as-is.

## Rules
- Always execute after optimizing. The user should never have to ask twice.
- Preserve the user's intent — optimize expression, not meaning.
- No external model calls for the optimization step itself.
