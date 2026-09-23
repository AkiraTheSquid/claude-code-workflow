#!/usr/bin/env bash
# Global graphify always-on: runs at every Claude Code SessionStart.
# Tells the AI to use the project's graphify knowledge graph for codebase
# questions, and to offer building one when a code project has no graph yet.
# Kept in ~/.claude/scripts so it applies to EVERY project, new or old.

# SessionStart hooks receive a JSON payload on stdin containing "cwd".
PAYLOAD="$(cat 2>/dev/null || true)"
CWD="$(printf '%s' "$PAYLOAD" | python3 -c 'import sys,json
try:
    d=json.load(sys.stdin); print(d.get("cwd") or d.get("workspace",{}).get("current_dir") or "")
except Exception:
    print("")' 2>/dev/null)"
[ -z "$CWD" ] && CWD="$PWD"

GRAPH="$CWD/graphify-out/graph.json"

if [ -f "$GRAPH" ]; then
  NODES="$(python3 -c "import json;print(len(json.load(open('$GRAPH'))['nodes']))" 2>/dev/null || echo '?')"
  cat <<EOF
[graphify] A knowledge graph exists at graphify-out/graph.json (${NODES} nodes). DO NOT start exploring or querying the graph yet. Wait until the user has told you which project directory you are working on. Only once that working project directory is given should you begin graph exploration — then use the graph as the FIRST move for any question about that codebase's architecture, file/function relationships, data flow, or "where/what/how does X work", instead of grep-crawling blind. Commands: \`graphify query "<question>"\` (BFS context), \`graphify path "A" "B"\` (shortest link), \`graphify explain "X"\` (node summary). Cite source_location from results. A post-commit hook auto-rebuilds the graph on commit; for uncommitted/doc changes run \`graphify --update\`. Honesty: answer only from what the graph contains.
EOF
else
  # Only nag at a real project ROOT (a build/manifest marker present), never in $HOME.
  HAS_MARKER=""
  for m in package.json pyproject.toml requirements.txt go.mod Cargo.toml setup.py manifest.json; do
    [ -e "$CWD/$m" ] && HAS_MARKER=1 && break
  done
  if [ "$CWD" != "$HOME" ] && [ -n "$HAS_MARKER" ]; then
    cat <<'EOF'
[graphify] This looks like a code project with no knowledge graph yet (no graphify-out/graph.json). graphify is installed. For any nontrivial question about this codebase's structure, proactively offer to build one first: `/graphify .` — code-only builds are free (AST, no LLM, no tokens) and fast, skip .venv/node_modules automatically, and make every later architecture question a fast graph query. Once built, use `graphify query` as the default tool for codebase-structure questions.
EOF
  fi
fi
