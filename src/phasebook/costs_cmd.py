"""phasebook costs — show token usage costs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from phasebook._helpers import get_phasebook_dir, get_project_root


def run_costs() -> None:
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

    # Read lifetime usage
    usage = _read_usage(pb_dir)

    # Read per-task sidecars
    sidecars = _read_sidecars(pb_dir)

    if not usage and not sidecars:
        print("No token usage data found.")
        return

    # Per-task breakdown
    if sidecars:
        print("## Per-Task Costs")
        print()
        print("| Task | Sessions | Cost |")
        print("|------|----------|------|")

        sorted_tasks = sorted(sidecars.items(), key=lambda x: x[1].get("total_cost", 0), reverse=True)
        for slug, data in sorted_tasks:
            cost = data.get("total_cost", 0)
            sessions = data.get("total_sessions", 0)
            print(f"| {slug} | {sessions} | ${cost:.2f} |")

            # Phase breakdown
            phases = data.get("phases", {})
            if phases:
                for phase, pdata in phases.items():
                    pcost = pdata.get("cost", 0)
                    psessions = pdata.get("sessions", 0)
                    print(f"|   ↳ {phase} | {psessions} | ${pcost:.2f} |")

    # Lifetime totals
    if usage:
        totals = usage.get("totals", {})
        if totals:
            print()
            print("## Lifetime")
            print()
            total_cost = totals.get("cost", 0)
            total_sessions = totals.get("sessions", 0)
            print(f"Sessions: {total_sessions}")
            print(f"Cost: ${total_cost:.2f}")

            by_model = totals.get("by_model", {})
            if by_model:
                print()
                print("| Model | Input | Output | Cache Read | Cost |")
                print("|-------|-------|--------|------------|------|")
                for model, buckets in by_model.items():
                    inp = buckets.get("input", 0)
                    out = buckets.get("output", 0)
                    cache = buckets.get("cache_read", 0)
                    print(f"| {model} | {inp:,} | {out:,} | {cache:,} | — |")

        last = usage.get("last_session", {})
        if last and last.get("cost"):
            print(f"\nLast session: ${last['cost']:.2f} ({last.get('date', '?')})")


def _read_usage(pb_dir: Path) -> dict:
    path = pb_dir / "token-usage.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _read_sidecars(pb_dir: Path) -> dict[str, dict]:
    result = {}
    tokens_dir = pb_dir / "tokens"
    if not tokens_dir.is_dir():
        return result
    for f in sorted(tokens_dir.iterdir()):
        if f.suffix == ".json" and f.is_file():
            try:
                result[f.stem] = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                pass
    return result
