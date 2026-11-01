# Claude Code workflow

The tools that changed how fast, how well and how cheaply I get work done with
Claude Code. They're **ranked by measured impact**, not by how clever they are.

Every number below comes from replaying my own Claude Code transcripts:
- **6 weeks:** 2026-09-20 → 2026-11-01.
- **268 sessions, 52,628 API calls.**
- **$3,330 at API list price**, about $2,400/month. On a Max plan that's
  usage-limit headroom, not cash.

The replay script is in [`tools/measure.py`](tools/measure.py), so you can run it
on your own history (method and limits at the bottom).

`./install.sh` (or `./install.sh --dry-run` first) sets everything up. It never
overwrites an existing `CLAUDE.md` or `settings.json`; it writes a copy beside it
for you to merge.

## The ranking

| # | Tool | Measured effect over 6 weeks | Kind of win |
|---|---|---|---|
| 1 | **Lower auto-compact window** (300k instead of ~1M) | **−$1,165** (24% of what stock would cost). Turns over 200k context: **24% instead of 50%** | money + quality |
| 2 | **CLIs + MCP for every website** | **2,060 actions** the agent ran itself, ~50/day | speed |
| 3 | **collab: parallel sessions** | **1.37× throughput**, 64 h of wall-clock saved; 2+ sessions running 28% of the time | speed |
| 4 | **Automatic critic** (Codex reviews every diff) | **535 reviews**, about 1 high-severity finding per review | quality |
| 5 | **Cache protection** (1-hour TTL + cache guard) | **−$300** (−$178 TTL, −$121 guard) | money |
| 6 | **Caveman** (terse output) | **−$60 to −$180** | money + reading time |
| 7 | **graphify** (codebase knowledge graph) | exploration is 8.5% of the bill; a further **−$57 to −$128** possible | money + speed |
| 8 | **`@` file picker** | 74 prompts with file references (installed late October) | speed |

**Total: about 31–33% cheaper than stock Claude Code**, i.e. ~$1,100–1,190 a month
at list price. On top of that come the speed and quality wins, which don't show
up in a bill. Details for each are below, in the same order.

---

## 1. Lower the auto-compact window

On 1M-context models, Claude Code doesn't compact until the context is nearly
1M tokens (~967k). Every turn re-sends the whole context, so a session left to
grow gets more expensive on every turn. It also gets worse at its job, because
models use long contexts less reliably.

**Measured.** I set `autoCompactWindow: 300000`, so compaction fires at ~267k. I
then replayed every session as if each of my 273 auto-compactions hadn't
happened. My 305 manual `/compact`s were kept, since those happen either way.
- **Average context per turn:** 156k → 283k.
- **Turns running above 200k:** 24% → 50%.
- **Cost of the extra context:** **$1,287.**
  - ~$1,232 is every warm turn re-reading a context that's nearly twice as large.
  - ~$55 is sessions resumed after a long break, which would have had to
    rewrite that larger context.
- **Minus the compactions themselves:** they cost ~$121.
- **Net: −$1,165**, the single biggest lever in this repo.

**Set up:** `"autoCompactWindow": 300000` in `~/.claude/settings.json`, or use the
command:

```
/compact-limit            show the window and where compaction actually fires
/compact-limit --at 150k  make compaction fire AT 150k
/compact-limit auto       back to the model default
```

## 2. Let the agent drive every website through a CLI or MCP

If a site has a CLI or an MCP server, the agent uses it the way it uses `git`.
Without one, every deploy log, database row, failed CI run or PR comment is a
round trip through you: open the dashboard, copy, paste, explain.

