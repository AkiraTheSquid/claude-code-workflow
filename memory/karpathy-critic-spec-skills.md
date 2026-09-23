---
name: karpathy-critic-spec-skills
description: /critic (codex second-model review) + /spec (interview-first spec) skills — Karpathy Layer-2 & Layer-1
metadata: 
  node_type: memory
  type: project
---

Two user-global skills added 2026-07-10, closing Karpathy-method gaps B & C (Layer-3 gap A = [[pretooluse-hard-guards]]). Context: [[kolb-vault-conceptual-its]].

**`/critic`** (`~/.claude/skills/critic/`) — Layer-2 "second librarian." `critic.sh [base|--files ...]` sends the git diff to `codex exec --sandbox read-only` (codex 0.144.1, model gpt-5.6-sol) with a fixed correctness-review contract; returns findings. **Reconcile, don't relay** — report agreed / codex-only(verified?) / you-only / disputed. Smoke-tested: codex caught a planted off-by-one w/ repro but MISSED an empty-list crash → proves why reconciliation matters. **Routine trigger** (CLAUDE.md rule, not on-request): diffs touching grading/mastery math, deploy pipeline, DB writes, auth/session, money → run before saying "done", still `/verify` after.

**`/spec`** (`~/.claude/skills/spec/`) — Layer-1, instruction-only. Interview for the GOAL (decision it drives, not the task) → carve smallest reviewable slice (agile) → precise checkable success criteria → explicit sign-off on key decisions BEFORE code. Skip for trivial/mechanical edits.

Both wired into global `~/.claude/CLAUDE.md` (new "Cross-model critic" + "Spec-first for fuzzy builds" sections). codex invocation that works headless: `codex exec --sandbox read-only -C <repo> "<prompt>"`, diff on stdin.
