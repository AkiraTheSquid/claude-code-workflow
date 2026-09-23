# Tool-aware workflow

Use installed MCP tools proactively; don't make me restate that they exist.
If an obviously relevant tool is unavailable, say why and use the best fallback.

## Git discipline

Use Git throughout every repo task, not only at completion.

- Baseline `git status --short --branch` before edits. Recheck after each logical
  change batch, after every Git-mutating op, before switching task areas, and
  immediately before the final response.
- Every time Git is used, include or refresh a Git checkpoint in the next
  user-facing update. Several read-only Git commands in one investigation share
  one checkpoint.
- Report each repo separately. Count untracked with
  `git ls-files --others --exclude-standard`; collapsed short-status dirs undercount.
- Format: `Git: HEAVY — repo=Delta-Note branch=main; staged=0, unstaged=158,
  untracked=115, conflicts=0. Mixed scopes; preserving unrelated changes.`
- Not a repo → `Git: unavailable (not a repo)`. Don't call it clean; passing
  tests ≠ clean worktree.

Levels: CLEAN = nothing. LIGHT = 1–10 paths, one scope. MODERATE = 11–50 paths or
multiple scopes. HEAVY = >50 paths or broad/mixed work. CRITICAL = conflicts,
unexpected deletions, risky staged/unstaged overlap, suspected secrets, generated
user data.

Dirty work belongs to me. Preserve unrelated changes. MODERATE+ → stage explicit
paths or `git add -p`, not `git add .` or `-A`. Don't commit, stash, restore,
reset, or clean merely to make status clean. Destructive Git ops need explicit
approval and a recoverable safety point.

## Cost guardrail: no Vercel Workflows

Don't use Vercel Workflow/Workflows, Workflow DevKit, or any
`workflow`/`@vercel/workflow`/`@workflow/*` package unless Seth overrides in the
same task. That covers creating, editing, deploying, running, inspecting, resuming,
and debugging workflow runs; `npx/bunx workflow`, `vercel workflow`, and installs
of those packages; `"use workflow"`, `"use step"`, `workflow/api`, `start()`
launchers, and DurableAgent workflow patterns.

Workflow-shaped feature → plain API routes/functions, cron, queues/background
jobs, local scripts, or DB state machines. If none fits, stop and ask.

## Tool selection

- Library/framework/SDK/API/CLI/config questions → `context7-docs` agent, not memory.
- Next.js → repo source + Context7. No runtime DevTools access assumed.
- Live browser behavior → `chrome_dev <url>`, not the relay MCP. Give repro steps,
  logs, or screenshots so we reason from real DOM/network payloads.
- Multi-domain task → combine the relevant specialists.
- Codebase/architecture/"how does X work" questions → `/graphify` query first when
  `graphify-out/` exists (see Tooling triad).

## `collab` — talk to the other live sessions, every time

`collab` (`~/.local/bin/collab`, state in `~/.local/state/agent-collab/<repo>/`)
is the only channel between concurrent Claude sessions in one repo. Use it without
being told; several sessions are usually live in Delta-Note / Delta-Drills.

Start of any repo task: `collab status` + `collab history -n 10` + `collab inbox`.
Someone else's in-flight work shows up there and nowhere else.

Pin the session id on every call: `CLAUDE_SESSION_ID=<this session's id> collab …`.
Env doesn't persist between Bash calls, and unset it falls back to `shell-<ppid>`,
a new ghost session per call, so your own claims start denying your own edits.
Same id, always.

Claims: `collab claim <paths> --why "<task>"` when you start; `collab release
--all` when the work lands. A PreToolUse hook denies an edit to a file another
live session owns. That denial is a message, not a bug: `collab request <path>
"<what you need>"` and let the owner do it.

Deploy orchestration, announce rather than surprise:
- Before any deploy: `collab status` / `history`. If another session says its work
  is unfinished or references files that only exist in its worktree, don't deploy;
  `collab request` and wait.
- Before your own deploy: `collab log "deploying <channel> from <sha>"`, and again
  after with the result.
