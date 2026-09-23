#!/usr/bin/env python3
"""Statusline helper: read the statusline JSON on stdin, print ONE cache line,
write this session's heartbeat (pid + expires_at + rebuild size) for the
watcher, and fire the EXPIRED alert once when a big cache goes cold.

Claude Code re-renders the statusline when a warm cache reaches expires_at, so
this script IS the expiry event for a live session; no polling needed for that.
Usage: cache_status.py [ppid]   (statusline.sh passes $PPID; the real claude pid is found by walking up)
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cache_common import claude_ancestor, fmt_tokens, load_config, marker_once, tmux_pane_of, write_heartbeat  # noqa: E402


def main() -> int:
    pid = claude_ancestor()  # argv[1] ($PPID) is only a fallback hint; the wrapper shell is not claude
    if pid is None and len(sys.argv) > 1 and sys.argv[1].isdigit():
        pid = claude_ancestor(int(sys.argv[1]))
    try:
        d = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    pc = d.get("prompt_cache") or {}
    sid = d.get("session_id", "")
    if not pc or not sid:
        print("cache: —")
        return 0
    now = time.time()
    expires_at = pc.get("expires_at")
    warm = bool(pc.get("warm")) and (not expires_at or now < float(expires_at))
    tokens = int(pc.get("recache_tokens_if_cold") or (d.get("context_window") or {}).get("total_input_tokens") or 0)
    hit = pc.get("hit_ratio")
    misses = pc.get("misses", 0)
    cause = ((pc.get("last_miss_cause") or {}).get("causes") or [""])[0]
    left = int((float(expires_at) - now) / 60) if expires_at and warm else 0

    write_heartbeat(sid, {"pid": pid, "transcript_path": d.get("transcript_path", ""), "cwd": d.get("cwd", ""),
                          "expires_at": expires_at, "warm": warm, "recache_tokens_if_cold": tokens,
                          "tmux_pane": tmux_pane_of(pid)})

    if warm:
        line = f"cache: warm {left}m left · hit {hit:.0%}" if hit is not None else f"cache: warm {left}m left"
        if misses:
            line += f" · {misses} miss" + (f" ({cause})" if cause else "")
        line += f" · cold-cost {fmt_tokens(tokens)}"
    else:
        line = f"cache: 🧊 COLD — next prompt rewrites {fmt_tokens(tokens)}" + (f" · {misses} miss" if misses else "")
        cfg = load_config()
        if tokens >= cfg["MIN_TOKENS"] and expires_at and marker_once(f"{sid}.expired.{int(float(expires_at))}"):
            subprocess.Popen([sys.executable, str(Path(__file__).with_name("cache_notify.py")), "expired", sid, str(tokens)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
