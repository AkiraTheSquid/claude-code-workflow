#!/usr/bin/env python3
"""PostToolUse hook: take ownership of whatever you just successfully edited.

Claiming by hand is the step every honour-system protocol loses first. An agent
deep in a task does not stop to update a table, and the one time it forgets is
the time another agent walks into the file. So the claim is a consequence of
editing rather than a promise to edit.

Silent by design: it prints nothing on the ordinary path. The one thing worth
saying out loud is the FIRST claim in a file another agent might care about, and
even that is left to `collab status` — a hook that comments on every edit trains
the model to stop reading hook output.

Claims are released by the SessionEnd hook, by `collab release`, or by the
session going stale. None of those is a lock: the point is to tell a concurrent
agent to keep out, not to defend against a determined one.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import collab  # noqa: E402

PATH_FIELDS = ("file_path", "notebook_path", "path")


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return

    # A failed edit changed nothing, so it earns nothing.
    response = event.get("tool_response")
    if isinstance(response, dict) and response.get("success") is False:
        return

    tool_input = event.get("tool_input") or {}
    target = next((tool_input.get(f) for f in PATH_FIELDS
                   if isinstance(tool_input.get(f), str)), None)
    if not target:
        return

    cwd = event.get("cwd") or os.getcwd()
    session_id = event.get("session_id") or collab.current_session_id()
    try:
        if not collab.common_git_dir(cwd):
            return
        collab.touch_session(session_id, cwd=cwd)
        collab.claim(session_id, [target], why="edited", cwd=cwd)
    except Exception:
        return  # coordination must never break an edit that already happened


if __name__ == "__main__":
    main()
