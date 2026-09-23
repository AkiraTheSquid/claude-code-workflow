---
description: Show or change the auto-compact window (context token threshold where compression starts)
argument-hint: [auto|<tokens>|--at <tokens>]
allowed-tools: Bash
---

`python3 ~/.claude/scripts/compact_limit.py $ARGUMENTS`

Run the compact-limit script to read or write the `autoCompactWindow` setting in `~/.claude/settings.json`.

Usage:
- `compact-limit` — show current window + where auto-compact actually fires
- `compact-limit 150k` — set the window to 150,000 tokens
- `compact-limit --at 150k` — set the window so compaction fires AT 150,000 tokens (not the window size itself)
- `compact-limit auto` — remove the setting, revert to model default

Accepted formats: `150000`, `150k`, `150` (bare ≤1000 is thousands), `1m`.
Valid range: 100,000–1,000,000.

Note: `autoCompactWindow` is the *window size*, not the fire point. The actual trigger is `window − 33,000` (20k output reserve + 13k headroom). So a 150,000 window fires at ~117,000 tokens; to fire at a true 150,000, set the window to ~183,000 (use `--at 150k`).

Env override: `CLAUDE_CODE_AUTO_COMPACT_WINDOW` takes precedence over the file setting. Changes apply to new sessions (run it again with the same value or export the env var to apply now).
