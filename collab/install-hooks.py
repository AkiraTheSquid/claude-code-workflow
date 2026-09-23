#!/usr/bin/env python3
"""Wire the coordination hooks into one worktree's .claude/settings.json.

Merges rather than overwrites: these worktrees already carry graphify guards and
the Vercel plugin, and blowing those away to install coordination would be a
poor trade. Re-running is safe — entries are matched by command path and
replaced in place, so an upgrade does not leave two copies firing.

    install-hooks.py $HOME/Applications/Delta-Drills-Colab
    install-hooks.py --remove <worktree>

Writes .claude/settings.local.json, which Claude Code merges over
settings.json. Deliberate: settings.json is tracked on some branches, and this
wiring contains absolute machine paths that must not be committed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent / "hooks"

WIRING = [
    ("SessionStart", None, HOOKS / "session_start.py"),
    ("PreToolUse", "Edit|Write|NotebookEdit", HOOKS / "pre_edit_guard.py"),
    ("PostToolUse", "Edit|Write|NotebookEdit", HOOKS / "post_edit_claim.py"),
    ("SessionEnd", None, HOOKS / "session_end.py"),
]


def command_for(script: Path) -> str:
    return f"/usr/bin/python3 {script}"


def strip_ours(settings: dict) -> dict:
    """Drop every entry pointing at this install, leaving foreign hooks alone."""
    ours = {command_for(script) for _, _, script in WIRING}
    hooks = settings.get("hooks") or {}
    for event, groups in list(hooks.items()):
        kept_groups = []
        for group in groups:
            kept = [h for h in (group.get("hooks") or []) if h.get("command") not in ours]
            if kept:
                kept_groups.append({**group, "hooks": kept})
        if kept_groups:
            hooks[event] = kept_groups
        else:
            hooks.pop(event)
    settings["hooks"] = hooks
    return settings


def install(worktree: Path, remove: bool = False) -> None:
    # settings.LOCAL.json, never settings.json. In Delta Drills the latter is
    # TRACKED on the deploy-colab branch, so writing machine-absolute hook paths
    # there would be committed and pushed by the Colab deploy's `git add -A`.
    # The two files merge, so graphify's hooks in settings.json keep working.
    settings_path = worktree / ".claude" / "settings.local.json"
    settings = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            sys.exit(f"{settings_path} is not valid JSON — fix it before installing.")

    settings = strip_ours(settings)

    if not remove:
        hooks = settings.setdefault("hooks", {})
        for event, matcher, script in WIRING:
            entry = {"type": "command", "command": command_for(script)}
            group = {"hooks": [entry]}
            if matcher:
                group["matcher"] = matcher
            # Fold into an existing group with the same matcher so one event
            # does not accumulate a group per install.
            existing = next(
                (g for g in hooks.get(event, []) if g.get("matcher") == matcher), None)
            if existing:
                existing.setdefault("hooks", []).append(entry)
            else:
                hooks.setdefault(event, []).append(group)

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    print(f"{'removed from' if remove else 'installed into'} {settings_path}")


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--remove"]
    remove = "--remove" in sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    for target in args:
        worktree = Path(target).expanduser().resolve()
        if not worktree.is_dir():
            sys.exit(f"{worktree} is not a directory")
        install(worktree, remove)


if __name__ == "__main__":
    main()
