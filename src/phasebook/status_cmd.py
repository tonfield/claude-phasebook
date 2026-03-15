"""phasebook status — executive overview of a task."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from phasebook._helpers import (
    find_task,
    get_phasebook_dir,
    get_project_root,
)


def run_status(slug: str) -> None:
    project_root = get_project_root()
    if project_root is None:
        print("Error: not in a project directory.")
        sys.exit(1)

    # Try phasebook/ first, fall back to pipeline/
    pb_dir = get_phasebook_dir(project_root)
    if not pb_dir.is_dir():
        pb_dir = project_root / "pipeline"
    if not pb_dir.is_dir():
        print("No phasebook/ or pipeline/ directory found.")
        sys.exit(1)

    tasks_dir = pb_dir / "tasks"
    result = find_task(slug, tasks_dir)
    if result is None:
        # Also try legacy folder names
        result = _find_task_legacy(slug, tasks_dir)

    if result is None:
        print(f"No task found for '{slug}'.")
        sys.exit(1)

    task_path, parsed, folder = result

    # Read task file
    try:
        content = task_path.read_text()
    except OSError:
        content = ""

    # Extract description (first paragraph after # slug)
    description = _extract_description(content)

    # Header
    print(f"## Status: {slug}")
    print()
    if description:
        print(f"**{description}**")
        print()

    # Info table
    print("| Field | Value |")
    print("|-------|-------|")
    print(f"| Location | {folder} |")
    if parsed["priority"] > 0:
        print(f"| Priority | {parsed['priority']} |")
        print(f"| Strip | `{parsed['strip']}` |")
    phase = parsed["phase"]
    if phase == "done":
        print("| Next phase | Done |")
    elif phase == "learn":
        print("| Next phase | Learn |")
    else:
        print(f"| Next phase | {phase.capitalize()} |")

    # Token cost
    cost_data = _read_cost(pb_dir, slug)
    if cost_data:
        cost = cost_data.get("total_cost", 0)
        sessions = cost_data.get("total_sessions", 0)
        print(f"| Cost | ${cost:.2f} ({sessions} sessions) |")

    # Timeline
    artifacts = _find_artifacts(pb_dir, slug)
    if artifacts:
        print()
        print("### Timeline")
        print()
        print("| Phase | Rounds | Key Outcome |")
        print("|-------|--------|-------------|")
        for phase_name, art_path, rounds in artifacts:
            summary = _extract_summary(art_path, phase_name)
            print(f"| {phase_name.capitalize()} | {rounds} | {summary} |")

    # Review highlights
    reviews = list((pb_dir / "reviews").glob(f"*{slug}*.md")) if (pb_dir / "reviews").is_dir() else []
    if reviews:
        print()
        print("### Review Highlights")
        print()
        print(f"**{len(reviews)} review file(s)** found")

    # Outstanding
    print()
    print("### Outstanding")
    print()
    markers = content.count(">>")
    actions = "[!ACTION]" in content
    if markers > 0 or actions:
        if markers:
            print(f"- {markers} unresolved >> marker(s)")
        if actions:
            print("- [!ACTION] block present")
    elif phase == "done":
        print("Complete — no outstanding items.")
    else:
        print(f"Next: {phase}")


def _find_task_legacy(slug: str, tasks_dir: Path) -> tuple[Path, dict, str] | None:
    """Search legacy folder names (processing, done, archive)."""
    from phasebook._helpers import parse_task_filename

    legacy = {"processing": "progress", "done": "completed", "archive": "archived"}
    for old_name, new_name in legacy.items():
        folder_path = tasks_dir / old_name
        if not folder_path.is_dir():
            continue
        for f in sorted(folder_path.iterdir()):
            if not f.is_file():
                continue
            parsed = parse_task_filename(f.name)
            if parsed and parsed["slug"] == slug:
                return f, parsed, old_name
    return None


def _extract_description(content: str) -> str:
    """Extract first sentence of description from task file."""
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("# "):
            # Get next non-empty line
            for j in range(i + 1, min(i + 5, len(lines))):
                text = lines[j].strip()
                if text and not text.startswith("#") and not text.startswith("**Completed"):
                    # First sentence
                    sentence = text.split(". ")[0]
                    if not sentence.endswith("."):
                        sentence += "."
                    return sentence
    return ""


def _read_cost(pb_dir: Path, slug: str) -> dict | None:
    """Read token sidecar for a task."""
    for name in (f"{slug}.json",):
        path = pb_dir / "tokens" / name
        if path.exists():
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
    return None


def _find_artifacts(pb_dir: Path, slug: str) -> list[tuple[str, Path, str]]:
    """Find phase artifacts for a task, return (phase_name, path, rounds_str)."""
    results = []
    dirs = [
        ("research", "research"),
        ("design", "designs"),
        ("plan", "plans"),
        ("execute", "executions"),
        ("learn", "learnings"),
    ]
    for phase_name, dir_name in dirs:
        art_dir = pb_dir / dir_name
        if not art_dir.is_dir():
            continue
        matches = sorted(art_dir.glob(f"*{slug}*"))
        if matches:
            path = matches[-1]
            rounds = _extract_round_str(path)
            results.append((phase_name, path, rounds))
    return results


def _extract_round_str(path: Path) -> str:
    """Extract round number from artifact."""
    if path.is_dir():
        return "*"
    try:
        text = path.read_text()[:500]
    except OSError:
        return "*"

    for pattern in [r"\(R(\d+)\)", r"Round\s+(\d+)", r"(\d+)\s+rounds?"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return "*"


def _extract_summary(path: Path, phase: str) -> str:
    """Extract a one-line summary from an artifact."""
    if path.is_dir():
        return "See execution logs"
    try:
        text = path.read_text()[:2000]
    except OSError:
        return ""

    # Look for objective or summary line
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("**Objective:"):
            return line.removeprefix("**Objective:").strip().rstrip("*")
        if line.startswith("## Summary"):
            continue
        if phase == "plan" and "steps" in line.lower():
            return line.strip("#").strip()

    return ""
