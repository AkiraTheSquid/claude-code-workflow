---
name: critic-invoke-as-claude-author
description: Run /critic as author=claude so codex reviews — critic.sh reviews with Fable and is expensive
metadata:
  type: feedback
---

🔴 Never invoke `~/.codex/skills/critic/scripts/critic.sh` from a Claude session.
That wrapper is `run_critic.py codex …` — it declares **codex** as the author, so
the reviewer is **Fable**, which Seth considers overkill and expensive.

Correct call (reviewer = codex `gpt-5.6-sol`, which is what the rule in
`~/.claude/CLAUDE.md` means by `/critic`):

    env -u MODULARIO_CRITIC_ACTIVE python3 \
      $HOME/Applications/Modulario/scripts/run_critic.py claude [base|--files paths...]

**Why:** `REVIEWERS = {'claude': ('codex', …), 'codex': ('fable', …)}` in
`run_critic.py` — the first positional arg is the AUTHOR, not the reviewer.

**How to apply:** pass `claude` as the author. `--files` diffs the WORKING tree,
so once work is committed it reports "empty diff"; to review committed work,
`git worktree add --detach <base>`, `git apply` the diff of just your paths, and
run the critic there — that also keeps a peer session's dirty files out of the
review. See [[karpathy-critic-spec-skills]].
