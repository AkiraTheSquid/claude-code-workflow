#!/usr/bin/env python3
"""Timer (every 5 min): for each LIVE Claude session with a big warm cache,
nag NUDGE_MIN minutes before expiry — the only moment /compact is cheap — and,
when AUTOCOMPACT=1 and the session runs in tmux, type /compact into it.
Also a fallback EXPIRED alert if the statusline did not fire one.
Liveness = the pid the statusline recorded still runs `claude`.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cache_common import all_heartbeats, load_config, marker_once, pid_is_claude  # noqa: E402

NOTIFY = str(Path(__file__).with_name("cache_notify.py"))


def notify(kind: str, sid: str, tokens: int, detail: str = "") -> None:
    subprocess.run([sys.executable, NOTIFY, kind, sid, str(tokens), detail], timeout=60, check=False)


def autocompact(pane: str) -> bool:
    if not pane:
        return False
    r = subprocess.run(["tmux", "send-keys", "-t", pane, "/compact", "Enter"], capture_output=True, timeout=10, check=False)
    return r.returncode == 0


def main() -> int:
    cfg = load_config()
    now = time.time()
    for hb in all_heartbeats():
        sid = os.path.basename(hb["_path"]).split(".")[0]
        pid = hb.get("pid")
        if not pid_is_claude(pid):
            if now - hb.get("rendered_at", now) > 86400:
                Path(hb["_path"]).unlink(missing_ok=True)
            continue
        tokens = int(hb.get("recache_tokens_if_cold") or 0)
        expires_at = hb.get("expires_at")
        if tokens < cfg["MIN_TOKENS"] or not expires_at:
            continue
        expires_at = float(expires_at)
        left_min = (expires_at - now) / 60
        if left_min <= 0:
            if marker_once(f"{sid}.expired.{int(expires_at)}"):
                notify("expired", sid, tokens)
            continue
        if left_min <= cfg["NUDGE_MIN"] and marker_once(f"{sid}.nudge.{int(expires_at)}"):
            if cfg["AUTOCOMPACT"] and autocompact(hb.get("tmux_pane", "")):
                notify("autocompacted", sid, tokens, f"{left_min:.0f}")
            else:
                notify("nudge", sid, tokens, f"{left_min:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
