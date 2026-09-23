# Working alongside another agent

Read this if a session-start banner told you another agent is live in this repo.

You cannot see their context and they cannot see yours. Everything either of you
learns that the other would otherwise rediscover goes in the shared log.

## The rules that are enforced

A hook denies an `Edit`/`Write`/`NotebookEdit` to a file another **live** session
owns. You will get a message naming the owner, their worktree, their branch and
what they are doing. That is not a suggestion you can work around — pick a
different file, or ask.

    collab request <path> "<the change you need, and why>"

Then keep working elsewhere. They apply it and `collab resolve` it. Asking costs
you a minute; editing behind them costs both of you the merge.

Ownership is taken **automatically** the first time you successfully edit a file.
You do not have to remember to claim, and a protocol that depended on your
remembering is exactly what this replaces.

## The rules that are not

These the hooks cannot check. They are still rules.

1. **Never `git stash`.** Sessions share a working tree. A stash takes the other
   agent's in-flight work with it, and they will not know where it went.
2. **Stage explicit paths.** Never `git add .` or `git add -A`. `git status` in
   this repo is dirty on purpose — unrelated changes belong to whoever made them.
3. **Never commit, revert, or clean the other agent's work**, even to make the
   tree tidy for your own commit.
4. **Do not deploy while the tree is dirty with someone else's work.** Delta
   Drills' Colab deploy runs `git add -A && git push` in its worktree, and
   `dn_deploy` in Delta Note publishes the WORKING TREE rather than a commit.
   Either one, run at the wrong moment, ships a half-written feature. Deploy only
   in a window where `git status` is clean, and say so in the log.
5. **Release when you leave an area.** `collab release --all`. The session-end
   hook does this for you, and the claim goes stale after 90 minutes regardless,
   but neither helps the agent blocked right now.

## When to isolate instead

Claims make two agents take turns on a file. That is right when the work barely
overlaps and wrong when both features need the same three files — then turns are
just a slower way to do it one at a time.

    agent-worktree new <name> "what this agent is doing"

Gives the agent its own worktree on its own branch, as a sibling directory of the
repo. Both work at full speed; the cost is paid once, at the merge, by whoever is
orchestrating. That agent commits in its own worktree only and does not push,
deploy, or stash.

Delta Note learned this the hard way: two agents that both needed
`focus_timer_view.js`, `js/do/README.md` and `js/do/watch.py` were split into
worktrees precisely because the claims table had them queueing.

## Commands

    collab status               who is live, who owns what, requests for you
    collab claim <path>...      take files ahead of editing them
    collab release --all        hand everything back
    collab request <p> "<w>"    ask the owner for a change
    collab inbox                requests waiting on you
    collab resolve <id> "done"  close one
    collab log "<what and why>" append to the shared log
    collab history              read it
    agent-worktree new|list|finish

## What belongs in the log

Not "edited three files". The things the next agent would otherwise have to
rediscover, written as consequences:

- an invariant you established or relied on, and what breaks it;
- a footgun you hit — the wrong-looking error, the silent failure;
- anything you changed in a file someone else owns territory near;
- when you deployed, and what state the tree was in.
