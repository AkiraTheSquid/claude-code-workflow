#!/usr/bin/env python3
"""
Keep several Claude sessions out of each other's way in one git repository.

Ported from the hand-maintained COLLAB-focus-timer.md protocol in Delta Note,
where two agents shared a worktree, could not see each other's context, and
coordinated entirely on the honour system. That worked because a person was
watching. This is the same protocol with the parts a machine can hold:

  who is live          sessions register themselves from a SessionStart hook
  who owns what        claims, taken automatically the first time you edit a file
  what you may not do  a PreToolUse hook DENIES an edit to a file another live
                       session owns, and tells you how to ask for it instead
  what happened        one shared append-only log, plus per-file requests

Everything lives OUTSIDE the repository, under ~/.local/state/agent-collab/<repo>/.
Two reasons. Delta Drills' Colab deploy runs `git add -A && git push` in its
worktree, so any coordination file left in the tree would be committed to a
deploy branch and shipped. And a claim has to be visible from every worktree of
the repo at once — which a file inside one worktree is not.

Claims are keyed by REPO-RELATIVE path, so two agents in two different
worktrees editing the same file are recognised as the collision they are: they
will conflict at merge, not at write.

Usage:
    collab.py status [--json]          who is live, who owns what
    collab.py claim <path>... [--why]  take files (usually automatic)
    collab.py release <path>...        give them back; `--all` for everything
    collab.py request <path> <text>    ask the owner for a change
    collab.py inbox                    requests addressed to you
    collab.py resolve <id> [<text>]    close a request you own
    collab.py log <text>               append to the shared log
    collab.py history [-n N]           read the shared log
    collab.py whoami                   this session's identity
    collab.py sessions --gc            forget sessions that went stale
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

STATE_ROOT = Path(os.environ.get("AGENT_COLLAB_STATE") or
                  Path.home() / ".local" / "state" / "agent-collab")

# A session that has not fired a hook in this long is treated as gone: its
# claims stop blocking anyone. Long enough to survive a session sitting idle
# while its human reads something; short enough that a crashed session does not
# hold a file hostage for a working day.
STALE_SESSION_SECONDS = 90 * 60

# Files nobody should be blocked on. They are append-mostly or regenerated, and
# a claim on them would stall every other agent for no benefit.
UNCLAIMABLE_SUFFIXES = (".lock", ".log", ".tmp")
UNCLAIMABLE_NAMES = ("MEMORY.md",)


# ---------------------------------------------------------------------------
# Repo identity
# ---------------------------------------------------------------------------

def _git(args: List[str], cwd: Optional[str] = None) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def common_git_dir(cwd: Optional[str] = None) -> str:
    """The ONE .git shared by every worktree of this repo, or ''."""
    return _git(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd)


def repo_key(cwd: Optional[str] = None) -> str:
    """Stable per-repository state key: readable name + a hash for uniqueness.

    Keyed on the common git dir rather than the working directory, so every
    worktree of a repo — main, deploy, and each agent's isolated copy — lands
    on the same state and can therefore see each other's claims.
    """
    git_dir = common_git_dir(cwd)
    if not git_dir:
        return "no-repo"
    root = Path(git_dir).parent
    digest = hashlib.sha1(str(root).encode()).hexdigest()[:8]
    return f"{root.name}-{digest}"


def worktree_roots(cwd: Optional[str] = None) -> List[Path]:
    roots = []
    for line in _git(["worktree", "list", "--porcelain"], cwd).splitlines():
        if line.startswith("worktree "):
            roots.append(Path(line.split(" ", 1)[1]))
    return roots


def repo_relative(path: str, cwd: Optional[str] = None) -> str:
    """Path as the REPO sees it, so two worktrees agree on what file this is.

    An absolute path outside every worktree is returned unchanged — it cannot
    collide with anyone, and silently rewriting it would be worse than leaving
    it alone.
    """
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path(cwd or os.getcwd()) / candidate
    try:
        candidate = candidate.resolve()
    except OSError:
        return str(candidate)
    for root in worktree_roots(cwd):
        try:
            return str(candidate.relative_to(root.resolve()))
        except (ValueError, OSError):
            continue
    return str(candidate)


def is_claimable(rel_path: str) -> bool:
    name = Path(rel_path).name
    if name in UNCLAIMABLE_NAMES:
        return False
    return not name.endswith(UNCLAIMABLE_SUFFIXES)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def state_dir(cwd: Optional[str] = None) -> Path:
    path = STATE_ROOT / repo_key(cwd)
    path.mkdir(parents=True, exist_ok=True)
    return path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _locked(path: Path):
    """Exclusive across processes. Several sessions write this concurrently."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(path.suffix + ".lock")
    with lock.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, payload) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _append_jsonl(path: Path, entry: dict) -> None:
    with _locked(path):
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def sessions_path(cwd=None) -> Path:
    return state_dir(cwd) / "sessions.json"


