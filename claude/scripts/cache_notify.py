#!/usr/bin/env python3
"""Deliver one prompt-cache alert: desktop (critical) + sound + Telegram + log.

Usage: cache_notify.py <kind> <session_id> <tokens> [detail]
kind: expired | nudge | autocompacted | blocked
Telegram goes through the Delta Note relay's config (destinations only, tokens
stay in their own files) so there is one phone channel to maintain.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cache_common import fmt_tokens, load_config, state_path, utc_now  # noqa: E402

TEXT = {
    "expired": ("🧊 Claude cache EXPIRED", "Session {sid}: {tok} tokens now cold. Next prompt = full rewrite. Use /clear or /refresh; /compact only if the summary is worth {tok} tokens."),
    "nudge": ("⏳ Claude cache expires in {detail} min", "Session {sid}: {tok} tokens still warm. Run /compact NOW (cheap while warm) or /refresh before it lapses."),
    "autocompacted": ("🧹 Claude auto-compacted", "Session {sid}: sent /compact into tmux at {tok} tokens, {detail} min before expiry."),
    "blocked": ("🛑 Cold prompt blocked", "Session {sid}: {tok} tokens cold; prompt saved to clipboard. Resend to pay, or /clear · /refresh."),
}


def desktop(summary: str, body: str) -> None:
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-u", "critical", "-a", "claude-cache", summary, body],
                       env={"DISPLAY": ":0", "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus", "PATH": "/usr/bin:/bin"},
                       timeout=10, check=False)
    sound = "/usr/share/sounds/freedesktop/stereo/dialog-warning.oga"
    if shutil.which("pw-play") and Path(sound).exists():
        subprocess.Popen(["pw-play", "--volume", "2.0", sound], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def telegram(text: str) -> str:
    try:
        sys.path.insert(0, str(Path.home() / ".local" / "bin"))
        import dn_alert_relay as relay  # type: ignore
        cfg = relay.load_config()
        targets, _problems = relay.build_targets(cfg)
        grades = []
        for t in targets:
            if not t["id"].startswith("telegram:"):
                continue
            grade, detail = t["send"](cfg, text)
            grades.append(f"{t['id']}={'ok' if grade == relay.FULL else detail}")
        return ", ".join(grades) or "no telegram target"
    except Exception as exc:  # noqa: BLE001 - alerting must never raise
        return f"telegram failed: {exc}"


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__, file=sys.stderr)
        return 2
    kind, sid, tok = sys.argv[1], sys.argv[2][:8], int(sys.argv[3])
    detail = sys.argv[4] if len(sys.argv) > 4 else ""
    summary, body = TEXT.get(kind, ("Claude cache: " + kind, "{sid} {tok} {detail}"))
    body = body.format(sid=sid, tok=fmt_tokens(tok), detail=detail)
    summary = summary.format(sid=sid, tok=fmt_tokens(tok), detail=detail)
    cfg = load_config()
    desktop(summary, body)
    tg = telegram(f"{summary}\n{body}") if cfg["TELEGRAM"] else "telegram off"
    with state_path("cache-guard.log").open("a") as fh:
        fh.write(f"{utc_now()} {kind} sid={sid} tokens={tok} {detail} | {tg}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