| Site | Tool | What the agent does on its own |
|---|---|---|
| GitHub | [`gh`](https://cli.github.com) | open PRs, read CI logs and review comments, create repos |
| Vercel | [`vercel`](https://vercel.com/docs/cli) | deploy, read build and runtime logs, set env vars, roll back |
| Supabase | [`supabase`](https://supabase.com/docs/guides/cli) + MCP | run SQL, apply migrations, inspect tables, read logs |
| Gmail, Calendar, Drive, Notion… | MCP connectors (claude.ai → Settings → Connectors) | read and draft mail, find events, pull docs |

**Measured:** 290 CLI calls and 1,770 MCP calls in 6 weeks.
- **CLI:** `vercel` 129, `fly` 112, `gh` 45.
- **MCP:** app/DB tools 1,180, browser 392, Google/Notion/Docs 113.

If one in three of those saved me a 1–2 minute manual trip, that's **11–23 hours**
(an estimate, not a measurement). The bigger effect is that "deploy, read the logs,
fix it, redeploy" becomes one instruction instead of five messages.

**Set up:** install each CLI and log in once (`gh auth login`, `vercel login`,
`supabase login`). The first rule in [`claude/CLAUDE.md`](claude/CLAUDE.md) tells
the agent to use them.

## 3. collab: run several sessions at once, safely

`collab` coordinates several Claude Code sessions in the same repo. Global hooks
enforce it:
- **Declare first:** a session's first edit is refused until it declares
  `collab intent "<task>" --files …`.
- **No collisions:** editing a file another live session owns is refused. The
  agent gets `collab request <path> "<what I need>"` to send instead.
- **No sweeping commits:** `git add -A` / `git add .` and `git stash` are refused
  while others are active.
- **Safe deploys:** `collab hold` blocks everyone's deploys while the tree is
  half-built.

**Measured:**
- My sessions logged **236 active hours** inside **172 hours of wall-clock**:
  **1.37× throughput, 64 hours saved**.
- Two or more sessions were working 28% of the time.
- The agents ran `collab` 5,074 times.

**Why by hand instead of an orchestrator agent:**
- **Overhead per spawn:** every spawned agent starts cold and pays the full
  session floor. My 174 subagents averaged **52k tokens of context before doing
  anything**.
- **Re-reading:** the orchestrator re-reads every worker's report on each of its
  own turns.
- **Lossy hand-offs:** results come back as summaries, so detail gets lost.

In my data the dollar amount is modest (all subagents together cost $56). The
real wins are control and speed. I start a second session only for work that
really is independent, I read each one's results first-hand, and each session
keeps its own warm cache and a focused context.

**Set up:** `install.sh` puts `collab` on PATH and wires the hook globally.
Protocol: [`collab/COLLAB.md`](collab/COLLAB.md).

## 4. Automatic critic: a second model reviews every real diff

The `/critic` skill sends the agent's diff to **Codex** (a different model family)
in a read-only sandbox, and Claude reconciles the findings: agreed / codex-only
(verified?) / Claude-only / disputed. A rule in `CLAUDE.md` makes it run
unprompted:
- after any non-trivial diff;
- before saying a bug is fixed;
- before every commit or deploy.

**Measured:** 535 critic runs in 6 weeks, about 13 a day. The 113 reviews kept on
disk contain **116 high-, 320 medium- and 150 low-severity findings**. Claude
verifies each one before acting, and not every finding is real, but that's about
one serious issue per review caught before it shipped. It costs one Codex call per
diff on an OpenAI/ChatGPT plan, not Anthropic tokens.

**Set up:** `npm install -g @openai/codex && codex login`. The runner lives in
[Modulario](https://github.com/AkiraTheSquid/Modulario), which `install.sh` clones.

## 5. Cache protection: 1-hour TTL + cache guard

Claude Code caches the conversation server-side. On Opus 5.5:

| Kind of turn | Price vs normal input |
|---|---|
| Warm turn (cache read) | **0.05×** |
| Rewriting the cache, 1-hour cache | 2× |
| Rewriting the cache, 5-minute cache | 1.25× |

So a turn after the cache expires costs **~40× a warm one** (80× on Fable 5.1,
whose reads are 0.025×).

- **1-hour TTL** (`"promptCacheTtl": "1h"`). The default cache dies after 5
  minutes. **839 of my turns came after a 5–60 minute pause.** Under the default,
  each would have rewritten the whole context.
  **Measured: −$178.**
- **Cache guard** (`scripts/cache_guard.py`, a UserPromptSubmit hook). It
  **blocks** a prompt when the cache is cold and the rebuild would be ≥60k tokens,
  copies your prompt to the clipboard, and tells you the cost. You then choose:
  `/clear`, `/compact` first, or send it again to pay deliberately.
  - **156 blocks across 142 cold episodes** (re-prompting while blocked counts
    once): I compacted 43 times, cleared or abandoned 83, and re-sent 16 anyway.
  - Only 9 large cold rebuilds were actually paid all period.
  - **Measured: −$121.**
  - The statusline shows the cache live: `cache: warm 42m left · hit 97%`.

**Set up:** installed by `install.sh`. Thresholds are in
`~/.config/claude-cache-guard.env`.

## 6. Caveman: terse output

[caveman](https://github.com/JuliusBrussee/caveman) makes the agent answer in
compressed fragments, while code, commits and security text stay normal. A
SessionStart hook (`scripts/caveman-ultra.sh`) forces the strongest level every
session.

**Measured:** prose is only **6% of my output tokens**. Thinking is 31%, and
tool calls (code, edits, commands) are the rest. With caveman on, my prose cost
$45 to generate plus $15 to re-read on later turns. Without caveman it would be
2–4× longer, depending on whether you trust a 50% reduction or caveman's own 75%.
**Saving: −$60 to −$180.** The bigger benefit is answers that are faster to read.

## 7. graphify: a knowledge graph of each codebase

[graphify](https://github.com/Graphify-Labs/graphify) builds a graph of a repo, so
"where is X / what calls Y" becomes a `graphify query` instead of grep-and-read.
A SessionStart hook (`scripts/graphify-startup.sh`) points the agent at the graph
when one exists. A post-commit hook keeps it current.

**Measured:**
- **Exploration volume:** 18,084 exploration calls (Read, Grep, Glob, `grep`,
  `find`, …) added 15.9M tokens to context.
- **Exploration cost:** **$284 (8.5% of the bill)**, counting the write plus
  re-reads on later turns.
- **Graph use so far:** the agents ran only 24 graph queries (`query` / `path` / `explain`).

graphify's headline is "71.5× fewer tokens", but that comes from a 52-file mixed
corpus. Independent tests on real code find 5–10× fewer tokens on orientation
queries in repos with hundreds of files, and ~1–3× under 100 files. If a quarter
to a half of my exploration were orientation queries cut by 80–90%: **−$57 to
−$128 more**. That's real but small next to items 1–5, and it's lowest when you
already point the agent at exact files (item 8).

## 8. A better `@` file picker

`file-suggestion.sh` (settings key `fileSuggestion`) replaces the `@` autocomplete:
- **Wider search:** the current project first, then `~/Applications`, then the
  whole home folder. Folders are included too.
- **Smarter ranking:** exact name > prefix > substring, shallower paths first.
- **Aliases:** `@app` jumps to a project folder; `@app readme` searches only
  inside it.

**Measured:** 74 prompts carried `@` path references, and the picker only arrived
in late October. Pointing the agent at the exact file skips its search turns and
makes cross-repo references instant. Too new to put a dollar figure on.

**Needs:** `rg`, `fzf`, `jq`.

---

## How the numbers were measured

`python3 tools/measure.py ~/.claude/projects report.json` replays every transcript:

- **Costs** use the `usage` block of each API call, deduplicated by message id,
  priced at list rates. Opus 5.5: $4 in / $20 out / $0.20 cache read. Cache
  writes cost 2× input (1 h) or 1.25× (5 min).
- **Compact window:** for each auto-compaction, the dropped tokens
  (`preTokens − postTokens`) are carried forward on every later turn until the
  next manual `/compact` or until the stock ~967k limit. They're priced as a warm
  read, or as a 2× write after a gap of more than 1 hour. The cost of the
  summarisation calls is credited back.
- **TTL:** each turn after a 5–60 minute gap is re-priced as a full 1.25×
  rewrite (the stock 5-minute cache).
- **Cache guard:** each block is classified by what happened next.
  - Compacted: saves 2× − 1.25× of the blocked context.
  - Cleared or abandoned: saves the full 2× rewrite.
  - Re-sent: saves nothing.
- **Caveman:** prose tokens = non-thinking output × the prose share of that
  message. The counterfactual is 2× and 4× the prose, plus its re-reads until the
  next compaction.
- **Parallelism:** a session is "active" while its turns are under 5 minutes
  apart. Throughput = sum of active time ÷ union of active time across sessions.

**Limits:**
- **Fixed behaviour:** every counterfactual assumes I'd have worked the same way
  without the tool. Someone without a low compact window probably `/clear`s more
  by hand, so treat item 1 as an upper-middle estimate.
- **Approximations:** tool-result tokens are approximated as characters ÷ 3.6.
- **Overlap:** the savings are treated as additive; interactions are ignored.
  These largely compound rather than overlap: a bigger context under a 5-minute
  cache costs more than either alone.
- **Sample:** one user, one workload (app development plus content work).
  Run the script on your own history.

---

## What's in this repo

```
install.sh                       installer (backs up anything it replaces)
tools/measure.py                 replay your transcripts, price each lever
claude/CLAUDE.md                 the rules that make the above automatic
claude/settings.json             hooks + autoCompactWindow + promptCacheTtl + fileSuggestion
claude/statusline.sh             model · cost · ctx %, plus the live cache line
claude/file-suggestion.sh        the @ picker (+ file-suggestion-aliases.example)
claude/scripts/cache_*.py        cache guard, statusline cache line, optional pre-expiry nudge
claude/scripts/caveman-ultra.sh  forces caveman ultra at SessionStart
claude/scripts/compact_limit.py  + commands/compact-limit.md
claude/scripts/graphify-startup.sh
claude/skills/critic/            /critic skill
collab/                          collab CLI, global hook, protocol, self-test
```