def claims_path(cwd=None) -> Path:
    return state_dir(cwd) / "claims.json"


def log_path(cwd=None) -> Path:
    return state_dir(cwd) / "log.jsonl"


def requests_path(cwd=None) -> Path:
    return state_dir(cwd) / "requests.jsonl"


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def current_session_id() -> str:
    """This session's id.

    Hooks pass it in; a human at a shell has none, so fall back to a stable
    per-terminal id rather than inventing a new session on every command.
    """
    explicit = os.environ.get("CLAUDE_SESSION_ID", "").strip()
    if explicit:
        return explicit
    return f"shell-{os.getppid()}"


def age_seconds(stamp: str) -> float:
    try:
        then = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return float("inf")
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - then).total_seconds()


def is_live(session: dict) -> bool:
    if session.get("ended_at"):
        return False
    return age_seconds(session.get("last_seen", "")) < STALE_SESSION_SECONDS


def load_sessions(cwd=None) -> Dict[str, dict]:
    return _read_json(sessions_path(cwd), {})


def touch_session(session_id: str, *, cwd: str, label: str = "", task: str = "") -> dict:
    """Register or heartbeat. Every hook calls this; it is the liveness signal."""
    path = sessions_path(cwd)
    with _locked(path):
        sessions = _read_json(path, {})
        session = sessions.get(session_id) or {
            "session_id": session_id,
            "started_at": now(),
            "label": "",
            "task": "",
        }
        session["last_seen"] = now()
        session["cwd"] = cwd
        session["worktree"] = str(Path(cwd).name)
        session["branch"] = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
        session.pop("ended_at", None)
        if label:
            session["label"] = label
        if task:
            session["task"] = task
        if not session.get("label"):
            session["label"] = _auto_label(sessions, session_id)
        sessions[session_id] = session
        _write_json(path, sessions)
    return session


def _auto_label(sessions: Dict[str, dict], session_id: str) -> str:
    """A, B, C… — short enough to say in a log line, stable per session."""
    taken = {s.get("label") for s in sessions.values() if s.get("session_id") != session_id}
    for i in range(26):
        letter = chr(ord("A") + i)
        if letter not in taken:
            return letter
    return session_id[:6]


def end_session(session_id: str, cwd: str) -> None:
    """Mark gone and drop its claims. A finished session holds nothing."""
    path = sessions_path(cwd)
    with _locked(path):
        sessions = _read_json(path, {})
        if session_id in sessions:
            sessions[session_id]["ended_at"] = now()
            _write_json(path, sessions)
    release(session_id, [], cwd=cwd, everything=True)


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------

def load_claims(cwd=None) -> Dict[str, dict]:
    return _read_json(claims_path(cwd), {})


def owner_of(rel_path: str, cwd=None) -> Optional[dict]:
    """The LIVE session holding this file, or None.

    A claim from a session that has gone quiet is not an owner. Blocking on a
    dead session's claim is how a coordination system becomes the thing people
    disable.
    """
    claim = load_claims(cwd).get(rel_path)
    if not claim:
        return None
    session = load_sessions(cwd).get(claim.get("session_id", ""))
    if not session or not is_live(session):
        return None
    return {**claim, "session": session}


def claim(session_id: str, paths: List[str], *, why: str = "", cwd=None) -> Dict[str, str]:
    """Take files for this session. Returns {rel_path: outcome}."""
    cwd = cwd or os.getcwd()
    path_file = claims_path(cwd)
    results: Dict[str, str] = {}
    with _locked(path_file):
        claims = _read_json(path_file, {})
        sessions = _read_json(sessions_path(cwd), {})
        for raw in paths:
            rel = repo_relative(raw, cwd)
            if not is_claimable(rel):
                results[rel] = "skipped (not claimable)"
                continue
            existing = claims.get(rel)
            if existing and existing.get("session_id") != session_id:
                other = sessions.get(existing.get("session_id", ""))
                if other and is_live(other):
                    results[rel] = f"HELD by {other.get('label', '?')}"
                    continue
            claims[rel] = {
                "session_id": session_id,
                "why": why or (existing or {}).get("why", ""),
                "since": (existing or {}).get("since") if existing and existing.get(
                    "session_id") == session_id else now(),
            }
            results[rel] = "claimed"
        _write_json(path_file, claims)
    return results


