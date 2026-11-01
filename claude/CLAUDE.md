# Workflow rules (paste into ~/.claude/CLAUDE.md)

## Drive every website through its CLI or MCP

Use installed CLIs and MCP servers proactively; don't make me restate that they
exist. GitHub → `gh`. Vercel → `vercel`. Supabase → `supabase` (and its MCP for
SQL). Gmail/Calendar/Drive/Notion → their MCP connectors. Read logs, run queries,
open PRs and deploy yourself instead of asking me to click through a dashboard.
If an obviously relevant tool is missing, say why and use the best fallback.

## `collab` — talk to the other live sessions, every time

`collab` is the only channel between concurrent Claude sessions in one repo.
Global hooks enforce it: your first change in a repo is refused until
`collab intent "<task>" --files …`; when another agent joins, your next change is
refused until `collab ack "<overlap>"`; writing another live agent's file is
refused → `collab request <path> "<what you need>"`. A refusal is a message, not a
bug: run the command it prints. Never route around it. `collab done "<summary>"`
when the work lands.

- Before any deploy: `collab status`. If another session's work is unfinished,
  don't deploy; `collab request` and wait.
- Half-finished state that would break a deploy → `collab hold "<why>"`, then
  `collab hold --release` when fixed.
- No `git add -A` / `git add .` in a shared repo. Stage explicit paths.

## /critic — cross-model verification, by default

Run `/critic` without asking after any non-trivial diff, the moment you believe
a bug is fixed (before telling me it works), before every commit or deploy, and
whenever you are uncertain. Skip only for doc/comment/typo/formatting-only edits.
If you skip it on a real diff, say so with the reason. Reconcile Codex's findings
against your own (agreed / codex-only / you-only / disputed); don't relay blindly.

## Context hygiene

- Caveman mode is on by default: compressed prose, normal code/commits/security text.
- `/clear` between unrelated tasks. Don't switch model mid-session (rebuilds the cache).
- When `graphify-out/` exists, answer codebase-structure questions with
  `graphify query` before grepping.
