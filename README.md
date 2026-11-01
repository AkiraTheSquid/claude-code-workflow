# Claude Code workflow

The tools that changed how fast, how well and how cheaply I get work done with
Claude Code. They're **ranked by measured impact**, not by how clever they are.

Every number below comes from replaying my own Claude Code transcripts:
- **6 weeks:** 2026-09-20 → 2026-11-01.
- **268 sessions, 52,628 API calls.**
- **Usage worth $3,330 at API list price** (about $2,400/month), a heavy
  Max-plan workload.

Most people pay for a subscription, not per token, so usage is shown as a
**share of your plan's usage limit**, not dollars.

The replay script is in [`tools/measure.py`](tools/measure.py), so you can run it
on your own history (method and limits at the bottom).

`./install.sh` (or `./install.sh --dry-run` first) sets everything up. It never
overwrites an existing `CLAUDE.md` or `settings.json`; it writes a copy beside it
for you to merge.

## The ranking

Each column is a % change against stock Claude Code. Negative usage is good;
positive quality and speed are good. Every cell says where its number comes from:
**M** = measured from my transcripts, **L** = from a published benchmark,
**E** = my estimate.

- **Plan usage:** how much of your usage limit the same work burns.
- **Quality:** defects caught before they reach you.
- **Speed:** work finished per wall-clock hour, across all my work.

| # | Tool | Plan usage | Quality | Speed |
|---|---|---|---|---|
| 1 | **Lower auto-compact window** (300k instead of ~1M) | **−24%** M | +5% E | −5% E (pauses alone −2% M) |
| 2 | **CLIs + MCP for every website** | 0% E | +5% E | +10% E |
| 3 | **collab: parallel sessions** | 0% per task M | −5% E | **+37%** M |
| 4 | **Automatic critic** (Codex reviews every diff) | +10% M (upper bound) | **+33%** L | **−14%** M |
| 5 | **Cache protection** (1-hour TTL + cache guard) | **−9%** M (TTL 3.6%, guard 5.1%) | 0% | 0% E |
| 6 | **graphify** (codebase knowledge graph) | −2 to −4% E, if used | 0% E | + E |
| | **Combined** | **≈ −26%** (≈1.35× as much work per plan) | **≈ +35 to +40%** E | **≈ +23 to +31%** |

**How the combined row is computed.** It multiplies each column's factors
(e.g. 0.76 × 0.94 × …), adjusted where two tools clearly aren't independent:
- **Usage:**
  - The compact window and the cache compound: a bigger context under a
    5-minute cache costs more than either alone. So I add their shares (−32.4%)
    rather than multiply them (−30.3%).
  - Then ×1.10 for the critic's extra Claude turns: **−26%**.
  - With graphify in daily use, roughly −28%.
- **Speed:**
  - Straight multiplication gives **+23%**.
  - collab's 1.37× was measured with the critic and compaction already on, and
    their slow stretches are when you switch to another pane. So part of their
    cost is already hidden inside the 1.37×, and the true figure is likely
    higher. My estimate is up to **+31%**.
- **Quality:**
  - Multiplying gives +39%, but the columns mix different measures, so treat it
    as rough. The critic dominates it.
  - The critic also catches some conflicts between agents, so collab's −5% is
    probably smaller.

