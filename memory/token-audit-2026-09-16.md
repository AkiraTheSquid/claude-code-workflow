---
name: token-audit-2026-09-16
description: Token-waste audit of the Claude Code setup on 2026-09-16 — what was measured, what was changed, what was deliberately left alone
metadata:
  type: project
---

Audit 2026-09-16 (report-only pass, then fixes). Measured with tiktoken + jsonl `usage` sums, not estimates.

Findings: one 22 h / 859-turn session (`50b9b490`) billed 140M tokens, median context 151k, 235 turns >200k, with a mid-session fable→opus switch (7 cache rebuilds). Session floor before the first prompt = 60–73k tokens. MEMORY.md was 7.2k tokens. Vercel plugin (30 skills, 33k tok of descriptions) was on in both Delta-Drills repos. Playwright + delta-note-relay MCPs were dead per memory but still registered. No proxy/gateway; tool deferral ACTIVE; timers never run Claude Code.

Changed: `~/.claude/settings.json` autoCompactWindow 300000→150000, promptCacheTtl "1h"; `claude mcp remove playwright` + `delta-note-relay`; vercel plugin off in `Delta-Drills-Local/.claude/settings.json` (gitignored) and committed in `Delta-Drills-Deployed`; MEMORY.md old/fixed/tombstone lines → `memory-archive.md` (7.2k→6.2k tok); skills installed: `refresh`, `interview-me`, `prompt-master`.

Left alone on purpose: model `claude-fable-5-1[1m]` (150k compact now keeps it under the >200k premium), Claude in Chrome (22 tools), claude.ai connectors (Gmail 31 / Drive 11 / Calendar 9 / Docs 8 — only removable on claude.ai), sunsama (2 tools, needs auth), CLAUDE.md wording (2.6k tok; Seth's rules).

**Why:** the bill is dominated by session length × context, not by setup; the floor is second.
**How to apply:** `/clear` per task; `/refresh` to hand off a long chat; never `/model` or `/fast` mid-session; re-measure with the jsonl parse before claiming a saving. See [[feedback-minimize-subagents]].
