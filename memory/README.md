# Memory notes

These are the feedback and reference notes behind the rules in `CLAUDE.md`, copied from a live Claude Code memory folder. Each file holds one fact. Most explain **why** a rule exists and **how to apply** it, often with the incident that caused it.

To use them, copy the ones you want into your own memory folder (`~/.claude/projects/<project>/memory/`) and add a one-line pointer for each to that folder's `MEMORY.md`. They mention "Seth" and his projects (Delta Note, Delta Drills); edit those to fit.

## How to work

| Note | Rule |
| --- | --- |
| [feedback-minimize-subagents](feedback-minimize-subagents.md) | Never spawn subagents; work inline unless an agent is asked for by name |
| [feedback-never-use-workflow](feedback-never-use-workflow.md) | Never use the Workflow tool: one run burned a whole session limit in 20 minutes |
| [feedback-never-stash-in-shared-repo](feedback-never-stash-in-shared-repo.md) | Never `git stash` in a shared worktree; use a temporary `git worktree` |
| [feedback-deploy-and-commit-each-feature](feedback-deploy-and-commit-each-feature.md) | Commit, push and deploy every finished feature without asking |
| [feedback_validate_dont_assert](feedback_validate_dont_assert.md) | Check generated output independently instead of asserting it's fine |
| [feedback_apply_obvious_fixes](feedback_apply_obvious_fixes.md) | Apply an obvious or approved fix without re-asking |
| [feedback_skip_permission_for_dev_installs](feedback_skip_permission_for_dev_installs.md) | Install routine dev tools without asking; report what you did |
| [feedback-never-drive-seths-brave](feedback-never-drive-seths-brave.md) | Never drive the user's own browser; use headless `chrome_dev` |
| [feedback-de-vercel-direction](feedback-de-vercel-direction.md) | New services go to Fly or portable containers, not Vercel |
| [feedback_modulario_templates](feedback_modulario_templates.md) | Fill Modulario templates with Read then Edit, never Write |
| [feedback_modulario_splits](feedback_modulario_splits.md) | Extract into sibling modules instead of growing warning-level files |
| [critic-invoke-as-claude-author](critic-invoke-as-claude-author.md) | Run `/critic` as author `claude` so Codex reviews |

## How the pieces work

| Note | What it covers |
| --- | --- |
| [karpathy-critic-spec-skills](karpathy-critic-spec-skills.md) | `/critic` and `/spec`, Karpathy Layers 2 and 1 |
| [pretooluse-hard-guards](pretooluse-hard-guards.md) | The PreToolUse guard: subagent spawns, Vercel Workflow code (Layer 3) |
| [agent-collab-infra](agent-collab-infra.md) | Claims, the deny-on-edit hook, the shared log, isolated worktrees |
| [claude-cache-guard](claude-cache-guard.md) | Cold-cache prompt guard, statusline cache line, expiry nudge |
| [token-audit-2026-09-16](token-audit-2026-09-16.md) | What a token-waste audit measured and changed |
| [chrome-dev-command](chrome-dev-command.md) | `chrome_dev`: a debug Chrome on :9222 at any URL |
| [reference-cdp-playwright-harness](reference-cdp-playwright-harness.md) | Driving `chrome_dev` from a Python Playwright venv over CDP |
