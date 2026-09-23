---
description: Set the context-token threshold at which you'll get a warning to wrap up before auto-compact
argument-hint: [auto|<tokens>]
allowed-tools: Bash
---

`python3 ~/.claude/scripts/compact_notify.py $ARGUMENTS`

This sets how many tokens *before* auto-compact triggers that you'll be warned to find a natural stopping point. It's earlier than the actual compaction, giving you a chance to wrap cleanly.

Usage:
- `compact-notify` — show current warn threshold + relationship to auto-compact
- `compact-notify 25000` — warn 25k tokens before compaction
- `compact-notify auto` — reset to default (20k before compaction)

Valid range: 5,000–50,000 tokens.

When you receive a warning at the notify threshold, you will:
1. Tell the user context is approaching a boundary
2. Suggest finding a natural stopping point or clear task boundary
3. Offer to create a new session if the current work isn't done
4. Never force-wrap; let the user decide

**Status:** The CLI (2.1.218) doesn't yet expose this setting, but the groundwork exists in the bundle. When support lands, this setting will activate automatically.
