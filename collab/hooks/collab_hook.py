#!/usr/bin/env python3
"""One hook for every event, wired GLOBALLY in ~/.claude/settings.json.

Why global: most sessions start in ~ and `cd` into an app per command, so a hook
wired into one repo's .claude/settings.local.json never fires for them. That is
how Delta Note went unguarded while Delta Drills was guarded. Here the scope is
worked out per tool call from what the call touches — the file an Edit names,
the directories a Bash command cds into or writes to, the app an MCP tool drives
— so every repo is coordinated, each in its own room.

  SessionStart      register; brief the agent on who is live where
  UserPromptSubmit  show other agents' new log lines and anyone not yet acked
  PreToolUse        THE GATE, on state-changing calls only (reads always pass):
                      - `git stash`, and add -A / reset --hard / clean / branch
                        switch while another agent is active   → deny
                      - writing a file another live agent owns  → deny
                      - first change in a repo with no intent   → deny until
                        `collab intent "<task>"`  (this is the JOIN)
                      - another agent joined since you looked   → deny until
                        `collab ack "<how your work overlaps>"`
                      - deploy while another agent holds        → deny
                      - deploy otherwise                        → auto-logged
  PostToolUse       claim what was written; auto-log commits; push others'
                    new log lines; nudge for a milestone log on long stretches
  SessionEnd        release everything, in every repo this session touched

Fails OPEN on any internal error: a coordination layer that can wedge every
session when it breaks is worse than none. Kill switch: touch
~/.local/state/agent-collab/DISABLED.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import collab  # noqa: E402
import scan  # noqa: E402

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
PATH_FIELDS = ("file_path", "notebook_path", "path")

# MCP servers that drive a specific app: server name -> repo. Tools listed as
# state-changing need the same intent/ack as an edit; dn_deploy is a deploy.
MCP_APPS = {"delta-note": scan.APPS / "Delta-Note"}
MCP_MUTATING = {"dn_deploy", "dn_db", "dn_sql"}
MCP_DEPLOY = {"dn_deploy"}

MILESTONE_NUDGE_SECONDS = 25 * 60


# ---------------------------------------------------------------------------
# What does this tool call touch?
# ---------------------------------------------------------------------------

class Target:
    def __init__(self) -> None:
        self.repos: Dict[str, bool] = {}       # worktree root -> state-changing?
        self.writes: List[Path] = []
        self.risky: List[Tuple[str, str]] = []
        self.deploys: List[Tuple[str, str]] = []
        self.commits: List[str] = []


def target_of(event: dict) -> Target:
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    cwd = event.get("cwd") or str(Path.home())
    out = Target()
    if tool in EDIT_TOOLS:
        raw = next((tool_input.get(f) for f in PATH_FIELDS
                    if isinstance(tool_input.get(f), str)), None)
        if raw:
            path = Path(raw).expanduser()
            path = path if path.is_absolute() else Path(cwd) / path
            root = scan.repo_root(path)
            if root:
                out.repos[root] = True
                out.writes.append(path)
    elif tool == "Bash":
        result = scan.scan(str(tool_input.get("command", "")), cwd)
        if result.collab_only:
            return out
        out.repos, out.writes = result.repos, result.writes
        out.risky, out.deploys, out.commits = result.git_risky, result.deploys, result.git_commit
    elif tool.startswith("mcp__"):
        parts = tool.split("__", 2)
        if len(parts) == 3 and parts[1] in MCP_APPS:
            root = scan.repo_root(MCP_APPS[parts[1]])
            if root:
                out.repos[root] = parts[2] in MCP_MUTATING
                if parts[2] in MCP_DEPLOY:
                    out.deploys.append((root, tool))
    return out


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def emit(event_name: str, **fields) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event_name, **fields}}))


def deny(reason: str) -> None:
    emit("PreToolUse", permissionDecision="deny", permissionDecisionReason=reason)


def name_of(root: str) -> str:
    return Path(root).name


def active_others(session_id: str, root: str) -> List[dict]:
    """Live agents in this repo that are actually working: declared or holding files."""
    claims = collab.load_claims(root)
    holders = {c.get("session_id") for c in claims.values()}
    return [s for s in collab.live_others(session_id, root)
            if s.get("task") or s.get("session_id") in holders]


def room(session_id: str, root: str, mine: List[str]) -> str:
    claims = collab.load_claims(root)
    others = active_others(session_id, root)
    if not others:
        return f"No other agent is active in {name_of(root)} right now."
    lines = [f"Active in {name_of(root)}:"]
    lines += [collab.describe_session(s, claims, mine=mine) for s in others]
    return "\n".join(lines)


def push_lines(session_id: str, roots: List[str]) -> str:
    """Other agents' log lines this session has not seen yet, across its repos."""
    chunks = []
    for root in roots:
        rows = collab.unread_log(session_id, root)
        if rows:
            body = "\n".join(f"  [{r.get('label', '?')}] {r.get('text', '')[:300]}" for r in rows)
            chunks.append(f"collab — new from other agents in {name_of(root)}:\n{body}")
    return "\n\n".join(chunks)