def release(session_id: str, paths: List[str], *, cwd=None, everything: bool = False) -> List[str]:
    cwd = cwd or os.getcwd()
    path_file = claims_path(cwd)
    released = []
    with _locked(path_file):
        claims = _read_json(path_file, {})
        if everything:
            for rel, held in list(claims.items()):
                if held.get("session_id") == session_id:
                    del claims[rel]
                    released.append(rel)
        else:
            for raw in paths:
                rel = repo_relative(raw, cwd)
                held = claims.get(rel)
                if held and held.get("session_id") == session_id:
                    del claims[rel]
                    released.append(rel)
        _write_json(path_file, claims)
    return released


def claims_by_session(cwd=None) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = {}
    for rel, held in load_claims(cwd).items():
        grouped.setdefault(held.get("session_id", "?"), []).append(rel)
    return grouped


# ---------------------------------------------------------------------------
# Log and requests
# ---------------------------------------------------------------------------

def append_log(session_id: str, text: str, *, cwd=None, kind: str = "note") -> dict:
    cwd = cwd or os.getcwd()
    session = load_sessions(cwd).get(session_id, {})
    entry = {
        "at": now(), "session_id": session_id,
        "label": session.get("label", "?"), "kind": kind, "text": text,
    }
    _append_jsonl(log_path(cwd), entry)
    return entry


def add_request(session_id: str, rel_path: str, text: str, *, cwd=None) -> dict:
    cwd = cwd or os.getcwd()
    held = load_claims(cwd).get(rel_path) or {}
    entry = {
        "id": uuid.uuid4().hex[:8],
        "at": now(),
        "from_session": session_id,
        "from_label": load_sessions(cwd).get(session_id, {}).get("label", "?"),
        "to_session": held.get("session_id", ""),
        "path": rel_path,
        "text": text,
        "status": "open",
    }
    _append_jsonl(requests_path(cwd), entry)
    return entry


def open_requests(cwd=None, *, to_session: Optional[str] = None) -> List[dict]:
    resolved = set()
    entries = []
    for row in _read_jsonl(requests_path(cwd)):
        if row.get("status") == "resolved":
            resolved.add(row.get("id"))
        entries.append(row)
    out = []
    seen = set()
    for row in reversed(entries):
        rid = row.get("id")
        if rid in seen or rid in resolved:
            continue
        seen.add(rid)
        if to_session and row.get("to_session") not in ("", to_session):
            continue
        out.append(row)
    return list(reversed(out))


