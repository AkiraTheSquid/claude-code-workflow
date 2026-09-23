#!/usr/bin/env bash
# Serve this mockup folder and show it in the real Chrome window.
#
#   ./serve.sh              start (or reuse) the server, open the index
#   ./serve.sh --no-browser start the server only, print the URL
#   ./serve.sh --port 8910  pin the port
#   ./serve.sh --stop       stop only THIS folder's server
#
# Two rules this script exists to keep:
#   1. It never touches another session's server — it picks a free port and
#      records its own pid, so a mockup server already running elsewhere
#      (someone else's port 8899) keeps running.
#   2. It never restarts Chrome when a debug Chrome is already up. Killing
#      that instance leaves an attached Playwright MCP holding a dead handle
#      for the rest of the session, so we open a TAB in it instead.

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$DIR/.serve.pid"
PORT_FILE="$DIR/.serve.port"
LOG_FILE="$DIR/.serve.log"
CHROME_PROFILE="${CHROME_DEV_PROFILE:-/tmp/chrome_dev_profile}"
DEBUG_PORT="${CHROME_DEV_PORT:-9222}"

OPEN_BROWSER=1
WANT_PORT=""
PAGE="index.html"

while [ $# -gt 0 ]; do
  case "$1" in
    --no-browser) OPEN_BROWSER=0; shift ;;
    --port) WANT_PORT="$2"; shift 2 ;;
    --page) PAGE="$2"; shift 2 ;;
    --stop)
      if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        kill "$(cat "$PID_FILE")" && echo "stopped server pid $(cat "$PID_FILE")"
      else
        echo "no server of ours is running"
      fi
      rm -f "$PID_FILE" "$PORT_FILE"
      exit 0 ;;
    -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown arg: $1"; exit 1 ;;
  esac
done

port_free() { ! (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

# Reuse our own server if it is still up.
PORT=""
if [ -f "$PID_FILE" ] && [ -f "$PORT_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  PORT="$(cat "$PORT_FILE")"
  echo "reusing server pid $(cat "$PID_FILE") on port $PORT"
else
  rm -f "$PID_FILE" "$PORT_FILE"
  if [ -n "$WANT_PORT" ]; then
    port_free "$WANT_PORT" || { echo "port $WANT_PORT is taken"; exit 1; }
    PORT="$WANT_PORT"
  else
    for p in $(seq 8900 8960); do
      if port_free "$p"; then PORT="$p"; break; fi
    done
    [ -n "$PORT" ] || { echo "no free port in 8900-8960"; exit 1; }
  fi

  cd "$DIR"
  nohup python3 -m http.server "$PORT" --bind 127.0.0.1 >"$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  echo "$PORT" > "$PORT_FILE"
  for _ in $(seq 1 40); do port_free "$PORT" || break; sleep 0.1; done
  echo "serving $DIR on port $PORT (pid $(cat "$PID_FILE"))"
fi

URL="http://localhost:$PORT/$PAGE"
echo "  $URL"

if [ "$OPEN_BROWSER" = "1" ]; then
  if curl -fsS --max-time 1 "http://127.0.0.1:$DEBUG_PORT/json/version" >/dev/null 2>&1; then
    # Debug Chrome is already up — add a tab, do NOT relaunch it.
    for bin in google-chrome google-chrome-stable chromium-browser chromium; do
      if command -v "$bin" >/dev/null 2>&1; then
        "$bin" --user-data-dir="$CHROME_PROFILE" "$URL" >/dev/null 2>&1 &
        echo "  opened a tab in the running debug Chrome (port $DEBUG_PORT)"
        break
      fi
    done
  elif command -v chrome_dev >/dev/null 2>&1; then
    chrome_dev "$URL"
  else
    echo "  chrome_dev not found — open the URL yourself"
  fi
fi
