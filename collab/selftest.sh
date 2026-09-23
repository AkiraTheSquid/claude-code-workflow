#!/usr/bin/env bash
# Two simulated sessions in one repo, driven through the REAL hooks.
#
# Run after changing anything under this directory. It exercises the paths that
# only appear when two agents overlap -- which is exactly when nobody is in a
# position to debug the coordination layer.
#
#     ~/.local/share/agent-collab/selftest.sh
#
# Needs two worktrees of ONE repo and a tracked file in it. Point it at yours:
#
#     COLLAB_TEST_A=~/code/app COLLAB_TEST_B=~/code/app-wt \
#     COLLAB_TEST_FILE=src/index.html ./selftest.sh
set -uo pipefail

H=$HOME/.local/share/agent-collab/hooks
COLAB=${COLLAB_TEST_A:-$HOME/Applications/Delta-Drills-Colab}
LOCAL=${COLLAB_TEST_B:-$HOME/Applications/Delta-Drills-Local}
FILE=${COLLAB_TEST_FILE:-Local_Deployed_Shared/index.html}
PASS=0; FAIL=0

ok() { if [ "$2" = "1" ]; then echo "ok   $1"; PASS=$((PASS+1)); else echo "FAIL $1 -- $3"; FAIL=$((FAIL+1)); fi; }

hook() { # hook <script> <session> <cwd> [tool_input_json]
  local script="$1" sid="$2" cwd="$3" ti="${4:-{\}}"
  printf '{"session_id":"%s","cwd":"%s","tool_name":"Edit","tool_input":%s}' "$sid" "$cwd" "$ti" \
    | /usr/bin/python3 "$H/$script"
}

# A throwaway state dir: the selftest must never touch the claims real
# sessions are relying on.
export AGENT_COLLAB_STATE="$(mktemp -d)/collab-state"
rm -rf "$AGENT_COLLAB_STATE"

# --- A starts in the Colab worktree, B starts in Local (same repo, 2 worktrees)
CLAUDE_SESSION_ID=sess-A collab whoami --task "colab edition auth" >/dev/null 2>&1
out_a=$(cd "$COLAB" && hook session_start.py sess-A "$COLAB")
ok "solo session gets no banner" "$([ -z "$out_a" ] && echo 1 || echo 0)" "$out_a"

out_b=$(cd "$LOCAL" && hook session_start.py sess-B "$LOCAL")
ok "second session IS told about the first" \
   "$(echo "$out_b" | grep -q 'Another agent is working' && echo 1 || echo 0)" "$out_b"

# --- A edits the file: allowed, then auto-claimed
deny_a=$(cd "$COLAB" && hook pre_edit_guard.py sess-A "$COLAB" "{\"file_path\":\"$COLAB/$FILE\"}")
ok "A may edit an unclaimed file" "$([ -z "$deny_a" ] && echo 1 || echo 0)" "$deny_a"
(cd "$COLAB" && hook post_edit_claim.py sess-A "$COLAB" "{\"file_path\":\"$COLAB/$FILE\"}") >/dev/null
held=$(cd "$COLAB" && CLAUDE_SESSION_ID=sess-A collab status --json | python3 -c "import json,sys; print(list(json.load(sys.stdin)['claims']))")
ok "editing auto-claims the file" "$(echo "$held" | grep -q "$FILE" && echo 1 || echo 0)" "$held"

# --- B, in a DIFFERENT worktree, is blocked on the same repo-relative path
deny_b=$(cd "$LOCAL" && hook pre_edit_guard.py sess-B "$LOCAL" "{\"file_path\":\"$LOCAL/$FILE\"}")
decision=$(echo "$deny_b" | python3 -c "import json,sys; print(json.load(sys.stdin)['hookSpecificOutput']['permissionDecision'])" 2>/dev/null)
ok "B is DENIED across worktrees" "$([ "$decision" = "deny" ] && echo 1 || echo 0)" "$deny_b"
ok "the denial names the owner and the way out" \
   "$(echo "$deny_b" | grep -q 'collab request' && echo 1 || echo 0)" "$deny_b"

# --- A is not blocked by its own claim
again=$(cd "$COLAB" && hook pre_edit_guard.py sess-A "$COLAB" "{\"file_path\":\"$COLAB/$FILE\"}")
ok "A is not blocked by its own claim" "$([ -z "$again" ] && echo 1 || echo 0)" "$again"

# --- an unrelated file stays free
free=$(cd "$LOCAL" && hook pre_edit_guard.py sess-B "$LOCAL" '{"file_path":"'"$LOCAL"'/vercel.json"}')
ok "unclaimed files stay editable" "$([ -z "$free" ] && echo 1 || echo 0)" "$free"

# --- request / inbox / resolve
(cd "$LOCAL" && CLAUDE_SESSION_ID=sess-B collab request "$FILE" "need the colab banner hidden") >/dev/null
inbox=$(cd "$COLAB" && CLAUDE_SESSION_ID=sess-A collab inbox)
ok "the owner sees the request" "$(echo "$inbox" | grep -q 'colab banner' && echo 1 || echo 0)" "$inbox"
rid=$(echo "$inbox" | head -1 | awk '{print $1}')
(cd "$COLAB" && CLAUDE_SESSION_ID=sess-A collab resolve "$rid" "done") >/dev/null
inbox2=$(cd "$COLAB" && CLAUDE_SESSION_ID=sess-A collab inbox)
ok "resolved requests leave the inbox" "$(echo "$inbox2" | grep -q 'No open requests' && echo 1 || echo 0)" "$inbox2"

# --- shared log
(cd "$COLAB" && CLAUDE_SESSION_ID=sess-A collab log "hid the banner behind a query flag") >/dev/null
hist=$(cd "$LOCAL" && collab history -n 5)
ok "the log is shared across worktrees" "$(echo "$hist" | grep -q 'query flag' && echo 1 || echo 0)" "$hist"

# --- A ends: claims are handed back and B is unblocked
(cd "$COLAB" && hook session_end.py sess-A "$COLAB") >/dev/null
after=$(cd "$LOCAL" && hook pre_edit_guard.py sess-B "$LOCAL" "{\"file_path\":\"$LOCAL/$FILE\"}")
ok "SessionEnd releases the claim" "$([ -z "$after" ] && echo 1 || echo 0)" "$after"

# --- a stale session must not block anyone
CLAUDE_SESSION_ID=sess-C bash -c "cd '$COLAB' && collab claim '$FILE' --why 'stale test'" >/dev/null 2>&1
python3 - "$AGENT_COLLAB_STATE" <<'PY'
import json, sys, glob
from datetime import datetime, timedelta, timezone
for path in glob.glob(sys.argv[1] + "/*/sessions.json"):
    data = json.load(open(path))
    for sid, s in data.items():
        if sid == "sess-C":
            s["last_seen"] = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
    json.dump(data, open(path, "w"), indent=2)
PY
stale=$(cd "$LOCAL" && hook pre_edit_guard.py sess-B "$LOCAL" "{\"file_path\":\"$LOCAL/$FILE\"}")
ok "a stale session's claim does not block" "$([ -z "$stale" ] && echo 1 || echo 0)" "$stale"

# --- broken state fails OPEN
mkdir -p "$AGENT_COLLAB_STATE/broken" && echo "not json" > "$AGENT_COLLAB_STATE"/*/claims.json
broken=$(cd "$LOCAL" && hook pre_edit_guard.py sess-B "$LOCAL" "{\"file_path\":\"$LOCAL/$FILE\"}")
ok "unreadable state fails OPEN, not closed" "$([ -z "$broken" ] && echo 1 || echo 0)" "$broken"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
