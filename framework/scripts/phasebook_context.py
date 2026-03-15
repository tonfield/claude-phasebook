#!/usr/bin/env python3
"""Output phasebook context for Claude Code SessionStart hook.

Called by the SessionStart hook to inject task context into Claude's
conversation. Three modes based on session source:

  --mode=status         Startup/resume: folder counts summary
  --mode=phase-context  Post-/clear: task context from .phasebook-task
  --mode=compact-state  Post-/compact: execute state from state.md

Stdlib only — no third-party dependencies.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _find_phasebook_dir() -> Path | None:
    """Find phasebook/ or pipeline/ tasks directory."""
    for name in ("phasebook", "pipeline"):
        d = PROJECT_ROOT / name / "tasks"
        if d.is_dir():
            return d
    return None


PHASE_LETTERS = "RDPE"
PHASE_NAMES = ["research", "design", "plan", "execute"]


def parse_task_filename(name: str) -> dict | None:
    """Parse a task filename into its components."""
    if not name.endswith(".md"):
        return None
    if name.startswith("."):
        return None

    stem = name[:-3]

    match = re.fullmatch(r"([1-9])\.([RDPE+\-]{4})\.([a-z0-9][a-z0-9-]*)", stem)
    if match:
        priority_str, strip, slug = match.groups()
        done_ended = False
        for i, ch in enumerate(strip):
            if ch not in (PHASE_LETTERS[i], "+", "-"):
                return None
            if done_ended and ch == PHASE_LETTERS[i]:
                return None
            if ch != PHASE_LETTERS[i]:
                done_ended = True
        phase = "learn"
        for i, ch in enumerate(strip):
            if ch != PHASE_LETTERS[i]:
                phase = PHASE_NAMES[i]
                break
        return {
            "priority": int(priority_str),
            "strip": strip,
            "slug": slug,
            "phase": phase,
        }

    if re.fullmatch(r"[a-z0-9][a-z0-9-]*", stem):
        return {
            "priority": 0,
            "strip": "RDPE",
            "slug": stem,
            "phase": "done",
        }

    return None


def _count_folder(folder: Path) -> int:
    if not folder.is_dir():
        return 0
    return sum(
        1 for f in folder.iterdir()
        if f.is_file() and parse_task_filename(f.name) is not None
    )


def mode_status() -> None:
    tasks_dir = _find_phasebook_dir()
    if tasks_dir is None:
        return

    drafts = _count_folder(tasks_dir / "drafts")
    queue = _count_folder(tasks_dir / "queue")

    # Support both new and legacy folder names
    progress = _count_folder(tasks_dir / "progress") or _count_folder(tasks_dir / "processing")
    completed = _count_folder(tasks_dir / "completed") or _count_folder(tasks_dir / "done")

    print(f"[Phasebook] {drafts} in drafts, {queue} in queue, {progress} in progress, {completed} completed")


def mode_phase_context() -> None:
    cwd = Path(os.getcwd())

    # Try both marker names
    marker = None
    for name in (".phasebook-task", ".pipeline-task"):
        candidate = cwd / name
        if candidate.exists():
            marker = candidate
            break

    if marker is None:
        return

    try:
        slug = marker.read_text().strip()
    except OSError:
        return

    if not slug:
        return

    tasks_dir = _find_phasebook_dir()
    if tasks_dir is None:
        return

    # Search progress/ and processing/ folders
    for folder_name in ("progress", "processing"):
        progress_dir = tasks_dir / folder_name
        if not progress_dir.is_dir():
            continue
        for f in progress_dir.iterdir():
            if not f.is_file():
                continue
            parsed = parse_task_filename(f.name)
            if parsed and parsed["slug"] == slug:
                print("[Phasebook Context]")
                print(f"Task: {slug}")
                print(f"Phase: {parsed['phase']}")
                print(f"File: {f}")
                return


def mode_compact_state() -> None:
    cwd = Path(os.getcwd())
    for name in ("phasebook", "pipeline"):
        state_file = cwd / name / "state.md"
        if state_file.exists():
            try:
                content = state_file.read_text().strip()
            except OSError:
                continue
            if content:
                print(f"[Phasebook State — restored after compact]\n{content}")
            return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["status", "phase-context", "compact-state"],
        required=True,
    )
    args = parser.parse_args()

    if args.mode == "status":
        mode_status()
    elif args.mode == "phase-context":
        mode_phase_context()
    elif args.mode == "compact-state":
        mode_compact_state()


if __name__ == "__main__":
    main()
