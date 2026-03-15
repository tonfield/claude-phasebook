"""phasebook index — show task index across all folders."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from phasebook._helpers import (
    TASK_FOLDERS,
    find_lost_and_found,
    get_phasebook_dir,
    get_project_root,
    scan_folder,
)

# Also support legacy pipeline/ layout for ibkr_bot compatibility
LEGACY_FOLDER_MAP = {
    "progress": "processing",
    "completed": "done",
    "archived": "archive",
}

ARTIFACT_PHASE_MAP = {
    "research": "R",
    "designs": "D",
    "plans": "P",
    "executions": "E",
}


def run_index() -> None:
    project_root = get_project_root()
    if project_root is None:
        print("Error: not in a project directory.")
        sys.exit(1)

    # Try phasebook/ first, fall back to pipeline/
    pb_dir = get_phasebook_dir(project_root)
    if not pb_dir.is_dir():
        pb_dir = project_root / "pipeline"
    if not pb_dir.is_dir():
        print("No phasebook/ or pipeline/ directory found. Run 'phasebook init' first.")
        sys.exit(1)

    tasks_dir = pb_dir / "tasks"
    if not tasks_dir.is_dir():
        print(f"No tasks directory found at {tasks_dir}")
        sys.exit(1)

    # Discover which folder names are actually on disk
    folder_map = _discover_folders(tasks_dir)

    # Read token data
    token_usage = _read_token_usage(pb_dir)
    token_sidecars = _read_token_sidecars(pb_dir)

    sections: list[str] = []
    all_lost: list[dict] = []

    # Display order: progress → queue → review → drafts → completed → archived
    display_order = ["progress", "queue", "review", "drafts", "completed", "archived"]

    for canonical in display_order:
        actual_folder = folder_map.get(canonical)
        if actual_folder is None:
            continue
        folder_path = tasks_dir / actual_folder

        tasks = scan_folder(folder_path)
        lost = find_lost_and_found(folder_path, actual_folder)
        all_lost.extend(lost)

        if not tasks:
            continue

        display_name = canonical.capitalize()
        lines = [f"### {display_name} ({len(tasks)})", ""]

        if canonical in ("completed", "archived"):
            lines.append("| Task | Rounds | Cost |")
            lines.append("|------|--------|------|")
            for path, parsed in tasks:
                slug = parsed["slug"]
                rounds = _get_rounds(pb_dir, slug)
                cost = _get_cost(slug, token_sidecars)
                lines.append(f"| {slug} | {rounds} | {cost} |")
        else:
            lines.append("| Priority | Status | Phase | Task | Rounds | Cost |")
            lines.append("|----------|--------|-------|------|--------|------|")
            for path, parsed in tasks:
                slug = parsed["slug"]
                rounds = _get_rounds(pb_dir, slug)
                cost = _get_cost(slug, token_sidecars)
                lines.append(
                    f"| {parsed['priority']} | {parsed['strip']} | {parsed['phase']} "
                    f"| {slug} | {rounds} | {cost} |"
                )

        sections.append("\n".join(lines))

    # Print
    print("## Phasebook")
    print()
    if sections:
        print("\n\n".join(sections))
    else:
        print("No tasks found.")

    # Lost & found
    if all_lost:
        print()
        print(f"### Lost & Found ({len(all_lost)})")
        print()
        print(f"> **Warning:** {len(all_lost)} file(s) don't match naming convention.")
        print()
        print("| Folder | File | Issue |")
        print("|--------|------|-------|")
        for item in all_lost:
            print(f"| {item['folder']} | {item['file']} | {item['issue']} |")

    # Commands
    print()
    print("## Commands")
    print()
    print("| Command | Action |")
    print("|---------|--------|")
    print("| `/draft <task>` | Create task in drafts |")
    print("| `/phasebook` | Start processing queue |")
    print("| `/phasebook stop` | Stop after current phase |")
    print("| `/index` | This view |")
    print()
    print("| File operation | Effect |")
    print("|----------------|--------|")
    print("| `phasebook submit <slug>` | drafts/ → queue/ |")
    print("| `phasebook approve <slug>` | review/ → queue/ |")
    print("| `phasebook pause <slug>` | queue/ → drafts/ |")
    print("| `phasebook archive <slug>` | completed/ → archived/ |")

    # Token summary
    _print_token_summary(token_sidecars, token_usage)

    # Suggestion
    _print_suggestion(folder_map, tasks_dir)


def _discover_folders(tasks_dir: Path) -> dict[str, str]:
    """Map canonical folder names to actual on-disk names.

    Supports both new names (progress, completed, archived) and legacy
    (processing, done, archive).
    """
    result = {}
    for canonical in TASK_FOLDERS:
        if (tasks_dir / canonical).is_dir():
            result[canonical] = canonical
        else:
            legacy = LEGACY_FOLDER_MAP.get(canonical)
            if legacy and (tasks_dir / legacy).is_dir():
                result[canonical] = legacy
    return result


def _read_token_usage(pb_dir: Path) -> dict:
    """Read lifetime token-usage.json."""
    for name in ("token-usage.json",):
        path = pb_dir / name
        if path.exists():
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
    return {}


def _read_token_sidecars(pb_dir: Path) -> dict[str, dict]:
    """Read all per-task token sidecar files."""
    result = {}
    tokens_dir = pb_dir / "tokens"
    if not tokens_dir.is_dir():
        return result
    for f in sorted(tokens_dir.iterdir()):
        if f.suffix == ".json" and f.is_file():
            try:
                data = json.loads(f.read_text())
                result[f.stem] = data
            except (json.JSONDecodeError, OSError):
                pass
    return result


def _get_rounds(pb_dir: Path, slug: str) -> str:
    """Build rounds string from artifact directories."""
    parts = []
    for dir_name, letter in ARTIFACT_PHASE_MAP.items():
        art_dir = pb_dir / dir_name
        if not art_dir.is_dir():
            parts.append("·")
            continue

        # Find matching artifacts
        matches = list(art_dir.glob(f"*{slug}*"))
        if not matches:
            parts.append("·")
            continue

        # Read first artifact for round info
        round_num = _extract_round(matches[-1])  # latest
        parts.append(str(min(round_num, 9)) if round_num > 0 else "*")

    return "/".join(parts)


def _extract_round(path: Path) -> int:
    """Extract round number from artifact's first lines."""
    if path.is_dir():
        return -1  # exists but can't read round
    try:
        text = path.read_text()[:500]
    except OSError:
        return -1

    # Pattern: (R<N>) or Round <N> or <N> rounds
    for pattern in [r"\(R(\d+)\)", r"Round\s+(\d+)", r"(\d+)\s+rounds?"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return int(m.group(1))

    return -1  # artifact exists, rounds unknown → show *


def _get_cost(slug: str, sidecars: dict[str, dict]) -> str:
    """Get cost string for a task."""
    data = sidecars.get(slug)
    if not data:
        return ""
    cost = data.get("total_cost", 0)
    if cost:
        return f"{cost:.2f}"
    return ""


def _print_token_summary(sidecars: dict[str, dict], usage: dict) -> None:
    """Print token cost summary."""
    if not sidecars and not usage:
        return

    print()
    print("## Tokens (est.)")
    print()
    print("| Task | Cost | Sessions |")
    print("|------|------|----------|")

    sorted_tasks = sorted(sidecars.items(), key=lambda x: x[1].get("total_cost", 0), reverse=True)
    for slug, data in sorted_tasks:
        cost = data.get("total_cost", 0)
        sessions = data.get("total_sessions", 0)
        print(f"| {slug} | {cost:.2f} | {sessions} |")

    totals = usage.get("totals", {})
    if totals:
        total_cost = totals.get("cost", 0)
        total_sessions = totals.get("sessions", 0)
        print(f"| **Lifetime** | **{total_cost:.2f}** | **{total_sessions}** |")


def _print_suggestion(folder_map: dict[str, str], tasks_dir: Path) -> None:
    """Print actionable suggestion."""
    counts = {}
    for canonical, actual in folder_map.items():
        folder_path = tasks_dir / actual
        tasks = scan_folder(folder_path)
        counts[canonical] = len(tasks)

    print()
    if counts.get("queue", 0) > 0:
        print(f"---\nSuggestion: {counts['queue']} tasks in queue. `/phasebook` to start processing.")
    elif counts.get("review", 0) > 0:
        print(f"---\nSuggestion: {counts['review']} tasks awaiting review. `phasebook approve <slug>` to approve.")
    elif counts.get("drafts", 0) > 0:
        print(f"---\nSuggestion: {counts['drafts']} tasks in drafts. `phasebook submit <slug>` when ready.")
    elif counts.get("progress", 0) > 0:
        print(f"---\nSuggestion: {counts['progress']} tasks being processed.")
    else:
        print("---\nSuggestion: `/draft <task>` to create a task.")
