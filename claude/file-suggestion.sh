#!/usr/bin/env bash
# Claude Code `@` file autocomplete (settings.json -> fileSuggestion).
# stdin: {"query": "..."}  stdout: up to 15 newline-separated paths.
#
# Candidates (files, plus folders with a trailing /) come from three tiers:
#   1. session project (relative paths)
#   2. ~/Applications (absolute paths)
#   3. rest of $HOME (absolute paths)
# Tiers 2-3 come from cached lists refreshed in background.
#
# Ranking: fzf picks each tier's best fuzzy matches, then results are sorted by
# how well the last word typed matches the item's OWN name:
#   exact name > name starts with it > name contains it > fuzzy only.
# Within the name-match classes, shallower paths win (so `delta-note` puts
# ~/Applications/Delta-Note/ above files deep inside it); fuzzy-only results
# keep tier order, then fzf order.

set -u
query=$(jq -r '.query // ""' 2>/dev/null)
project=${CLAUDE_PROJECT_DIR:-$PWD}
cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/claude-file-suggest"
apps_root="$HOME/Applications"
apps_list="$cache_dir/apps.txt"   # tier 2
rest_list="$cache_dir/rest.txt"   # tier 3
max_age=600   # seconds before the home list is rebuilt
per_tier=40   # fzf matches taken from each tier before re-ranking

# Folders never worth suggesting (matched anywhere in the path).
excludes=(-g '!**/node_modules/**' -g '!**/__pycache__/**' -g '!**/venv/**'
          -g '!**/site-packages/**' -g '!**/*[Bb]ackup*/**' -g '!**/snap/**'
          -g '!**/.venv/**' -g '!**/.git/**')

list_files() {  # $1 = root, rest = extra rg flags; prints paths relative to root
    local root=$1; shift
    (cd "$root" 2>/dev/null && rg --files --follow "$@" "${excludes[@]}" 2>/dev/null)
}

with_dirs() {  # stdin = file paths; also emit each ancestor folder (with /) once, stopping at $1
    awk -v stop="$1" '{ print; p = $0
        while (sub(/\/[^\/]*$/, "", p) && p != stop && p != "" && !(p in seen)) {
            seen[p] = 1; print p "/" } }'
}

rank() {  # rank stdin against the query, best first
    fzf --filter "$query" --scheme=path 2>/dev/null
}

refresh_home_list() {
    mkdir -p "$cache_dir"
    # flock -n: if a rebuild is already running, don't start another
    ( flock -n 9 || exit 0
      : > "$apps_list.tmp"; : > "$rest_list.tmp"   # both exist even if a tier is empty
      { list_files "$HOME" | sed "s|^|$HOME/|"
        # Hidden dirs are skipped above; add back the useful parts of ~/.claude.
        (cd "$HOME/.claude" && rg --files --hidden -g '/*' -g '/skills/**' \
            -g '/scripts/**' -g '/hooks/**' -g '/agents/**' -g '/commands/**' \
            -g '/projects/*/memory/**' -g '!**/node_modules/**' 2>/dev/null) \
          | sed "s|^|$HOME/.claude/|"
      } | with_dirs "$HOME" \
        | awk -v p="$apps_root/" -v a="$apps_list.tmp" -v r="$rest_list.tmp" \
            'index($0, p) == 1 && $0 != p { print > a; next } { print > r }' \
        && mv "$apps_list.tmp" "$apps_list" && mv "$rest_list.tmp" "$rest_list"
    ) 9>"$cache_dir/lock"
}

# Missing or stale: rebuild in background so a keystroke never waits on it
# (first-ever query just shows project files).
if [[ ! -e $apps_list || ! -s $rest_list ]] || (( $(date +%s) - $(stat -c %Y "$rest_list") > max_age )); then
    refresh_home_list >/dev/null 2>&1 &
    disown
fi

# Shortcuts (file-suggestion-aliases): `name` -> folder.
aliases_file="$HOME/.claude/file-suggestion-aliases"
alias_lookup() {  # $1 = mode (exact|prefix), $2 = word; prints matching folders with trailing /
    [[ -r $aliases_file ]] || return 0
    awk -v mode="$1" -v w="$(tr '[:upper:]' '[:lower:]' <<<"$2")" -v home="$HOME" '
        /^[ \t]*(#|$)/ || NF < 2 { next }   # skip comments, blanks, rows without a folder
        { name = tolower($1); dir = $2
          if (substr(dir, 1, 1) == "~") dir = home substr(dir, 2)
          sub(/\/*$/, "/", dir)
          if ((mode == "exact" && name == w) || (mode == "prefix" && index(name, w) == 1)) print dir }
    ' "$aliases_file"
}

first=${query%%[ /]*}          # first word, up to a space or /
rest=${query#"$first"}; rest=${rest#[ /]}
if [[ -n $first && -n $rest ]] && scope=$(alias_lookup exact "$first") && [[ -n $scope ]]; then
    # `@name more words`: search only inside the shortcut's folder.
    scope=${scope%%$'\n'*}; query=$rest
    list_files "$scope" --hidden | with_dirs "" | rank | head -n 15 | awk -v p="$scope" '{ print p $0 }'
    exit 0
fi
shortcut_hits=""
(( ${#query} >= 2 )) && shortcut_hits=$(alias_lookup prefix "$query")

tier() {  # $1 = tier number, $2 = tier root, $3 = cached list
    local skip="$project/"
    [[ $project == "$HOME" ]] && skip=$'\x01'   # project is all of home: skip nothing
    awk -v p="$skip" 'index($0, p) != 1' "$3" 2>/dev/null | rank | head -n "$per_tier" \
        | awk -v t="$1" -v root="$2/" '{ print t "\t" NR "\t" root "\t" $0 }'
}

{
    if [[ $project != "$HOME" ]]; then
        list_files "$project" --hidden | with_dirs "" | rank | head -n "$per_tier" \
            | awk '{ print 1 "\t" NR "\t\t" $0 }'   # relative already: empty root
    fi
    tier 2 "$apps_root" "$apps_list"
    tier 3 "$HOME" "$rest_list"
} | awk -F'\t' -v q="$query" '
    function norm(s) { s = tolower(s); gsub(/[^a-z0-9]/, "", s); return s }
    BEGIN { n = split(q, w, /[ \t]+/); want = (n ? norm(w[n]) : "") }   # last word typed
    {
        tier = $1; rank = $2; root = $3
        path = $0; sub(/^[^\t]*\t[^\t]*\t[^\t]*\t/, "", path)   # rest of line: keeps tabs in names
        rel = (root != "" && index(path, root) == 1) ? substr(path, length(root) + 1) : path
        name = rel; sub(/\/$/, "", name); sub(/.*\//, "", name)
        stem = name; sub(/\.[^.]*$/, "", stem)
        depth = gsub(/\//, "/", rel) - (rel ~ /\/$/)   # folders count as their own level
        cls = 3
        if (want != "") {
            if (norm(name) == want || norm(stem) == want) cls = 0
            else if (index(norm(name), want) == 1)        cls = 1
            else if (index(norm(name), want) > 0)         cls = 2
        }
        printf "%d\t%d\t%d\t%d\t%s\n", cls, (cls < 3 ? depth : 0), tier, rank, path
    }' \
  | { [[ -n $shortcut_hits ]] && printf '%s\n' "$shortcut_hits"   # shortcuts go first
      sort -t$'\t' -k1,1n -k2,2n -k3,3n -k4,4n | cut -f5-; } \
  | if [[ $project == "$HOME" ]]; then sed "s|^$HOME/||"; else cat; fi \
  | awk '!seen[$0]++' | head -n 15
