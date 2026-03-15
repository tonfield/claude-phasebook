"""phasebook queue operations — approve, pause, submit, archive, reprioritize, strip."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from phasebook._helpers import (
    PHASE_LETTERS,
    find_task,
    get_phasebook_dir,
    get_project_root,
    parse_task_filename,
)

# Valid transitions: (source_folder, dest_folder)
TRANSITIONS = {
    "approve": ("review", "queue"),
    "pause": ("queue", "drafts"),
    "submit": ("drafts", "queue"),
    "archive": ("completed", "archived"),
}

# Legacy folder name fallbacks
LEGACY_NAMES = {
    "progress": "processing",
    "completed": "done",
    "archived": "archive",
}


def run_queue_cmd(args) -> None:
    project_root = get_project_root()
    if project_root is None:
        print("Error: not in a project directory.")
        sys.exit(1)

    pb_dir = get_phasebook_dir(project_root)
    if not pb_dir.is_dir():
        pb_dir = project_root / "pipeline"
    if not pb_dir.is_dir():
        print("No phasebook/ or pipeline/ directory found.")
        sys.exit(1)

    tasks_dir = pb_dir / "tasks"

    if args.command in TRANSITIONS:
        _move_task(args.slug, args.command, tasks_dir)
    elif args.command == "reprioritize":
        _reprioritize(args.slug, args.priority, tasks_dir)
    elif args.command == "strip":
        _change_strip(args.slug, args.new_strip, tasks_dir)


def _resolve_folder(tasks_dir: Path, canonical: str) -> Path | None:
    """Find actual folder path, trying canonical then legacy name."""
    path = tasks_dir / canonical
    if path.is_dir():
        return path
    legacy = LEGACY_NAMES.get(canonical)
    if legacy:
        path = tasks_dir / legacy
        if path.is_dir():
            return path
    return None


def _move_task(slug: str, command: str, tasks_dir: Path) -> None:
    src_canonical, dst_canonical = TRANSITIONS[command]

    src_folder = _resolve_folder(tasks_dir, src_canonical)
    dst_folder = _resolve_folder(tasks_dir, dst_canonical)

    if src_folder is None:
        print(f"Error: {src_canonical}/ folder not found.")
        sys.exit(1)
    if dst_folder is None:
        print(f"Error: {dst_canonical}/ folder not found.")
        sys.exit(1)

    # Find task in source
    found = None
    for f in sorted(src_folder.iterdir()):
        if not f.is_file():
            continue
        parsed = parse_task_filename(f.name)
        if parsed and parsed["slug"] == slug:
            found = f
            break

    if found is None:
        print(f"Error: task '{slug}' not found in {src_folder.name}/.")
        # Suggest where it might be
        result = find_task(slug, tasks_dir)
        if result:
            print(f"  Found in {result[2]}/ instead.")
        sys.exit(1)

    # For archive: rename to slug-only format
    if command == "archive":
        dst_name = f"{slug}.md"
    else:
        dst_name = found.name

    dst_path = dst_folder / dst_name
    if dst_path.exists():
        print(f"Error: {dst_path.name} already exists in {dst_folder.name}/.")
        sys.exit(1)

    shutil.move(str(found), str(dst_path))
    print(f"{slug}: {src_folder.name}/ → {dst_folder.name}/")


def _reprioritize(slug: str, priority: int, tasks_dir: Path) -> None:
    result = find_task(slug, tasks_dir)
    if result is None:
        # Try legacy
        result = _find_task_legacy(slug, tasks_dir)
    if result is None:
        print(f"Error: task '{slug}' not found.")
        sys.exit(1)

    path, parsed, folder = result
    if folder in ("completed", "archived", "done", "archive"):
        print(f"Error: cannot reprioritize tasks in {folder}/.")
        sys.exit(1)

    old_name = path.name
    new_name = f"{priority}.{parsed['strip']}.{slug}.md"
    if old_name == new_name:
        print(f"{slug}: already priority {priority}.")
        return

    new_path = path.parent / new_name
    shutil.move(str(path), str(new_path))
    print(f"{slug}: priority {parsed['priority']} → {priority}")


def _change_strip(slug: str, new_strip: str, tasks_dir: Path) -> None:
    # Validate strip
    if len(new_strip) != 4:
        print("Error: strip must be exactly 4 characters.")
        sys.exit(1)

    for i, ch in enumerate(new_strip):
        if ch not in (PHASE_LETTERS[i], "+", "-"):
            print(f"Error: position {i} must be '{PHASE_LETTERS[i]}', '+', or '-'. Got '{ch}'.")
            sys.exit(1)

    result = find_task(slug, tasks_dir)
    if result is None:
        result = _find_task_legacy(slug, tasks_dir)
    if result is None:
        print(f"Error: task '{slug}' not found.")
        sys.exit(1)

    path, parsed, folder = result
    if folder in ("completed", "archived", "done", "archive"):
        print(f"Error: cannot change strip for tasks in {folder}/.")
        sys.exit(1)

    old_name = path.name
    new_name = f"{parsed['priority']}.{new_strip}.{slug}.md"
    if old_name == new_name:
        print(f"{slug}: strip unchanged.")
        return

    new_path = path.parent / new_name
    shutil.move(str(path), str(new_path))
    print(f"{slug}: strip {parsed['strip']} → {new_strip}")


def _find_task_legacy(slug: str, tasks_dir: Path) -> tuple[Path, dict, str] | None:
    """Search legacy folder names."""
    legacy = {"processing": "progress", "done": "completed", "archive": "archived"}
    for old_name in legacy:
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
