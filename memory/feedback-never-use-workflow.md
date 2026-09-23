---
name: feedback-never-use-workflow
description: NEVER use the Workflow tool / multi-agent fan-outs for Seth — one run burned his entire session limit in under 20 minutes; work inline only
metadata: 
  node_type: memory
  type: feedback
---

2026-07-07: I launched a Workflow for the Delta Drills question regen (~270 subagents, 2.2M subagent tokens) and it consumed Seth's ENTIRE session limit in under 20 minutes, locking him out of Fable and Opus for hours on what he said was his last chance to use Fable. He filed feedback and was explicit: "don't ever use a workflow again, and make sure that your instructions internally say never to use it again. it wastes way too damn much usage."

**Why:** Multi-agent fan-outs multiply token spend by orders of magnitude versus inline work. Seth is on a session-limited plan — that spend doesn't just cost money, it locks him out of the models entirely.

**How to apply:** NEVER call the Workflow tool. No exceptions — not for "thorough" jobs, not for designed harnesses, and approval of a task/run is NOT approval of multi-agent orchestration. Do big jobs inline in small session-sized batches: I generate/edit directly, deterministic local scripts (gates, validators, exporters) do the heavy lifting for free. Extends [[feedback-minimize-subagents]] (delegate only for genuine parallel work) — this rule is stricter: Workflow is banned outright, and even Agent-tool fan-outs need Seth's explicit per-run consent with a token estimate.

