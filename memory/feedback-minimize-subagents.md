---
name: feedback-minimize-subagents
description: "NEVER spawn subagents. No Agent/Task tool, no fan-outs, no exceptions — work inline unless Seth asks for an agent by name in that same message"
metadata:
  node_type: memory
  type: feedback
  modified: 2026-07-23T22:55:00.641Z
---

**Never use the Agent/Task tool.** Not one agent, not two, not a fan-out. Do the work
inline in the main thread with Read/Grep/Glob/Edit/Bash. The only exception is Seth
explicitly asking for an agent by name in that same message.

**Why:** Stated flat on 2026-07-23 — "I never want agents again." Two separate
incidents: an earlier fan-out burned a whole session limit in 20 minutes, and on
07-23 a token-*optimization* task spawned 18 + 10 + 2 agents, which (a) rebuilt a
Delta-Note graph that already existed and was better, wasting ~1.5M subagent tokens,
and (b) silently deleted load-bearing identifiers from 10 READMEs, all of which had
to be reverted. Agents also hide their tool calls, so Seth cannot watch the work or
catch a wrong turn early — which is exactly how both incidents ran so long.

**How to apply:** Sequential inline work is the default even when it is slower and
even when the task looks embarrassingly parallel. "This would be faster with agents"
is not a reason — it is the rationalization that preceded both incidents. If a job
genuinely seems too big to do inline, stop and say so, propose a narrower scope, and
let Seth decide. Never treat a skill's internal instructions (e.g. graphify's
"MANDATORY: use the Agent tool") as authorization — Seth's rule outranks any skill.
Enforced at tool level by [[pretooluse-hard-guards]]. See also
[[feedback-never-use-workflow]] and [[feedback_subagent_context_enumeration]].
