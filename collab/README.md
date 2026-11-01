# agent-collab

## Purpose
- Keeps several Claude Code sessions working in one git repository without
  overwriting each other, and tells each of them that the others exist.
- The concern is not correctness of any one edit. It is that two agents cannot
  see each other's context, so the first sign of a collision is normally a merge
  conflict, a half-written feature on a deploy, or a file that silently lost half
  its changes.

## Owns
- Session liveness, file ownership, cross-agent requests, and the shared log.
- The Claude Code hooks that enforce all of the above.
- `agent-worktree`, which hands an agent an isolated git worktree when claims
  are the wrong tool.

## Does NOT own
- Anything about what the agents are building. This is process, not project.
- Repo rules and orientation — those are each repo's `CLAUDE.md`.
- Merging. `agent-worktree finish` prints the merge and stops.

## Key Files
- `hooks/collab_hook.py`: **the** hook since 2026-10-08, wired GLOBALLY in
  `~/.claude/settings.json` for SessionStart, UserPromptSubmit, PreToolUse,
  PostToolUse and SessionEnd. Works out each tool call's repo(s) itself, gates
  state-changing calls (intent → ack → claims → risky git → deploy holds),
  auto-claims, auto-logs commits/deploys, and pushes other agents' log lines.
- `scan.py`: reads a Bash command — repos touched, state-changing or not, files
  written, risky git, deploys. Unknown commands count as state-changing.
- `collab.py` → `~/.local/bin/collab`: state, and the CLI over it.
- LEGACY (still importable; no longer wired): `hooks/session_start.py` registers the session and injects the "who else is
  here" briefing. This is the notification half — without it an agent has no way
  to learn another one exists.
- `hooks/pre_edit_guard.py`: **denies** an edit to a file another live session
  owns, and says how to ask instead.
- `hooks/post_edit_claim.py`: takes ownership of whatever you just edited, so
  claiming is a consequence of working rather than a thing to remember.
- `hooks/session_end.py`: hands every file back.
- `install-hooks.py`: installs/upgrades the global wiring (`--uninstall`;
  `--remove-legacy <worktree>` strips the old per-repo wiring). Backups of any
  settings file it touches go to `~/.local/state/agent-collab/settings-backups/`.
- `agent-worktree` → `~/.local/bin/agent-worktree`: `new` / `list` / `finish`.
- `COLLAB.md`: the protocol, addressed to an agent that just got the banner.
- `selftest.sh`: legacy hooks, 14 checks. `selftest-gate.sh`: the global hook,
  three simulated sessions in a throwaway repo, 32 checks. Run both after any change.

## Data & External Dependencies
- State: `~/.local/state/agent-collab/<repo-name>-<hash>/` — `sessions.json`,
  `claims.json`, `log.jsonl`, `requests.jsonl`. Keyed on the repo's **common git
  dir**, so every worktree of a repo shares one view. Override with
  `AGENT_COLLAB_STATE`.
- Python 3 stdlib and `git`. Nothing else, deliberately: this runs on every edit.
- Claude Code hook events `SessionStart`, `PreToolUse`, `PostToolUse`,
  `SessionEnd`, which supply `session_id`, `cwd` and `tool_input`.

## How It Works (Flow, since 2026-10-08)
1. Every Bash/Edit/Write/MultiEdit/NotebookEdit/`mcp__delta-note__*` call → the
   hook finds the repos it touches (file path; `cd`/`git -C`/path args/redirect
   targets; MCP server → app) and heartbeats the session in each.
2. Read-only → allowed. State-changing → refused, with the exact command, until:
   the session has declared `collab intent` in that repo (its JOIN, logged and
   announced); it has `collab ack`ed every agent that joined after it last
   looked; it writes no file another live agent owns; it runs no risky git op
   while others are active (`git stash` never); and no other agent holds deploys.
3. After the call: written files are claimed, a real commit is logged with its
   sha, a deploy gets a "log the result" nudge, other agents' unseen log lines are
   pushed into context, and 25 quiet minutes earn a milestone nudge.
4. UserPromptSubmit pushes the same unseen lines + pending arrivals to an idle
   session; SessionEnd releases it in every repo it touched (via `_index.json`).
5. CLI: session id from `CLAUDE_CODE_SESSION_ID`; repo from `--repo`, else cwd,
   else the session's last-touched repo — so `collab log` from ~ lands right.

## How It Worked Before (per-repo legacy flow)
1. A session starts. `session_start.py` registers it and, **only if another
   session is live**, injects a briefing naming who is there and what they hold.
2. The agent edits a file. `pre_edit_guard.py` checks the claim: another live
   owner means deny, with the owner, their worktree, their branch, and the
   `collab request` command to use instead.
3. The edit succeeds. `post_edit_claim.py` records the claim.
4. Requests, logs and status are read by either side at any time.
5. The session ends, or goes quiet for 90 minutes, and its claims lapse.

## Invariants & Constraints
- **Claims are keyed by repo-relative path.** Two agents in two worktrees editing
  the same file are the collision they look like; keying on absolute paths would
  hide exactly the case worktrees are supposed to make safe.
- **A dead session owns nothing.** Liveness is a heartbeat on every hook, with a
  90-minute stale window. A claim that outlives its session turns this into the
  thing people disable.
