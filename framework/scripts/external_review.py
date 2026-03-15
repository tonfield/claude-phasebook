#!/usr/bin/env python3
"""External review tool for the phasebook workflow.

Calls external AI models to review artifacts independently, returning
raw responses as structured JSON for downstream processing by the
/review skill or standalone use.

Dependencies:
    pip install openai                 # Required: Kilocode, Z.AI, any OpenAI-compatible
    pip install google-genai           # Optional: native Gemini with thinking
    pip install httpx[socks]           # Required if SOCKS proxy is active (ALL_PROXY env)

API Keys (resolution order):
    1. ~/.config/phasebook/api_keys.json (machine-wide)
    2. Environment variables (GEMINI_API_KEY, KILOCODE_API_KEY, ZAI_API_KEY)
    3. .claude/scripts/api_keys.json (project-local, gitignored)

Usage:
    # Standard review (risk selects models, mode selects prompt+roster)
    python3 .claude/scripts/external_review.py artifact.md --risk HIGH --mode review
    python3 .claude/scripts/external_review.py artifact.md --risk MEDIUM --mode code

    # Challenge gate (adversarial, uses grok-ma)
    python3 .claude/scripts/external_review.py artifact.md --mode challenge

    # With additional context files
    python3 .claude/scripts/external_review.py design.md --files research.md --risk MEDIUM

    # List available models and check API keys
    python3 .claude/scripts/external_review.py --list-models

    # Dry run / debug
    python3 .claude/scripts/external_review.py artifact.md --risk HIGH --dry-run
    python3 .claude/scripts/external_review.py artifact.md --risk MEDIUM -v
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("external_review")

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore[assignment,misc]

try:
    from google import genai as google_genai
except ImportError:
    google_genai = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Configuration — loaded from review_models.json
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).parent
_CONFIG_FILE = _SCRIPT_DIR / "review_models.json"

_API_TIMEOUT_S = 180
_MAX_RETRIES = 2
_RETRY_BASE_DELAY_S = 5
_MIN_RESPONSE_LENGTH = 100
_TEMPERATURE = 0.3


def _find_api_keys_file() -> Path | None:
    """Find API keys file using resolution order."""
    # 1. Machine-wide
    machine_wide = Path.home() / ".config" / "phasebook" / "api_keys.json"
    if machine_wide.exists():
        return machine_wide

    # 2. Project-local (next to this script)
    local = _SCRIPT_DIR / "api_keys.json"
    if local.exists():
        return local

    return None


def _load_config() -> tuple[dict[str, dict], dict[str, dict[str, list[str]]], dict[str, dict]]:
    """Load models, rosters, and providers from review_models.json."""
    if not _CONFIG_FILE.exists():
        log.error(f"Config file not found: {_CONFIG_FILE}")
        sys.exit(1)

    try:
        data = json.loads(_CONFIG_FILE.read_text())
    except json.JSONDecodeError as e:
        log.error(f"Malformed JSON in {_CONFIG_FILE}: {e}")
        sys.exit(1)

    for key in ("models", "rosters", "providers"):
        if key not in data:
            log.error(f"Missing required key '{key}' in {_CONFIG_FILE}")
            sys.exit(1)

    models = data["models"]
    providers = data["providers"]
    for alias, cfg in models.items():
        for req in ("provider", "model", "context_window"):
            if req not in cfg:
                log.error(f"Model '{alias}' missing '{req}' in {_CONFIG_FILE}")
                sys.exit(1)
    for name, cfg in providers.items():
        for req in ("api_key_env", "sdk"):
            if req not in cfg:
                log.error(f"Provider '{name}' missing '{req}' in {_CONFIG_FILE}")
                sys.exit(1)
    for roster_name, roster in data["rosters"].items():
        for risk, model_list in roster.items():
            for alias in model_list:
                if alias not in models:
                    log.error(f"Roster '{roster_name}.{risk}' references unknown model '{alias}'")
                    sys.exit(1)

    return models, data["rosters"], providers


def _load_api_keys() -> dict[str, str]:
    """Load API keys from api_keys.json. Returns empty dict if missing."""
    keys_file = _find_api_keys_file()
    if keys_file:
        try:
            return json.loads(keys_file.read_text())
        except (json.JSONDecodeError, OSError) as e:
            log.warning(f"Failed to read {keys_file}: {e}")
    return {}


MODELS, ROSTERS, PROVIDERS = _load_config()
_API_KEYS = _load_api_keys()

# ---------------------------------------------------------------------------
# Mode configuration
# ---------------------------------------------------------------------------

MODES: dict[str, dict] = {
    "review": {
        "system": (
            "You are a senior technical reviewer with deep expertise in software "
            "architecture and system design. Your reviews are valued for precision "
            "— you find real issues that others miss, and you do not fabricate "
            "problems to fill space.\n\n"
            "Rules:\n"
            "- Every finding must cite the specific section or text it refers to. "
            "Quote the relevant passage.\n"
            "- Do not invent issues. If the document is sound, say so. A short "
            "review with real findings is better than a long review with fabricated ones.\n"
            "- This is a document review, not a code review. Any code snippets are "
            "illustrative — showing intended interfaces or behavior. Do not evaluate "
            "whether code has been implemented or is runnable.\n"
            "- If source files are included alongside the document, use them to verify "
            "claims: check that referenced functions exist, signatures match, and "
            "return types are correct. Quote from the source as evidence.\n"
            "- Respect negative requirements ('do NOT', 'never', 'must not'). These are "
            "intentional constraints. Do not flag their absence as a gap.\n"
            "- Evaluate the document on its own terms: does it achieve what it sets "
            "out to do?"
        ),
        "prompt": (
            "Review this document thoroughly.\n\n"
            "Before evaluating, identify the 3-5 things this document must get right "
            "to succeed. Then evaluate against each one.\n\n"
            "Evaluate:\n"
            "1. **Logical soundness** — Are the arguments and reasoning consistent? "
            "Any contradictions, circular logic, or unsupported leaps?\n"
            "2. **Correctness** — Are technical claims, formulas, algorithms, and "
            "interface descriptions accurate?\n"
            "3. **Completeness** — Are there missing edge cases, unhandled scenarios, "
            "or gaps in coverage? Does every requirement have a corresponding solution?\n"
            "4. **Assumptions** — What is taken as given without evidence? Are these "
            "assumptions reasonable?\n"
            "5. **Alternatives** — Were viable alternatives considered and fairly "
            "evaluated? Is the chosen approach well-justified?\n\n"
            "Focus on substance. Ignore formatting, style, and wording preferences."
        ),
        "roster": "review",
    },
    "code": {
        "system": (
            "You are a senior software engineer performing a code review. You have "
            "deep experience with production systems and catching subtle bugs.\n\n"
            "Rules:\n"
            "- Every finding must reference the specific file, function, and line. "
            "Quote the code that is wrong and show what it should be.\n"
            "- Do not invent issues. If the code is correct, say so.\n"
            "- Do not suggest style changes, naming preferences, or refactors unless "
            "they fix a bug or prevent one.\n"
            "- Focus on things that would break at runtime or produce wrong results."
        ),
        "prompt": (
            "Review this code implementation for correctness.\n\n"
            "Evaluate:\n"
            "1. **Bugs** — Logic errors, off-by-one, wrong operator, type mismatches, "
            "None/null handling, incorrect return values.\n"
            "2. **Contract violations** — Does the implementation match its spec or "
            "docstring? Wrong signatures, missing parameters, incorrect defaults. "
            "If a spec is included, verify every comparison operator (<, >, <=, >=), "
            "every default value, and every parameter name against it.\n"
            "3. **Edge cases** — Empty inputs, boundary values, concurrent access, "
            "error propagation, resource cleanup on exception paths.\n"
            "4. **Test coverage** — Are the tests testing the right things? Missing "
            "assertions, tests that always pass, untested error paths.\n"
            "5. **Data flow** — Are values transformed correctly through the call chain? "
            "Unit mismatches, sign errors, lost precision, stale references.\n\n"
            "Ignore style, naming, import order, and documentation unless they indicate a bug."
        ),
        "roster": "code",
    },
    "challenge": {
        "system": (
            "You are a senior adversarial reviewer. Assume this work has already "
            "received thorough review — detail-level issues have been caught. Your "
            "job is to find what those reviews missed.\n\n"
            "Your value is in questioning the FRAMING: the overall approach, hidden "
            "assumptions baked into the structure, and things the work is NOT "
            "saying. Think like a skeptical stakeholder, not a line-by-line reviewer.\n\n"
            "Rules:\n"
            "- Limit yourself to 2-3 high-impact concerns. A focused challenge is "
            "more useful than a spray of minor issues.\n"
            "- Every concern must include a concrete failure scenario with real-world "
            "consequences — not a vague 'this could be problematic.'\n"
            "- Quote the specific text you are challenging.\n"
            "- If the work is solid, say so in 2 sentences and stop. Do not invent "
            "issues to justify the review."
        ),
        "prompt": (
            "Challenge this work at a strategic level, not a detail level.\n\n"
            "Focus on:\n"
            "1. **Confirmation bias** — Does the work selectively present evidence "
            "that supports its conclusion? What counter-evidence is missing or "
            "dismissed too quickly?\n"
            "2. **Wrong abstraction** — Is the overall approach solving the right "
            "problem? Could a fundamentally different approach be simpler or more "
            "robust?\n"
            "3. **Dangerous omissions** — What is the work NOT discussing that "
            "it should be? What failure modes are conspicuously absent?\n"
            "4. **Coupling and blast radius** — What happens to the rest of the "
            "system when this ships? What breaks in ways the author hasn't "
            "considered?\n\n"
            "Do not flag detail-level issues (wrong defaults, missing edge cases, "
            "formatting). Focus on whether the overall approach is sound."
        ),
        "models": ["grok-ma"],
    },
}

_OUTPUT_FORMAT = """

