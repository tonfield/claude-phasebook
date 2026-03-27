#!/usr/bin/env python3
"""Send a notification from the phasebook worker.

Usage:
  phasebook_notify.py "task-slug: research complete, starting design"
  phasebook_notify.py "worker idle, no tasks in queue"

Fire-and-forget. Logs a warning on failure, never blocks, never exits(1).

Notification command resolution:
  1. PHASEBOOK_NOTIFY_CMD env var (e.g. "pushover-notify Pipeline")
  2. ~/bin/pushover-notify (legacy default)
  3. Noop (print to stderr)

Stdlib only — no third-party dependencies.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path


def _get_notify_cmd() -> list[str] | None:
    """Resolve the notification command."""
    # 1. Environment variable
    env_cmd = os.environ.get("PHASEBOOK_NOTIFY_CMD")
    if env_cmd:
        return shlex.split(env_cmd)

    # 2. Legacy pushover-notify
    pushover = Path.home() / "bin" / "pushover-notify"
    if pushover.exists():
        return [str(pushover), "Phasebook"]

    return None


def send(message: str) -> None:
    cmd = _get_notify_cmd()
    if cmd is None:
        print(f"[phasebook] {message}", file=sys.stderr)
        return

    try:
        subprocess.run(
            [*cmd, message],
            check=False,
            capture_output=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"Warning: notification failed: {exc}", file=sys.stderr)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: phasebook_notify.py <message>", file=sys.stderr)
        return

    send(sys.argv[1])


if __name__ == "__main__":
    main()
