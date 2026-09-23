---
name: agent-collab-infra
description: "Enforced multi-agent coordination for one repo — claims, deny-on-edit hook, shared log, isolated worktrees. Lives at ~/.local/share/agent-collab/, wired into Delta-Drills-Colab + Delta-Drills-Local."
metadata: 
  node_type: memory
  type: project
  modified: 2026-08-18T23:40:17.476Z
---

2026-08-18. Built after this very session was bitten by it: another agent was
editing `questions.py` / `export_questions.py` in the shared Delta-Drills
worktree and neither of us knew.

Ported Delta Note's `COLLAB-focus-timer.md` honour-system protocol
([[delta-note-agent-collab-file]]) into something **enforced**.

- Tool: `~/.local/share/agent-collab/` — `collab.py` (→ `collab` on PATH),
  `hooks/`, `install-hooks.py`, `agent-worktree`, `COLLAB.md`, `selftest.sh`
  (14 checks, two simulated sessions through the real hooks).
- State: `~/.local/state/agent-collab/<repo>-<hash>/`, keyed on the repo's
  **common git dir** so every worktree shares one view.
- 🔴 Claiming is AUTOMATIC on a successful edit (PostToolUse). A PreToolUse hook
  **denies** an Edit/Write to a file another *live* session owns and prints
  `collab request <path> "<what>"` as the way through.
- 🔴 Claims keyed by REPO-RELATIVE path, so two agents in two worktrees editing
  the same file are caught — that is the collision worktrees exist to survive.
- Liveness = heartbeat on every hook; stale after 90 min. Guard **fails OPEN**.
- Isolation: `agent-worktree new <name>` → branch `agent/<name>` in a **sibling**
  dir `<repo-parent>/Delta-Drills-agents/<name>`. NOT under `.claude/` the way
  Delta Note did it — see the deploy hazard below.

🔴 **The Colab deploy is why nothing lives in the tree.**
`This-Directory-Only/scripts/deploy_delta_drills_colab.sh` runs
`git add -A && git commit && git push` inside `Delta-Drills-Colab`. Anything
left in that worktree — untracked included — is committed to `deploy-colab` and
pushed. Hence: tooling outside the repo, `.claude/` + `.agent-task` in the
shared `.git/info/exclude`, and wiring written to
**`.claude/settings.local.json`, never `settings.json`** (the latter is already
TRACKED on `deploy-colab`, so the exclude does not cover it — exclusion only
applies to untracked paths).

Hooks take effect at the NEXT session start, never in the one that installed
them. Verify with `selftest.sh`, not by trying it live.
2026-08-22 — 🔴 **A claim can outlive its session by 90 minutes and block you.**
`collab` keys identity to `CLAUDE_SESSION_ID`, and falls back to
`shell-<os.getppid()>` when that env var is absent — so every Bash tool call in
a Claude session registers a *different* shell session, and claims scatter
across ids that die with the shell. Two consequences seen in one evening in
Delta-Drills-Local:

- An agent that announced "files released" had released under its NEWEST shell
  id while `index.html`, `infotips-registry.js` and `practice/README.md` stayed
  claimed by a shell id that no longer existed. `is_live()` only checks
  `last_seen < 90 min`, so those orphans blocked a real session for an hour.
- Fix that worked: `ps -p <pid>` on the `shell-<pid>` id — no process means the
  session is genuinely gone. Then set `ended_at` on it in
  `~/.local/state/agent-collab/<repo>-<hash>/sessions.json` (an `is_live()`
  short-circuit) and claim normally. Log the takeover with the ps evidence.
- 🔴 **Always export `CLAUDE_SESSION_ID=<real session id>` before every `collab`
  call** or your own claims land under a throwaway shell id and you cannot
  release them later.
- 🔴 `collab` resolves paths against CWD: running it from inside
  `Local_Deployed_Shared/` claims `Local_Deployed_Shared/Local_Deployed_Shared/...`
  — a claim on a path that does not exist, protecting nothing. Run it from the
  repo root.
- Claims only gate the Edit/Write tools. An agent working through Bash
  (`sed`/heredoc, as bypass mode encourages) writes straight through a claim, so
  a claimed file can still come back with someone else's hunks in it — check
  `git diff` before committing a shared file.
