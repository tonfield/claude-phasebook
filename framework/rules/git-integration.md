---
description: Git commit protocol for all phases
---

## Commit Protocol

Every phase commits on approval. Formats:

research(<topic>): approved brief
design(<topic>): approved architecture
plan(<topic>): approved plan with N steps
step(<topic>): N - <description>
learn(<topic>): system updated

Atomic commits. Stage only relevant files.
Commit gating per `strip-semantics.md`: `-` positions wait for human
approval, `+` positions commit automatically after review passes clean.

## Pathspec Commit Protocol

Workers commit on `main` using pathspec:

```
git add <specific-files> && git commit -m "<message>"
```

Never `git add .` or `git add -A`. Stage only the current task's
slug-namespaced artifacts and task file.

If commit fails (index lock, HEAD moved), retry once.
No remote push during phasebook. User pushes when ready.
