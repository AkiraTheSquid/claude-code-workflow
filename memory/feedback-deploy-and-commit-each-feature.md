---
name: feedback-deploy-and-commit-each-feature
description: "Seth wants every finished feature committed, pushed AND deployed without being asked — standing, not per-task"
metadata: 
  node_type: memory
  type: feedback
  modified: 2026-08-12T16:40:06.281Z
---

Commit, push, and deploy after finishing a piece of work. Standing order as of
2026-08-12 ("push and deploy always after finishing") — do not stop and ask each
time, and do not stop at "committed" and offer to deploy.

**Why:** the work isn't done until it's on the channel he can look at; asking every
time turns a finished feature into another round-trip.

**How to apply:** check `git status` scope first and stage explicit paths (never
`git add .`) — the worktree is shared with other sessions. For Delta Note,
`dn_deploy beta` publishes the **WORKING TREE**, so when another session has
in-flight edits, deploy from a temporary `git clone` of the repo checked out at
your commit rather than skipping the deploy or shipping their half-done work —
`dn_deploy` rejects a `git worktree` (`.git` is a file there, and it tests
`-d "$REPO_DIR/.git"`), so a clone is the move. Delete the clone afterwards.
See [[delta-note-release-channels]], [[feedback-never-stash-in-shared-repo]].
