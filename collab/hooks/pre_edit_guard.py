#!/usr/bin/env python3
"""PreToolUse hook: refuse to edit a file another live session is holding.

The honour-system version of this protocol failed in a specific way — an agent
that never read the coordination file was invisible to it, and the first sign of
trouble was a merge or a half-written feature reaching a deploy. A hook has the
property the markdown table did not: it fires whether or not the agent knows the
protocol exists.

Deliberately narrow:

  denies   an Edit/Write/NotebookEdit to a file a DIFFERENT, LIVE session claimed
  allows   everything else, including reads, and including a file whose claimant
           has gone quiet — a dead session's claim must not outlive it

Failure is open, not closed. If the state is unreadable this hook allows the
edit: a broken coordination system that stops all work is worse than one that
stops none. The deny path is the exception, and it explains exactly how to
proceed rather than just saying no.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import collab  # noqa: E402

PATH_FIELDS = ("file_path", "notebook_path", "path")


def allow() -> None:
    sys.exit(0)


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def main() -> None:
    try:
        event = json.load(sys.stdin)
        cwd = event.get("cwd") or os.getcwd()
        session_id = event.get("session_id") or collab.current_session_id()
        tool_input = event.get("tool_input") or {}
    except Exception:
        allow()
        return

    target = next((tool_input.get(f) for f in PATH_FIELDS
                   if isinstance(tool_input.get(f), str)), None)
    if not target:
        allow()
        return

    try:
        collab.touch_session(session_id, cwd=cwd)
        rel = collab.repo_relative(target, cwd)
        owner = collab.owner_of(rel, cwd)
    except Exception:
        allow()
        return

    if not owner or owner.get("session_id") == session_id:
        allow()
        return

    session = owner.get("session", {})
    why = owner.get("why") or "no reason recorded"
    deny(
        f"{rel} is owned by agent [{session.get('label', '?')}], live in "
        f"{session.get('worktree', '?')} on branch {session.get('branch', '?')} "
        f"since {owner.get('since', '?')[:19]} — {why}. "
        f"Their task: {session.get('task') or 'not stated'}.\n\n"
        f"Do NOT edit it. Either work elsewhere, or ask them:\n"
        f"  collab request {rel} \"<the change you need and why>\"\n"
        f"Then keep going on something else; they apply it and resolve the request. "
        f"Run `collab status` to see everything currently held."
    )


if __name__ == "__main__":
    main()
