"""phasebook lint — validate task files and project structure."""

from __future__ import annotations

import sys
from pathlib import Path

from phasebook._helpers import (
    PHASE_LETTERS,
    TASK_FOLDERS,
    find_lost_and_found,
    get_phasebook_dir,
    get_project_root,
    parse_task_filename,
)

LEGACY_FOLDER_MAP = {
    "processing": "progress",
    "done": "completed",
    "archive": "archived",
}


def run_lint() -> None:
    project_root = get_project_root()
    if project_root is None:
        print("Error: not in a project directory.")
        sys.exit(1)

    pb_dir = get_phasebook_dir(project_root)
    legacy = False
    if not pb_dir.is_dir():
        pb_dir = project_root / "pipeline"
        legacy = True
    if not pb_dir.is_dir():
        print("No phasebook/ or pipeline/ directory found.")
        sys.exit(1)

    tasks_dir = pb_dir / "tasks"
    issues: list[str] = []
    warnings: list[str] = []

    # 1. Check folder structure
    if legacy:
        warnings.append("Using legacy 'pipeline/' directory name (expected 'phasebook/')")

    for canonical in TASK_FOLDERS:
        folder_path = tasks_dir / canonical
        if folder_path.is_dir():
            continue
        # Check legacy name
        legacy_name = {"progress": "processing", "completed": "done", "archived": "archive"}.get(canonical)
        if legacy_name and (tasks_dir / legacy_name).is_dir():
            warnings.append(f"Legacy folder name: {legacy_name}/ (expected {canonical}/)")
        else:
            if not legacy:
                warnings.append(f"Missing folder: tasks/{canonical}/")

    # 2. Validate all task filenames
    all_lost: list[dict] = []
    all_slugs: dict[str, list[str]] = {}  # slug → [folders]

    for folder_name in _get_actual_folders(tasks_dir):
        folder_path = tasks_dir / folder_name
        if not folder_path.is_dir():
            continue

        lost = find_lost_and_found(folder_path, folder_name)
        all_lost.extend(lost)

        for f in sorted(folder_path.iterdir()):
            if not f.is_file() or f.name.startswith("."):
                continue
            parsed = parse_task_filename(f.name)
            if parsed:
                slug = parsed["slug"]
                if slug not in all_slugs:
                    all_slugs[slug] = []
                all_slugs[slug].append(folder_name)

                # Check strip consistency
                strip = parsed["strip"]
                done_ended = False
                for i, ch in enumerate(strip):
                    if ch == PHASE_LETTERS[i]:
                        if done_ended:
                            issues.append(
                                f"{f.name}: gap in strip — '{PHASE_LETTERS[i]}' after pending at position {i}"
                            )
                    else:
                        done_ended = True

    # 3. Check for duplicate slugs across folders
    for slug, folders in all_slugs.items():
        if len(folders) > 1:
            issues.append(f"Duplicate slug '{slug}' in: {', '.join(folders)}")

    # 4. Check for orphaned artifacts
    artifact_dirs = ["research", "designs", "plans", "executions", "learnings"]
    for dir_name in artifact_dirs:
        art_dir = pb_dir / dir_name
        if not art_dir.is_dir():
            continue
        for f in sorted(art_dir.iterdir()):
            if f.name.startswith("."):
                continue
            # Extract slug from artifact name (typically *-<slug>.md)
            name = f.stem if f.is_file() else f.name
            matched = False
            for slug in all_slugs:
                if slug in name:
                    matched = True
                    break
            if not matched:
                warnings.append(f"Orphaned artifact: {dir_name}/{f.name}")

    # 5. Check for orphaned token sidecars
    tokens_dir = pb_dir / "tokens"
    if tokens_dir.is_dir():
        for f in sorted(tokens_dir.iterdir()):
            if f.suffix == ".json" and f.is_file():
                if f.stem not in all_slugs:
                    warnings.append(f"Orphaned token sidecar: tokens/{f.name}")

    # 6. Check for stale signal files
    for signal in (".phasebook-stop", ".pipeline-stop"):
        if (project_root / signal).exists():
            warnings.append(f"Stale stop signal: {signal} exists")
    for marker in (".phasebook-task", ".pipeline-task"):
        if (project_root / marker).exists():
            warnings.append(f"Stale task marker: {marker} exists")

    # Report
    if not issues and not warnings and not all_lost:
        print("Lint: all clean.")
        return

    if issues:
        print(f"Issues ({len(issues)}):")
        for issue in issues:
            print(f"  ERROR: {issue}")

    if all_lost:
        print(f"\nLost & Found ({len(all_lost)}):")
        for item in all_lost:
            print(f"  WARN: {item['folder']}/{item['file']} — {item['issue']}")

    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  WARN: {w}")

    if issues:
        sys.exit(1)


def _get_actual_folders(tasks_dir: Path) -> list[str]:
    """Get all actual folder names under tasks/."""
    if not tasks_dir.is_dir():
        return []
    return [d.name for d in sorted(tasks_dir.iterdir()) if d.is_dir()]