**Plan usage assumes** your plan counts tokens with the same weights as API
prices (cache reads cheap; cache writes and output expensive). Anthropic doesn't
publish the formula, but three independent community datasets that logged the
live quota % per call agree: cache reads count at about **0.1× input**, the
published billing rate.
- [cache-fix](https://github.com/anthropics/claude-code/issues/45756#issuecomment-4307428785):
  16,531 calls over 57 windows.
- [ArkNill](https://github.com/ArkNill/claude-code-hidden-problem-analysis/blob/main/02_RATELIMIT-HEADERS.md):
  38,996 requests.
- [seanGSISG](https://github.com/ArkNill/claude-code-hidden-problem-analysis/issues/3):
  179k calls.

Those were measured on Opus 4.6. Opus 5.5's API read rate is 0.05×; if plans
still count reads at 0.1×, item 1 is worth more than shown here.

Details for each tool are below, in the same order.

### Two of these make each agent slower, and that's fine

The compact window and the critic both make a single agent **take longer**:
- **Compaction:** it pauses to summarise, then re-reads files it no longer
  remembers.
- **Critic:** every diff waits for a second model's review and a round of fixes.

In return each agent finishes **cheaper** (compaction) and **better** (critic).
On a single agent, that's a real trade.

**With collab it mostly stops being one.** You're running several agents in
split terminal panes anyway (item 3). While one agent compacts or waits on its
critic, you're reviewing another. A longer gap before you return to an agent
costs you nothing, and when you do look, the result is better and was cheaper
to produce.

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
- **Net: −$1,165, about 24% of the usage stock Claude Code would burn.**
  It's the single biggest lever in this repo.

**Trade-off: slower agents.**
- **Compaction pauses:** 273 auto-compactions at ~67 s each = **5.1 hours**
  waiting on summaries, plus 3.8 hours on manual `/compact`s.
- **Re-reading afterwards:** after each summary the agent has to rediscover
  files and decisions it dropped. That's not measured here, but it's the larger
  part of the slowdown.
- **Quality:** the gain is moderate. A tighter context keeps the agent sharper,
  but every summary loses some detail.

Net: cheaper and somewhat better per task, but each task takes noticeably
longer. See the box above for why that's fine with parallel agents.

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
The catch: the agent can now deploy and write to production itself, so a wrong
command hits real systems.

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
- **Plan usage:** the same per task, but spent 1.37× faster per hour. Parallel
  sessions get you to your usage limit sooner in the day; they don't make the
  work cheaper.

**How I run it:** one agent per split pane in the terminal, each on an
independent task.

**The ceiling is you, at about 4–5 agents.** Past that you lose track of which
agent is doing what, and reviewing every diff becomes impossible. What works at
that point:

1. **Integrate in one place.** Pick one agent and have it commit everyone's
   finished changes and deploy them. It's one commit and deploy pass instead of
   five racing each other.
2. **Check the running app, not the diffs.** Don't dig through each agent's code
   changes. Open the app and look at every change taking effect. You can see
   right away which tasks are finished, and which half-landed or need another
   pass to clean them up the way you want.
3. **Send each unfinished one back** to the agent that owns it.

**Where parallel agents lower quality.** collab stops the mechanical collisions.
Over 6 weeks it refused:
- **32 edits** to a file another live agent owned;
- **16 sweeping commits** (`git add -A` / `git stash`) that would have swept up
  another agent's work;
- **8 deploys** while another agent's tree was half-built.

It also made agents check in 133 times when a new agent joined their repo.

What it **can't** see is a semantic conflict:
- **Same behaviour, different files:** two agents change the same behaviour from
  different files, and the second quietly undoes the first.
- **Mistaken clean-up:** an agent "cleans up" something another agent did on
  purpose.
- **Shipping half-done work:** a deploy ships one agent's finished change
  alongside another's half-done one.

Those show up as features that worked an hour ago. Step 2 above (look at the
running app) is how you catch them.

**Why not an orchestrator agent instead?** An orchestrator (one lead agent
spawning workers) is probably **more capable**. Anthropic's multi-agent research
system beat a single Claude Opus 4 agent by **90.2%** on its internal research
eval. It also replaces your own oversight time, which is usually the most
expensive thing in the loop. But it costs far more:
- **Usage:** multi-agent runs used about **15× the tokens of a chat**, against
  about 4× for a single agent. That's roughly **4× the plan usage per task**.
- **Not a great fit for code:** Anthropic notes that most coding tasks have
  fewer truly parallel pieces than research. It also says agents "are not yet
  great at coordinating and delegating to other agents in real time"
  ([source](https://www.anthropic.com/engineering/built-multi-agent-research-system)).
- **In practice it was too expensive for me.** Every spawned agent pays the full
  session floor before doing anything: my subagents averaged **52k tokens** of
  context first. One fan-out burned ~1.5M tokens on work a single session could
  have done.

Running sessions by hand with collab keeps the parallelism and drops the
orchestration bill. You pay with your attention instead, which is why the
4–5-agent ceiling matters.

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

**Measured:** 545 critic runs in 6 weeks, about 13 a day. The 113 reviews kept on
disk contain **116 high-, 320 medium- and 150 low-severity findings**: about one
serious issue per review caught before it shipped. The review itself runs
on a ChatGPT/Codex plan. Claude's own turns reconciling and fixing cost up to
~10% more Claude usage (below).

**Trade-off: tasks it runs on take 1.84× as long.**
Measured with [`tools/critic_loop.py`](tools/critic_loop.py). The "loop" runs
from the first critic call in a task to my next prompt:
- **Per task:** the whole task took **1.84×** as long as the work before the
  first critic call (median 1.76×; middle half 1.39× to 2.78×), over 399 tasks.
- **Across all my work:** critic loops took **13.9% of active time** (−14%
  speed) and **9.6% of Claude usage** (about +10%).
- **Upper bounds:** both numbers include whatever happened after the review
  before I next typed, such as the commit, deploy and reply.
- **Codex itself:** 545 runs spent **11.1 hours** waiting on Codex. The rest is
  Claude reconciling, fixing and re-verifying.
- **What you get back is quality.** With parallel panes (item 3), the extra time
  is mostly time you spend on other agents anyway.

**What Claude does with Codex's findings.** Codex never edits. Claude checks
each finding against the code, then fixes it, leaves it, or disputes it.
Measured with [`tools/critic_verdicts.py`](tools/critic_verdicts.py), which has
Sonnet label every finding from what Claude wrote afterwards. It covered 230
reviews with 750 findings, and a hand check of 30 labels found 29 right:

| Claude's verdict | All | High | Medium | Low |
|---|---|---|---|---|
| Agreed and fixed (incl. 2% partly) | **72%** | 53% | 73% | 79% |
| Agreed, left for later | 11% | 16% | 10% | 11% |
| Disputed: wrong, already handled, or intended | **17%** | **32%** | 17% | 10% |

- **Base:** these shares cover the 474 findings (63%) where Claude stated a
  verdict. For the rest, Claude's text says nothing about the finding. Some were
  findings on another session's files, some were cut off when the output was
  piped through `tail`, and some got a blanket "no live bugs".
- **Severity:** the higher the severity Codex claims, the more often Claude
  rejects it. High findings are disputed **32%** of the time, low ones 10%.
  76 more reviews, seen only through `tail`/`jq`, give the same pattern
  (18% disputed, 31% for high).
- **Compared with people:** developers accept 36.4% of CodeRabbit comments and
  reject 56.3%; 43.3% of the rejected ones were false positives
  ([Lin et al., 2026](https://arxiv.org/html/2607.03316v2)). Codex's GitHub
  review comments get marked resolved 54.8% of the time, against 72.9% for
  Copilot's ([Cynthia et al., 2026](https://arxiv.org/html/2607.21997v2)).

**Were the findings real? Checked against the code.** I hand-checked 40 findings
(high and medium, 10 per verdict) against the repos as they were at review time
and their git history afterwards: later fixes, reverts, features removed.

| Claude's verdict | Real bug | Real but minor, by design, or moot later | Codex wrong | Unclear |
|---|---|---|---|---|
| Fixed | 6 | 3 | 0 | 1 |
| Left for later | 4 | 5 | 0 | 1 |
| Disputed | 0 | 1 | **9** | 0 |
| No verdict stated | 2 | 5 | 3 | 0 |

- **Claude's call was right in all 34 cases I could judge.** Every dispute was a
  Codex error, or behaviour that was intended. Every fix addressed a real
  problem.
- **Weighted to the full 750 findings,** about 41% are real bugs that mattered,
  38% are real but minor, by design, or made moot by a later change, and 21% are
  wrong. That's roughly **one real bug fixed per review**.
- **Codex's errors have a pattern.** Of the 12 wrong findings, 6 said something
  something was missing ("never wired up", "no data") when it sat in a file
  outside the reviewed `--files` list. 4 were code paths that can't be reached, and 2 misread the
  logic.
- **"No verdict" mostly means quietly handled.** Claude dropped Codex's wrong
  findings without comment, and two real bugs were fixed in the next commit
  without being mentioned.
- **Limits:** 40 findings gives roughly ±15 points on each share. I'm the same
  model family as the author, so this is a careful check of the code, not an
  independent one.

**What the research says:**
- **Two different models catch more than two passes of one.** One same-model
  review plus one cross-model review caught **56.7%** of planted errors, against
  **42.7%** for two same-model reviews. The two kinds of reviewer find partly
  different errors (41% overlap)
  ([Song, 2026](https://arxiv.org/abs/2610.01471)).
- **Direction matters, and a reviewer that rewrites the code itself can make it
  worse.** On 116 LiveCodeBench tasks, where the reviewer returns the final
  program with no check by the author:

  | Reviewer → author | Pass rate before → after review |
  |---|---|
  | Claude reviewing Codex | **71.6% → 89.7%** |
  | Codex reviewing itself | 71.6% → 84.5% |
  | Codex reviewing Claude | **91.4% → 82.8%** (worse) |

  ([Xiang et al., 2026](https://arxiv.org/abs/2607.21656)). In the
  Codex-reviews-Claude case, Codex fixed 3 of Claude's failures and broke 13 of
  its passes, often by throwing away a working approach. The authors suggest
  letting the reviewer "first decide whether to intervene" as the next
  experiment.
- **The setup here wasn't tested.** I found no study of the loop used here:
  the reviewer only flags issues and the author decides. That loop is the
  guard against Xiang's failure mode. The 17% (32% on high findings) that Claude
  disputes are the edits a rewriting reviewer would have forced in.

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
  **Measured: −$178, about 3.6% of plan usage.**
- **Cache guard** (`scripts/cache_guard.py`, a UserPromptSubmit hook). It
  **blocks** a prompt when the cache is cold and the rebuild would be ≥60k tokens,
  copies your prompt to the clipboard, and tells you the cost. You then choose:
  `/clear`, `/compact` first, or send it again to pay deliberately.
  - **156 blocks across 142 cold episodes** (re-prompting while blocked counts
    once): I compacted 43 times, cleared or abandoned 83, and re-sent 16 anyway.
  - Only 9 large cold rebuilds were actually paid all period.
  - **Measured: −$250, about 5.1% of plan usage.** Two parts:
    - **$121 on the blocked turn itself:** the cold rewrite you didn't pay.
    - **$129 afterwards:** each guard-prompted `/compact` or `/clear` left a
      smaller context, re-read more cheaply on **3,372 later turns**. Without the
      guard you'd have resent into the big context and carried it until
      auto-compact fired anyway.
  - **Why it isn't bigger:** a cold turn costs ~40× a warm one, but it's still
    one turn. 142 episodes against 52,000 turns, at ~$1–2 each, adds up to a few
    percent. The guard matters more in practice than in totals: it's what makes
    you compact at the right moment instead of dragging a stale context along.

**Other people's data** on cold caches:
- **One resumed message, 9% of a 5-hour limit:** a user resumed a 500k-token
  session after 7 hours idle, and that single message took the window from 0% to
  9%. The issue asks for exactly what the guard does: "Gate large replays with
  user confirmation"
  ([anthropics/claude-code#43599](https://github.com/anthropics/claude-code/issues/43599)).
- **Anthropic agrees:** Claude Code's creator, Boris Cherny: "if you leave your
  computer for over an hour then continue a stale session, it's often a full
  cache miss", and those misses "are expensive" with a 1M window
  ([DevClass](https://www.devclass.com/ai-ml/2026/04/14/claude-code-cache-confusion-as-anthropic-tweaks-defaults-but-quotas-still-drain/5216975)).
- **Up to 20× cost on resumed sessions:**
  [claude-code-cache-fix](https://github.com/cnighswonger/claude-code-cache-fix)
  is a community proxy that pins the 1-hour TTL and stabilises the cached
  prefix. It reports up to 20× cost on resumed sessions without it, and a 95.5%
  cache hit rate through it against 82.3% direct.
- **Aggregates are missing:** none of these give the share of total usage lost
  to cold rebuilds, which is the number above. Everything published is
  per-incident, so a single bad resume looks huge, while across 52,000 turns
  it's a few percent.
  - The statusline shows the cache live: `cache: warm 42m left · hit 97%`.

**Set up:** installed by `install.sh`. Thresholds are in
`~/.config/claude-cache-guard.env`.

## 6. graphify: a knowledge graph of each codebase

[graphify](https://github.com/Graphify-Labs/graphify) builds a graph of a repo, so
"where is X / what calls Y" becomes a `graphify query` instead of grep-and-read.
A SessionStart hook (`scripts/graphify-startup.sh`) points the agent at the graph
when one exists. A post-commit hook keeps it current.

**Measured:**
- **Exploration volume:** 18,084 exploration calls (Read, Grep, Glob, `grep`,
  `find`, …) added 15.9M tokens to context.
- **Exploration cost:** **$284, 8.5% of my plan usage**, counting the write plus
  re-reads on later turns.
- **Graph use so far:** the agents ran only 24 graph queries (`query` / `path` / `explain`).

graphify's headline is "71.5× fewer tokens", but that comes from a 52-file mixed
corpus. Independent tests on real code find 5–10× fewer tokens on orientation
queries in repos with hundreds of files, and ~1–3× under 100 files. If a quarter
to a half of my exploration were orientation queries cut by 80–90%: **−$57 to
−$128 more, 2–4% of what I use now**. That's real but small next to items 1–5,
and it's lowest when you already point the agent at exact files.

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
  - Carry-forward: after a compact or clear, the dropped tokens are priced on
    every later turn (warm read, or 2× after a gap of more than 1 hour). This
    stops at the next compaction, or when the larger context would have hit my
    own ~267k auto-compact.
- **Plan share:** each saving ÷ stock usage, i.e. actual ($3,330) plus all
  measured savings ($4,932). graphify's not-yet-realised saving is ÷
  current usage instead. Assumes plan limits weight tokens like API
  prices; Anthropic doesn't publish the formula.
- **Parallelism:** a session is "active" while its turns are under 5 minutes
  apart. Throughput = sum of active time ÷ union of active time across sessions.

**Limits:**
- **Fixed behaviour:** every counterfactual assumes I'd have worked the same way
  without the tool. Someone without a low compact window probably `/clear`s more
  by hand, so treat item 1 as an upper-middle estimate.
- **Critic verdicts:** `tools/critic_verdicts.py` finds Codex's findings for
  each critic run, including backgrounded runs read back later and output viewed
  through `tail`/`jq`. Of 548 runs, 230 had complete JSON findings, 76 only a
  partial view, 72 were clean, and 170 were unreadable or still open (blocked,
  empty diff, cancelled, or output gone). The labels come
  from Claude's text, not its edits, so a finding fixed without comment counts as
  "no verdict".
- **Critic loop:** `tools/critic_loop.py` attributes everything from a task's
  first critic call to your next prompt to the critic.
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
tools/critic_loop.py             time + usage the /critic loop adds
tools/critic_verdicts.py         what Claude did with each Codex finding
claude/CLAUDE.md                 the rules that make the above automatic
claude/settings.json             hooks + autoCompactWindow + promptCacheTtl + fileSuggestion
claude/statusline.sh             model · cost · ctx %, plus the live cache line
claude/file-suggestion.sh        the @ picker (+ file-suggestion-aliases.example)
claude/scripts/cache_*.py        cache guard, statusline cache line, optional pre-expiry nudge
claude/scripts/compact_limit.py  + commands/compact-limit.md
claude/scripts/graphify-startup.sh
claude/skills/critic/            /critic skill
collab/                          collab CLI, global hook, protocol, self-test
```
