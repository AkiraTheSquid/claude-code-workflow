# Mockup harness

Static, unwired UI mockups. One HTML file per **variant** (a layout), one
function per **scene** (a moment that layout has to survive). An index page
lists every variant × scene as a card; a floating bar on each variant page
switches scene and layout without going back.

```
index.html          gallery — generated, do not hand-edit cards
mockups.config.js   THE list: variants, scenes, blurbs, notes
harness.css         tokens + gallery + bar. Load first everywhere.
harness.js          renders gallery / bar, applies ?scene=, keys
variant-a.html      a layout. Copy for variant-c, -d, …
variant-b.html      the alternative
serve.sh            serve on a free port + open in the real Chrome
shots.sh            headless PNG of every variant × scene → shots/
```

## Add a scene

1. Add `{ id, name, note }` to that variant's `scenes` in `mockups.config.js`.
2. Add a function of the same id to `SCENES` in the variant file.

Mismatches warn in the console — a scene on the index with no function, or a
function no card points at.

## Add a variant

Copy `variant-a.html` → `variant-c.html`, change `Mockup.boot({ variant: 'c' })`,
add the entry to `mockups.config.js`. Reuse scene **ids** across variants where
the scene means the same moment; the bar then flips layouts without changing
the situation being compared.

## Run it

```bash
./serve.sh              # free port from 8900, opens the index in Chrome
./serve.sh --no-browser # server only
./serve.sh --stop       # stops only this folder's server
./shots.sh --phone      # stills for a write-up
```

`serve.sh` never restarts a debug Chrome that is already running — it opens a
tab in it. Restarting Chrome mid-session leaves an attached Playwright MCP
holding a dead handle for the rest of the session.

## Keys on a variant page

`←` `→` scene · `[` `]` variant · `i` index · `p` phone window · `h` hide bar.
Ignored while the caret is in a field.

## Conventions worth keeping

- **A scene never mutates another scene.** Switching scenes is a navigation,
  so every scene starts from the markup in the file.
- **Every scene is a state, not a screenshot.** Fresh, mid-task, error, empty,
  too-slow, out-of-time. The states usually skipped are the ones a mockup is
  for.
- **Small `mock` verbs, shared across variants** (`mock.clock`, `mock.words`).
  Scenes stay readable and two layouts stay comparable.
- **Nothing is wired.** No fetch, no storage, no real data. If a mock needs a
  number, the scene hard-codes it.
- **`notes` on the index is for the open calls** — the decisions you want back,
  not a caption of the pictures.
