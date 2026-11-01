#!/usr/bin/env bash
set -euo pipefail
exec python3 "$HOME/Applications/Modulario/scripts/run_critic.py" claude "$@"
