"""Shared utilities for phasebook CLI."""

from __future__ import annotations

import re
from pathlib import Path


PHASE_LETTERS = "RDPE"
PHASE_NAMES = ["research", "design", "plan", "execute"]

TASK_FOLDERS = ["drafts", "queue", "progress", "review", "completed", "archived"]

ARTIFACT_DIRS = ["research", "designs", "plans", "executions", "learnings",
                 "reviews", "obligations", "tokens", "reports"]


def get_project_root() -> Path | None:
    """Walk up from cwd to find a project root (has .claude/ or .git/)."""
    cwd = Path.cwd()
    for d in [cwd, *cwd.parents]:
        if (d / ".claude").is_dir() or (d / ".git").is_dir():
            return d
    return None


def get_phasebook_dir(project_root: Path) -> Path:
    """Return the phasebook/ directory under the project root."""
    return project_root / "phasebook"


def get_framework_dir() -> Path:
    """Locate the bundled framework files in the installed package."""
    return Path(__file__).resolve().parent / "framework"


def get_templates_dir() -> Path:
    """Locate the bundled template files in the installed package."""
    return Path(__file__).resolve().parent / "templates"


def get_framework_version(project_root: Path) -> str | None:
    """Read the installed phasebook version from the project."""
    version_file = project_root / ".claude" / ".phasebook-version"
    if version_file.exists():
        return version_file.read_text().strip()
    return None


def parse_task_filename(name: str) -> dict | None:
    """Parse a task filename into its components.

    Accepts:
      <priority>.<strip>.<slug>.md  — drafts/queue/progress/review files
      <slug>.md                     — completed/archived files

    Returns a dict with keys: priority, strip, slug, phase (next phase name).
    Returns None for non-matching filenames.
    """
    if not name.endswith(".md"):
        return None
    if name.startswith("."):
        return None

    stem = name[:-3]

    # Try full format: <priority>.<strip>.<slug>
    match = re.fullmatch(r"([1-9])\.([RDPErdpe+\-]{4})\.([a-z0-9][a-z0-9-]*)", stem)
    if match:
        priority_str, strip, slug = match.groups()
        strip = strip.upper().replace("+", "+").replace("-", "-")
        # Re-validate with original case preserved from filename
        strip = name[:-3].split(".")[1] if len(name[:-3].split(".")) >= 3 else strip

        # Validate strip positions
        done_ended = False
        for i, ch in enumerate(strip):
            if ch not in (PHASE_LETTERS[i], "+", "-"):
                return None
            if done_ended and ch == PHASE_LETTERS[i]:
                return None
            if ch != PHASE_LETTERS[i]:
                done_ended = True

        # Determine next phase
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

    # Try completed/archived format: <slug>.md
    if re.fullmatch(r"[a-z0-9][a-z0-9-]*", stem):
        return {
            "priority": 0,
            "strip": "RDPE",
            "slug": stem,
            "phase": "done",
        }

    return None


def find_task(slug: str, tasks_dir: Path) -> tuple[Path, dict, str] | None:
    """Find a task file by slug across all folders.

    Returns (file_path, parsed_info, folder_name) or None.
    """
    for folder in TASK_FOLDERS:
        folder_path = tasks_dir / folder
        if not folder_path.is_dir():
            continue
        for f in sorted(folder_path.iterdir()):
            if not f.is_file():
                continue
            parsed = parse_task_filename(f.name)
            if parsed and parsed["slug"] == slug:
                return f, parsed, folder
    return None


def scan_folder(folder_path: Path) -> list[tuple[Path, dict]]:
    """Scan a folder and return parsed task files, sorted by priority then slug."""
    results = []
    if not folder_path.is_dir():
        return results
    for f in sorted(folder_path.iterdir()):
        if not f.is_file() or f.name.startswith("."):
            continue
        parsed = parse_task_filename(f.name)
        if parsed:
            results.append((f, parsed))
    results.sort(key=lambda x: (x[1]["priority"], x[1]["slug"]))
    return results


def find_lost_and_found(folder_path: Path, folder_name: str) -> list[dict]:
    """Find files that don't match naming convention."""
    lost = []
    if not folder_path.is_dir():
        return lost
    for f in sorted(folder_path.iterdir()):
        if not f.is_file() or f.name.startswith("."):
            continue
        parsed = parse_task_filename(f.name)
        if parsed is None:
            lost.append({
                "folder": folder_name,
                "file": f.name,
                "issue": "Not a valid task file" if not f.name.endswith(".md")
                         else "Invalid naming convention",
            })
    return lost
