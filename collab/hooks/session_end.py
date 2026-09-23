#!/usr/bin/env python3
"""SessionEnd hook: hand every file back.

Without this a finished session's claims sit there until they go stale, and the
next agent is blocked for an hour and a half by somebody who left. The stale
timeout in collab.py is the safety net for a session that dies without ever
reaching this hook; this is the ordinary path.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import collab  # noqa: E402


def main() -> None:
    try:
        event = json.load(sys.stdin)
        cwd = event.get("cwd") or os.getcwd()
        session_id = event.get("session_id") or collab.current_session_id()
        if collab.common_git_dir(cwd):
            collab.end_session(session_id, cwd)
    except Exception:
        return


if __name__ == "__main__":
    main()
