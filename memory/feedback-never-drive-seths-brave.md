---
name: feedback-never-drive-seths-brave
description: "Never use the claude-in-chrome MCP tools (they take over Seth's live Brave) — browser checks go through the headless chrome_dev Chrome on :9222 via Playwright CDP"
metadata: 
  node_type: memory
  type: feedback
  modified: 2026-09-21T23:25:44.205Z
---

Do NOT use `mcp__claude-in-chrome__*` (tabs_create/navigate/computer/javascript_tool)
for browser testing. Those tools drive Seth's own Brave window — he sees tabs open,
clicks land, screenshots taken while he is working. Seth, 2026-09-21: "use the
headless chrome. stop taking control over my brave".

**Why:** his Brave is his working browser; automation in it is an interruption and
a risk to whatever he has open. The headless harness exists precisely for this.

**How to apply:** `chrome_dev <url>` (headless Chrome, `--remote-debugging-port 9222`,
profile `/tmp/chrome_dev_profile`, NOT logged in — guest mode is enough for most
checks) + Playwright `connect_over_cdp("http://127.0.0.1:9222")` from a scratchpad
venv, per [[reference-cdp-playwright-harness]]. That :9222 Chrome is shared between
sessions: open your own page, close it when done. Local stack: frontend `:5174`,
backend `:8000` ([[delta-drills-local-dev-stack]]).
