"""phasebook init — initialize phasebook in current project."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from phasebook import __version__
from phasebook._helpers import (
    ARTIFACT_DIRS,
    TASK_FOLDERS,
    get_framework_dir,
    get_phasebook_dir,
    get_project_root,
    get_templates_dir,
)


# Files that are managed by phasebook and overwritten on update
MANAGED_DIRS = ["rules", "phases", "agents", "scripts", "references"]
MANAGED_SKILL_DIRS = ["phasebook", "index", "draft", "status", "review", "optimize"]

# Template files — only copied if target doesn't exist (user-owned)
TEMPLATE_FILES = {
    "CLAUDE.md": "CLAUDE.md",
    "reference-data.md": "references/reference-data.md",
    "review_models.json": "scripts/review_models.json",
    "api_keys.example.json": None,  # informational only
    "settings.json": "settings.json",
    "launch.json": None,  # skip for now
}

GITIGNORE_ENTRIES = [
    ".phasebook-stop",
    ".phasebook-task",
    "api_keys.json",
    "__pycache__/",
]


def run_init(*, force: bool = False) -> None:
    project_root = get_project_root()
    if project_root is None:
        print("Error: not in a project directory (no .git/ or .claude/ found).")
        sys.exit(1)

    framework_src = get_framework_dir()
    templates_src = get_templates_dir()
    claude_dir = project_root / ".claude"
    phasebook_dir = get_phasebook_dir(project_root)

    if not framework_src.is_dir():
        print(f"Error: framework files not found at {framework_src}")
        sys.exit(1)

    created: list[str] = []
    skipped: list[str] = []

    # 1. Create phasebook/ directory tree
    for folder in TASK_FOLDERS:
        d = phasebook_dir / "tasks" / folder
        d.mkdir(parents=True, exist_ok=True)
        _gitkeep(d)

    for artifact in ARTIFACT_DIRS:
        d = phasebook_dir / artifact
        d.mkdir(parents=True, exist_ok=True)
        _gitkeep(d)

    created.append("phasebook/ directory tree")

    # 2. Create .claude/ subdirectories
    claude_dir.mkdir(exist_ok=True)
    for d in MANAGED_DIRS:
        (claude_dir / d).mkdir(exist_ok=True)
    for s in MANAGED_SKILL_DIRS:
        (claude_dir / "skills" / s).mkdir(parents=True, exist_ok=True)

    # 3. Copy managed framework files
    for d in MANAGED_DIRS:
        src_dir = framework_src / d
        dst_dir = claude_dir / d
        if src_dir.is_dir():
            for f in sorted(src_dir.iterdir()):
                if f.is_file():
                    dst = dst_dir / f.name
                    if not dst.exists() or force:
                        shutil.copy2(f, dst)
                        created.append(f".claude/{d}/{f.name}")
                    else:
                        skipped.append(f".claude/{d}/{f.name}")

    # Copy skill files
    skills_src = framework_src / "skills"
    if skills_src.is_dir():
        for skill_dir in sorted(skills_src.iterdir()):
            if skill_dir.is_dir():
                dst_skill_dir = claude_dir / "skills" / skill_dir.name
                dst_skill_dir.mkdir(parents=True, exist_ok=True)
                for f in sorted(skill_dir.iterdir()):
                    if f.is_file():
                        dst = dst_skill_dir / f.name
                        if not dst.exists() or force:
                            shutil.copy2(f, dst)
                            created.append(f".claude/skills/{skill_dir.name}/{f.name}")
                        else:
                            skipped.append(f".claude/skills/{skill_dir.name}/{f.name}")

    # 4. Copy template files (never overwrite)
    for template_name, dest_rel in TEMPLATE_FILES.items():
        if dest_rel is None:
            continue
        src = templates_src / template_name
        if not src.exists():
            continue

        # CLAUDE.md and reference-data.md go to project root / .claude/references/
        if template_name == "CLAUDE.md":
            dst = project_root / "CLAUDE.md"
        elif template_name == "reference-data.md":
            dst = claude_dir / "references" / "reference-data.md"
        elif template_name == "settings.json":
            dst = claude_dir / "settings.json"
        else:
            dst = claude_dir / dest_rel

        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(src, dst)
            created.append(str(dst.relative_to(project_root)))
        else:
            skipped.append(str(dst.relative_to(project_root)))

    # 5. Resolve absolute paths in settings.json hooks
    settings_path = claude_dir / "settings.json"
    if settings_path.exists():
        _resolve_hook_paths(settings_path, project_root)

    # 6. Append to .gitignore
    _update_gitignore(project_root)

    # 7. Write version file
    version_file = claude_dir / ".phasebook-version"
    version_file.write_text(__version__)
    created.append(".claude/.phasebook-version")

    # Summary
    print(f"Phasebook v{__version__} initialized in {project_root}")
    print(f"  Created: {len(created)} files/dirs")
    if skipped:
        print(f"  Skipped: {len(skipped)} existing files (use --force to overwrite managed files)")
    print()
    print("Next steps:")
    print("  /draft <task>   — create your first task")
    print("  /index          — view the task index")
    print("  /phasebook      — start the worker loop")


def _gitkeep(directory: Path) -> None:
    """Add .gitkeep to an empty directory."""
    gitkeep = directory / ".gitkeep"
    if not any(f for f in directory.iterdir() if f.name != ".gitkeep"):
        gitkeep.touch()


def _resolve_hook_paths(settings_path: Path, project_root: Path) -> None:
    """Resolve relative script paths to absolute paths in settings.json."""
    import json

    try:
        data = json.loads(settings_path.read_text())
    except (json.JSONDecodeError, OSError):
        return

    scripts_dir = project_root / ".claude" / "scripts"
    modified = False

    hooks = data.get("hooks", {})
    for event_hooks in hooks.values():
        if not isinstance(event_hooks, list):
            continue
        for hook_group in event_hooks:
            if not isinstance(hook_group, dict):
                continue
            for hook in hook_group.get("hooks", []):
                if not isinstance(hook, dict):
                    continue
                cmd = hook.get("command", "")
                # Replace relative script refs with absolute
                if "phasebook_context.py" in cmd and str(scripts_dir) not in cmd:
                    hook["command"] = cmd.replace(
                        ".claude/scripts/phasebook_context.py",
                        str(scripts_dir / "phasebook_context.py"),
                    )
                    modified = True
                if "token_usage.py" in cmd and str(scripts_dir) not in cmd:
                    hook["command"] = cmd.replace(
                        ".claude/scripts/token_usage.py",
                        str(scripts_dir / "token_usage.py"),
                    )
                    modified = True

    if modified:
        settings_path.write_text(json.dumps(data, indent=2) + "\n")


def _update_gitignore(project_root: Path) -> None:
    """Append phasebook entries to .gitignore if not present."""
    gitignore = project_root / ".gitignore"
    existing = ""
    if gitignore.exists():
        existing = gitignore.read_text()

    to_add = [e for e in GITIGNORE_ENTRIES if e not in existing]
    if to_add:
        with open(gitignore, "a") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write("\n# phasebook\n")
            for entry in to_add:
                f.write(f"{entry}\n")
