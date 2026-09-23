#!/usr/bin/env bash
# Screenshot every variant × scene in mockups.config.js into ./shots/.
#
#   ./shots.sh                 1400x1000 desktop shots of everything
#   ./shots.sh --phone         420x860 as well
#   ./shots.sh --only a:fresh  one scene
#
# Uses headless Chrome directly, so it does not touch the debug Chrome the
# Playwright MCP may be attached to. Needs the server running (./serve.sh).

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT_FILE="$DIR/.serve.port"
[ -f "$PORT_FILE" ] || { echo "no server — run ./serve.sh --no-browser first"; exit 1; }
PORT="$(cat "$PORT_FILE")"

SIZES="1400,1000"
ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --phone) SIZES="$SIZES 420,860"; shift ;;
    --only) ONLY="$2"; shift 2 ;;
    *) echo "unknown arg: $1"; exit 1 ;;
  esac
done

CHROME=""
for bin in google-chrome google-chrome-stable chromium-browser chromium; do
  command -v "$bin" >/dev/null 2>&1 && { CHROME="$bin"; break; }
done
[ -n "$CHROME" ] || { echo "no chrome binary found"; exit 1; }

mkdir -p "$DIR/shots"

# The config is the list of what exists — never hand-maintain a second one.
PAIRS="$(cd "$DIR" && node -e '
  global.window = {};
  require("./mockups.config.js");
  for (const v of window.MOCKUPS.variants || [])
    for (const s of v.scenes || [])
      console.log(`${v.id}\t${v.file}\t${s.id}`);
')"

while IFS=$'\t' read -r vid vfile sid; do
  [ -z "$vid" ] && continue
  [ -n "$ONLY" ] && [ "$ONLY" != "$vid:$sid" ] && continue
  for size in $SIZES; do
    w="${size%%,*}"
    suffix=""
    [ "$w" -lt 700 ] && suffix="-phone"
    out="$DIR/shots/${vid}-${sid}${suffix}.png"
    "$CHROME" --headless=new --disable-gpu --hide-scrollbars \
      --window-size="$size" --virtual-time-budget=1500 \
      --user-data-dir="/tmp/mockup-shots-profile" \
      --screenshot="$out" "http://localhost:$PORT/$vfile?scene=$sid" >/dev/null 2>&1
    echo "  $out"
  done
done <<< "$PAIRS"

echo "done → $DIR/shots/"
