---
description: Handles >> feedback markers, QA sections, delta blocks, and action items in artifacts
---

## >> Marker Protocol

Before producing any new artifact version:
1. Find all lines containing `>>`
2. Interpret from context: feedback -> incorporate; question -> answer;
   approval -> keep; override -> accept and log
3. Remove resolved `>>` markers
4. List addressed items in review summary

## Q&A Sections

When `>>` asks a question, answer in TWO places:
1. In the normal document text
2. In a visible block near the question:

```
> [!QA R<N>]
> **Q:** <question>
> **A:** <answer with evidence>
```

- Split compound questions into separate pairs
- Tag with round number `R<N>`
- REMOVED before next phase, NOT between review rounds

## Delta Blocks

After revising, add `[!DELTA]` after the status line:

```
> [!DELTA] Round N -> Round N+1
>
> **Modified:**
> - Section 3d: Rewrote ISK tax model
>
> **Added:**
> - Section 3g: Decision framework
>
> **Removed:**
> - Section 2f: XSP analysis
```

- Accumulate: each revision adds a new block, previous blocks preserved
- Remove all delta blocks before next phase, NOT between review rounds

## Action Items

When human input is needed, add at BEGINNING of artifact (after status + DELTA):

```
> [!ACTION]
> **Blocking:**
> - [ ] <decision needed>
>
> **Optional:**
> - [ ] <would improve next round>
```

One per artifact. Remove completed items. Remove block when empty.
