#!/usr/bin/env python3
"""Parse Claude Code JSONL transcripts and write token usage summary.

Called by the Stop hook. Reads hook stdin for session context, scans all
transcripts in the project sessions directory, and writes:

  1. phasebook/token-usage.json  — lifetime aggregate
  2. phasebook/tokens/<slug>.json — per-task sidecar (race-condition-free)

Stdlib only — no third-party dependencies.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Pricing per million tokens (USD)
# ---------------------------------------------------------------------------
PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-6": {
        "input": 15.0,
        "output": 75.0,
        "cache_read": 1.50,
        "cache_write_5m": 18.75,
        "cache_write_1h": 18.75,
    },
    "claude-sonnet-4-6": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.30,
        "cache_write_5m": 3.75,
        "cache_write_1h": 3.75,
    },
    "claude-haiku-4-5-20251001": {
        "input": 0.80,
        "output": 4.0,
        "cache_read": 0.08,
        "cache_write_5m": 1.0,
        "cache_write_1h": 1.0,
    },
}

MODEL_ALIAS: dict[str, str] = {
    "claude-opus-4-6": "opus",
    "claude-sonnet-4-6": "sonnet",
    "claude-haiku-4-5-20251001": "haiku",
}

_SESSIONS_BASE = Path.home() / ".claude" / "projects"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _compute_sessions_prefix() -> str:
    """Compute the Claude sessions prefix from the project root path."""
    return str(PROJECT_ROOT).replace("/", "-")


_SESSIONS_PREFIX = _compute_sessions_prefix()
SESSIONS_DIR = _SESSIONS_BASE / _SESSIONS_PREFIX


def _output_file() -> Path:
    """Find the phasebook/ or pipeline/ output location."""
    for name in ("phasebook", "pipeline"):
        d = _main_repo_root() / name
        if d.is_dir():
            return d / "token-usage.json"
    return _main_repo_root() / "phasebook" / "token-usage.json"


def _all_session_dirs() -> list[Path]:
    dirs = []
    if not _SESSIONS_BASE.is_dir():
        return dirs
    for d in _SESSIONS_BASE.iterdir():
        if d.is_dir() and d.name.startswith(_SESSIONS_PREFIX):
            dirs.append(d)
    return sorted(dirs)


def _main_repo_root() -> Path:
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith("worktree "):
                    return Path(line.split(" ", 1)[1].strip())
    except (subprocess.TimeoutExpired, OSError):
        pass
    return PROJECT_ROOT


def _tokens_dir() -> Path:
    for name in ("phasebook", "pipeline"):
        d = _main_repo_root() / name / "tokens"
        if d.parent.is_dir():
            return d
    return _main_repo_root() / "phasebook" / "tokens"


def _empty_buckets() -> dict[str, int]:
    return {
        "input": 0,
        "output": 0,
        "cache_read": 0,
        "cache_write_5m": 0,
        "cache_write_1h": 0,
    }


def _parse_jsonl(path: Path) -> dict[str, dict[str, int]]:
    last_by_id: dict[str, dict] = {}

    try:
        with open(path) as f:
            for line in f:
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                inner = msg.get("message")
                if not isinstance(inner, dict):
                    continue
                if inner.get("role") != "assistant":
                    continue

                model = inner.get("model", "")
                if not model or model == "<synthetic>":
                    continue

                usage = inner.get("usage")
                if not usage:
                    continue

                mid = inner.get("id", "")
                if mid:
                    last_by_id[mid] = {"model": model, "usage": usage}
                else:
                    last_by_id[str(id(usage))] = {"model": model, "usage": usage}
    except (OSError, PermissionError):
        return {}

    by_model: dict[str, dict[str, int]] = {}
    for entry in last_by_id.values():
        model = entry["model"]
        usage = entry["usage"]
        if model not in by_model:
            by_model[model] = _empty_buckets()
        b = by_model[model]
        b["input"] += usage.get("input_tokens", 0)
        b["output"] += usage.get("output_tokens", 0)
        b["cache_read"] += usage.get("cache_read_input_tokens", 0)

        cache_creation = usage.get("cache_creation", {})
        if isinstance(cache_creation, dict):
            b["cache_write_5m"] += cache_creation.get("ephemeral_5m_input_tokens", 0)
            b["cache_write_1h"] += cache_creation.get("ephemeral_1h_input_tokens", 0)
        else:
            b["cache_write_1h"] += usage.get("cache_creation_input_tokens", 0)

    return by_model


def _merge_buckets(target: dict[str, dict[str, int]], source: dict[str, dict[str, int]]) -> None:
    for model, buckets in source.items():
        if model not in target:
            target[model] = _empty_buckets()
        for key in target[model]:
            target[model][key] += buckets.get(key, 0)


def _cost_for_buckets(model: str, buckets: dict[str, int]) -> float:
    prices = PRICING.get(model)
    if not prices:
        return 0.0
    mtok = 1_000_000
    return (
        buckets["input"] / mtok * prices["input"]
        + buckets["output"] / mtok * prices["output"]
        + buckets["cache_read"] / mtok * prices["cache_read"]
        + buckets["cache_write_5m"] / mtok * prices["cache_write_5m"]
        + buckets["cache_write_1h"] / mtok * prices["cache_write_1h"]
    )


def _total_cost(by_model: dict[str, dict[str, int]]) -> float:
    return sum(_cost_for_buckets(m, b) for m, b in by_model.items())


def _extract_task(jsonl_path: Path) -> str | None:
    try:
        with open(jsonl_path) as f:
            for line in f:
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                branch = msg.get("gitBranch", "")
                if branch.startswith("phasebook/"):
                    return branch.removeprefix("phasebook/")
                if branch.startswith("pipeline/"):
                    return branch.removeprefix("pipeline/")
                if branch:
                    return None
    except (OSError, PermissionError):
        pass
    return None


def _extract_phase_from_session(jsonl_path: Path) -> str:
    phase_keywords = {"research", "design", "plan", "execute", "learn"}
    try:
        with open(jsonl_path) as f:
            for i, line in enumerate(f):
                if i > 50:
                    break
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                inner = msg.get("message")
                if isinstance(inner, dict):
                    for block in inner.get("content", []):
                        text = ""
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                        elif isinstance(block, str):
                            text = block
                        for kw in phase_keywords:
                            if f"Phase: {kw}" in text:
                                return kw
    except (OSError, PermissionError):
        pass
    return "unknown"


def _session_id_from_path(path: Path) -> str:
    return path.stem


def _find_session_file(session_id: str) -> Path | None:
    for d in _all_session_dirs():
        candidate = d / f"{session_id}.jsonl"
        if candidate.exists():
            return candidate
    return None


def _find_subagent_files(session_file: Path) -> list[Path]:
    subagent_dir = session_file.parent / session_file.stem / "subagents"
    if not subagent_dir.is_dir():
        return []
    return sorted(subagent_dir.glob("agent-*.jsonl"))


def _extract_date(jsonl_path: Path) -> str:
    try:
        with open(jsonl_path) as f:
            for line in f:
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = msg.get("timestamp")
                if ts and isinstance(ts, str) and len(ts) >= 10:
                    return ts[:10]
    except (OSError, PermissionError):
        pass
    try:
        from datetime import datetime, timezone
        mtime = jsonl_path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
    except OSError:
        return ""


def write_sidecar(slug: str, session_cost: float, phase: str) -> None:
    tokens_dir = _tokens_dir()
    tokens_dir.mkdir(parents=True, exist_ok=True)
    sidecar_path = tokens_dir / f"{slug}.json"

    existing: dict = {}
    if sidecar_path.exists():
        try:
            existing = json.loads(sidecar_path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}

    phases: dict[str, dict] = existing.get("phases", {})

    if phase not in phases:
        phases[phase] = {"sessions": 0, "cost": 0.0}

    phases[phase]["sessions"] += 1
    phases[phase]["cost"] = round(phases[phase]["cost"] + session_cost, 4)

    total_sessions = sum(p["sessions"] for p in phases.values())
    total_cost = round(sum(p["cost"] for p in phases.values()), 4)

    sidecar = {
        "phases": phases,
        "total_sessions": total_sessions,
        "total_cost": total_cost,
    }

    tmp = sidecar_path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(sidecar, indent=2))
        tmp.rename(sidecar_path)
    except OSError as exc:
        print(f"Warning: could not write sidecar for {slug}: {exc}", file=sys.stderr)


def process_all() -> dict:
    output_file = _output_file()

    existing: dict = {}
    if output_file.exists():
        try:
            with open(output_file) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = {}

    cache = existing.get("_cache", {})

    all_dirs = _all_session_dirs()
    if not all_dirs:
        return {}

    session_files: list[Path] = []
    for d in all_dirs:
        session_files.extend(d.glob("*.jsonl"))
    session_files.sort()

    current_session_id: str | None = None
    hook_data = existing.get("_hook_input")
    if isinstance(hook_data, dict):
        current_session_id = hook_data.get("session_id")

    sessions: dict[str, dict] = existing.get("sessions", {})

    for sf in session_files:
        sid = _session_id_from_path(sf)

        try:
            stat = sf.stat()
            mtime = stat.st_mtime
            size = stat.st_size
        except OSError:
            continue

        cache_key = str(sf)
        cached = cache.get(cache_key)
        if cached and sid != current_session_id:
            if cached.get("mtime") == mtime and cached.get("size") == size:
                continue

        by_model = _parse_jsonl(sf)

        for sub_file in _find_subagent_files(sf):
            sub_data = _parse_jsonl(sub_file)
            _merge_buckets(by_model, sub_data)

        task = _extract_task(sf)
        date = _extract_date(sf)

        sessions[sid] = {
            "date": date,
            "task": task,
            "by_model": {
                MODEL_ALIAS.get(m, m): b for m, b in by_model.items()
            },
            "cost": round(_total_cost(by_model), 4),
        }

        cache[cache_key] = {"mtime": mtime, "size": size}

    by_task: dict[str, dict] = {}
    totals_by_model: dict[str, dict[str, int]] = {}
    total_cost = 0.0
    latest_date = ""

    for sid, sdata in sessions.items():
        total_cost += sdata.get("cost", 0)
        if sdata.get("date", "") > latest_date:
            latest_date = sdata["date"]

        for alias, buckets in sdata.get("by_model", {}).items():
            if alias not in totals_by_model:
                totals_by_model[alias] = _empty_buckets()
            for key in totals_by_model[alias]:
                totals_by_model[alias][key] += buckets.get(key, 0)

        task = sdata.get("task")
        if task:
            if task not in by_task:
                by_task[task] = {"cost": 0.0, "sessions": 0}
            by_task[task]["cost"] = round(
                by_task[task]["cost"] + sdata.get("cost", 0), 4
            )
            by_task[task]["sessions"] += 1

    last_session_cost = 0.0
    last_session_date = ""
    if current_session_id and current_session_id in sessions:
        last_session_cost = sessions[current_session_id].get("cost", 0)
        last_session_date = sessions[current_session_id].get("date", "")

    result = {
        "last_session": {
            "session_id": current_session_id or "",
            "date": last_session_date,
            "cost": round(last_session_cost, 2),
        },
        "by_task": dict(
            sorted(by_task.items(), key=lambda x: x[1]["cost"], reverse=True)
        ),
        "totals": {
            "sessions": len(sessions),
            "cost": round(total_cost, 2),
            "by_model": totals_by_model,
        },
        "sessions": sessions,
        "_cache": cache,
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_file.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(result, f, indent=2)
    tmp.rename(output_file)

    return result


def main() -> None:
    task_slug: str | None = None
    for arg in sys.argv[1:]:
        if arg.startswith("--task="):
            task_slug = arg.split("=", 1)[1].strip() or None

    hook_input: dict = {}
    if not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
            if raw.strip():
                hook_input = json.loads(raw)
        except (json.JSONDecodeError, OSError):
            pass

    output_file = _output_file()

    existing: dict = {}
    if output_file.exists():
        try:
            with open(output_file) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = {}

    existing["_hook_input"] = hook_input

    output_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_file.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(existing, f)
    tmp.rename(output_file)

    result = process_all()

    if task_slug is None:
        session_id = hook_input.get("session_id")
        if session_id:
            session_file = _find_session_file(session_id)
            if session_file:
                task_slug = _extract_task(session_file)

    session_id = hook_input.get("session_id")
    if task_slug and session_id and isinstance(result, dict):
        sdata = result.get("sessions", {}).get(session_id)
        if sdata and sdata.get("task") != task_slug:
            sdata["task"] = task_slug

            by_task: dict[str, dict] = {}
            for _, sd in result.get("sessions", {}).items():
                t = sd.get("task")
                if t:
                    if t not in by_task:
                        by_task[t] = {"cost": 0.0, "sessions": 0}
                    by_task[t]["cost"] = round(
                        by_task[t]["cost"] + sd.get("cost", 0), 4
                    )
                    by_task[t]["sessions"] += 1
            result["by_task"] = dict(
                sorted(by_task.items(), key=lambda x: x[1]["cost"], reverse=True)
            )

            tmp = output_file.with_suffix(".tmp")
            with open(tmp, "w") as f:
                json.dump(result, f, indent=2)
            tmp.rename(output_file)

    if task_slug and result is not None:
        session_id = hook_input.get("session_id")
        session_cost = 0.0
        session_phase = "unknown"
        if session_id and isinstance(result, dict):
            sdata = result.get("sessions", {}).get(session_id, {})
            session_cost = sdata.get("cost", 0.0)
            session_file = _find_session_file(session_id)
            if session_file:
                session_phase = _extract_phase_from_session(session_file)

        write_sidecar(task_slug, session_cost, session_phase)


if __name__ == "__main__":
    main()
