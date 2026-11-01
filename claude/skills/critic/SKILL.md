---
name: critic
description: Get an independent Codex review of a Claude-authored Git diff, then reconcile its findings with your own. This is the DEFAULT verification step for authored code — use it proactively and without being asked after ANY non-trivial diff: new feature, new file, refactor, or a bug fix you believe is done, before reporting success, and before any commit or deploy. Also use for /critic, any review or second-opinion request in any wording, whenever you are uncertain about a change, and always for scoring math, deploy pipeline, DB writes/migrations, auth/session, money, or real-user-data changes. Skip only for doc/comment/typo/formatting-only edits or when already acting as critic.
---

# critic

A second model catches what the author rationalizes past. Hand Claude's diff to
**Codex** (a different model family) in a read-only sandbox, get findings back,
reconcile.

## When to reach for it

The default answer to "should I critic this?" is **yes**. The bar is not "is this
important enough", it is "is this too trivial to bother".

**Run it unprompted when any of these holds:**
- Any non-trivial diff you authored: new feature, new file, refactor, bug fix.
- A bug fix you think is done: critic it **before** telling the user it works.
- Before any commit or deploy of authored changes.
- Expensive-to-be-wrong areas, always: scoring math, deploy pipeline, DB
  writes/migrations, auth/session, money, real user data.
- The user asks in any wording ("check this", "second opinion", "run it past codex").
- **You are uncertain, or notice yourself explaining away a doubt.** Highest-yield case.

**Skip only for:** doc/README/comment-only edits, typo or formatting diffs,
single-line config flips, read-only investigation, and when
`MODULARIO_CRITIC_ACTIVE=1` or you are the critic (nesting is rejected).

Skipping on a real diff must be stated out loud with a reason.

## How to run

```bash
~/.claude/skills/critic/critic.sh            # staged+unstaged+untracked vs HEAD
~/.claude/skills/critic/critic.sh main       # current tree vs main
~/.claude/skills/critic/critic.sh --files path/to/a.py path/to/b.ts
```

One pass only. Critic output is verification, not authored work; never invoke this
skill while acting as a critic.

## Reconcile — the actual work

Codex's output is **signal, not verdict**:

1. **Agreement** → the finding is real; fix it.
2. **Codex flags something you missed** → verify it against the code before acting. Codex can hallucinate a caller or misread context.
3. **Codex contradicts your review** → that disagreement is the valuable part. Work out which model is right and say so.
4. Fix verified small refactors immediately. Critic never edits.
5. Codex says clean AND you found nothing → report agreement, then still run the code.

Report as: **agreed / codex-only (verified?) / you-only / disputed.**
