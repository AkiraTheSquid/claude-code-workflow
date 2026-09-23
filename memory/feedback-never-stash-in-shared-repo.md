---
name: feedback-never-stash-in-shared-repo
description: "Seth runs concurrent Claude sessions in the same worktree — never `git stash` to isolate a test; use a temporary `git worktree` at HEAD instead."
metadata: 
  node_type: memory
  type: feedback
  modified: 2026-08-18T13:39:42.658Z
---

Seth often has **another Claude session editing the same worktree at the same time**
(seen 2026-08-01 in `~/Applications/Delta-Note`: a second session was building the
brain-dump day-window + day-move drag while I fixed the capture bar).

**Never `git stash` (especially `-u`) to get a clean tree for a baseline run.** It
sweeps up the other session's in-flight work, and `git stash pop` then fails on
files they have re-edited since — their uncommitted changes end up recoverable only
from the stash, and any Edit they attempt in between fails on content that no longer
matches.

**Why:** stash is worktree-global; "my changes" is not a unit git understands.

🔴 **The INDEX is shared too — staging is not a safe place to park work.** Happened
2026-08-12: I `git add`-ed my 13 paths, spent ~1 min composing the commit message,
and the other session committed + pushed in that window. Its commit
(`fix(deploy): let dn_deploy run from a linked git worktree`) swallowed my entire
Daily-board Schedule feature; my own `git commit` then reported "no changes added to
commit". Correct code, wrong commit message, already on `origin/main`.

🔴 **HAPPENED AGAIN 2026-08-18 — so stop using `git add` at all here.** I staged three
paths, ran the checks, and another session's commit (`976d652`, about the goal tree)
swallowed all three; my own commit came out holding one file of four.

**How to apply — `git commit -F msg -- <explicit paths>` and never `git add` first.**
A path-limited commit takes those paths from the WORKTREE, ignores the rest of the
index, and leaves everyone else's staging untouched. One command, no window at all.
The older "add + commit in one bash call" still leaves a window while the message
heredoc is being written; this has none. After committing, re-read `git log -1 --stat`:
if your files landed in someone else's commit, SAY SO instead of silently rewriting.

🟢 **There IS a per-session staging area: `GIT_INDEX_FILE`.** Point it at a scratch
path and every index command in that one shell uses a private index; the shared one
is never read or written. This is the tool that makes a split safe with another
session live in the tree — 2026-08-18, verified.

**The split recipe that never touches the worktree or the shared index** (use this
one; the reset recipe below is the fallback when the commit to split is the tip and
nobody else is editing):
```
git tag safety/pre-split-<tip> <tip>          # recoverable point FIRST
export GIT_INDEX_FILE=<scratch>/split.index   # private staging area
git read-tree <base>                          # base = the commit BEFORE theirs
git ls-tree <mixed-sha> -- <their path> | git update-index --index-info   # per path
TREE=$(git write-tree); unset GIT_INDEX_FILE
C1=$(GIT_AUTHOR_DATE=<orig> GIT_COMMITTER_DATE=<orig> git commit-tree $TREE -p <base> -F theirs.msg)
C2=$(... git commit-tree <later-commit>^{tree} -p $C1 -F mine.msg)   # reuse EXISTING trees
git diff $CN <old-tip>                        # MUST be empty — content identical
git update-ref refs/heads/main $CN <old-tip>  # old-value guard: a concurrent commit ABORTS
```
🔑 Later commits usually need no custom tree at all — reuse `<sha>^{tree}` and just
re-parent. Only the commit being split needs one built by hand. Pass the original
`GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` or the log jumps. `git status` is byte-identical
afterwards, so the other session never sees it happen.
🔴 Check `git branch -r --contains <sha>` first: if it is UNPUSHED there is no
force-push and no lease to worry about (2026-08-18: `origin/main` was 15 behind, so
the whole split was local). Tell the other sessions their shas moved — the collab
file is the place.

**Seth's call when it happens: split it.** He asked for the fix (2026-08-12 and again
2026-08-18) — a mislabelled feature in the log is worse than a rewrite. The older
recipe, with the other session mid-edit in the same tree:
`git tag safety/pre-split-<sha> <sha>` → `git log -1 --format=%B <sha> > theirs.msg`
→ `git reset --soft <sha>~1` (soft leaves the worktree ALONE, so their uncommitted
work is untouched) → `git restore --staged -- <your paths>` → commit theirs → add +
commit yours → verify `git diff <tag> HEAD` is EMPTY (content identical, only history
reshaped) → `git push --force-with-lease=main:<sha> origin main`. The lease pinned to
the old sha is what makes a concurrent push abort rather than get clobbered.

**How to apply:**
- To run a check against HEAD without your patch:
  `git worktree add --detach <scratch>/verify HEAD`, `git diff -- <your files> > p.patch`,
  apply it there, run. Remove with `git worktree remove --force`. Zero effect on the
  shared tree.
- If a file (typically a folder `README.md`) holds BOTH sessions' edits: rebuild a
  your-lines-only version from `git show HEAD:<path>`, write it to disk for the length
  of ONE `git commit -- <path>`, then restore the full text. (The `git hash-object -w`
  + `git update-index --cacheinfo` route also works and never touches disk, but it
  parks the result in the shared index — where the next session's commit takes it.)
- 🔴 **You CAN deploy — from a throwaway worktree, never from the shared tree.**
  `dn_deploy` publishes the WORKING TREE, so running it here ships the other session's
  uncommitted work (2026-08-18: beta came up `dirty:true` carrying another agent's
  in-flight bell changes). Recipe: `git worktree add --detach <scratch> <sha>` →
  run **that worktree's own** `scripts/dn_deploy.sh beta` ([[delta-note-dn-deploy-worktree-trap]])
  → confirm `channel.json` says `dirty:false` → `git worktree remove`. ~30s, and it
  beats holding the deploy ([[feedback-deploy-and-commit-each-feature]]).
- Recheck `git status` often — the file list changes under you mid-task.
