---
name: critic
description: Get an independent Codex (gpt-5.6-sol, high effort) review of a Claude-authored Git diff, record feature purpose/duplication notes plus minimal and major refactor suggestions for Modulario, then reconcile findings. This is the DEFAULT verification step for authored code — use it proactively and without being asked after ANY non-trivial diff: new feature, new file, refactor, or a bug fix you believe is done, before reporting success, and before any commit or deploy. Also use for /critic, any review or second-opinion request in any wording, whenever you are uncertain about a change, and always for high-stakes grading/mastery/scoring math, deploy pipeline, DB writes/migrations, auth/session, money, or real-user-data changes. Skip only for doc/comment/typo/formatting-only edits or when already acting as critic.
---

# critic

A second model catches what the author rationalizes past. Hand Claude's diff to
**Codex** in an isolated temporary directory. Shared runner records structured
critic notes for Modulario.

## When to reach for it

Codex here is **`gpt-5.6-sol` at `xhigh` reasoning effort**, pinned on the command line by `run_critic.py` so a config-file downgrade cannot reach it. Strong reviewer, one call
per diff — so the default answer to "should I critic this?" is **yes**. The bar is
not "is this important enough", it is "is this too trivial to bother".

**Run it unprompted when any of these holds:**
- Any non-trivial diff you authored — new feature, new file, refactor, or bug fix.
- A bug fix you think is done — critic it **before** telling Seth it works.
- Before any commit or deploy of authored changes.
- The expensive-to-be-wrong set, always: grading / mastery / scoring math, deploy
  pipeline, DB writes/migrations, auth/session, money, real user data.
- Seth asks in any wording (`/critic`, "run it past codex", "second opinion",
  "check this", "does this look right").
- **You are uncertain, or you notice yourself explaining away a doubt.** That is
  the highest-yield case, not a reason to skip.

**Skip only for:** doc/README/comment-only edits, typo or pure-formatting diffs,
single-line config flips, read-only investigation with no diff, and when
`MODULARIO_CRITIC_ACTIVE=1` or you are the critic (nesting is rejected).

Skipping on a real diff must be stated out loud with a reason. Never skip for speed
or token cost — that trade is already approved.

## How to run

```bash
~/.claude/skills/critic/critic.sh            # staged+unstaged vs HEAD (default)
~/.claude/skills/critic/critic.sh main       # current tree vs main
~/.claude/skills/critic/critic.sh --files path/to/a.py path/to/b.ts
```

Runner includes staged, unstaged, and untracked changes. Codex returns strict
feature JSON: category, subcategory, purpose, duplication evidence, correctness
findings, minimal refactors, and major refactors. Notes persist under ignored
`Modulario/data/critic/`; target repo is untouched. Refactor reason categories
include `performance` for concrete speed/runtime-cost concerns.

One pass only. Critic output is verification, not authored feature work; never
invoke this skill while acting as a critic. Runner rejects nested critic calls.

## Reconcile — the actual work

codex's output is **signal, not verdict**. Two librarians, two libraries:

1. **Agreement** → the finding is real; fix it.
2. **codex flags something you missed** → verify it yourself against the code before acting. codex can hallucinate a caller or misread context.
3. **codex contradicts your own review** → that disagreement is the valuable part. Investigate which model is right; say so explicitly to Seth.
4. Verify every minimal refactor; fix valid ones immediately. Critic never edits.
5. Keep major refactors documented; do not implement without user scope.
6. Codex says clean AND you found nothing → report agreement, then `/verify`.

Never present codex's findings as fact without checking them, and never suppress your own findings because codex missed them. Report to Seth as: **agreed / codex-only (verified?) / you-only / disputed.**

## Domain rules to check by name

Rules that cost a real learning session to discover, and that a diff can quietly
break without failing anything. Check these whenever the diff touches the area.

**Fading (Delta Drills lesson content, `## Faded practice`).** A faded starter
must blank the concept and keep the scaffold. The shape to want is `z.__(__)` —
structure given, call hidden. The failure is the inverse: blanking the argument
and leaving the method (`z.clamp(_____=0.0)` on the KP that teaches `clamp`), a
drill anyone can pass by reading, which the ladder then promotes on. The
operative rule: every symbol in the KP's `new_syntax` frontmatter is blanked,
everything an earlier lesson taught may stay. Enforced by
`lesson_quality.check_fade_leak` (FADE_LEAK) and applied by
`lesson_lib.blank_new_syntax`; a diff that touches either, or that hand-authors
a starter, gets this read explicitly. Same rule at any size — on a long solution
the scaffold gives away every supporting step and hides only the move being
learned plus its arguments.

## Cost note

One Codex call per meaningful diff — pre-approved, do not weigh it. Re-run after
high-stakes fixes. A missed bug in grading, deploy, or DB costs far more than the
call.
