#!/usr/bin/env bash
set -uo pipefail
H=$HOME/.local/share/agent-collab/hooks/collab_hook.py
T=$(mktemp -d); export AGENT_COLLAB_STATE=$T/state
R=$T/app; mkdir -p $R/js; git -C $R init -q; echo a > $R/js/a.js; echo b > $R/js/b.js; echo c > $R/c.txt
git -C $R add -A; git -C $R -c user.email=x@y -c user.name=t commit -qm init
PASS=0; FAIL=0
ok(){ if eval "$2"; then echo "ok   $1"; PASS=$((PASS+1)); else echo "FAIL $1"; echo "     out: ${OUT:0:600}"; FAIL=$((FAIL+1)); fi; }
ev(){ # event sid tool input_json
  printf '{"hook_event_name":"%s","session_id":"%s","cwd":"%s","tool_name":"%s","tool_input":%s,"tool_response":{}}' "$1" "$2" "${CWD:-$HOME}" "$3" "$4" | python3 $H; }
dec(){ python3 -c "import json,sys; d=sys.stdin.read().strip(); print(json.loads(d)['hookSpecificOutput'].get('permissionDecision','') if d else 'allow')"; }
cmd(){ python3 -c "import json,sys;print(json.dumps({'command':sys.argv[1]}))" "$1"; }