def my_live_roots(session_id: str) -> List[str]:
    roots = []
    for key, entry in collab.session_repos(session_id).items():
        cwd = entry.get("cwd", "")
        if cwd and Path(cwd).is_dir() and collab.age_seconds(entry.get("last_seen", "")) \
                < collab.STALE_SESSION_SECONDS:
            roots.append(cwd)
    return roots


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

def gate(event: dict, session_id: str) -> None:
    target = target_of(event)
    if not target.repos:
        return
    reasons = []
    for root, mutating in target.repos.items():
        collab.touch_session(session_id, cwd=root)
        if not mutating:
            continue
        reason = check_repo(session_id, root, target)
        if reason:
            reasons.append(reason)
    if reasons:
        deny("\n\n".join(reasons))
        return
    for root, cmd in target.deploys:
        if root:
            collab.append_log(session_id, f"deploying: {cmd}", cwd=root, kind="deploy")
    for root in set(target.commits):
        # Remember HEAD so the post hook logs a commit only if one really landed.
        collab.update_session(session_id, root, pre_commit_head=collab._git(["rev-parse", "HEAD"], root))


def check_repo(session_id: str, root: str, target: Target) -> str:
    repo = name_of(root)
    others = active_others(session_id, root)

    for risky_root, why in target.risky:
        if risky_root != root:
            continue
        if "stash" in why:
            return (f"collab: refused in {repo} — {why}. Seth's standing rule is never "
                    f"`git stash` in these repos. For a clean tree use a temporary "
                    f"`git worktree add`, or commit explicit paths.")
        if others:
            return (f"collab: refused in {repo} — {why}.\n{room(session_id, root, [])}\n"
                    f"If Seth explicitly approved this, he can run it himself with `! <command>`.")

    for path in target.writes:
        if scan.repo_root(path) != root:
            continue
        rel = collab.repo_relative(str(path), root)
        owner = collab.owner_of(rel, root)
        if owner and owner.get("session_id") != session_id:
            s = owner.get("session", {})
            return (f"collab: {rel} is owned by agent [{s.get('label', '?')}] "
                    f"({s.get('task') or owner.get('why') or 'task not stated'}), live in "
                    f"{s.get('worktree', '?')} on {s.get('branch', '?')}. Do NOT write it — "
                    f"not with Edit, not with sed/redirects. Work elsewhere, or ask:\n"
                    f"  collab --repo {root} request {rel} \"<the change you need and why>\"")

    me = collab.load_sessions(root).get(session_id) or {}
    claims = collab.load_claims(root)
    mine = collab.files_of(me, claims)
    if not me.get("task") or me.get("rejoin_needed"):
        back = " (you were away long enough that the others stopped counting you)" \
            if me.get("rejoin_needed") else ""
        return (f"collab: before changing anything in {repo}, say what you are about to do"
                f"{back}. Run:\n"
                f"  collab --repo {root} intent \"<one line: your task>\" --files <files you expect to change>\n"
                f"That announces you to every other agent in {repo}, claims those files, and "
                f"shows you anything you'd overlap with. Then retry.\n\n"
                f"{room(session_id, root, mine)}")

    arrivals = collab.unacked_arrivals(session_id, root)
    if arrivals:
        lines = "\n".join(collab.describe_session(s, claims, mine=mine) for s in arrivals)
        return (f"collab: a new agent joined {repo} since you last looked. Before your next "
                f"change there, check how your work overlaps theirs and log it:\n{lines}\n\n"
                f"Your task: {me.get('task')}; your files: {', '.join(mine) or 'none yet'}.\n"
                f"  collab --repo {root} ack \"<overlap: none | which files/areas and how you'll split them>\"\n"
                f"If you overlap on a file, settle it in the log or with `collab request` before editing.")

    if any(r == root for r, _ in target.deploys):
        holds = collab.holds_by_others(session_id, root)
        if holds:
            held = "\n".join(f"  [{s.get('label', '?')}] {s['hold'].get('text', '')}" for s in holds)
            return (f"collab: deploy of {repo} refused — another agent has a deploy hold:\n{held}\n"
                    f"Wait for `hold --release` (you'll see it in your context), or ask in the log:\n"
                    f"  collab --repo {root} log \"<why you need to deploy now>\"")
    return ""


# ---------------------------------------------------------------------------
# After the tool ran
# ---------------------------------------------------------------------------

