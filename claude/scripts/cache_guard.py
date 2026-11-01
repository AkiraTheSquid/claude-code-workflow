#!/usr/bin/env python3
"""UserPromptSubmit hook: refuse to send a prompt into a COLD cache when the
rebuild is big. Blocking is the only moment a warning helps; after the request
leaves, the full-price rewrite is already billed.

Flow: cold + big + no recent ack -> save prompt (file + clipboard), notify,
exit 2 (Claude Code erases the typed text, hence the clipboard). Resend within
ACK_MIN minutes -> allowed, and Claude is told the rebuild just happened so it
can suggest /compact. Slash commands (/clear, /compact, /refresh) always pass.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cache_common import (TTL_SECONDS, compacted_since_last_turn, fmt_tokens, load_config,  # noqa: E402
                          read_heartbeat, state_path, transcript_last_turn)


def cold_state(sid: str, transcript: str) -> tuple[bool, int, int]:
    """(cold?, rebuild tokens, idle minutes). Heartbeat from the statusline is
    authoritative when present (it carries Claude Code's own expires_at)."""
    now = time.time()
    hb = read_heartbeat(sid) or {}
    last_ts, ctx = transcript_last_turn(transcript)
    idle_min = int((now - last_ts) / 60) if last_ts else 0
    tokens = int(hb.get("recache_tokens_if_cold") or ctx or 0)
    expires_at = hb.get("expires_at")
    if expires_at and hb.get("rendered_at", 0) >= (last_ts or 0) - 5:
        cold = now >= float(expires_at)
    else:
        cold = bool(last_ts) and now - last_ts >= TTL_SECONDS
    return cold, tokens, idle_min


def stash_prompt(sid: str, prompt: str) -> Path:
    p = state_path(f"{sid}.blocked-prompt.txt")
    p.touch(mode=0o600, exist_ok=True)
    p.chmod(0o600)  # a prompt can carry secrets; never world-readable
    p.write_text(prompt)
    try:
        # xclip forks a child that owns the selection; it must NOT inherit our stdout,
        # or Claude Code (which reads the hook's stdout to EOF) waits until the hook times out.
        proc = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                env={"DISPLAY": ":0", "PATH": "/usr/bin:/bin"}, start_new_session=True)
        proc.communicate(prompt.encode(), timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return p


def main() -> int:
    # Headless runners with no terminal to "send again" (the Delta Note chat
    # worker, ops/claude-chat) set this and make the cold-cache call themselves.
    if os.environ.get("CACHE_GUARD_SKIP") == "1":
        return 0
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    prompt = data.get("prompt", "")
    ptype = data.get("prompt_type") or ("slash_command" if prompt.lstrip().startswith("/") else "user")
    if ptype != "user":
        return 0  # slash commands (/clear, /compact, /refresh) and control requests must always pass
    sid = data.get("session_id", "")
    transcript = data.get("transcript_path", "")
    if not sid or not transcript or not Path(transcript).exists():
        return 0
    if compacted_since_last_turn(transcript):
        return 0  # already compacted: next turn rebuilds only the small summary, never block
    cfg = load_config()
    cold, tokens, idle_min = cold_state(sid, transcript)
    if not cold or tokens < cfg["MIN_TOKENS"]:
        return 0

    ack = state_path(f"{sid}.ack")
    if ack.exists() and time.time() - ack.stat().st_mtime < cfg["ACK_MIN"] * 60:
        ack.unlink(missing_ok=True)
        ctx = (f"[cache-guard] The prompt cache was cold (idle {idle_min} min); this turn rebuilt about "
               f"{fmt_tokens(tokens)} tokens at full price. Seth chose to continue. If this session's "
               f"remaining work does not need the old history, say so in one line and suggest /compact or /refresh.")
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ctx}}))
        return 0

    ack.write_text(str(int(time.time())))
    saved = stash_prompt(sid, prompt)
    subprocess.Popen([sys.executable, str(Path(__file__).with_name("cache_notify.py")), "blocked", sid, str(tokens)],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sys.stderr.write(
        f"🧊 CACHE COLD — idle {idle_min} min (> 60 min TTL), context ≈ {fmt_tokens(tokens)} tokens.\n"
        f"Sending now rewrites all {fmt_tokens(tokens)} at full price (~20× a warm turn).\n"
        f"  /clear    free, start fresh (usually right: the repo remembers)\n"
        f"  /refresh  hand off a 2k-token brief to a new session\n"
        f"  /compact  same cold cost once, then cheap\n"
        f"Your prompt is on the clipboard and in {saved}.\n"
        f"Paste + send again within {cfg['ACK_MIN']} min to go ahead anyway.\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
