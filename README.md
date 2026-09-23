# claude-code-workflow

A working Claude Code setup: the global `CLAUDE.md`, hooks, skills, statusline, a multi-session coordination tool, a headless-Chrome debug launcher, and the memory notes that explain why each rule exists. It is built on [Modulario](https://github.com/AkiraTheSquid/Modulario), which scores every file's structural health after each edit and runs the cross-model `/critic` review.

Everything here grew out of real incidents between April and September 2026, while running several Claude sessions at once on two production web apps. Each rule is here because something broke without it.

```bash
git clone https://github.com/AkiraTheSquid/claude-code-workflow.git
cd claude-code-workflow
./install.sh --dry-run   # see what it would do
./install.sh
```

The installer backs up anything it replaces to `~/.claude/backup-workflow-<timestamp>/`. It never overwrites an existing `CLAUDE.md` or `settings.json`: the repo version lands beside it as `CLAUDE.workflow.md` / `settings.workflow.json` so you can merge by hand. Full walkthrough, including tokens and the Vercel / Supabase / Fly / GitHub CLIs: [docs/SETUP.md](docs/SETUP.md).

## The workflow in ten lines

1. **Work inline where you can watch it.** No subagents and no Workflow fan-outs; a PreToolUse hook blocks them. If a job looks too big, stop and propose a smaller scope.
2. **Turn rules into hooks.** A rule that fails twice as prose in CLAUDE.md becomes a hook. The model is Karpathy's three layers: spec, then critic, then environment guards.
3. **Treat Git as a running instrument.** Check status before, during and after every change, and report a one-line checkpoint with a severity level. Stage explicit paths; never `git add -A` and never `git stash` in a shared repo.
4. **Coordinate live sessions through `collab`.** Sessions claim files, a hook denies edits to another session's files, and sessions pass requests and deploy announcements through a shared log.
5. **Review with a second model.** `/critic` sends every meaningful diff to Codex before commit, deploy, or saying it works.
6. **Spec first when the goal is fuzzy.** `/spec` interviews for the goal, carves the smallest slice, and gets sign-off before code.
7. **Validate, don't assert.** Check in a real browser (headless `chrome_dev` + Playwright over CDP), against real DB rows, and read deploys back. Passing tests don't mean a clean worktree.
8. **Use CLIs, not dashboards.** Vercel, Supabase, Fly and GitHub are driven from their CLIs so Claude can act and read back the result. Run Claude with `--dangerously-skip-permissions` and let the hooks be the safety net.
9. **Watch structural health.** Modulario scores each file after every edit; a blocking error stops all work.
10. **Keep sessions short and the cache warm.** Use `/clear` per task and `/refresh` to hand off, never switch models mid-session, and let a hook block cold-cache prompts.

The long version, with the incidents behind each rule, is in [docs/WORKFLOW.md](docs/WORKFLOW.md).

## What's in the repo

| Path | Installs to | What it is |
| --- | --- | --- |
| `claude/CLAUDE.md` | `~/.claude/CLAUDE.md` | Global instructions: Git discipline, collab, `/critic`, `/spec`, tooling triad, defaults |
| `claude/settings.json` | `~/.claude/settings.json` | Hooks, statusline, plugins, bypass-permissions mode, 1 h prompt cache |
| `claude/hooks/pretooluse_guard.py` | `~/.claude/hooks/` | Blocks Agent/Task/Workflow spawns (budget read from Modulario) and Vercel Workflow code |
| `claude/scripts/cache_*.py` | `~/.claude/scripts/` | Cache guard: blocks a prompt that would rebuild a cold 60k+ token cache and copies it to the clipboard; expiry watcher |
| `claude/scripts/compact_*.py`, `token_stats_hook.py`, `loc_tracker_hook.py` | `~/.claude/scripts/` | Compaction limit and notifications, per-turn token log, lines read/written |
| `claude/scripts/caveman-ultra.sh`, `graphify-startup.sh`, `stop_notify.sh` | `~/.claude/scripts/` | SessionStart mode + graph hint; desktop notification on Stop |
| `claude/statusline.sh` | `~/.claude/` | Statusline with cache warmth, hit rate and expiry |
| `claude/skills/` | `~/.claude/skills/` | `critic`, `spec`, `interview-me`, `prompt-master`, `refresh`, `modulario-ops`, `mockup` |
| `claude/commands/`, `claude/agents/` | `~/.claude/…` | `/compact-limit`, `/compact-notify`; `context7-docs` and `modulario` agent definitions |
| `collab/` | `~/.local/share/agent-collab/` | `collab` CLI, claim/deny hooks, `agent-worktree`, self-test. See [collab/README.md](collab/README.md) |
| `bin/chrome_dev` | `~/.local/bin/` | Launch a headless debug Chrome on :9222 for Playwright over CDP |
| `memory/` | (reference) | The feedback and reference notes behind the rules. See [memory/README.md](memory/README.md) |
| `docs/` | (reference) | [WORKFLOW.md](docs/WORKFLOW.md), [SETUP.md](docs/SETUP.md) |

`install.sh` also clones Modulario to `~/Applications/Modulario` if it isn't there, and links `mod` into `~/.local/bin`.

## Everything it uses, with links

### Built here

| Tool | Link | Role |
| --- | --- | --- |
| Modulario | https://github.com/AkiraTheSquid/Modulario | Structural-health scoring hooks, `mod` CLI, `run_critic.py` (the `/critic` engine), stop gate and agent budget |
| This repo | https://github.com/AkiraTheSquid/claude-code-workflow | Everything else above |

### Plugins and skills from others

| Tool | Link | Install |
| --- | --- | --- |
| caveman (compressed replies, `caveman-commit`, `caveman-review`, `compress`) | https://github.com/JuliusBrussee/caveman | `/plugin marketplace add JuliusBrussee/caveman` then `/plugin install caveman@caveman` |
| graphify (codebase knowledge graph, `/graphify`) | https://github.com/Graphify-Labs/graphify | `uv tool install graphifyy && graphify install` |
| typesafe-ai skills | https://github.com/typesafe-ai/skills | `/plugin marketplace add typesafe-ai/skills` |
| frontend-design | https://github.com/anthropics/claude-plugins-official | `/plugin install frontend-design@claude-plugins-official` |
| humanizer (optional) | https://github.com/blader/humanizer | Copy into `~/.claude/skills/` |
| Context7 (docs lookups for the `context7-docs` agent) | https://github.com/upstash/context7 | See its README for the MCP server |

`interview-me` follows Anthropic's [field guide to Claude Fable 5](https://claude.com/blog/a-field-guide-to-claude-fable-finding-your-unknowns). `prompt-master` cites Anthropic's prompting docs throughout `references/rulebook.md`.

### MCP servers and connectors

| Server | Link | Notes |
| --- | --- | --- |
| Actual Budget | https://github.com/henfrydls/actual-budget-mcp | `npx actual-budget-mcp`; `ACTUAL_BUDGET_ID` is the budget's **groupId**, not its file id |
| Sunsama | https://api.sunsama.com/mcp | Official remote with OAuth. Not the unofficial npm `mcp-sunsama` package |
| claude.ai connectors | https://claude.ai/settings/connectors | Gmail, Google Calendar, Google Drive, Claude Docs |
| Project MCP (per app) | — | Each app can ship a local stdio MCP that exposes its own DB probes, deploy and browser drivers. Local only |

Dropped on purpose: the Playwright MCP (it kept returning nothing; Playwright over CDP against `chrome_dev` replaced it) and Claude in Chrome (never drive the user's own browser).

### CLIs

| CLI | Link | Used for |
| --- | --- | --- |
| Claude Code | https://docs.claude.com/en/docs/claude-code | The harness; run with `--dangerously-skip-permissions` |
| Codex | https://github.com/openai/codex | The `/critic` reviewer (`npm install -g @openai/codex`) |
| Vercel | https://vercel.com/docs/cli | Frontend deploys |
| Supabase | https://github.com/supabase/cli | DB, migrations, project links |
| flyctl | https://fly.io/docs/flyctl/ | Backends and new services |
| GitHub | https://cli.github.com | Repos, PRs |
| Playwright | https://playwright.dev/python/ | Driven over CDP against `chrome_dev` |

## Adapting it

- **Names.** `CLAUDE.md` and some skills mention "Seth" and his projects (Delta Note, Delta Drills). Search and replace with your own.
- **Agent budget.** The PreToolUse guard reads Modulario's `max_agents` (`configs/stopgate.json`). `mod agents set 0` blocks every spawn; a higher number allows that many per session.
- **collab self-test.** `collab/selftest.sh` points at example repo paths; edit them before running it.
- **Left out on purpose.** Project deploy scripts, per-app MCP servers, the accountability gate, personal automations, tokens, and anything with user data.

Third-party tools linked above keep their own licenses; nothing of theirs is vendored here.