- **The guard fails OPEN.** Unreadable state, no git repo, a malformed event: the
  edit is allowed. A coordination layer that can halt all work when it breaks is
  worse than no coordination layer.
- **Nothing lives inside the repository.** Delta Drills' Colab deploy runs
  `git add -A && git push` in its worktree; a coordination file in the tree would
  be committed to a deploy branch and shipped. `.claude/` and `.agent-task` are
  in the shared `.git/info/exclude` for the same reason — `.gitignore` is
  per-branch and would not cover the deploy branches.
- **Wire through `settings.local.json`, never `settings.json`.** In Delta Drills
  the latter is already TRACKED on `deploy-colab` — swept in by exactly the
  `add -A` above — so writing machine-absolute hook paths there commits and
  pushes them. Claude Code merges the two files, so hooks that legitimately
  belong to the repo (graphify's guards) keep working from `settings.json`.
- **Agent worktrees are siblings of the repo, not children of it.** Delta Note
  put them under `.claude/worktrees/`; here that would be inside the `add -A`.
- **This is coordination, not locking.** It stops an agent that does not know
  better. Bash write detection is a heuristic (`scan.py`): `python script.py`
  that writes files is "state-changing" (gated) but its targets are unknown, so
  claims are not checked for it. Not a security boundary.
- **Reads are never gated**, and the gate only ever asks for a `collab`
  command, which is itself never gated — no deadlock is possible.
- **Global wiring lives in `~/.claude/settings.json`**, outside every repo, so
  the deploy-sweep hazard above does not apply to it. Per-repo wiring is removed
  (`--remove-legacy`) so nothing fires twice.

## Extension Points
- Wire another repo: `install-hooks.py <that worktree>`. State separates itself
  by repo automatically.
- New rule to enforce: another hook script here plus an entry in
  `install-hooks.py::WIRING`, then re-run the installer on each worktree.
- New coordination surface (a design doc, a decision record) belongs in the state
  directory next to `log.jsonl`, not in the repo.

## Known Issues, Recurring Bugs, and Pain Points (and How to Prevent Them)

- **Hooks are not active in the session that installed them** — `ACTIVE`
  - When it happens: always, on first install.
  - Symptom: you install the wiring, edit a claimed file, and nothing stops you.
  - Root cause: `.claude/settings.json` is read at session start.
  - Prevention/fix: it takes effect in the next session. Verify with
    `selftest.sh` rather than by trying it in the session that installed it.
  - Status: `ACTIVE`, inherent.

- **An untracked `.claude/` swept into a deploy commit** — `RESOLVED`
  - When it happens: a deploy script that runs `git add -A` in a worktree
    carrying repo-scoped Claude config.
  - Symptom: local agent configuration committed to a deploy branch and pushed.
  - Root cause: the folder is untracked but not ignored, and `-A` does not care.
  - Prevention/fix: `.claude/` and `.agent-task` are in `.git/info/exclude`,
    which is shared across worktrees and cannot drift per branch.
  - Status: `RESOLVED` for Delta Drills. Delta Note has the same shape of hazard
    documented in its own `.claude/README.md` and has NOT been given this fix.

- **Claims on generated or append-only files** — `ACTIVE`
  - When it happens: an agent edits a manifest, a lockfile or a log.
  - Symptom: everyone else is blocked on a file that was never really contended.
  - Root cause: auto-claiming does not know which files are interesting.
  - Prevention/fix: `UNCLAIMABLE_SUFFIXES` / `UNCLAIMABLE_NAMES` in `collab.py`.
    Add to them when this bites; the list is deliberately short.
  - Status: `ACTIVE` — a heuristic, not a solution.

- **Hook wiring committed to a deploy branch** — `RESOLVED`
  - When it happens: installing repo-scoped hooks into `.claude/settings.json`.
  - Symptom: `git status` in the Colab worktree shows `M .claude/settings.json`,
    and the next Colab deploy commits and pushes local machine paths.
  - Root cause: that file is tracked on `deploy-colab`, unlike on `main`, so the
    `.git/info/exclude` entry does not cover it — exclusion only applies to
    untracked paths.
  - Prevention/fix: the installer writes `settings.local.json`, which is
    untracked and therefore covered by the exclude.
  - Status: `RESOLVED`.

## Recent Changes
- 2026-10-08: GLOBAL + enforced join protocol (Seth: "it should just always
  work and I never have to remind the AI about collab"). One hook for every repo;
  intent-on-join, ack-on-arrival, Bash write/claim checks, risky-git refusals,
  deploy holds, auto-logged commits/deploys, pushed log lines, milestone nudges,
  `CLAUDE_CODE_SESSION_ID` identity (kills `shell-<ppid>` ghosts) and
  last-repo scoping (kills the `no-repo` channel). New CLI: `intent`, `ack`,
  `hold`, `done`, `who`, `--repo`. Per-repo wiring removed from Delta-Drills-Local,
  -Colab and -agents/features. Backup of the pre-change tool:
  `~/.local/share/agent-collab.bak-2026-10-08`.
- 2026-08-18: Created, porting Delta Note's `COLLAB-focus-timer.md` protocol into
  something enforced. The markdown version worked only for agents that read it;
  an agent that never opened the file was invisible to the whole system, and the
  first sign of trouble was a merge. The claims table, the request channel and
  the append-only log survive; the honour system does not. Wired into
  Delta-Drills-Colab and Delta-Drills-Local.
