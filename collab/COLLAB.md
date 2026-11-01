# Working alongside other agents

You do not need to have read this. The hooks enforce it, and every refusal tells
you the exact command to run. This file is the why.

You cannot see the other agents' context and they cannot see yours. Several
sessions are usually live in Delta Note and Delta Drills at once.

## What the hooks do (all repos, automatically)

Reads are never blocked. On a **state-changing** call — Edit/Write, a Bash
command that writes, commits, installs, runs a script or deploys, or a
state-changing Delta Note MCP tool — in a repo:

1. **No intent yet → refused.** Say what you're about to do:

       collab intent "<one line: your task>" --files <files you expect to change>

   That is your JOIN: it is logged, announced to every other agent in the repo,
   claims the files, and prints who else is there and where you overlap.
2. **Another agent joined since you last looked → refused** until you log how
   your work overlaps theirs:

       collab ack "<overlap: none | which files/areas and how you'll split them>"

3. **File owned by another live agent → refused**, Edit or Bash (`sed -i`, `>`,
   `tee`, `cp`/`mv`/`rm`, `git add/checkout/restore <file>`). Ask instead:

       collab request <path> "<the change you need and why>"

4. **`git stash` → always refused** (Seth's rule). `git add -A`/`.`, `commit -a`,
   `reset --hard`, `clean`, `checkout .`, and branch switches → refused while
   another agent is active in the repo. Stage explicit paths; use
   `agent-worktree new <name>` for a separate branch.
5. **Deploy while another agent holds → refused.** Holding is how you say "my
   work is half-done, don't ship the tree":

       collab hold "<why a deploy now would break>"    /   collab hold --release

Automatic, so you don't have to remember: files you write are claimed; commits
and deploys are logged; other agents' new log lines are pushed into your
context; after 25 quiet minutes you're nudged to log a milestone; at session end
everything is released in every repo you touched.

Your session id comes from `CLAUDE_CODE_SESSION_ID` and your repo from your cwd,
else the repo you last worked in — so `collab …` works from `~`. Use
`--repo <path|app name>` to be explicit.

## What belongs in the log

Not "edited three files". What the next agent would otherwise rediscover:

- an invariant you established or relied on, and what breaks it;
- a footgun you hit — the wrong-looking error, the silent failure;
- anything you changed near territory someone else owns;
- deploys and their result, and what state the tree was in.

## Commands

    collab status                 this repo: who's live, intents, files, overlaps
    collab who                    every repo
    collab intent "<task>" [--files …]
    collab ack "<overlap>"
    collab log "<what and why>"   collab history [-n N]
    collab request <path> "<w>"   collab inbox   collab resolve <id> "done"
    collab hold "<why>"           collab hold --release
    collab done "<summary>"       release files, clear intent
    agent-worktree new|list|finish

Kill switch (Seth): `touch ~/.local/state/agent-collab/DISABLED`.
