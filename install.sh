#!/usr/bin/env bash
# Install this Claude Code workflow onto a machine.
#
#   ./install.sh            install
#   ./install.sh --dry-run  print what would happen, change nothing
#
# Safe to re-run. Anything it would replace is moved to
# ~/.claude/backup-workflow-<timestamp>/ first. An existing CLAUDE.md or
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
        run mkdir -p "$(dirname "$dest")"
        run cp "$src" "$dest"
    fi
}

echo "Installing Claude Code workflow from $REPO"
(( DRY )) && echo "(dry run: nothing will change)"

for cmd in git python3; do
    command -v "$cmd" >/dev/null || { echo "ERROR: $cmd not found"; exit 1; }
done
for cmd in rg fzf jq codex gh; do
    command -v "$cmd" >/dev/null || echo "  note: $cmd not found (see README: what needs it)"
done
if [[ -e "$MODULARIO_DIR" && ! -d "$MODULARIO_DIR/.git" ]]; then
    echo "ERROR: $MODULARIO_DIR exists but is not a git clone of Modulario."
    echo "       Move it aside, then re-run. Nothing was changed."
    exit 1
fi

# settings.json uses $HOME placeholders; write a copy with the real path.
SETTINGS_SRC="$(mktemp)"
trap 'rm -f "$SETTINGS_SRC"' EXIT
python3 - "$REPO/claude/settings.json" "$SETTINGS_SRC" <<'PY'
import json, os, sys

def expand(v):
    if isinstance(v, str):
        return v.replace("$HOME", os.environ["HOME"])
    if isinstance(v, list):
        return [expand(x) for x in v]
    if isinstance(v, dict):
        return {k: expand(x) for k, x in v.items()}
    return v

with open(sys.argv[1]) as f:
    data = expand(json.load(f))
with open(sys.argv[2], "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY

echo "-> ~/.claude (CLAUDE.md, settings, statusline, @ autocomplete, scripts, skill, command)"
run mkdir -p "$CLAUDE_DIR"/{scripts,skills,commands}
place_or_beside "$REPO/claude/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.workflow.md"
place_or_beside "$SETTINGS_SRC" "$CLAUDE_DIR/settings.json" "$CLAUDE_DIR/settings.workflow.json"
place "$REPO/claude/statusline.sh" "$CLAUDE_DIR/statusline.sh"
place "$REPO/claude/file-suggestion.sh" "$CLAUDE_DIR/file-suggestion.sh"
[[ -e "$CLAUDE_DIR/file-suggestion-aliases" ]] || \
    run cp "$REPO/claude/file-suggestion-aliases.example" "$CLAUDE_DIR/file-suggestion-aliases"
for f in "$REPO"/claude/scripts/* "$REPO"/claude/commands/*; do
    place "$f" "$CLAUDE_DIR/$(basename "$(dirname "$f")")/$(basename "$f")"
done
place "$REPO/claude/skills/critic" "$CLAUDE_DIR/skills/critic"
[[ -e "$HOME/.config/claude-cache-guard.env" ]] || \
    place "$REPO/claude/claude-cache-guard.env.example" "$HOME/.config/claude-cache-guard.env"
run chmod +x "$CLAUDE_DIR/statusline.sh" "$CLAUDE_DIR/file-suggestion.sh" \
    "$CLAUDE_DIR"/scripts/*.sh "$CLAUDE_DIR"/skills/critic/critic.sh

echo "-> agent-collab (~/.local/share/agent-collab), wired globally"
place "$REPO/collab" "$COLLAB_DIR"
run mkdir -p "$BIN_DIR"
link "$COLLAB_DIR/collab.py" "$BIN_DIR/collab"
link "$COLLAB_DIR/agent-worktree" "$BIN_DIR/agent-worktree"
run chmod +x "$COLLAB_DIR/collab.py" "$COLLAB_DIR/agent-worktree"
run python3 "$COLLAB_DIR/install-hooks.py"

echo "-> Modulario (~/Applications/Modulario), which hosts the /critic runner"
if [[ -d "$MODULARIO_DIR/.git" ]]; then
    echo "  already cloned; leaving it alone (git -C $MODULARIO_DIR pull to update)"
else
    run mkdir -p "$(dirname "$MODULARIO_DIR")"
    run git clone "$MODULARIO_URL" "$MODULARIO_DIR"
fi

if [[ -d "$BACKUP" ]]; then
    echo "Replaced files were backed up to $BACKUP"
fi

cat <<EOF

Done. Remaining steps (README has the why for each):
  1. CLIs, if missing:  gh auth login · npm i -g vercel && vercel login ·
     supabase login   (plus any MCP connectors for the sites you use)
  2. caveman plugin, inside Claude Code:
       /plugin marketplace add JuliusBrussee/caveman
       /plugin install caveman@caveman
  3. Codex for /critic:  npm install -g @openai/codex && codex login
  4. graphify:  uv tool install graphifyy && graphify install
     then in each big repo:  /graphify .
  5. Edit ~/.claude/file-suggestion-aliases with your own project folders.
  6. Make sure $BIN_DIR is on your PATH, then start a NEW Claude session
     (hooks load at session start).
EOF
