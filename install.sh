#!/usr/bin/env bash
# Install this Claude Code workflow onto a machine.
#
#   ./install.sh            install
#   ./install.sh --dry-run  print what would happen, change nothing
#
# Safe to re-run. Anything it would replace (files, dirs, symlinks in
# ~/.local/bin) is moved to ~/.claude/backup-workflow-<timestamp>/ first. An existing CLAUDE.md or
# settings.json is never overwritten: the repo version lands beside it as
# CLAUDE.workflow.md / settings.workflow.json for you to merge.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
BIN_DIR="$HOME/.local/bin"
COLLAB_DIR="$HOME/.local/share/agent-collab"
MODULARIO_DIR="$HOME/Applications/Modulario"
MODULARIO_URL="https://github.com/AkiraTheSquid/Modulario.git"
BACKUP="$CLAUDE_DIR/backup-workflow-$(date +%Y%m%d-%H%M%S)"
DRY=0
case "${1:-}" in
    "") ;;
    --dry-run) DRY=1 ;;
    *) echo "usage: $0 [--dry-run]"; exit 2 ;;
esac

run() {
    if (( DRY )); then echo "  would: $*"; else "$@"; fi
}

# Move dest (file, dir or symlink) into the backup folder.
backup() {
    local dest="$1" rel="${1#"$HOME"/}"
    run mkdir -p "$BACKUP/$(dirname "$rel")"
    run mv "$dest" "$BACKUP/$rel"
}

# Copy src -> dest, backing up dest first if it exists and differs.
place() {
    local src="$1" dest="$2"
    if [[ -e "$dest" && ! -L "$dest" ]] && diff -rq "$src" "$dest" >/dev/null 2>&1; then
        return 0
    fi
    if [[ -e "$dest" || -L "$dest" ]]; then
        backup "$dest"
    fi
    run mkdir -p "$(dirname "$dest")"
    run cp -a "$src" "$dest"
}

# Point link at target, backing up whatever else is already there.
link() {
    local target="$1" link="$2"
    if [[ -L "$link" && "$(readlink "$link")" == "$target" ]]; then
        return 0
    fi
    if [[ -e "$link" || -L "$link" ]]; then
        backup "$link"
    fi
    run ln -s "$target" "$link"
}

# Never clobber a file the user already customised.
place_or_beside() {
    local src="$1" dest="$2" beside="$3"
    if [[ -e "$dest" ]] && cmp -s "$src" "$dest"; then
        return 0
    elif [[ -e "$dest" ]]; then
        echo "  $dest exists -> writing $beside (merge it by hand)"
        place "$src" "$beside"
    else
        run cp "$src" "$dest"
    fi
}

echo "Installing Claude Code workflow from $REPO"
(( DRY )) && echo "(dry run: nothing will change)"

for cmd in git python3; do
    command -v "$cmd" >/dev/null || { echo "ERROR: $cmd not found"; exit 1; }
done
if [[ -e "$MODULARIO_DIR" && ! -d "$MODULARIO_DIR/.git" ]]; then
    echo "ERROR: $MODULARIO_DIR exists but is not a git clone of Modulario."
    echo "       Move it aside, then re-run. Nothing was changed."
    exit 1
fi

echo "-> ~/.claude (CLAUDE.md, settings, hooks, scripts, skills, commands, agents)"
run mkdir -p "$CLAUDE_DIR"/{hooks,scripts,skills,commands,agents}
place_or_beside "$REPO/claude/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.workflow.md"
place_or_beside "$REPO/claude/settings.json" "$CLAUDE_DIR/settings.json" "$CLAUDE_DIR/settings.workflow.json"
place "$REPO/claude/statusline.sh" "$CLAUDE_DIR/statusline.sh"
for f in "$REPO"/claude/hooks/* "$REPO"/claude/scripts/*; do
    place "$f" "$CLAUDE_DIR/$(basename "$(dirname "$f")")/$(basename "$f")"
done
for d in "$REPO"/claude/skills/*/; do
    place "${d%/}" "$CLAUDE_DIR/skills/$(basename "$d")"
done
for f in "$REPO"/claude/commands/* "$REPO"/claude/agents/*; do
    place "$f" "$CLAUDE_DIR/$(basename "$(dirname "$f")")/$(basename "$f")"
done
run chmod +x "$CLAUDE_DIR/statusline.sh" "$CLAUDE_DIR"/scripts/*.sh "$CLAUDE_DIR"/skills/critic/critic.sh

echo "-> agent-collab (~/.local/share/agent-collab) + chrome_dev"
place "$REPO/collab" "$COLLAB_DIR"
run mkdir -p "$BIN_DIR"
link "$COLLAB_DIR/collab.py" "$BIN_DIR/collab"
link "$COLLAB_DIR/agent-worktree" "$BIN_DIR/agent-worktree"
place "$REPO/bin/chrome_dev" "$BIN_DIR/chrome_dev"
run chmod +x "$COLLAB_DIR/collab.py" "$COLLAB_DIR/agent-worktree" "$BIN_DIR/chrome_dev"

echo "-> Modulario (~/Applications/Modulario)"
if [[ -d "$MODULARIO_DIR/.git" ]]; then
    echo "  already cloned; leaving it alone (git -C $MODULARIO_DIR pull to update)"
else
    run mkdir -p "$(dirname "$MODULARIO_DIR")"
    run git clone "$MODULARIO_URL" "$MODULARIO_DIR"
fi
link "$MODULARIO_DIR/bin/modulario.py" "$BIN_DIR/mod"

if [[ -d "$BACKUP" ]]; then
    echo "Replaced files were backed up to $BACKUP"
fi

cat <<EOF

Done. Next steps (see docs/SETUP.md for the full walkthrough):
  1. $MODULARIO_DIR/setup/install.sh   wires Modulario's hooks and picks a target project
  2. In each repo you share between sessions:
       python3 $COLLAB_DIR/install-hooks.py <repo>
  3. Plugins, inside Claude Code:
       /plugin marketplace add JuliusBrussee/caveman
       /plugin marketplace add typesafe-ai/skills
  4. graphify:  uv tool install graphifyy && graphify install
  5. Codex for /critic:  npm install -g @openai/codex && codex login
  6. Make sure $BIN_DIR is on your PATH, then start a NEW Claude session
     (hooks load at session start).
EOF
