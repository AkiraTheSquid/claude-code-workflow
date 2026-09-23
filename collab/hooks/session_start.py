#!/usr/bin/env python3
"""SessionStart hook: register this session and tell it who else is here.

This is the "notify Claude" half of the system. A session cannot see any other
session's context, so unless something puts it in front of the model at the
start of the turn, an agent has no way to know that another one is halfway
through the file it is about to rewrite.

Emits nothing when it is the only session in the repo — a coordination banner
on a solo session is noise, and noise is how a banner stops being read.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import collab  # noqa: E402


BRIEFING = """\
Another agent is working in this repository right now. Coordination is enforced,
not advisory: an Edit or Write to a file another live session owns will be DENIED
by a hook.

  collab status            who is live, who owns what, requests for you
  collab claim <path>      take a file (also happens automatically when you edit)
  collab release --all     give your files back when you finish an area
  collab request <path> "<what you need>"    ask the owner instead of editing
  collab log "<what you did and what it makes true>"

Two standing rules in a shared tree, both from Seth: never `git stash`, and stage
explicit paths when you commit so you cannot carry off someone else's in-flight
work.\
"""


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return

    cwd = event.get("cwd") or os.getcwd()
    session_id = event.get("session_id") or collab.current_session_id()
    if not collab.common_git_dir(cwd):
        return  # not a git repo: nothing to coordinate

    collab.touch_session(session_id, cwd=cwd)

    sessions = collab.load_sessions(cwd)
    others = [s for sid, s in sessions.items()
              if sid != session_id and collab.is_live(s)]
    inbox = [r for r in collab.open_requests(cwd, to_session=session_id)
             if r.get("to_session") == session_id]

    if not others and not inbox:
        return

    body = collab.render_status(cwd, session_id=session_id)
    context = f"# Agent collaboration\n\n{body}\n\n{BRIEFING}"
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }))


if __name__ == "__main__":
    main()
