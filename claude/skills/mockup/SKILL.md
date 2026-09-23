---
name: mockup
description: Build static, unwired UI mockups of a feature before it is coded — several layout variants, each with a scene per state — from a ready-made harness, then serve them and open them in Seth's real Chrome window so he can click through every version. Use when Seth says "/mockup", "mock this up", "show me what it would look like", "make some mockups of X", "I want to see a few versions of this screen", or when a UI decision needs pictures before code.
---

# mockup

Make the picture before the code. Output: a folder of static HTML that Seth
opens in **his** Chrome and clicks through — an index of every version, and a
bar on each screen that flips between scenes and layouts.

Nothing is wired. No fetch, no storage, no real app imports. A mockup that has
to boot the app is not a mockup.

## The shape (do not invent another one)

- **Variant** = one layout answering the design question. Usually 2, sometimes 3.
  One file each: `variant-a.html`, `variant-b.html`.
- **Scene** = one moment that layout must survive, selected by `?scene=id`,
  implemented as a function that mutates the already-rendered markup.
- **`mockups.config.js`** = the only list of what exists. The index gallery, the
  in-page bar, and `shots.sh` all read it.

## Steps

**1. Know what is being decided.** If the goal, the states, or which layouts to
compare are unstated, ask — briefly, in one message, then build. A mockup that
answers no question is a drawing.

**2. Scaffold.** Never write the harness by hand:

```bash
MOCK=<scratchpad>/mockups-<feature>
mkdir -p "$MOCK" && cp -r ~/.claude/skills/mockup/template/* "$MOCK"/
chmod +x "$MOCK"/serve.sh "$MOCK"/shots.sh
```

Put it in the session scratchpad unless Seth names a place. Never inside an app
repo without asking — mockups are not source.

**3. Read the real thing first.** Pull the actual colors, type, spacing and
component shapes out of the app being mocked (for Delta Note:
`shared/web-components/css/`). A mockup in the app's own skin gets judged on
the design; one in generic Bootstrap gets judged on the skin. Overwrite the
tokens at the top of `harness.css` with the app's real values.

**4. Write the variants.** Replace the throwaway markup in `variant-a.html` /
`variant-b.html`. Keep the `mock` verb pattern and keep scene ids equal across
variants where the scene is the same moment, so `[` / `]` compares like with
like.

Cover the states that get skipped, not just the happy one: fresh, mid-task,
requirement unmet, error/over-limit, empty, and the ≤900px fold.

**5. Fill `mockups.config.js`.** Every scene gets a `note` that says what the
scene is testing. Mark variants `chosen` / `reference` when there is a
recommendation. Use `notes` at the bottom for the **open calls** — the decisions
you want back, and what changes if the answer goes the other way.

**6. Serve it and PUT IT IN HIS BROWSER. Not optional.**

```bash
"$MOCK"/serve.sh          # free port from 8900, then opens the index in Chrome
```

`serve.sh` handles both rules that matter here, so use it instead of hand-rolling:
- it picks a **free** port and tracks its own pid — another session's server
  (e.g. something already on 8899) is left alone;
- if a debug Chrome is already listening on 9222 it opens a **tab** in it. It
  does not relaunch. `chrome_dev <url>` always kills the running instance first,
  and killing it leaves an attached Playwright MCP with a dead handle for the
  rest of the session — every `browser_*` call then errors until the MCP is
  restarted.

If Chrome is not up at all, `serve.sh` calls `chrome_dev` for you. Do that
before any Playwright MCP call, never after.

Delivering the URL in chat is not delivery. The window has to be open on
Seth's screen with the index in it.

**7. Verify it renders — with your own eyes.** Attach with the Playwright MCP
(`mcp__playwright__browser_navigate` to the index URL, then `browser_take_screenshot`),
or run `./shots.sh` for a headless PNG of every scene. Check the console is
clean: the harness warns for a scene on the index with no function, and for a
function no card points at. Fix those before reporting.

**8. Report.** Give the index URL, the variants with your recommendation and
the reason, and the open calls. Say plainly that nothing is wired.

## Iterating

Seth's feedback is usually "B but with A's clock". Edit in place, keep the same
port, tell him to reload — do not scaffold a second folder. When a variant dies,
set `status: 'archived'` (or run `./shots.sh --only b:working` and move it to
`stills`) rather than deleting it; the rejected layout is why the chosen one is
chosen.

## Never

- Wire it to real data, real auth, or the app's modules.
- Kill a running debug Chrome, or run `chrome_dev --stop`, mid-session.
- Touch another agent's scratchpad or another server's port.
- Hand-write cards into `index.html` — it is generated from the config.
- Report "mockups are ready" without a Chrome window open on them.