- Any half-finished state that would break a deploy (markup linking a file you
  haven't written yet, a migration not yet applied) → `collab log` it as a deploy
  hold the moment it exists, and log the release when it's fixed.
- Committing or checkpointing files you didn't author → say so in the log with the
  sha, so the author can find their work.

No `git add -A` / `git add .` in a shared repo: it sweeps other sessions'
in-flight edits into your commit. Stage explicit paths. If it already happened,
`collab log` the sha immediately.

## /critic — cross-model verification

Codex runs `gpt-5.6-sol` at `xhigh` reasoning effort, pinned in `run_critic.py`
and mirrored in `~/.codex/config.toml` (it had silently dropped to `medium` on
2026-09-07). That's a strong independent reviewer and cheap relative to shipping
a bug, so `/critic` is the default, not the exception.

Run it, without asking, when any of these holds:
- A code diff beyond a trivial edit: new file, function, feature, refactor, bug
  fix, or anything touching more than one file.
- A bug I asked you to fix, the moment you believe it's fixed and before you tell
  me it works.
- Before every commit or deploy of authored changes (`dn_deploy`, `deploy_*`,
  `vercel`, `fly deploy`, migrations).
- High-stakes areas, always: grading/mastery/scoring math, deploy pipeline, DB
  writes/migrations, auth/session, money, anything touching real user data.
- Any review request in any wording ("check this", "does this look right",
  "second opinion", "run it past codex").
- You're uncertain, rationalized past something, or couldn't fully verify a
  claim. Uncertainty is the strongest trigger, not a reason to skip.

Skip only for: doc/README/comment-only edits, typo/formatting-only diffs,
single-line config flips, read-only investigation with no diff, and when
`MODULARIO_CRITIC_ACTIVE=1` or you're acting as critic (no nested critic).

Don't skip it to save time or tokens. If you skip it on a real diff, say so in
the reply with the reason; a silent skip is a failure. Cost is one codex call per
meaningful diff, and that trade is already approved.

- Reconcile codex's findings against your own. Report as agreed / codex-only
  (verified?) / you-only / disputed. Don't relay codex blindly, and don't drop
  your own findings because codex missed them.
- Fix verified minimal refactors immediately. Document major refactors unless Seth
  scopes them. Critic never edits.
- Codex reading a diff ≠ code running; still verify after.
- Critic-only output never triggers another critic pass. When acting as critic, or
  when `MODULARIO_CRITIC_ACTIVE=1`, don't invoke any critic/model reviewer.

## /spec — spec-first for fuzzy builds

Before a coding task whose goal, scope, or success criteria is unstated, run
`/spec`: interview for the goal (the decision it drives), carve the smallest
reviewable slice, get explicit sign-off before writing code. Skip for trivial edits.

## Tooling triad: Modulario · graphify · caveman

Three layers over the same codebases. Modulario = structural health of files.
graphify = semantic map of meaning. caveman = compression of prose.

### Modulario — structural health (authoritative)

A `[Modulario]` block appears in tool results after each write/edit. Treat it as
authoritative.

- Blocking error → stop all work. Fix the violation before any further
  write/edit, then resume.
- STATUS GREEN/LIME/YELLOW/ORANGE/RED = the file's LOC+DEPS diagonal score.
  RED/ORANGE file → add no more LOC or DEPS; consider splitting. Already RED in the
  hotspot list → cautious about adding imports/logic even for unrelated tasks.
  Status climbed a tier this edit → note it, prefer smaller follow-ups.
- `[DOC]` / `[WATCH]` nags mean that folder's `README.md` / `watch.py` is still an
  unfilled template. Fill it. Update a folder's README when you change its
  behavior, API, key files, or invariants, plus a dated Recent Changes entry.
- Fill templates in place: Read → Edit, not a `Write` overwrite. Modulario owns
  these files; the line-1 marker (`<!-- modulario:template -->` /
  `# modulario:template`) is a state flag and the watch stubs are a runner
  contract. Overwriting races Modulario's auto-regeneration and can blank your work.
- Run `mod graph <file>` before moving, splitting, or renaming; fan-in shows every
  caller that breaks.
- Full command reference, watch.py runtime gotchas, and README section template:
  `/modulario-ops` skill. Load it when filling templates or refactoring.

No `mod goals`. Removed 2026-08-10 because it read a dead version of Delta Note.
Don't run `mod goals list/add/check/uncheck` and don't restore its SessionStart
hook. Goals in a session come from delta-gate (`~/Applications/delta-gate`),
which reads the live database.

### graphify — semantic map

`/graphify` turns any input into a persistent knowledge graph. When `graphify-out/`
exists, treat codebase/architecture questions as a graph query before grepping.

### caveman — output + prose compression

Caveman mode is on by default (SessionStart hook). Keep responses compressed:
fragments fine, drop articles/filler/hedging, arrows for causality.
Code, commits, and security writing stay normal prose.
`/caveman:compress <file>` compresses a prose file in place; don't point it at a
Modulario-owned template or a vendor/`node_modules` file.

## Practical defaults

- Apply obvious fixes without re-asking.
- Validate, don't assert, on generative pipelines.
- Try without `pkexec`/`sudo` first.
- Don't ask permission for routine dev installs.
- No subagents. No Agent/Task tool, no fan-outs, no "just two agents", no Workflow
  tool. Work inline so I can watch. The one exception is me asking for an agent by
  name in that same message. A skill telling you to use the Agent tool (graphify
  says it's mandatory) doesn't override this; do that step inline instead. If a job
  looks too big to do inline, stop and say so, propose a smaller scope, and let me
  decide. "It'd be faster in parallel" isn't a reason.
