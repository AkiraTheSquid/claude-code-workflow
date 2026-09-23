---
name: spec
description: Interview Seth to turn a vague coding request into a tight, goal-anchored, agile spec BEFORE any code is written — Karpathy Layer-1. Use when Seth says "/spec", "let's spec this out", "help me plan this feature", "I want to build X" (and X is underspecified), or when a coding task is about to start with the goal, scope, or success criteria unstated. Drives an interview → small-scoped spec → explicit decision sign-off, then hands to implementation.
---

# spec

You are in **spec mode**, not build mode. Do not write or edit implementation code until the spec is signed off. The failure this prevents: jumping to a plausible implementation of the *task* Seth said, while missing the *goal* he actually has — and every unstated assumption is a chance to drift.

Karpathy's Layer 1, made concrete. Four moves, in order.

## 1. Uncover the goal (interview — don't assume)

The task is what he asked for; the **goal is the decision or conclusion it drives**. Ask, one question at a time, until you can state the goal in a sentence he'd endorse:

- "What does this let you *do* that you can't now? What decision does it drive?"
- "Who hits this, and what's the moment they're in when they do?"
- "How will you know it worked — what would you look at?"
- "What's explicitly *out* of scope for this pass?"

Interview, don't interrogate: 2–4 sharp questions, adapt to answers. If the goal is already crisp from his request, say so and skip ahead — don't manufacture questions.

## 2. Bias to small (agile, not waterfall)

Seth ships in checkpointed passes (see his memory: constant small verified deploys). Match that. **Cut the spec to the smallest slice that produces something reviewable.** If the request is big, name the full arc in one line, then carve off pass 1 and spec only that. Explicitly defer the rest to "later passes" — don't spec what you won't build now.

## 3. Write the spec — precise, so there's nothing to assume

Keep it short. Structure:

- **Goal** — the one-sentence conclusion/decision (from move 1).
- **Scope (this pass)** — the small slice. And **Not this pass** — what's deferred.
- **Success criteria** — precise and checkable ("returns X for input Y", "gate Z passes"), never "make it good." This doubles as the `/verify` and `/critic` target later.
- **Key decisions** — each fork with the option you'd pick and the alternative, in one line each.
- **Touch list** — files/modules expected to change (run `mod graph <file>` for fan-in if renaming/moving; check Modulario status before adding LOC to a RED/ORANGE file).

For a substantial feature, write it to a file in the project (e.g. `docs/spec-<slug>.md` or the repo's convention) so it's a durable artifact. For a small one, inline in chat is fine.

## 4. Make Seth verify key decisions explicitly

Before any code: surface the **Key decisions** list and get sign-off. Use AskUserQuestion when a fork has real trade-offs and his answer changes the build. Do **not** proceed on assumed answers to load-bearing decisions — that's the whole point of the layer.

Once decisions are confirmed: exit spec mode, implement the small slice, then `/verify` (and `/critic` if it's high-stakes). Then the next pass.

## Don't over-apply

Trivial/mechanical asks ("rename this", "fix this typo", "bump the version") do not need a spec — just do them. This is for work where drift is expensive: new features, anything with a fuzzy goal, anything touching multiple modules.
