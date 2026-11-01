# Claude Code workflow

The handful of things that changed how fast, how well and how cheaply I get work
done with Claude Code, ordered by how much they matter. Each section says what it
is, why I use it, and how to turn it on. Everything here is in daily use.

`./install.sh` (or `./install.sh --dry-run` first) sets up all of it. It never
overwrites an existing `CLAUDE.md` or `settings.json`; it writes a copy beside
it for you to merge.

---

## 0. Let the agent drive every website through a CLI or MCP

**The most important one, and the one most people miss.** If a website has a CLI
or an MCP server, the agent can use it directly, the same way it uses `git`.
Without one, every deploy log, database row, failed CI run or PR comment becomes
a round trip through you: you open the dashboard, copy, paste, explain.

| Site | Tool | What the agent can do on its own |
|---|---|---|
| GitHub | [`gh`](https://cli.github.com) | open PRs, read CI logs, review comments, create repos, check issues |
| Vercel | [`vercel`](https://vercel.com/docs/cli) | deploy, read build and runtime logs, set env vars, roll back |
| Supabase | [`supabase`](https://supabase.com/docs/guides/cli) + Supabase MCP | run SQL, apply migrations, inspect tables, read logs |
| Gmail, Calendar, Drive, Notion… | MCP connectors (claude.ai → Settings → Connectors) | read and draft mail, find events, pull docs |

**Why:** the agent closes its own loop. "Deploy it, read the logs, fix what broke,
redeploy" becomes one instruction instead of five messages. This is a bigger
speed-up than any token trick below.

**Set up:** install each CLI and log in once (`gh auth login`, `vercel login`,
`supabase login`). Then tell the agent to use them; the first rule in
[`claude/CLAUDE.md`](claude/CLAUDE.md) does that.

---

## 1. Caveman mode: terse output, every session

[caveman](https://github.com/JuliusBrussee/caveman) makes the agent answer in
compressed fragments ("Pool = reuse DB conn. Skip handshake → fast under load.")
while code, commits and security text stay normal. A SessionStart hook
(`scripts/caveman-ultra.sh`) forces the strongest level, *ultra*, every session.

**Why:**
- caveman's own benchmark: **about 75% fewer output tokens**. Output is the
  priciest token type (about 5× input).
- Shorter answers stream faster and take less of my time to read.
- Less of the agent's own chatter goes back into context on later turns.

**Honest size of the saving:** most of a long session's bill is re-reading
context, not output. So caveman typically takes **~5–15%** off the bill. The time
saved reading answers matters as much as the money.

---

## 2. collab: run several sessions by hand, safely

`collab` coordinates several Claude Code sessions working in the same repo at
once. Global hooks make it enforced, not an honour system:

- **Declare first:** a session's first edit is refused until it runs
  `collab intent "<task>" --files …`.
- **No collisions:** editing a file another live session owns is refused. The
  agent gets `collab request <path> "<what I need>"` to send instead.
- **No sweeping commits:** `git add -A` / `git add .` and `git stash` are refused
  while other sessions are active, so one agent can't commit another's
  half-finished work.
- **Safe deploys:** `collab hold "<why>"` blocks everyone's deploys while the
  tree is half-built. Deploys and commits go to a shared log.

### Why by hand plus collab beats both alternatives

**Cheaper than an orchestrator.** An orchestrator agent that spawns subagents
pays for the same work several times:
- Every subagent starts cold and pays the full session floor: system prompt,
  tool schemas, CLAUDE.md, memory. I measured ~60–70k tokens before the first
  prompt.
- Subagents re-explore code the orchestrator already read.
- Results come back as lossy summaries. The orchestrator then carries all of
  them in its own context and re-reads them every turn.
- Orchestrators also over-spawn. One fan-out of mine burned **~1.5M tokens** on
  work a single session could have done.

With collab, *I* am the orchestrator. I only start a second session when the
work really is independent. Each session keeps its own warm cache and a focused
context, and nothing gets summarised second-hand.

**Faster than one agent.** One agent does tasks one after another. Its context
also fills with unrelated work, so it hits compaction sooner and gets worse as it
goes (see §4). Two or three sessions on independent tasks finish in roughly half
or a third of the wall-clock time, and each stays sharp.

**Set up:** `install.sh` puts `collab` on your PATH and wires the hook globally
(`collab/install-hooks.py`). Protocol: [`collab/COLLAB.md`](collab/COLLAB.md).

---

## 3. Automatic critic: a second model reviews every real diff

The `/critic` skill sends the agent's git diff to **Codex** (OpenAI, a different
model family) in a read-only sandbox. Claude then reconciles the findings:
agreed / codex-only (verified?) / Claude-only / disputed. A rule in
`CLAUDE.md` makes it automatic, so it runs without being asked:
- after any non-trivial diff;
- before saying a bug is fixed;
- before every commit or deploy;
- whenever the agent is unsure.

**Why:** an author rationalises past its own mistakes, and a second model from a
different lab doesn't share those blind spots. Codex regularly catches real
bugs Claude missed. It also misses some, which is why Claude reconciles instead
of relaying. It costs one Codex call per diff on your OpenAI/ChatGPT plan, not
Anthropic tokens. That's very cheap next to shipping a bug.

**Set up:** `npm install -g @openai/codex && codex login`. The runner lives in
[Modulario](https://github.com/AkiraTheSquid/Modulario), which `install.sh` clones.

---

## 4. Lower the auto-compact limit (the default is ~1M tokens)

On 1M-context models, Claude Code's default auto-compact window is the full ~1M.
The session doesn't compress until it's nearly a million tokens deep. That hurts
twice:

- **Dumber.** Models get worse at using their context as it grows, so a session
  hundreds of thousands of tokens deep follows instructions less well and forgets
  earlier decisions.
- **More expensive.** Every turn re-sends the whole context. A turn at 900k
  tokens costs ~3–4× a turn at 250k, even fully cached, and a long session has
  hundreds of turns. One 22-hour session of mine billed **140M tokens**, with a
  median context of 151k. Context size × number of turns is the bill.

**Set up:** `autoCompactWindow: 300000` in settings.json (compaction fires at
~267k), or use the `/compact-limit` command:

```
/compact-limit            show the current window and where it actually fires
/compact-limit --at 150k  make compaction fire AT 150k
/compact-limit auto       back to the model default
```

150k–300k is the useful range. Lower means cheaper and sharper, with more
frequent summaries.

---

## 5. Cache guard: never pay for a cold cache by accident

Claude Code caches your conversation server-side. A warm turn reads it back at
~0.1× the input price. After the cache expires (5 min by default, 1 h with
`promptCacheTtl: "1h"`), the next prompt re-writes the *entire* context at cache
write price (~2× input for the 1-hour cache). That one turn costs **~20× a warm
one.** Mine: a 70-minute break followed by "ok continue" re-wrote **237k tokens**.

The guard (`scripts/cache_guard.py`, a UserPromptSubmit hook) **blocks** a prompt
when the cache is cold **and** the rebuild is ≥60k tokens. It saves your prompt to
the clipboard and tells you the cost. Then you choose:
- **`/compact` first:** the rebuild is only the short summary.
- **Paste and send again:** you're deliberately paying for the full context.

It never blocks right after a `/compact`, slash commands, or small sessions. The
statusline shows the cache live: `cache: warm 42m left · hit 97%`.

**Set up:** installed by `install.sh`. Thresholds live in
`~/.config/claude-cache-guard.env`. Also set `"promptCacheTtl": "1h"` so
ordinary pauses don't expire the cache in the first place.

---

## 6. A better `@` file picker

Claude Code's `@` autocomplete only searches the current project.
`file-suggestion.sh` (settings key `fileSuggestion`) replaces it:
- **Wider search:** the current project first, then `~/Applications`, then the
  rest of your home folder. Folders are included too.
- **Smarter ranking:** an exact name beats a prefix, a prefix beats a substring,
  and a shallower path wins ties.
- **Aliases:** `@app` jumps to a project folder; `@app readme` searches only
  inside it. Set them up in `~/.claude/file-suggestion-aliases`.

**Why:** pointing the agent at the exact file skips its "let me search for that"
turns. Each of those turns re-reads the whole context, so skipping them saves
tokens and time. It also makes referencing a file in *another* repo instant.
This sped my workflow up more than I expected.

**Needs:** `rg`, `fzf`, `jq`.

---

## 7. graphify: a knowledge graph of each codebase

[graphify](https://github.com/Graphify-Labs/graphify) builds a graph of a repo
(files, functions, calls, docs). The agent can then answer "where is X / what
calls Y" with `graphify query` instead of grepping and reading files. A
SessionStart hook (`scripts/graphify-startup.sh`) tells the agent to use the graph
when one exists, and to offer to build one when it doesn't. A post-commit hook
keeps the graph current.

**Honest numbers.** graphify's headline is "71.5× fewer tokens", but that was a
52-file mixed corpus of code, papers and images. On real code, independent tests
find:

| Repo size | Saving on exploration queries |
|---|---|
| under 100 files | ~1–3× |
| 100–500 files | ~5–15× |
| 500+ files | ~30×+ |

That's per *exploration query*, not per session. The system prompt, history,
edits and output are untouched. Realistically it takes **~10–30%** off a typical
session in a mid-to-large repo, and close to nothing on small repos or when
you're iterating on files already open. With the `@` picker and focused sessions
already in place, expect the low end. Run `/graphify .` once per big repo; a
code-only build uses no LLM tokens.

---

## What it adds up to

These are estimates, so measure your own: sum the `usage` fields in
`~/.claude/projects/*/*.jsonl` for a week with and a week without. The savings
overlap, so **don't multiply them.**

| | Money / tokens | Speed | Quality |
|---|---|---|---|
| **CLIs + MCP** | fewer pasted logs and screenshots | biggest win: agent closes its own loops | agent sees real errors, not your summary |
| **Caveman** | ~75% less output → ~5–15% of bill | answers stream faster, read faster | neutral (code untouched) |
| **collab** | no orchestrator overhead; avoids 1M+ token fan-outs | 2–3× wall-clock on independent work | each session stays focused and sharp |
| **Critic** | Codex call is on OpenAI's side | catches bugs before deploy, not after | the biggest quality win |
| **Compact limit** | late-session turns ~3× cheaper at 300k vs ~1M | fewer slow long-context turns | noticeably sharper long sessions |
| **Cache guard** | each blocked cold rewrite saves ~20× that turn (237k-token example) | — | — |
| **`@` picker** | fewer search turns | instant cross-repo file references | agent reads the right file first |
| **graphify** | ~10–30% on exploration-heavy repo work | faster "how does X work" answers | answers cite the real structure |

My rough read on the overall effect for long sessions: **~40–60% lower bill**
than stock Claude Code. Most of it comes from the compact limit and the cache
guard, because they attack the dominant cost: context size × number of turns.
Caveman and graphify add smaller cuts on top. The speed and quality gains from
CLIs, collab and the critic matter more than the money.

---

## What's in this repo

```
install.sh                       installer (backs up anything it replaces)
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
