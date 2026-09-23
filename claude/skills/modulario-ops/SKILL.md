---
name: modulario-ops
description: Modulario command reference and template-filling procedure. Load when filling a README.md or watch.py template (a [DOC] or [WATCH] nag fired), when refactoring/moving/splitting files, when resolving a Modulario blocking error, or when working with mod goals, mod graph, mod query, or mod watch. The always-on rules live in CLAUDE.md; this is the detail.
---

# Modulario ops

Structural-health tooling over tracked projects. CLAUDE.md carries the operative
rules (blocking errors stop work; RED/ORANGE files get no new LOC/DEPS; fill
templates in place; goals only checked on Seth's explicit confirmation). This file
is the reference you load when actually doing the work.

## Filling templates in place — the procedure

Modulario owns `README.md` and `watch.py`. The line-1 marker is a state flag it
watches; the watch stubs are a contract its runner expects. **Read → Edit. Never
`Write`-overwrite** — that bypasses the read-first guard, destroys the scaffold, and
races auto-regeneration (a resumed session or re-run analysis will write a blank
template over your work).

**watch.py:** Read → Edit each stub body (replace `pass  # e.g. ...` with real
assertions) → Edit line 1 to drop `# modulario:template` → leave the
`if __name__ == '__main__':` runner block untouched. Add helpers (e.g.
`_pyside_available()`) *around* the stubs, never in place of them.

**README.md:** Read → Edit each section → Edit line 1 to drop
`<!-- modulario:template -->`.

### watch.py stub contract

- `check_imports()` — key modules in this folder import cleanly
- `check_public_api()` — expected functions/classes exist and are callable
- `check_invariants()` — structural rules that must stay true

Exit 0 = PASS, non-zero = FAIL surfaced in hook output. Filled + unmarked scripts
run automatically on every file edit; no registration needed.

### watch.py runtime gotchas

`mod watch` runs in a minimal environment.

- A check that transitively imports heavy deps (PySide6, psycopg2, …) needs a
  `_<dep>_available()` guard that returns early when the dep is missing.
- Parent `__init__.py` files that eagerly import Qt/GUI/DB modules will break even
  `from app_modules.db import ...` under `mod watch`.
- Pure-Python files that can't be imported in isolation (e.g. `@dataclass` +
  `from __future__ import annotations`, which needs `sys.modules[__module__]`) →
  fall back to `open()` + text-grep for required symbols. Not `exec()`, not
  `importlib.util`.
- Fix `sys.path` relative depth to match actual folder nesting — the generated
  template sometimes assumes a different depth than where the file landed.

### README.md sections

Purpose (business/domain, not technical) · Owns (what changes when this folder
changes) · Does NOT own (boundaries + link to the real owner) · Key Files (one line
each) · Data & External Dependencies · How It Works (Flow) · Invariants &
Constraints (including "never do X") · Extension Points · Recent Changes (dated).

Update a folder's README whenever you change its behavior, API, key files, or
invariants — dated **Recent Changes** entry included — even with no `[DOC]` nag.

Keep READMEs tight. A folder README that runs past ~400 lines costs real tokens
every time it's read; compress prose, keep code/paths/commands exact.

## Import graph (`mod graph`)

```
mod graph <file>                       # imports (fan-out) + imported-by (fan-in)
mod graph <file> --target <dir>        # override the active mod directory
```

Run before moving, splitting, or renaming anything. Fan-in = every caller that
breaks if you change the public API. Fan-out = what a file pulls in before you split
it. Reads existing `state.json` — run `mod query <dir>` first if state is stale.

## Watch commands

```
mod watch run                # run all enabled watch.py
mod watch status             # status per folder
mod watch init <folder>      # create template manually
mod watch enable <folder>    # re-enable
mod watch disable <folder>   # temporarily skip
mod watch dismiss <folder>   # permanently dismiss (no source files)
```

## Doc commands

```
mod doc init <folder>        # create template manually (auto-creation also does this)
mod doc list                 # unfilled/filled status per folder
```

## Goals (`mod goals`)

```
mod goals on | off | status            # SessionStart injection of today's Delta Note goals
mod goals list                         # canonical state — IDs `1` (top) / `1.2` (subgoal)
mod goals check <id> / uncheck <id>
mod goals add <parent_id> "<text>"     # append open subgoal
mod goals describe [id]                # write .md into Delta-Note-Local/instructions/
```

`mod goals list` is the source of truth — re-run between issues rather than trusting
a cached SessionStart view.

**Capture:** when Seth describes a new bug/feature during a debugging run, add it
immediately under the best-matching top-level goal (usually `1`). Short and specific
— "fix header overlap on mobile", not a paragraph. Then `list` and confirm the
wording back so he can correct it.

**Check-off is gated on Seth's words.** Finishing the code, a green build, or your
own confidence is not confirmation. Ask "Should I check `<id>` off?" and move on
until he answers. If he later confirms without an id ("yeah that one's fixed"), match
it to the most recently discussed goal; ask if ambiguous.

Data source: local Delta Note Postgres (`daily_sections`, today's `goals` row +
`goals_meta` JSON). Writes hit the DB and show up in the app immediately.

## Status scale

GREEN / LIME / YELLOW / ORANGE / RED — the file's LOC + DEPS diagonal score.
Churn lines read `[churn] file.js: 4% this session · 3/20 sessions → MEDIUM`.

## Target selection

`mod ignore` mirrors entries into `.gitignore`, and **ignore config is global across
projects** — check what you're excluding before adding a pattern.
