#!/usr/bin/env python3
"""Set / query the context-token threshold at which the model gets a warning to wrap up.

This is NOT the auto-compact trigger point. It's earlier — a chance to find a clean
stopping boundary before compression becomes necessary.

Math:
  auto_trigger  = autoCompactWindow - 33_000
  warn_point    = auto_trigger - delta

So with autoCompactWindow=150k (fires at 117k), a warn_delta of 20k means warn at 97k.

The CLI (2.1.218) doesn't yet expose a settings key for this, but the groundwork exists
in the bundle (`tRu` checks for "warn" level). This script prepares the key for when
the CLI adds support, and documents what the model should do when warned.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SETTINGS = Path.home() / ".claude" / "settings.json"
KEY = "compactWarnThreshold"
COMPACT_KEY = "autoCompactWindow"

MIN_DELTA = 5_000
DEFAULT_DELTA = 20_000
MAX_DELTA = 50_000


def load_settings() -> dict:
    if not SETTINGS.exists():
        return {}
    with SETTINGS.open(encoding="utf-8") as fh:
        return json.load(fh)


def save_settings(data: dict) -> None:
    tmp = SETTINGS.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, SETTINGS)


def trigger_for(window: int) -> int:
    """Context-token count at which auto-compact actually fires."""
    return window - 20_000 - 13_000  # output reserve + headroom


def describe(settings: dict) -> str:
    window = settings.get(COMPACT_KEY)
    delta = settings.get(KEY)

    if window is None:
        trigger = 967_000  # Opus 4.8 default for 1M context
    else:
        trigger = trigger_for(window)

    if delta is None:
        delta = DEFAULT_DELTA
        warn_point = trigger - delta
        status = "using default"
    else:
        warn_point = trigger - delta
        status = "set"

    lines = [
        f"{KEY}: {status}",
        f"  warn at         ~{warn_point:,} tokens",
        f"  auto-compact    ~{trigger:,} tokens",
        f"  delta           {delta:,} tokens",
    ]

    env = os.environ.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW")
    if env:
        lines.append(f"  NOTE: env CLAUDE_CODE_AUTO_COMPACT_WINDOW={env} affects trigger point.")

    if not os.environ.get("DISABLE_AUTO_COMPACT") and not os.environ.get("DISABLE_COMPACT"):
        lines.append(
            "\nWhen context approaches the warn point, you will:\n"
            "  1. Tell the user you're near the boundary\n"
            "  2. Suggest finding a natural stopping point\n"
            "  3. Offer to create a new session if the task isn't complete\n"
            "  4. Not force-wrap without asking"
        )

    return "\n".join(lines)


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a.strip()]

    if not args:
        print(describe(load_settings()))
        return 0

    raw = args[0]

    if raw.lower() in ("auto", "reset", "unset", "default", "clear"):
        data = load_settings()
        if KEY in data:
            del data[KEY]
            save_settings(data)
            print(f"{KEY} removed — back to default ({DEFAULT_DELTA:,} token delta).")
        else:
            print(f"{KEY} was already unset.")
        return 0

    try:
        delta = int(raw)
    except ValueError:
        print(
            f"Couldn't parse '{raw}'. Expected 'auto' or a number of tokens "
            f"(e.g. 20000 or 20k).",
            file=sys.stderr,
        )
        return 1

    if not MIN_DELTA <= delta <= MAX_DELTA:
        print(
            f"Delta {delta:,} is outside the recommended {MIN_DELTA:,}-{MAX_DELTA:,} range.",
            file=sys.stderr,
        )
        return 1

    data = load_settings()
    previous = data.get(KEY)
    data[KEY] = delta
    save_settings(data)

    if previous == delta:
        print(f"{KEY} already {delta:,} — unchanged.")
    else:
        was = f"{previous:,}" if isinstance(previous, int) else "default"
        print(f"{KEY}: {was} → {delta:,}")

    print(describe(data))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
