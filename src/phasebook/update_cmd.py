"""phasebook update — update managed framework files."""

from __future__ import annotations

import difflib
import shutil
import sys
from pathlib import Path

from phasebook import __version__
from phasebook._helpers import get_framework_dir, get_framework_version, get_project_root
from phasebook.init_cmd import MANAGED_DIRS


# Files that are never overwritten by update
USER_OWNED = {
    "CLAUDE.md",
    "reference-data.md",
    "review_models.json",
    "api_keys.json",
    "settings.json",
    "launch.json",
}


def run_update(*, check: bool = False, diff: bool = False) -> None:
    project_root = get_project_root()
    if project_root is None:
        print("Error: not in a project directory.")
        sys.exit(1)

    current_version = get_framework_version(project_root)
    if current_version is None:
        print("Error: .claude/.phasebook-version not found. Run 'phasebook init' first.")
        sys.exit(1)

    framework_src = get_framework_dir()
    claude_dir = project_root / ".claude"

    if not framework_src.is_dir():
        print(f"Error: framework files not found at {framework_src}")
        sys.exit(1)

    would_update: list[str] = []
    would_skip: list[str] = []

    # Walk managed directories
    for d in MANAGED_DIRS:
        src_dir = framework_src / d
        dst_dir = claude_dir / d
        if not src_dir.is_dir():
            continue
        for f in sorted(src_dir.rglob("*")):
            if not f.is_file():
                continue
            if f.name in USER_OWNED:
                would_skip.append(f".claude/{d}/{f.name}")
                continue
            rel = f.relative_to(src_dir)
            dst = dst_dir / rel
            if _files_differ(f, dst):
                would_update.append(f".claude/{d}/{rel}")
                if diff and dst.exists():
                    _show_diff(dst, f, f".claude/{d}/{rel}")

    # Walk skills
    skills_src = framework_src / "skills"
    if skills_src.is_dir():
        for skill_dir in sorted(skills_src.iterdir()):
            if not skill_dir.is_dir():
                continue
            for f in sorted(skill_dir.iterdir()):
                if not f.is_file() or f.name in USER_OWNED:
                    continue
                dst = claude_dir / "skills" / skill_dir.name / f.name
                rel_path = f".claude/skills/{skill_dir.name}/{f.name}"
                if _files_differ(f, dst):
                    would_update.append(rel_path)
                    if diff and dst.exists():
                        _show_diff(dst, f, rel_path)

    if check or diff:
        print(f"Phasebook update check (installed: {current_version} → {__version__})")
        if would_update:
            print(f"\nWould update {len(would_update)} files:")
            for p in would_update:
                print(f"  {p}")
        else:
            print("\nAll managed files are up to date.")
        if would_skip:
            print(f"\nWould skip {len(would_skip)} user-owned files.")
        return

    # Apply updates
    updated = 0
    for d in MANAGED_DIRS:
        src_dir = framework_src / d
        dst_dir = claude_dir / d
        if not src_dir.is_dir():
            continue
        for f in sorted(src_dir.rglob("*")):
            if not f.is_file() or f.name in USER_OWNED:
                continue
            rel = f.relative_to(src_dir)
            dst = dst_dir / rel
            if _files_differ(f, dst):
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
                updated += 1

    skills_src = framework_src / "skills"
    if skills_src.is_dir():
        for skill_dir in sorted(skills_src.iterdir()):
            if not skill_dir.is_dir():
                continue
            for f in sorted(skill_dir.iterdir()):
                if not f.is_file() or f.name in USER_OWNED:
                    continue
                dst = claude_dir / "skills" / skill_dir.name / f.name
                if _files_differ(f, dst):
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dst)
                    updated += 1

    # Update version
    version_file = claude_dir / ".phasebook-version"
    version_file.write_text(__version__)

    print(f"Phasebook updated: {current_version} → {__version__}")
    print(f"  Updated: {updated} files")
    if would_skip:
        print(f"  Skipped: {len(would_skip)} user-owned files")


def _files_differ(src: Path, dst: Path) -> bool:
    """Check if source and destination files differ."""
    if not dst.exists():
        return True
    return src.read_bytes() != dst.read_bytes()


def _show_diff(old_path: Path, new_path: Path, label: str) -> None:
    """Print a unified diff between old and new file."""
    old_lines = old_path.read_text().splitlines(keepends=True)
    new_lines = new_path.read_text().splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{label}", tofile=f"b/{label}")
    sys.stdout.writelines(diff)
