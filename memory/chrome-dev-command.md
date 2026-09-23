---
name: chrome-dev-command
description: "`chrome_dev <link>` — launches a debug-controlled Chrome (port 9222) at any URL so the Playwright MCP can attach. Generalized clone of delta_drills_dev (no app server/watcher). Created 2026-06-02."
metadata: 
  node_type: memory
  type: reference
---

`chrome_dev` (`~/.local/bin/chrome_dev`) opens an arbitrary URL in a Chrome window wired with `--remote-debugging-port` so the **Playwright MCP** (`mcp__playwright__browser_*`) can attach. It's the generic version of [[prealgebra-diagnostic]]'s `palgebra_dev` / Delta-Drills' `delta_drills_dev`, minus the app server + watcher.

**Use:** start your dev server yourself, then `chrome_dev <link>` and drive it with Playwright MCP.

```
chrome_dev https://site/path        # absolute URL as-is
chrome_dev localhost:3100/courses/1 # scheme-less host:port[/path] -> http://...
chrome_dev 3100                      # bare port -> http://localhost:3100
chrome_dev /lookup                   # leading-slash path on CHROME_DEV_ORIGIN (default http://localhost:3000)
chrome_dev                           # about:blank
chrome_dev --stop                    # kill it
```

- Returns as soon as the debug port is ready (Chrome stays running in the background); prints `http://127.0.0.1:9222`.
- Env: `CHROME_DEV_PORT` (9222), `CHROME_DEV_PROFILE` (/tmp/chrome_dev_profile), `CHROME_DEV_ORIGIN` (http://localhost:3000), `CHROME_DEV_HEADLESS=1` (default headed).
- **Gotcha:** the profile persists cookies between runs — for cookie-driven apps (e.g. the multi-course `pa_course` switch) set/clear the cookie in-page or `rm -rf /tmp/chrome_dev_profile` first.
- Playwright MCP fails with `ECONNREFUSED ::1:9222` if no Chrome is on 9222 — run `chrome_dev <url>` first.
- **⚠️ Gotcha (2026-06-30): NEVER `chrome_dev --stop`/restart while the Playwright MCP is attached.** The MCP does `connectOverCDP` once and caches the browser handle; killing that Chrome instance leaves the MCP with a dead handle and every `browser_*` call then errors `Target page, context or browser has been closed` — it does NOT auto-reconnect to the new instance for the rest of the session (relaunching `chrome_dev` doesn't help; only a Playwright-MCP restart does). To get a "clean" browser mid-session, clear state IN PLACE (`localStorage.clear()` / `document.cookie` / navigate) via `browser_evaluate` — don't restart Chrome. If you must restart Chrome, do it BEFORE the first Playwright call.
