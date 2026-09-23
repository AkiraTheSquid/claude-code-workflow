#!/usr/bin/env bash

# Play a short completion sound when Claude finishes a turn.

set -u

SOUND_FILE="/usr/share/sounds/Yaru/stereo/complete.oga"

if [ ! -f "$SOUND_FILE" ]; then
  SOUND_FILE="/usr/share/sounds/freedesktop/stereo/complete.oga"
fi

if [ ! -f "$SOUND_FILE" ]; then
  exit 0
fi

if command -v pw-play >/dev/null 2>&1; then
  pw-play --volume 3.0 "$SOUND_FILE" >/dev/null 2>&1 &
elif command -v paplay >/dev/null 2>&1; then
  paplay "$SOUND_FILE" >/dev/null 2>&1 &
elif command -v aplay >/dev/null 2>&1; then
  aplay "$SOUND_FILE" >/dev/null 2>&1 &
fi

exit 0
