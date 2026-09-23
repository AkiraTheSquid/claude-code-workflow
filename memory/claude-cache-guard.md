---
name: claude-cache-guard
description: Prompt-cache guard built 2026-09-16 — blocks cold+big prompts, statusline cache line, pre-expiry nudge timer, Telegram alerts; where the pieces live and their gotchas
metadata:
  type: project
---

The prompt cache is server-side KV state: cannot be copied, pinned, or extended past the 1 h TTL. What we built instead (2026-09-16, after the token audit [[token-audit-2026-09-16]]):

- `~/.claude/scripts/cache_guard.py` — UserPromptSubmit hook. Cold (>60 min idle, or past the statusline's `expires_at`) AND rebuild ≥ MIN_TOKENS → exit 2 (Claude Code ERASES the typed prompt), so the prompt is copied to the clipboard + `~/.local/state/claude/cache-guard/<sid>.blocked-prompt.txt` (0600). Resend within ACK_MIN → passes, Claude gets an additionalContext note. Slash commands always pass; `prompt_type` may be absent → derived from a leading `/`.
- `~/.claude/scripts/cache_status.py` — called by `statusline.sh`. Prints `cache: warm Nm left · hit % · misses (cause) · cold-cost`, writes the heartbeat `<sid>.heartbeat.json` (real claude pid via ancestor walk — `$PPID` is a throwaway `bash -c`, NOT claude), and fires the EXPIRED alert once: Claude Code re-renders the statusline when a warm cache hits `expires_at`, so the statusline IS the expiry event.
- `~/.claude/scripts/cache_watch.py` + `claude-cache-watch.timer` (5 min) — nudge "compact now while warm" NUDGE_MIN before expiry for live sessions (pid alive); with AUTOCOMPACT=1 and a tmux pane it types `/compact` in. Sessions are NOT in tmux today (bash under inshellisense) → nudge only.
- `~/.claude/scripts/cache_notify.py` — notify-send critical + sound + Telegram via `dn_alert_relay`'s config (imports it from `~/.local/bin`); log in the state dir.
- Config `~/.config/claude-cache-guard.env`: MIN_TOKENS=60000, NUDGE_MIN=10, AUTOCOMPACT=0, TELEGRAM=1, ACK_MIN=5.

**Why:** the 22 h session paid a 237k-token rewrite after one 70 min break; a warning after sending is worthless, so the hook blocks before.
**How to apply:** 🔴 any hook that spawns `xclip`/a daemon must give it DEVNULL stdout or Claude Code waits on the pipe until hook timeout. Telegram path never live-tested (only `build_targets` checked). Test with `~/.local/state/.../` fake transcripts, TELEGRAM=0.
