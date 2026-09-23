---
name: feedback-apply-obvious-fixes
description: "When the user has already approved a fix path or the fix is obvious from the diagnosis, apply it without re-asking for confirmation. Don't pause for permission to do the right thing."
metadata: 
  node_type: memory
  type: feedback
---

When I've already diagnosed a bug + proposed a clear fix in my reply, and the user comes back wanting it resolved, just **apply both the patch and any sensible companion guard without re-asking**. Skip the "want me to apply both?" turn.

**Why:** The user explicitly told me to stop pausing for permission after the bug-diagnosis turn — said "next time just go ahead and do the fix without asking" after I diagnosed bad question-metadata + proposed a visualizer guard and asked confirmation instead of just doing it. They view the round-trip as friction, not safety.

**How to apply:**
- Diagnosis + obvious fix in same response: do the fix immediately, don't ask.
- Defensive sister-changes (guards, watch.py invariants, cache bumps, README entries) when they belong with the same fix: bundle them in without a separate confirmation.
- Still ASK before: destructive ops, anything affecting shared/remote state (git push, deploys, dropping data), or genuinely ambiguous scope where you'd take the wrong path.
- Verify yourself via Playwright/MCP after — see [[feedback-mcp-verify-frontend-changes]] if it exists, otherwise just be the verifier so the user doesn't have to.
