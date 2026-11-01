#!/usr/bin/env python3
"""Wire the coordination hook GLOBALLY into ~/.claude/settings.json.

    install-hooks.py                       install / upgrade the global wiring
    install-hooks.py --uninstall           remove it
    install-hooks.py --remove-legacy <worktree>...
                                           strip the old per-repo wiring from a
                                           worktree's .claude/settings.local.json

Global since 2026-10-08. The per-repo wiring (one worktree's
settings.local.json) only fired for sessions launched INSIDE that worktree; most
sessions start in ~ and cd per command, so they ran unguarded. The hook now
works out each call's repo itself, so one global entry covers every repo.

Merges rather than overwrites, and re-running is safe: entries are matched by
command path and replaced, so an upgrade never leaves two copies firing. A
global settings.json is not inside any repo, so the old "never write
settings.json, it gets swept into a deploy commit" hazard does not apply here.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

HOOKS = Path(__file__).resolve().parent / "hooks"
HOOK = HOOKS / "collab_hook.py"
GLOBAL_SETTINGS = Path.home() / ".claude" / "settings.json"

TOOL_MATCHER = "Bash|Edit|Write|MultiEdit|NotebookEdit|mcp__delta-note__.*"
WIRING = [
    ("SessionStart", None),
    ("UserPromptSubmit", None),
    ("PreToolUse", TOOL_MATCHER),
    ("PostToolUse", TOOL_MATCHER),
    ("SessionEnd", None),
]


def command() -> str:
    return f"/usr/bin/python3 {HOOK}"


def ours(cmd: str) -> bool:
    return str(HOOKS) in (cmd or "")


def strip_ours(settings: dict) -> dict:
    """Drop every entry pointing at this install, leaving foreign hooks alone."""
    hooks = settings.get("hooks") or {}
    for event, groups in list(hooks.items()):
        kept_groups = []
        for group in groups:
            kept = [h for h in (group.get("hooks") or []) if not ours(h.get("command", ""))]
            if kept:
                kept_groups.append({**group, "hooks": kept})
        if kept_groups:
            hooks[event] = kept_groups
        else:
            hooks.pop(event)
    settings["hooks"] = hooks
    return settings


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        sys.exit(f"{path} is not valid JSON — fix it before installing.")


def save(path: Path, settings: dict) -> None:
    if path.exists():
        # Backups go to the state dir, never next to the file: a worktree's
        # .claude/ can be swept into a deploy commit by `git add -A`.
        backups = Path.home() / ".local" / "state" / "agent-collab" / "settings-backups"
        backups.mkdir(parents=True, exist_ok=True)
        tag = str(path.parent.parent.name) + "-" + path.name
        backup = backups / f"{tag}.{datetime.now():%Y%m%d-%H%M%S}"
        shutil.copy2(path, backup)
    tmp = path.with_suffix(".tmp-collab")
    tmp.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def install_global(remove: bool) -> None:
    settings = strip_ours(load(GLOBAL_SETTINGS))
    if not remove:
        hooks = settings.setdefault("hooks", {})
        for event, matcher in WIRING:
            group = {"hooks": [{"type": "command", "command": command(), "timeout": 10}]}
            if matcher:
                group["matcher"] = matcher
            hooks.setdefault(event, []).append(group)
    save(GLOBAL_SETTINGS, settings)
    print(f"{'removed from' if remove else 'installed into'} {GLOBAL_SETTINGS}")


def remove_legacy(worktree: Path) -> None:
    path = worktree / ".claude" / "settings.local.json"
    if not path.exists():
        print(f"no {path}")
        return
    settings = strip_ours(load(path))
    if not settings.get("hooks"):
        settings.pop("hooks", None)
    save(path, settings)
    print(f"legacy wiring removed from {path}")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        install_global(remove=False)
    elif args == ["--uninstall"]:
        install_global(remove=True)
    elif args[0] == "--remove-legacy" and len(args) > 1:
        for target in args[1:]:
            remove_legacy(Path(target).expanduser().resolve())
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