def resolve_request(request_id: str, text: str, *, cwd=None) -> None:
    _append_jsonl(requests_path(cwd), {
        "id": request_id, "at": now(), "status": "resolved", "text": text,
    })


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_status(cwd=None, *, session_id: str = "") -> str:
    cwd = cwd or os.getcwd()
    sessions = load_sessions(cwd)
    grouped = claims_by_session(cwd)
    live = {sid: s for sid, s in sessions.items() if is_live(s)}

    lines = []
    others = [s for sid, s in live.items() if sid != session_id]
    if not others:
        lines.append("No other agent is working in this repo right now.")
    else:
        lines.append(f"{len(others)} other agent(s) live in this repo:")
        for session in sorted(others, key=lambda s: s.get("started_at", "")):
            sid = session.get("session_id", "")
            held = sorted(grouped.get(sid, []))
            lines.append(
                f"  [{session.get('label', '?')}] {session.get('worktree', '?')} "
                f"({session.get('branch', '?')}) — {session.get('task') or 'task not stated'}"
            )
            if held:
                lines.append(f"      owns: {', '.join(held[:8])}"
                             + (f" (+{len(held) - 8} more)" if len(held) > 8 else ""))

    mine = sorted(grouped.get(session_id, []))
    if mine:
        lines.append(f"\nYou own {len(mine)} file(s): {', '.join(mine[:8])}"
                     + (f" (+{len(mine) - 8} more)" if len(mine) > 8 else ""))

    inbox = open_requests(cwd, to_session=session_id) if session_id else []
    mine_inbox = [r for r in inbox if r.get("to_session") == session_id]
    if mine_inbox:
        lines.append(f"\n{len(mine_inbox)} open request(s) for you:")
        for row in mine_inbox[:5]:
            lines.append(f"  {row['id']}  {row['path']} — {row['text'][:100]} "
                         f"(from {row.get('from_label', '?')})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    subs = parser.add_subparsers(dest="command")

    p_status = subs.add_parser("status", help="who is live and who owns what")
    p_status.add_argument("--json", action="store_true")

    p_claim = subs.add_parser("claim", help="take files for this session")
    p_claim.add_argument("paths", nargs="+")
    p_claim.add_argument("--why", default="")

    p_release = subs.add_parser("release", help="give files back")
    p_release.add_argument("paths", nargs="*")
    p_release.add_argument("--all", action="store_true")

    p_request = subs.add_parser("request", help="ask the owner of a file for a change")
    p_request.add_argument("path")
    p_request.add_argument("text")

    subs.add_parser("inbox", help="requests addressed to you")

    p_resolve = subs.add_parser("resolve", help="close a request")
    p_resolve.add_argument("request_id")
    p_resolve.add_argument("text", nargs="?", default="done")

    p_log = subs.add_parser("log", help="append to the shared log")
    p_log.add_argument("text")

    p_hist = subs.add_parser("history", help="read the shared log")
    p_hist.add_argument("-n", type=int, default=25)

    p_who = subs.add_parser("whoami", help="this session's identity")
    p_who.add_argument("--label", default="")
    p_who.add_argument("--task", default="")

    p_sessions = subs.add_parser("sessions", help="list sessions")
    p_sessions.add_argument("--gc", action="store_true", help="forget stale sessions")

    args = parser.parse_args()
    cwd = os.getcwd()
    session_id = current_session_id()

    if not args.command:
        parser.print_help()
        return

    if args.command == "status":
        if args.json:
            print(json.dumps({
                "sessions": load_sessions(cwd),
                "claims": load_claims(cwd),
                "requests": open_requests(cwd),
            }, indent=2))
        else:
            print(render_status(cwd, session_id=session_id))

    elif args.command == "claim":
        touch_session(session_id, cwd=cwd)
        for rel, outcome in claim(session_id, args.paths, why=args.why, cwd=cwd).items():
            print(f"{outcome:>22}  {rel}")

    elif args.command == "release":
        released = release(session_id, args.paths, cwd=cwd, everything=args.all)
        print(f"released {len(released)}: {', '.join(released) or '(nothing)'}")

    elif args.command == "request":
        rel = repo_relative(args.path, cwd)
        entry = add_request(session_id, rel, args.text, cwd=cwd)
        owner = owner_of(rel, cwd)
        who = owner["session"].get("label", "?") if owner else "nobody (file is free)"
        print(f"request {entry['id']} on {rel} -> {who}")

    elif args.command == "inbox":
        rows = [r for r in open_requests(cwd, to_session=session_id)
                if r.get("to_session") == session_id]
        if not rows:
            print("No open requests for you.")
        for row in rows:
            print(f"{row['id']}  {row['path']}\n    {row['text']}\n    from {row.get('from_label')} at {row['at']}")

    elif args.command == "resolve":
        resolve_request(args.request_id, args.text, cwd=cwd)
        print(f"resolved {args.request_id}")

    elif args.command == "log":
        touch_session(session_id, cwd=cwd)
        entry = append_log(session_id, args.text, cwd=cwd)
        print(f"[{entry['label']}] logged")

    elif args.command == "history":
        for row in _read_jsonl(log_path(cwd))[-args.n:]:
            print(f"{row['at'][:19]}  [{row.get('label', '?')}] {row.get('text', '')}")

    elif args.command == "whoami":
        session = touch_session(session_id, cwd=cwd, label=args.label, task=args.task)
        print(json.dumps(session, indent=2))

    elif args.command == "sessions":
        sessions = load_sessions(cwd)
        if args.gc:
            path = sessions_path(cwd)
            with _locked(path):
                keep = {sid: s for sid, s in _read_json(path, {}).items() if is_live(s)}
                dropped = set(sessions) - set(keep)
                _write_json(path, keep)
            for sid in dropped:
                release(sid, [], cwd=cwd, everything=True)
            print(f"forgot {len(dropped)} stale session(s)")
            return
        for sid, session in sessions.items():
            mark = "live" if is_live(session) else "gone"
            print(f"[{session.get('label', '?')}] {mark:>4}  {session.get('worktree', '?')} "
                  f"({session.get('branch', '?')})  {session.get('task', '')}  {sid}")


if __name__ == "__main__":
    main()
