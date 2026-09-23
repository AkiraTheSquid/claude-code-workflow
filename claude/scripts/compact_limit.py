#!/usr/bin/env python3
"""Read / set the Claude Code auto-compact window in ~/.claude/settings.json.

Why this exists
---------------
`autoCompactWindow` is NOT the token count at which compaction fires. Reading the
2.1.218 CLI bundle, the trigger is derived from it:

    window    = min(model_max_context, autoCompactWindow)
    effective = window - min(max_output_tokens, 20_000)     # output reserve
    trigger   = effective - 13_000                          # headroom

so with a 150,000 window on a model that reserves the full 20,000, auto-compact
actually fires at 117,000 context tokens. Precomputed-compact arming starts even
earlier, at effective - 20% (~104,000).

This script therefore supports two ways of asking:

    compact_limit.py                 show current window + derived trigger point
    compact_limit.py 200k            set the WINDOW to 200,000
    compact_limit.py --at 150k       set the window so compaction FIRES at 150,000
    compact_limit.py auto            remove the setting (fall back to the default)

Accepted number forms: 150000, 150k, 150 (bare <= 1000 is read as thousands), 1m.
Valid window range is 100,000 - 1,000,000 (the CLI's own schema bounds).

Precedence: env CLAUDE_CODE_AUTO_COMPACT_WINDOW > settings.json > model default.
A change to settings.json applies to new sessions, not the running one.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

SETTINGS = Path.home() / ".claude" / "settings.json"
KEY = "autoCompactWindow"

MIN_WINDOW = 100_000
MAX_WINDOW = 1_000_000

# Derived-trigger constants, read off the CLI bundle (see module docstring).
OUTPUT_RESERVE = 20_000  # min(max_output_tokens, 20_000); 20k for every current model
HEADROOM = 13_000
PRECOMPUTE_FRACTION = 0.2  # default arming buffer

_NUM = re.compile(r"^(\d+(?:\.\d+)?)\s*([km]?)$", re.I)


def parse_tokens(raw: str) -> int | None:
    """'150k' | '150000' | '150' | '1m' -> int, or None when unparseable."""
    m = _NUM.match(raw.strip().lower())
    if not m:
        return None
    value, suffix = float(m.group(1)), m.group(2)
    if suffix == "k":
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000
    elif value <= 1_000:
        value *= 1_000  # bare shorthand: "150" means 150k
    return int(round(value))


def trigger_for(window: int) -> int:
    """Context-token count at which auto-compact actually fires."""
    return window - OUTPUT_RESERVE - HEADROOM


def window_for_trigger(trigger: int) -> int:
    """Inverse of trigger_for."""
    return trigger + OUTPUT_RESERVE + HEADROOM


def arm_point(window: int) -> int:
    """Context-token count at which the precomputed compact starts running."""
    effective = window - OUTPUT_RESERVE
    return min(effective - round(effective * PRECOMPUTE_FRACTION), trigger_for(window))


def load_settings() -> dict:
    if not SETTINGS.exists():
        return {}
    with SETTINGS.open(encoding="utf-8") as fh:
        return json.load(fh)


def save_settings(data: dict) -> None:
    """Write atomically so a crash can never leave settings.json truncated."""
    tmp = SETTINGS.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, SETTINGS)


def describe(window: int | None) -> str:
    env = os.environ.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW")
    lines = []
    if window is None:
        lines.append(f"{KEY}: not set (model default)")
    else:
        lines.append(f"{KEY}: {window:,}")
        lines.append(f"  auto-compact fires at ~{trigger_for(window):,} context tokens")
        lines.append(f"  precompute arms at   ~{arm_point(window):,} context tokens")
    if env:
        lines.append(f"  NOTE: env CLAUDE_CODE_AUTO_COMPACT_WINDOW={env} overrides this file.")
    if os.environ.get("DISABLE_AUTO_COMPACT") or os.environ.get("DISABLE_COMPACT"):
        lines.append("  NOTE: auto-compact is disabled by env (DISABLE_AUTO_COMPACT/DISABLE_COMPACT).")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a.strip()]

    if not args:
        print(describe(load_settings().get(KEY)))
        return 0

    at_mode = args[0] in ("--at", "-a", "at")
    if at_mode:
        args = args[1:]
        if not args:
            print("--at needs a token count, e.g. `--at 150k`", file=sys.stderr)
            return 1

    raw = args[0]

    if raw.lower() in ("auto", "reset", "unset", "default", "clear"):
        data = load_settings()
        if KEY in data:
            del data[KEY]
            save_settings(data)
            print(f"{KEY} removed — back to the model default. Applies to new sessions.")
        else:
            print(f"{KEY} was already unset.")
        return 0

    tokens = parse_tokens(raw)
    if tokens is None:
        print(
            f"Couldn't parse '{raw}'. Expected 'auto' or a token count "
            f"(150000, 150k, 150, 1m).",
            file=sys.stderr,
        )
        return 1

    window = window_for_trigger(tokens) if at_mode else tokens

    if not MIN_WINDOW <= window <= MAX_WINDOW:
        detail = f" (a {tokens:,}-token trigger needs a {window:,} window)" if at_mode else ""
        print(
            f"Window {window:,} is outside the allowed {MIN_WINDOW:,}-{MAX_WINDOW:,} "
            f"range{detail}.",
            file=sys.stderr,
        )
        return 1

    data = load_settings()
    previous = data.get(KEY)
    data[KEY] = window
    save_settings(data)

    if previous == window:
        print(f"{KEY} already {window:,} — unchanged.")
    else:
        was = f"{previous:,}" if isinstance(previous, int) else "unset"
        print(f"{KEY}: {was} -> {window:,}")
    print(describe(window))
    print("Applies to new sessions. For this one, restart or export "
          f"CLAUDE_CODE_AUTO_COMPACT_WINDOW={window}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
