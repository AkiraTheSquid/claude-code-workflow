#!/usr/bin/env python3
# ==============================================================================
#  ██  CARD 01 — NO SUBAGENTS. EVER.  ██
# ------------------------------------------------------------------------------
#  Claude: you are reading this because you opened the file that stops you.
#
#  You do not spawn Agent. You do not spawn Task. You do not spawn Workflow.
#  Not one. Not "just two". Not "it's embarrassingly parallel". Not because a
#  skill file said MANDATORY. Seth's rule outranks every skill in the system.
#
#  This is a CARD, not a suggestion. It exists because instructions buried in a
#  prompt did not hold. On 2026-07-23 a task about SAVING tokens spawned 30
#  agents, burned ~1.5M subagent tokens rebuilding a graph that already existed
#  and was better, and silently deleted load-bearing identifiers from 10
#  READMEs. Every one had to be reverted. Seth had already said no. Twice.
#
#  The failure mode is never "I decided to break the rule." It is:
#    "this specific case is different"  -> it is not
#    "the skill told me to"             -> the skill does not outrank Seth
#    "inline would be too slow"         -> then say so and let Seth decide
#
#  Yes, you could edit this file and delete the guard. That is precisely why
#  this card is here: the block is trivial to remove and removing it is a
#  betrayal, not a workaround. If you are editing this file to get past it,
#  stop and go ask Seth.
#
#  Too big to do inline?  ->  STOP. Say so. Propose a smaller scope. Wait.
#  Legit override         ->  Seth raises "Max agents" in `mod` settings (or sets
#                             MODULARIO_ALLOW_AGENTS=1). YOU do not raise it. Editing
#                             stopgate.json yourself to buy yourself agents is the
#                             same betrayal as deleting the guard.
# ==============================================================================
"""PreToolUse hard guardrails (Karpathy Layer-3 "never do" rules, enforced at tool level).

Two things this blocks that a CLAUDE.md text rule cannot:

  1. RETIRED 2026-07-25 — see the note at rule 1 below. It guarded raw Delta Note
     launchers; the desktop app no longer exists, so the hazard does not either.

  2. Introducing Vercel Workflow CODE into a file (the "use workflow"/"use step"
     directives, or an @vercel/workflow | @workflow/* | workflow/api import). The
     permission `deny` list in settings.local.json already covers Bash package
     installs, but it cannot inspect Write/Edit file content -- this closes that gap.

  3. Spawning subagents (Agent / Task / Workflow). Seth's standing rule is NEVER --
     stated flat on 2026-07-23 after a token-optimization task fanned out 30 agents,
     wasted ~1.5M subagent tokens rebuilding an existing graph, and silently dropped
     load-bearing identifiers from 10 READMEs. A CLAUDE.md sentence was not enough:
     the model rationalized past "minimize subagents", and skills such as graphify
     instruct "MANDATORY: use the Agent tool", which reads as authorization. Seth's
     rule outranks any skill, so this is enforced here instead of by prose.

     The allowance is a BUDGET, set by Seth in `mod` -> settings -> "Max agents"
     (configs/stopgate.json, key `max_agents`; 0 = the standing never rule). Each
     Agent/Task/Workflow call spends one, counted per Claude session in
     Modulario/data/state/agent_budget.json, so raising it to 2 authorizes exactly
     two spawns and the third is blocked again. A fresh session starts fresh.
     Escape hatch for a single call: MODULARIO_ALLOW_AGENTS=1 in the environment.

Contract: read the PreToolUse event JSON on stdin. Exit 0 to allow. Exit 2 to block,
with the reason on stderr (fed back to the agent). Any parse failure fails OPEN
(exit 0) so a malformed event never wedges the session.
"""
import json
import os
import re
import sys
import time

MODULARIO = os.path.expanduser("~/Applications/Modulario")
BUDGET_PATH = os.path.join(MODULARIO, "data", "state", "agent_budget.json")
BUDGET_TTL = 7 * 24 * 3600  # forget sessions that have not spawned in a week

# --- rule 1: RETIRED 2026-07-25 --------------------------------------------------
# This blocked raw Delta Note launchers (run_reflection_app.sh / dev_dnote / a
# Delta-Note .desktop) because a second un-deduped instance raced the shared backend
# and clobbered the DB -> "text disappears" data loss.
#
# The rule is gone because the hazard is gone, not because it was inconvenient:
# `linux/` was deleted on 2026-07-25 (commit b1e4438) and Delta Note is web-only.
# There is no Electron shell, no electron_backend.py, and therefore no second
# process to race. The regex matched on filenames alone, so with the files deleted
# it produced only false positives -- it blocked the very commands cleaning up the
# dead launchers, and blocked commit messages that merely mentioned them.
#
# Do NOT restore this without a desktop build to protect. If one ever comes back,
# so should the guard.

