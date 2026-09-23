---
name: reference-cdp-playwright-harness
description: The Playwright MCP is dead — drive the chrome_dev Chrome (:9222) from a scratchpad Python venv via connect_over_cdp for Delta Drills browser tests
metadata: 
  node_type: memory
  type: reference
  modified: 2026-09-06T16:57:45.278Z
---

Playwright MCP tools returned nothing (2026-09-06). Working substitute: a venv in the session
scratchpad — `python3 -m venv pw && pw/bin/pip install playwright` (no browser download
needed), then

    from playwright.sync_api import sync_playwright
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222"); page = b.contexts[0].new_page()

against `chrome_dev` (memory [[chrome-dev-command]]), logged in as Seth, local stack
`:5174` frontend / `:8000` backend (Modal kernel).

**Gotchas:** a test that dies leaves its tab OPEN with the session clock ticking, and
`_persist()` rewrites the `*_session` snapshot every second — close stray localhost tabs
before the next run or "the snapshot won't clear". Clear ALL keys ending `_session` (the
account key isn't resolved at DOMContentLoaded). `locator.check()` fails on visually-hidden
radios — click the label. `page.evaluate` sees script-global consts (`PracticeAPI`) but
`window.PracticeAPI` is undefined. Harness scripts to rebuild: `arena_run_test.py` (runs
notebook cells for real, splices the solution into a faded cell, checks the error path) and
`ex_session_test.py` ([[delta-drills-exercise-sessions]]).

🔴 **The practice Start/Resume buttons are screen-reader-only** (2026-09-09). In
`styles/practice/timer.css`, `.session-resume-panel` and `.session-start-btn` are
`position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%)` —
kept because a `display:none` button still takes a synthetic click but leaves the
accessibility tree. So `#session-start-btn` / `#session-resume-btn` / `#session-discard-btn`
report `offsetParent` truthy and Playwright calls them "visible, enabled and stable", then
the click times out with "`#practice-session-setup` intercepts pointer events" — they sit
at y≈1039 on a 900px viewport inside a 1px-tall clipped panel. **The real control is
`#session-continue-btn` ("Continue practicing") on the dial**, which forwards to whichever
of the three applies. Filter candidates by `getComputedStyle(e).clipPath === 'none'`, not
by `offsetParent`. Same trap on the clock: `#session-countdown` is a hidden mirror stuck at
`--:--`; the visible one is `#practice-notch-clock`.

🔴 **Type the answer through `window.DeltaNotebook.restore(sol)`**, not into `#code-editor`
— the legacy textarea is not what Submit serializes, so a submit looks like it does nothing
(no network, no verdict). With the notebook written, Submit gives `/api/practice/submit` 200
then `/api/practice/next-question`. Related: [[delta-drills-local-always-local-cpu]].
