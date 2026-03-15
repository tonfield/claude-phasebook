"""Phasebook CLI entry point."""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="phasebook",
        description="Phased workflow framework for Claude Code",
    )
    subparsers = parser.add_subparsers(dest="command")

    # init
    sub = subparsers.add_parser("init", help="Initialize phasebook in current project")
    sub.add_argument("--force", action="store_true", help="Overwrite managed files even if present")

    # update
    sub = subparsers.add_parser("update", help="Update managed framework files")
    sub.add_argument("--check", action="store_true", help="Dry-run: show what would change")
    sub.add_argument("--diff", action="store_true", help="Show diffs before applying")

    # index
    subparsers.add_parser("index", help="Show phasebook index — overview of all tasks")

    # status
    sub = subparsers.add_parser("status", help="Executive overview of a task")
    sub.add_argument("slug", help="Task slug")

    # approve
    sub = subparsers.add_parser("approve", help="Move task from review/ to queue/")
    sub.add_argument("slug", help="Task slug")

    # pause
    sub = subparsers.add_parser("pause", help="Move task from queue/ to drafts/")
    sub.add_argument("slug", help="Task slug")

    # submit
    sub = subparsers.add_parser("submit", help="Move task from drafts/ to queue/")
    sub.add_argument("slug", help="Task slug")

    # archive
    sub = subparsers.add_parser("archive", help="Move task from completed/ to archived/")
    sub.add_argument("slug", help="Task slug")

    # reprioritize
    sub = subparsers.add_parser("reprioritize", help="Change task priority")
    sub.add_argument("slug", help="Task slug")
    sub.add_argument("priority", type=int, choices=range(1, 10), help="New priority (1-9)")

    # strip
    sub = subparsers.add_parser("strip", help="Change task strip")
    sub.add_argument("slug", help="Task slug")
    sub.add_argument("new_strip", help="New strip (e.g. --++)")

    # lint
    subparsers.add_parser("lint", help="Validate task files and project structure")

    # costs
    subparsers.add_parser("costs", help="Show token usage costs")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "init":
        from phasebook.init_cmd import run_init
        run_init(force=args.force)
    elif args.command == "update":
        from phasebook.update_cmd import run_update
        run_update(check=args.check, diff=args.diff)
    elif args.command == "index":
        from phasebook.index_cmd import run_index
        run_index()
    elif args.command == "status":
        from phasebook.status_cmd import run_status
        run_status(args.slug)
    elif args.command in ("approve", "pause", "submit", "archive", "reprioritize", "strip"):
        from phasebook.queue_cmd import run_queue_cmd
        run_queue_cmd(args)
    elif args.command == "lint":
        from phasebook.lint_cmd import run_lint
        run_lint()
    elif args.command == "costs":
        from phasebook.costs_cmd import run_costs
        run_costs()


if __name__ == "__main__":
    main()