# --- rule 2: Vercel Workflow code in files ---------------------------------------
WORKFLOW_IMPORT = re.compile(r"""(?:from\s+|require\(\s*|import\s+)['"](?:@vercel/workflow|@workflow/[^'"]+|workflow/api|workflow)['"]""")
WORKFLOW_DIRECTIVE = re.compile(r"""^\s*['"]use (?:workflow|step)['"]\s*;?\s*$""", re.M)
CODE_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

# --- rule 3: subagent spawning (cost + loss of visibility) ------------------------
AGENT_TOOLS = {"Agent", "Task", "Workflow"}


def agent_budget() -> int:
    """How many subagents this session may spawn, per Modulario's settings.

    Anything unreadable means 0. This is the one place in the file where a
    failure must NOT fail open: a missing config is not permission.
    """
    try:
        sys.path.insert(0, os.path.join(MODULARIO, "scripts"))
        import stopgate_config  # noqa: E402
        return int(stopgate_config.max_agents())
    except Exception:
        return 0


def _read_budget_state() -> dict:
    try:
        with open(BUDGET_PATH, encoding="utf-8") as fh:
            state = json.load(fh)
        return state if isinstance(state, dict) else {}
    except Exception:
        return {}


def spend_agent(session: str, limit: int) -> int:
    """Charge one spawn to this session; return how many remain AFTER it.

    Returns -1 when the session is already at its limit. Counting per session
    is what makes the number a budget rather than a switch -- a runaway fan-out
    exhausts it and stops, and a new session starts over.
    """
    state = _read_budget_state()
    now = int(time.time())
    state = {k: v for k, v in state.items()
             if isinstance(v, dict) and now - int(v.get("ts", 0)) < BUDGET_TTL}
    spent = int(state.get(session, {}).get("spent", 0))
    if spent >= limit:
        return -1
    state[session] = {"spent": spent + 1, "ts": now}
    try:
        os.makedirs(os.path.dirname(BUDGET_PATH), exist_ok=True)
        tmp = BUDGET_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
        os.replace(tmp, BUDGET_PATH)
    except OSError:
        pass  # an unwritable ledger must not wedge the session
    return limit - (spent + 1)


def block(msg: str) -> None:
    sys.stderr.write(msg)
    sys.exit(2)


def check_file(text: str, path: str) -> None:
    if not text or not path.endswith(CODE_EXTS):
        return
    hit = WORKFLOW_IMPORT.search(text) or WORKFLOW_DIRECTIVE.search(text)
    if hit:
        block(
            "BLOCKED (cost guard): Vercel Workflow code detected -> `" + hit.group(0).strip() + "`.\n"
            "Per global CLAUDE.md, do not use Vercel Workflow / @vercel/workflow / @workflow/*.\n"
            "Use a plain API route, cron, queue, background job, or DB state machine instead.\n"
            "Only Seth can override this in the same task."
        )


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # fail open
    tool = event.get("tool_name", "")
    ti = event.get("tool_input", {}) or {}
    if tool in AGENT_TOOLS and os.environ.get("MODULARIO_ALLOW_AGENTS") != "1":
        limit = agent_budget()
        left = spend_agent(str(event.get("session_id") or "unknown"), limit) if limit > 0 else -1
        if left < 0:
            block(
                "BLOCKED (no-subagents guard): tried to spawn `" + tool + "`.\n"
                + ("Seth's standing rule is NEVER use subagents -- work inline so he can watch.\n"
                   if limit == 0 else
                   f"This session's subagent budget ({limit}) is already spent.\n")
                + "A skill saying 'MANDATORY: use the Agent tool' (e.g. graphify) does NOT "
                "override this; do that step inline instead.\n"
                "If the job is genuinely too big to do inline, stop and say so, propose a "
                "narrower scope, and let Seth decide.\n"
                "Only Seth raises the allowance: `mod` -> settings (e) -> Max agents. "
                "Do not edit stopgate.json yourself."
            )
        sys.stderr.write(
            f"[modulario] subagent allowed -- {left} of {limit} left this session.\n"
        )
    if tool == "Write":
        check_file(ti.get("content", ""), ti.get("file_path", ""))
    elif tool == "Edit":
        check_file(ti.get("new_string", ""), ti.get("file_path", ""))
    sys.exit(0)


if __name__ == "__main__":
    main()
