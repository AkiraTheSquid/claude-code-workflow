---
name: feedback-validate-dont-assert
description: "On generative-pipeline work, validate that output is correct with an independent check — don't just assert 'DAG clean / loads OK'"
metadata: 
  node_type: memory
  type: feedback
---

On graph/data-generation work (e.g. the Delta Drills encompassing graph), the
user explicitly wants **validation that it actually works**, not just structural
assertions like "schema loads" or "DAG is acyclic."

**Why:** "done right" to this user means evidence the *content* is correct, not
just that the artifact is well-formed. Loading cleanly proves nothing about
whether the edges/weights are right.

**How to apply:**
- Add a real validation layer: (1) structural invariants, (2) BEHAVIORAL — run
  the artifact the way it'll be used (e.g. simulate the propagation/trickle-down)
  and assert it behaves, (3) an INDEPENDENT blind check (a fresh judge re-derives
  a stratified sample, compare for agreement %/error rate).
- Don't impose a prior and force the data to match it. I added a skeptical
  "demote most to zero" pass based on Skycak's K-12-math "most relationships are
  non-encompassing" claim; a blind validator showed it over-corrected for ARENA's
  from-scratch corpus, and I had to revert. Let independent neutral judgment
  decide; flag genuinely-contested magnitude for human/domain-expert sign-off.
- Also: the user got impatient with repeated AskUserQuestion prompts mid-task
  ("stop asking questions and figure it out on your own"). On exploratory work,
  make the call from the evidence and proceed; surface decisions in the writeup,
  not as blocking questions — unless it's genuinely their call (scope/cost).

See [[delta-drills-encompassing-graph-model]], [[feedback_apply_obvious_fixes]].
