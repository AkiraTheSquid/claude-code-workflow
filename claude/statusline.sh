#!/usr/bin/env bash
input=$(cat)

model=$(echo "$input" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('model',{}).get('display_name','?'))" 2>/dev/null)
cost=$(echo "$input"  | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"\${d.get('cost',{}).get('total_cost_usd',0):.3f}\")" 2>/dev/null)
pct=$(echo "$input"   | python3 -c "import json,sys; d=json.load(sys.stdin); print(int(d.get('context_window',{}).get('used_percentage',0) or 0))" 2>/dev/null)

last=""
if [[ -f "$HOME/.claude/token_last.txt" ]]; then
    last=$(cat "$HOME/.claude/token_last.txt" 2>/dev/null | tr -d '\n')
fi

echo "${model}  \$${cost} session  ${pct}% ctx"
echo "$input" | python3 "$HOME/.claude/scripts/cache_status.py" "$PPID" 2>/dev/null
if [[ -n "$last" ]]; then
    echo "last: ${last}"
fi
if [[ -f "$HOME/.claude/token_loc.txt" ]]; then
    cat "$HOME/.claude/token_loc.txt" 2>/dev/null
fi