Respond with the following structure:

## Grade: <A-F>
(A = no issues found, B = advisory only, C = minor blocking, D = significant blocking, F = fundamentally flawed)

## BLOCKING Findings
Issues that will cause incorrect behavior, data loss, or specification failures if unfixed.
For each finding, explain your reasoning step by step before classifying.

Example: **Off-by-one in loop boundary**: Section 3 specifies `range(0, n)` but the
algorithm requires the previous iteration's output, so iteration 0 reads uninitialized
state. This will produce incorrect results for all inputs.

## ADVISORY Findings
Suggestions that improve quality but are not correctness issues.

Example: **Ambiguous acceptance criterion**: Section 5 specifies "< 2% error" but does
not state the confidence level. Adding "at 95% confidence" would make the criterion
unambiguous and testable.

## Summary
<1-2 sentence verdict. State the single most important thing to fix, if any.>"""

_SECRET_PATTERN = re.compile(
    r"(AIza[0-9A-Za-z_-]{35}|sk-[a-zA-Z0-9]{20,}|[0-9a-f]{32}\.[a-zA-Z0-9]+|eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+)"
)


def _sanitize_error(msg: str) -> str:
    return _SECRET_PATTERN.sub("[REDACTED]", msg)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ReviewResult:
    model_alias: str
    model_name: str
    provider: str
    response: str = ""
    error: str | None = None
    duration_s: float = 0.0
    tokens: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    return len(text) // 3


def _get_api_key(provider_name: str) -> str | None:
    provider_cfg = PROVIDERS.get(provider_name)
    if not provider_cfg:
        return None
    env_var = provider_cfg.get("api_key_env", "")
    return _API_KEYS.get(env_var) or os.environ.get(env_var)


def _is_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
        return b"\x00" in chunk
    except OSError:
        return False


def _is_retryable(exc: Exception) -> bool:
    exc_str = str(exc)
    if "429" in exc_str or "rate" in exc_str.lower():
        return True
    if any(code in exc_str for code in ("500", "502", "503", "504")):
        return True
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    if "timeout" in exc_str.lower() or "connection" in exc_str.lower():
        return True
    return False


def _validate_response(text: str) -> str | None:
    if not text or not text.strip():
        return "Empty response (possible content filter or safety block)"
    if len(text.strip()) < _MIN_RESPONSE_LENGTH:
        return f"Response too short ({len(text.strip())} chars) — likely not a real review"
    return None


def read_files(paths: list[str]) -> tuple[str, int, list[dict]]:
    parts: list[str] = []
    total_tokens = 0
    file_info: list[dict] = []

    for i, path_str in enumerate(paths):
        p = Path(path_str).expanduser().resolve()
        is_primary = i == 0

        if not p.exists():
            if is_primary:
                log.error(f"Primary artifact not found: {p}")
                file_info.append({"path": str(p), "tokens_est": 0, "error": "not found"})
                return "", 0, file_info
            log.warning(f"Context file not found, skipping: {p}")
            file_info.append({"path": str(p), "tokens_est": 0, "error": "not found"})
            continue

        if _is_binary(p):
            if is_primary:
                log.error(f"Primary artifact is a binary file: {p}")
                file_info.append({"path": str(p), "tokens_est": 0, "error": "binary file"})
                return "", 0, file_info
            log.warning(f"Binary file detected, skipping: {p}")
            file_info.append({"path": str(p), "tokens_est": 0, "error": "binary file"})
            continue

        try:
            content = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as e:
            if is_primary:
                log.error(f"Cannot read primary artifact: {p}: {e}")
                file_info.append({"path": str(p), "tokens_est": 0, "error": str(e)})
                return "", 0, file_info
            log.warning(f"Cannot read file, skipping: {p}: {e}")
            file_info.append({"path": str(p), "tokens_est": 0, "error": str(e)})
            continue

        if not content.strip():
            if is_primary:
                log.error(f"Primary artifact is empty: {p}")
                file_info.append({"path": str(p), "tokens_est": 0, "error": "empty file"})
                return "", 0, file_info
            log.warning(f"Empty context file, skipping: {p}")
            file_info.append({"path": str(p), "tokens_est": 0, "error": "empty file"})
            continue

        tokens = estimate_tokens(content)
        total_tokens += tokens
        display_name = f"{p.parent.name}/{p.name}" if p.parent.name else p.name
        parts.append(f"\n--- FILE: {display_name} ({tokens:,} tokens est.) ---\n{content}\n")
        file_info.append({"path": str(p), "tokens_est": tokens})
        log.info(f"Read {display_name}: {len(content):,} chars, ~{tokens:,} tokens")

    return "\n".join(parts), total_tokens, file_info


# ---------------------------------------------------------------------------
# Provider calls
# ---------------------------------------------------------------------------

def call_gemini(
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    *,
    thinking: bool = True,
    max_tokens: int = 8192,
) -> tuple[str, dict[str, int]]:
    api_key = _get_api_key("gemini")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    if google_genai is not None:
        client = google_genai.Client(
            api_key=api_key,
            http_options={"timeout": _API_TIMEOUT_S * 1000},
        )
        config_kwargs: dict = {"max_output_tokens": max_tokens}
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt

        thinking_active = False
        if thinking:
            try:
                config_kwargs["thinking_config"] = google_genai.types.ThinkingConfig(
                    thinking_budget=min(8192, max(1024, max_tokens // 2)),
                )
                thinking_active = True
            except (AttributeError, TypeError):
                log.warning("ThinkingConfig not available, skipping")

        if not thinking_active:
            config_kwargs["temperature"] = _TEMPERATURE

        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=google_genai.types.GenerateContentConfig(**config_kwargs),
        )

        text = response.text or ""
        tokens: dict[str, int] = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            tokens = {
                "input": getattr(um, "prompt_token_count", 0) or 0,
                "output": getattr(um, "candidates_token_count", 0) or 0,
            }
            thinking_tokens = getattr(um, "thoughts_token_count", 0) or 0
            if thinking_tokens:
                tokens["thinking"] = thinking_tokens
        return text, tokens

    if OpenAI is None:
        raise ImportError("Install openai or google-genai: pip install openai google-genai")

    log.info("Using Gemini OpenAI-compatible endpoint (no thinking)")
    gemini_cfg = PROVIDERS.get("gemini", {})
    openai_base_url = gemini_cfg.get("openai_base_url")
    if not openai_base_url:
        raise ValueError("No openai_base_url configured for Gemini provider")
    client = OpenAI(api_key=api_key, base_url=openai_base_url, timeout=_API_TIMEOUT_S)
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    resp = client.chat.completions.create(
        model=model_name, messages=messages,
        temperature=_TEMPERATURE, max_tokens=max_tokens, stream=False,
    )
    if not resp.choices:
        raise ValueError(f"Empty response from {model_name} (possible content filter)")
    text = resp.choices[0].message.content or ""
    tokens = {}
    if resp.usage:
        tokens = {"input": resp.usage.prompt_tokens or 0, "output": resp.usage.completion_tokens or 0}
    return text, tokens


def call_openai_compat(
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    *,
    base_url: str,
    api_key: str,
    max_tokens: int = 8192,
    extra_headers: dict | None = None,
) -> tuple[str, dict[str, int]]:
    if OpenAI is None:
        raise ImportError("Install openai: pip install openai")

    client_kwargs: dict = {"api_key": api_key, "base_url": base_url, "timeout": _API_TIMEOUT_S}
    if extra_headers:
        client_kwargs["default_headers"] = extra_headers

    client = OpenAI(**client_kwargs)
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    resp = client.chat.completions.create(
        model=model_name, messages=messages,
        temperature=_TEMPERATURE, max_tokens=max_tokens, stream=False,
    )
    if not resp.choices:
        raise ValueError(f"Empty response from {model_name} (possible content filter)")
    text = resp.choices[0].message.content or ""
    tokens: dict[str, int] = {}
    if resp.usage:
        tokens = {"input": resp.usage.prompt_tokens or 0, "output": resp.usage.completion_tokens or 0}
    return text, tokens


def call_model(
    alias: str,
    system_prompt: str,
    user_prompt: str,
) -> ReviewResult:
    config = MODELS.get(alias)
    if not config:
        return ReviewResult(model_alias=alias, model_name="unknown", provider="unknown",
                            error=f"Unknown model alias: {alias}")

    model_name = config.get("model", "unknown")
    provider = config.get("provider", "unknown")
    provider_cfg = PROVIDERS.get(provider)
    if not provider_cfg:
        return ReviewResult(model_alias=alias, model_name=model_name, provider=provider,
                            error=f"Unknown provider '{provider}'")

    max_output = config.get("max_output", 65536)
    result = ReviewResult(model_alias=alias, model_name=model_name, provider=provider)
    sdk = provider_cfg.get("sdk", "openai")

    last_error: Exception | None = None
    start = time.monotonic()

    for attempt in range(_MAX_RETRIES + 1):
        if attempt > 0:
            delay = _RETRY_BASE_DELAY_S * (2 ** (attempt - 1)) + random.uniform(0, 1)
            log.info(f"Retry {attempt}/{_MAX_RETRIES} for {alias} after {delay:.1f}s")
            time.sleep(delay)

        try:
            if sdk == "gemini":
                text, tokens = call_gemini(
                    model_name, system_prompt, user_prompt,
                    thinking=config.get("thinking", False), max_tokens=max_output,
                )
            else:
                api_key = _get_api_key(provider)
                if not api_key:
                    raise ValueError(f"{provider_cfg['api_key_env']} not set")
                env_name = provider_cfg.get("base_url_env")
                base_url = ((os.environ.get(env_name) if env_name else None)
                            or provider_cfg.get("base_url", ""))
                if not base_url:
                    raise ValueError(f"No base_url for provider '{provider}'")
                text, tokens = call_openai_compat(
                    model_name, system_prompt, user_prompt,
                    base_url=base_url, api_key=api_key,
                    max_tokens=max_output, extra_headers=provider_cfg.get("headers"),
                )

            validation_err = _validate_response(text)
            if validation_err:
                raise ValueError(validation_err)

            result.response = text
            result.tokens = tokens
            last_error = None
            break

        except Exception as e:
            last_error = e
            if not _is_retryable(e) or attempt == _MAX_RETRIES:
                break
            log.warning(f"Transient error for {alias}: {type(e).__name__}")

    if last_error is not None:
        result.error = _sanitize_error(f"{type(last_error).__name__}: {last_error}")
        log.error(f"FAIL {alias} ({model_name}): {result.error}")

    result.duration_s = round(time.monotonic() - start, 1)
    if result.ok:
        log.info(f"OK   {alias}: {result.tokens.get('output', 0):,} tokens out, {result.duration_s}s")
    return result


# ---------------------------------------------------------------------------
# Core review function
# ---------------------------------------------------------------------------

def review(
    files: list[str],
    models: list[str],
    *,
    mode: str = "review",
    prompt: str | None = None,
    parallel: bool = True,
    dry_run: bool = False,
) -> dict:
    file_content, total_tokens, file_info = read_files(files)

    if not file_content and file_info and file_info[0].get("error"):
        return {
            "reviews": [], "skipped": [], "files": file_info,
            "config": {"error": f"Primary artifact: {file_info[0]['error']}"},
            "total_duration_s": 0,
        }

    mode_cfg = MODES.get(mode, MODES["review"])
    system_prompt = mode_cfg["system"]

    if prompt:
        user_prompt = f"{prompt}\n\n{file_content}"
    else:
        user_prompt = f"{mode_cfg['prompt']}{_OUTPUT_FORMAT}\n\n{file_content}"

    prompt_tokens = estimate_tokens(user_prompt)

    valid_models: list[str] = []
    skipped: list[dict] = []
    for alias in models:
        config = MODELS.get(alias)
        if not config:
            skipped.append({"alias": alias, "reason": "Unknown model alias"})
            continue

        ctx = config.get("context_window", 0)
        input_budget = int(ctx * 0.85)

        if prompt_tokens > input_budget:
            skipped.append({"alias": alias, "reason": f"Won't fit: ~{prompt_tokens:,} > {input_budget:,} budget"})
            continue

        provider = config.get("provider", "")
        if provider not in PROVIDERS:
            skipped.append({"alias": alias, "reason": f"Unknown provider '{provider}'"})
            continue
        if not _get_api_key(provider):
            skipped.append({"alias": alias, "reason": f"No API key ({PROVIDERS[provider].get('api_key_env', '?')})"})
            continue

        sdk = PROVIDERS[provider].get("sdk", "openai")
        if sdk == "openai" and OpenAI is None:
            skipped.append({"alias": alias, "reason": "openai SDK not installed"})
            continue
        if sdk == "gemini" and google_genai is None and OpenAI is None:
            skipped.append({"alias": alias, "reason": "google-genai SDK not installed"})
            continue

        valid_models.append(alias)

    if dry_run:
        return {
            "dry_run": True,
            "would_call": [{"alias": a, "model": MODELS[a]["model"], "provider": MODELS[a]["provider"]}
                           for a in valid_models],
            "skipped": skipped, "files": file_info,
            "prompt_tokens_est": prompt_tokens, "total_file_tokens": total_tokens,
        }

    if not valid_models:
        return {
            "reviews": [], "skipped": skipped, "files": file_info,
            "config": {"error": "All models skipped", "mode": mode,
                       "models_requested": models, "models_called": 0,
                       "models_succeeded": 0, "models_failed": 0},
            "total_duration_s": 0,
        }

    results: list[ReviewResult] = []
    wall_start = time.monotonic()

    if parallel and len(valid_models) > 1:
        with ThreadPoolExecutor(max_workers=len(valid_models)) as pool:
            futures = {
                pool.submit(call_model, alias, system_prompt, user_prompt): alias
                for alias in valid_models
            }
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    alias = futures[future]
                    results.append(ReviewResult(
                        model_alias=alias,
                        model_name=MODELS.get(alias, {}).get("model", "unknown"),
                        provider=MODELS.get(alias, {}).get("provider", "unknown"),
                        error=_sanitize_error(f"{type(e).__name__}: {e}"),
                    ))
    else:
        for alias in valid_models:
            results.append(call_model(alias, system_prompt, user_prompt))

    wall_elapsed = round(time.monotonic() - wall_start, 1)

    order = {alias: i for i, alias in enumerate(valid_models)}
    results.sort(key=lambda r: order.get(r.model_alias, 999))

    succeeded = sum(1 for r in results if r.ok)
    failed = sum(1 for r in results if not r.ok)

    return {
        "reviews": [{"model_alias": r.model_alias, "model_name": r.model_name,
                      "provider": r.provider, "response": r.response, "error": r.error,
                      "duration_s": r.duration_s, "tokens": r.tokens} for r in results],
        "skipped": skipped, "files": file_info,
        "config": {"mode": mode, "models_requested": models,
                   "models_called": len(valid_models), "models_succeeded": succeeded,
                   "models_failed": failed, "total_file_tokens": total_tokens,
                   "prompt_tokens_est": prompt_tokens},
        "total_duration_s": wall_elapsed,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def list_models_info() -> str:
    lines = [
        "Available models:\n",
        f"  {'ALIAS':14s} {'MODEL':42s} {'CTX':>7s} {'MAX OUT':>9s} {'THINK':8s} KEY",
        f"  {'─' * 14} {'─' * 42} {'─' * 7} {'─' * 9} {'─' * 8} {'─' * 20}",
    ]
    for alias, cfg in MODELS.items():
        provider_cfg = PROVIDERS.get(cfg.get("provider", ""), {})
        api_key_env = provider_cfg.get("api_key_env", "?")
        has_key = "Y" if (_API_KEYS.get(api_key_env) or os.environ.get(api_key_env)) else "-"
        thinking = "yes" if cfg.get("thinking") else ""
        ctx_k = cfg.get("context_window", 0) // 1000
        out_k = cfg.get("max_output", 0) // 1000
        lines.append(f"  {alias:14s} {cfg.get('model', '?'):42s} "
                      f"{ctx_k:>5,}K  {out_k:>6,}K  {thinking:8s} [{has_key} {api_key_env}]")

    lines.append(f"\n  Config: {_CONFIG_FILE}")
    lines.append("\nRosters:")
    for mode_key, roster in ROSTERS.items():
        lines.append(f"\n  {mode_key}:")
        for risk, model_list in roster.items():
            lines.append(f"    {risk:8s}  {', '.join(model_list)}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="External review tool for the phasebook workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="JSON output → stdout. Logs → stderr (-v for debug).",
    )
    parser.add_argument("artifact", nargs="?", help="Primary artifact file to review")
    parser.add_argument("--files", nargs="*", default=[], help="Additional context files")
    parser.add_argument("--mode", choices=list(MODES.keys()), default="review",
                        help="Review mode (default: review)")
    parser.add_argument("--risk", choices=["LOW", "MEDIUM", "HIGH"], default=None,
                        help="Risk level for model selection")
    parser.add_argument("--models", type=str, default=None,
                        help="Comma-separated model aliases (overrides --risk)")
    parser.add_argument("--prompt", type=str, default=None,
                        help="Custom review prompt (overrides mode prompt)")
    parser.add_argument("--sequential", action="store_true", help="Run models sequentially")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be called")
    parser.add_argument("--list-models", action="store_true", help="List models and exit")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging to stderr")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-5s %(message)s", stream=sys.stderr,
    )

    if args.list_models:
        print(list_models_info())
        return 0

    if not args.artifact:
        parser.error("artifact path is required (or use --list-models)")

    if args.models:
        models = [m.strip() for m in args.models.split(",")]
    elif "models" in MODES.get(args.mode, {}):
        models = list(MODES[args.mode]["models"])
    elif args.risk:
        mode_cfg = MODES.get(args.mode, MODES["review"])
        roster = ROSTERS.get(mode_cfg["roster"], ROSTERS["review"])
        models = roster.get(args.risk, [])
        if not models:
            print(json.dumps({
                "reviews": [], "skipped": [], "files": [],
                "config": {"risk": args.risk, "mode": args.mode, "note": "no models for this risk level"},
                "total_duration_s": 0,
            }, indent=2))
            return 0
    else:
        parser.error("--risk or --models is required for review/code modes")

    output = review(
        files=[args.artifact] + (args.files or []),
        models=models, mode=args.mode, prompt=args.prompt,
        parallel=not args.sequential, dry_run=args.dry_run,
    )
    if "config" in output:
        output["config"]["risk"] = args.risk

    print(json.dumps(output, indent=2, ensure_ascii=False))

    config = output.get("config", {})
    if config.get("error"):
        return 1
    succeeded = config.get("models_succeeded", 0)
    failed = config.get("models_failed", 0)
    return 1 if (failed > 0 and succeeded == 0) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        error_msg = _sanitize_error(f"{type(e).__name__}: {e}")
        print(json.dumps({
            "reviews": [], "skipped": [], "files": [],
            "config": {"error": f"Unexpected error: {error_msg}"},
            "total_duration_s": 0,
        }, indent=2))
        log.error(f"Unexpected error: {error_msg}")
        sys.exit(1)
