---
name: pretooluse-hard-guards
description: PreToolUse hook hard-enforces the costliest footguns at tool level (Vercel Workflow code + subagent spawning; the Delta Note launch rule was retired 2026-07-25)
metadata: 
  node_type: memory
  type: project
  modified: 2026-07-28T17:56:58.657Z
---

Karpathy-method Layer-3 "never do" rules promoted from CLAUDE.md text (soft) to a **PreToolUse hook** (hard, agent-can't-bypass). Built 2026-07-10.

**Script:** `~/.claude/hooks/pretooluse_guard.py`, registered in `~/.claude/settings.json` under `hooks.PreToolUse`. Exit 2 = block (reason to stderr); fails OPEN on any parse error. ⚠️ The matcher must cover `Agent|Task|Workflow` as well as `Bash|Write|Edit`, or rule 3 never fires.

The file opens with a large **CARD 01 — NO SUBAGENTS. EVER.** banner comment, added 2026-07-23 at Seth's request: he wanted a visible reminder in code rather than a rule buried in prompt text, explicitly acknowledging the model could delete the guard and stating that doing so is a betrayal rather than a workaround.

**What it blocks (2 rules; was 3):**
1. ~~**Data loss** — raw Delta Note launch~~ — **RETIRED 2026-07-25.** The hazard was a second Electron instance racing the shared backend; `linux/` was deleted (`b1e4438`) and Delta Note is web-only, so there is no backend process to race and no launcher to match. Because the regex keyed on filenames alone, it degenerated into pure false positives — it blocked the commands cleaning up the dead launchers, and blocked a `git commit` whose *message* mentioned them. `check_bash` and the Bash dispatch branch are gone; a comment block in the file records why, and says to restore it only if a desktop build returns. Verified after the change: subagent + Workflow blocks still fire (exit 2), ordinary Bash/Write pass (exit 0). See [[deltanote-brave-pair]].
2. **Cost** — Vercel Workflow CODE written into a `.ts/.tsx/.js/.jsx/.mjs/.cjs` file (`"use workflow"`/`"use step"` directive, or `@vercel/workflow`|`@workflow/*`|`workflow/api` import). Closes the gap the `settings.local.json` `deny` list (Bash-only) can't see. `.md`/`.txt` docs excluded → no false-positive when writing *about* the rule. See [[feedback-never-use-workflow]].

3. **Cost + lost visibility** — spawning `Agent` / `Task` / `Workflow`. Seth's rule is NEVER ([[feedback-minimize-subagents]]). Added 2026-07-23 after a token-*optimization* task fanned out 30 agents, wasted ~1.5M subagent tokens rebuilding a Delta-Note graph that already existed and was richer, and silently dropped load-bearing identifiers from 10 READMEs (all reverted). Prose alone failed twice: the model rationalized past "minimize subagents", and graphify's SKILL.md says "MANDATORY: use the Agent tool", which reads as authorization.

**2026-07-28 — the block became a BUDGET.** Seth asked for a settings-level dial so he no longer has to fight the guard when he does want agents. `max_agents` now lives in Modulario's `configs/stopgate.json` (default `0` = the old never-rule), editable two ways: **`mod agents [count|reset]`** (`Modulario/scripts/cli_agents.py`) or the "Max agents per session" row in the `mod` TUI settings page (`e`). The guard spends one per Agent/Task/Workflow call and counts per Claude `session_id` in `Modulario/data/state/agent_budget.json` (pruned after 7 days), so setting 2 authorizes exactly two spawns and the third blocks again; a new session starts fresh. `MODULARIO_ALLOW_AGENTS=1` still overrides without spending.
- The config read **fails CLOSED** — unreadable or missing config means 0, because a missing config is not permission.
- ⚠️ The two surfaces fight: the TUI holds the whole config in memory and `save()` writes all of it, so a TUI left open overwrites a CLI change on its next toggle. Close it before using `mod agents`.
- Raising the number is **Seth's** call. An agent that edits `stopgate.json` to buy itself agents has defeated the control, not used it — the card in the hook says so explicitly.

**If a legit launch gets blocked:** Seth runs it himself via `! <cmd>`. 10/10 case-suite passed; verified live (hook fired on a real Bash call). Same-model context: [[kolb-vault-conceptual-its]] (Karpathy 3-layer method mapped onto Seth's stack — Layer-3 environment).