def after(event: dict, session_id: str) -> None:
    response = event.get("tool_response")
    if isinstance(response, dict) and response.get("success") is False:
        return
    target = target_of(event)
    notes = []
    for root, mutating in target.repos.items():
        if not mutating:
            continue
        task = (collab.load_sessions(root).get(session_id) or {}).get("task", "")
        writes = [p for p in target.writes if scan.repo_root(p) == root and p.exists()]
        if writes:
            collab.claim(session_id, [str(p) for p in writes], why=task or "edited", cwd=root)
        if root in target.commits:
            before = (collab.load_sessions(root).get(session_id) or {}).get("pre_commit_head", "")
            if collab._git(["rev-parse", "HEAD"], root) != before:
                head = collab._git(["log", "-1", "--format=%h %s"], root)
                collab.append_log(session_id, f"committed {head}", cwd=root, kind="commit")
            collab.update_session(session_id, root, pre_commit_head=None)
        if any(r == root for r, _ in target.deploys):
            notes.append(f"collab: log the deploy RESULT for {name_of(root)} now: "
                         f"`collab --repo {root} log \"<deployed ok / failed: …>\"`")
        me = collab.load_sessions(root).get(session_id) or {}
        last = me.get("last_log_at") or me.get("intent_at") or ""
        if me.get("task") and collab.age_seconds(last) > MILESTONE_NUDGE_SECONDS and \
                collab.age_seconds(me.get("nudged_at", "")) > MILESTONE_NUDGE_SECONDS:
            collab.update_session(session_id, root, nudged_at=collab.now())
            notes.append(f"collab: no log line from you in {name_of(root)} for "
                         f"{int(collab.age_seconds(last) // 60)} min. Log the milestone you're at: "
                         f"`collab --repo {root} log \"<what now works / what's next>\"`")
    pushed = push_lines(session_id, my_live_roots(session_id))
    context = "\n\n".join(x for x in [pushed, *notes] if x)
    if context:
        emit("PostToolUse", additionalContext=context)


# ---------------------------------------------------------------------------
# Session lifecycle and prompts
# ---------------------------------------------------------------------------

BRIEF = ("Coordination is automatic and enforced by hooks: reads are never blocked; your "
         "first change in a repo asks for `collab intent`, a newcomer's arrival asks you "
         "for `collab ack`, and every refusal prints the exact command to run. Your "
         "session id and repo are picked up automatically. Log milestones with "
         "`collab log \"…\"`; finish with `collab done \"…\"`.")


def session_start(event: dict, session_id: str) -> None:
    cwd = event.get("cwd") or ""
    root = scan.repo_root(Path(cwd)) if cwd else None
    if root:
        collab.touch_session(session_id, cwd=root)
    who = collab.render_who(session_id)
    if who.startswith("No live agents") and not root:
        return
    emit("SessionStart", additionalContext=f"# Agents working right now (collab)\n{who}\n\n{BRIEF}")


def prompt_submit(event: dict, session_id: str) -> None:
    parts = []
    roots = my_live_roots(session_id)
    pushed = push_lines(session_id, roots)
    if pushed:
        parts.append(pushed)
    for root in roots:
        arrivals = collab.unacked_arrivals(session_id, root)
        if arrivals:
            names = ", ".join(f"[{s.get('label', '?')}] {s.get('task', '')}" for s in arrivals)
            parts.append(f"collab: new in {name_of(root)}: {names}. Your next change there "
                         f"will ask you to `collab ack` how your work overlaps.")
    if parts:
        emit("UserPromptSubmit", additionalContext="\n\n".join(parts))


def session_end(event: dict, session_id: str) -> None:
    for key, entry in collab.session_repos(session_id).items():
        cwd = entry.get("cwd", "")
        if not cwd or not Path(cwd).is_dir():
            continue
        me = collab.load_sessions(cwd).get(session_id) or {}
        if me.get("task"):
            collab.append_log(session_id, f"session ended (was: {me['task']})", cwd=cwd, kind="leave")
        collab.end_session(session_id, cwd)


HANDLERS = {
    "SessionStart": session_start,
    "UserPromptSubmit": prompt_submit,
    "PreToolUse": gate,
    "PostToolUse": after,
    "SessionEnd": session_end,
}


def main() -> None:
    if (collab.STATE_ROOT / "DISABLED").exists() or os.environ.get("MODULARIO_CRITIC_ACTIVE"):
        return
    try:
        event = json.load(sys.stdin)
        session_id = event.get("session_id") or collab.current_session_id()
        handler = HANDLERS.get(event.get("hook_event_name", ""))
        if handler:
            handler(event, session_id)
    except Exception as exc:  # fail open, but leave a trace for debugging
        try:
            with (collab.STATE_ROOT / "hook-errors.log").open("a") as fh:
                fh.write(f"{collab.now()} {type(exc).__name__}: {exc}\n")
        except OSError:
            pass


if __name__ == "__main__":
    main()
