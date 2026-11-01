"""Shared bits for the prompt-cache guard: config, state dir, transcript tail, heartbeats.

The cache is server-side and cannot be copied; the only things we can know are
(a) when Claude Code says it expires (statusline `prompt_cache.expires_at`) and
(b) how big the rebuild would be (`recache_tokens_if_cold`, or the last turn's
context from the transcript). Everything here reads those two facts.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

CONFIG = Path.home() / ".config" / "claude-cache-guard.env"
STATE = Path.home() / ".local" / "state" / "claude" / "cache-guard"
TTL_SECONDS = 3600  # promptCacheTtl is 1h in ~/.claude/settings.json


def load_config() -> dict[str, int]:
    cfg = {"MIN_TOKENS": 60000, "NUDGE_MIN": 10, "AUTOCOMPACT": 0, "TELEGRAM": 1, "DESKTOP": 1, "ACK_MIN": 15}
    try:
        for raw in CONFIG.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            try:
                cfg[k.strip()] = int(v.strip())
            except ValueError:
                pass
    except OSError:
        pass
    return cfg


def state_path(name: str) -> Path:
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    return STATE / name


def marker_once(name: str) -> bool:
    """True the first time a marker is requested, False after. Dedups alerts."""
    p = state_path(name)
    try:
        with p.open("x") as fh:  # exclusive create: statusline and timer cannot both win
            fh.write(str(int(time.time())))
    except FileExistsError:
        return False
    return True


def transcript_last_turn(path: str | Path, tail_bytes: int = 1 << 20) -> tuple[float | None, int]:
    """(epoch seconds of the last assistant response with cache tokens, its context size)."""
    try:
        p = Path(path)
        size = p.stat().st_size
        with p.open("rb") as fh:
            fh.seek(max(0, size - tail_bytes))
            chunk = fh.read().decode("utf-8", "ignore")
    except OSError:
        return None, 0
    for line in reversed(chunk.splitlines()):
        if '"assistant"' not in line or '"usage"' not in line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("type") != "assistant":
            continue
        u = (d.get("message") or {}).get("usage") or {}
        ctx = u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("input_tokens", 0)
        if ctx <= 0:
            continue
        ts = d.get("timestamp")
        try:
            when = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() if ts else None
        except ValueError:
            when = None
        return when, ctx
    return None, 0


def compacted_since_last_turn(path: str | Path, tail_bytes: int = 1 << 20) -> bool:
    """True when a /compact (compact_boundary) is newer than the last assistant response.
    Compaction logs no assistant usage line, so without this check the guard still sees
    the pre-compact context size and timestamp and blocks the cheap post-compact turn."""
    try:
        p = Path(path)
        size = p.stat().st_size
        with p.open("rb") as fh:
            fh.seek(max(0, size - tail_bytes))
            chunk = fh.read().decode("utf-8", "ignore")
    except OSError:
        return False
    for line in reversed(chunk.splitlines()):
        if '"compact_boundary"' in line:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") == "system" and d.get("subtype") == "compact_boundary":
                return True
        elif '"assistant"' in line and '"usage"' in line:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") == "assistant":
                return False
    return False


def heartbeat_path(session_id: str) -> Path:
    return state_path(f"{session_id}.heartbeat.json")


def write_heartbeat(session_id: str, data: dict) -> None:
    data = dict(data, rendered_at=int(time.time()))
    tmp = heartbeat_path(session_id).with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    os.replace(tmp, heartbeat_path(session_id))


def read_heartbeat(session_id: str) -> dict | None:
    try:
        return json.loads(heartbeat_path(session_id).read_text())
    except (OSError, json.JSONDecodeError):
        return None


def all_heartbeats() -> list[dict]:
    out = []
    for p in STATE.glob("*.heartbeat.json"):
        try:
            d = json.loads(p.read_text())
            d["_path"] = str(p)
            out.append(d)
        except (OSError, json.JSONDecodeError):
            continue
    return out


def claude_ancestor(pid: int | None = None, hops: int = 8) -> int | None:
    """Walk up from pid (default: this process) to the nearest `claude` process.
    The statusline runs under a throwaway `bash -c` wrapper, so $PPID is NOT claude."""
    pid = pid or os.getpid()
    for _ in range(hops):
        if pid_is_claude(pid):
            return pid
        try:
            for line in Path(f"/proc/{pid}/status").read_text().splitlines():
                if line.startswith("PPid:"):
                    pid = int(line.split()[1])
                    break
            else:
                return None
        except (OSError, ValueError):
            return None
        if pid <= 1:
            return None
    return None


def pid_is_claude(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        return Path(f"/proc/{pid}/comm").read_text().strip() == "claude"
    except OSError:
        return False


def tmux_pane_of(pid: int | None) -> str:
    if not pid:
        return ""
    try:
        env = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
    except OSError:
        return ""
    for item in env:
        if item.startswith(b"TMUX_PANE="):
            return item.split(b"=", 1)[1].decode()
    return ""


def fmt_tokens(n: int) -> str:
    return f"{n/1000:.0f}k" if n >= 1000 else str(n)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