# A reads: allowed, no intent needed
OUT=$(ev PreToolUse A Bash "$(cmd "cd $R && git status && cat js/a.js")"); ok "reads never blocked" '[ "$(echo "$OUT"|dec)" = allow ]'
# A edits without intent: denied with intent instructions
OUT=$(ev PreToolUse A Edit "{\"file_path\":\"$R/js/a.js\"}"); ok "first change needs intent" 'echo "$OUT" | grep -q "intent"  && [ "$(echo "$OUT"|dec)" = deny ]'
# A bash write without intent: denied too
OUT=$(ev PreToolUse A Bash "$(cmd "cd $R && sed -i s/a/A/ js/a.js")"); ok "bash write needs intent" '[ "$(echo "$OUT"|dec)" = deny ]'
# A declares intent from ~ using --repo, session from CLAUDE_CODE_SESSION_ID
OUT=$(cd ~ && CLAUDE_CODE_SESSION_ID=A collab --repo $R intent "refactor a.js" --files js/a.js 2>&1); ok "intent via CLAUDE_CODE_SESSION_ID" 'echo "$OUT" | grep -q "joined"'
OUT=$(ev PreToolUse A Edit "{\"file_path\":\"$R/js/a.js\"}"); ok "after intent, edit allowed" '[ "$(echo "$OUT"|dec)" = allow ]'
ev PostToolUse A Edit "{\"file_path\":\"$R/js/a.js\"}" >/dev/null
# B arrives: B write to a.js -> intent first; B intent shows A + overlap
OUT=$(cd ~ && CLAUDE_CODE_SESSION_ID=B collab --repo $R intent "fix a.js bug" --files js/a.js js/b.js 2>&1); ok "B's intent shows A and HELD overlap" 'echo "$OUT" | grep -q "refactor a.js" && echo "$OUT" | grep -q "HELD"'
OUT=$(ev PreToolUse B Edit "{\"file_path\":\"$R/js/a.js\"}"); ok "B blocked from A's file" 'echo "$OUT" | grep -q "owned by" && [ "$(echo "$OUT"|dec)" = deny ]'
OUT=$(ev PreToolUse B Bash "$(cmd "echo x > $R/js/a.js")"); ok "B blocked from A's file via redirect" 'echo "$OUT" | grep -q "owned by"'
OUT=$(ev PreToolUse B Edit "{\"file_path\":\"$R/js/b.js\"}"); ok "B may edit its own file" '[ "$(echo "$OUT"|dec)" = allow ]'
# A now must ack B
OUT=$(ev PreToolUse A Edit "{\"file_path\":\"$R/js/a.js\"}"); ok "A must ack newcomer B" 'echo "$OUT" | grep -q "new agent joined" && echo "$OUT" | grep -q "fix a.js bug"'
OUT=$(ev PreToolUse A Bash "$(cmd "cd $R && ls")"); ok "A can still read while ack pending" '[ "$(echo "$OUT"|dec)" = allow ]'
OUT=$(ev UserPromptSubmit A "" "{}"); ok "A's prompt shows B joined" 'echo "$OUT" | grep -q "fix a.js bug"'
OUT=$(cd $R && CLAUDE_CODE_SESSION_ID=A collab ack "B wants a.js; I keep it, B sends requests" 2>&1); ok "ack logs" 'echo "$OUT" | grep -q "acknowledged"'
OUT=$(ev PreToolUse A Edit "{\"file_path\":\"$R/js/a.js\"}"); ok "after ack A unblocked" '[ "$(echo "$OUT"|dec)" = allow ]'
# B does not need to ack A (saw A at intent)
OUT=$(ev PreToolUse B Edit "{\"file_path\":\"$R/js/b.js\"}"); ok "newcomer need not ack earlier agents" '[ "$(echo "$OUT"|dec)" = allow ]'
# push: B logs, A sees it in PostToolUse
(cd ~ && CLAUDE_CODE_SESSION_ID=B collab log "b.js now exports helper") >/dev/null 2>&1
OUT=$(ev PostToolUse A Edit "{\"file_path\":\"$R/js/a.js\"}"); ok "A gets B's log pushed (B via last-repo fallback)" 'echo "$OUT" | grep -q "exports helper"'
OUT=$(ev PostToolUse A Edit "{\"file_path\":\"$R/js/a.js\"}"); ok "push shown once" '! echo "$OUT" | grep -q "exports helper"'
# risky git
OUT=$(ev PreToolUse A Bash "$(cmd "cd $R && git add -A")"); ok "git add -A refused with others active" 'echo "$OUT" | grep -q "add -A"'
OUT=$(ev PreToolUse A Bash "$(cmd "git -C $R stash")"); ok "git stash refused" 'echo "$OUT" | grep -q "stash"'
OUT=$(ev PreToolUse A Bash "$(cmd "cd $R && git checkout -b feat")"); ok "branch switch refused" 'echo "$OUT" | grep -q "switching branch"'
echo A2 > $R/js/a.js
OUT=$(ev PreToolUse A Bash "$(cmd "cd $R && git add js/a.js && git commit -m 'a refactor'")"); ok "explicit add+commit allowed" '[ "$(echo "$OUT"|dec)" = allow ]'
(cd $R && git add js/a.js && git -c user.email=x@y -c user.name=t commit -qm "a refactor")
ev PostToolUse A Bash "$(cmd "cd $R && git add js/a.js && git commit -m 'a refactor'")" >/dev/null
ev PreToolUse A Bash "$(cmd "cd $R && git commit -m 'noop'")" >/dev/null; ev PostToolUse A Bash "$(cmd "cd $R && git commit -m 'noop'")" >/dev/null
OUT=$(cd $R && collab history -n 9); ok "no-op commit not logged" '! echo "$OUT" | grep -q "committed .* init"' 
OUT=$(cd $R && collab history -n 5); ok "commit auto-logged" 'echo "$OUT" | grep -q "committed .* a refactor"'
# holds
(cd $R && CLAUDE_CODE_SESSION_ID=B collab hold "b.js half-migrated") >/dev/null
OUT=$(ev PreToolUse A Bash "$(cmd "cd $R && ./deploy_app.sh")"); ok "deploy refused under other's hold" 'echo "$OUT" | grep -q "deploy hold"'
(cd $R && CLAUDE_CODE_SESSION_ID=B collab hold --release) >/dev/null
OUT=$(ev PreToolUse A Bash "$(cmd "cd $R && ./deploy_app.sh")"); ok "deploy allowed after release" '[ "$(echo "$OUT"|dec)" = allow ]'
OUT=$(cd $R && collab history -n 3); ok "deploy auto-logged" 'echo "$OUT" | grep -q "deploying: ./deploy_app.sh"'
# collab command itself never gated
OUT=$(ev PreToolUse C Bash "$(cmd "cd $R && collab log hi")"); ok "collab commands never gated" '[ "$(echo "$OUT"|dec)" = allow ]'
# C solo intent requirement message mentions others
OUT=$(ev PreToolUse C Write "{\"file_path\":\"$R/c.txt\"}"); ok "C's intent prompt lists A and B" 'echo "$OUT" | grep -q "refactor a.js" && echo "$OUT" | grep -q "fix a.js bug"'
# session end releases everywhere
ev SessionEnd A "" "{}" >/dev/null
OUT=$(ev PreToolUse B Edit "{\"file_path\":\"$R/js/a.js\"}"); ok "A ending frees a.js for B" '[ "$(echo "$OUT"|dec)" = allow ]'
# stale rejoin
python3 - "$AGENT_COLLAB_STATE" <<'PY'
import json,sys,glob
from datetime import datetime,timedelta,timezone
for p in glob.glob(sys.argv[1]+"/*/sessions.json"):
    d=json.load(open(p))
    if "B" in d: d["B"]["last_seen"]=(datetime.now(timezone.utc)-timedelta(hours=3)).isoformat()
    json.dump(d,open(p,"w"))
PY
OUT=$(ev PreToolUse B Edit "{\"file_path\":\"$R/js/b.js\"}"); ok "stale session must re-announce" 'echo "$OUT" | grep -q "away long enough"'
# broken state fails open
for f in $AGENT_COLLAB_STATE/*/sessions.json; do echo garbage > $f; done
OUT=$(ev PreToolUse B Edit "{\"file_path\":\"$R/js/b.js\"}"); ok "garbage state: no crash (deny or allow, no traceback)" '! echo "$OUT" | grep -q Traceback'
# non-repo edit never gated
OUT=$(ev PreToolUse Z Write "{\"file_path\":\"$T/notrepo.txt\"}"); ok "non-repo file never gated" '[ "$(echo "$OUT"|dec)" = allow ]'
cat $AGENT_COLLAB_STATE/hook-errors.log 2>/dev/null | tail -3
echo; echo "$PASS passed, $FAIL failed"; rm -rf "$T"; [ "$FAIL" -eq 0 ]
