#!/usr/bin/env python3
"""
Stop/SubagentStop hook: prints per-request token stats after each Claude response.
Reads the transcript path from stdin and finalizes only the matching request bucket.
"""
import json
import os
import sys
from datetime import datetime

PRICING = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "claude-opus-4-6":   {"input": 15.00, "output": 75.00, "cache_read": 1.50, "cache_write": 18.75},
    "claude-haiku-4-5":  {"input": 0.80, "output": 4.00,  "cache_read": 0.08, "cache_write": 1.00},
}
DEFAULT_PRICING = {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75}
ACCUM_FILE = os.path.expanduser("~/.claude/request_locs.jsonl")
TEXT_FILE = os.path.expanduser("~/.claude/token_loc.txt")
JSON_FILE = os.path.expanduser("~/.claude/token_loc.json")
STATS_FILE = os.path.expanduser("~/.claude/token_last.txt")


def estimate_cost(usage, model):
    p = PRICING.get(model, DEFAULT_PRICING)
    m = 1_000_000
    return (
        usage.get("input_tokens", 0) * p["input"] / m
        + usage.get("output_tokens", 0) * p["output"] / m
        + usage.get("cache_read_input_tokens", 0) * p["cache_read"] / m
        + usage.get("cache_creation_input_tokens", 0) * p["cache_write"] / m
    )


def request_key(hook_input):
    agent_id = hook_input.get("agent_id")
    if agent_id:
        return f"agent:{agent_id}"
    transcript_path = hook_input.get("agent_transcript_path") or hook_input.get("transcript_path")
    if transcript_path:
        return f"transcript:{transcript_path}"
    return "session:unknown"


def parse_request_locs(match_key):
    entries = []
    leftovers = []
    try:
        with open(ACCUM_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                if entry.get("request_key", "session:unknown") == match_key:
                    entries.append(entry)
                else:
                    leftovers.append(entry)
    except OSError:
        return [], [], None, None, None
    finally:
        try:
            with open(ACCUM_FILE, "w", encoding="utf-8") as f:
                for entry in leftovers:
                    f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    reads = {}
    edits = {}
    agent_id = None
    agent_type = None
    transcript_path = None
    for entry in entries:
        path = entry.get("path", "")
        tool = entry.get("tool", "")
        if not path:
            continue
        agent_id = agent_id or entry.get("agent_id")
        agent_type = agent_type or entry.get("agent_type")
        transcript_path = transcript_path or entry.get("transcript_path")
        if tool == "Read":
            reads[path] = entry.get("loc", 0)
        elif tool in ("Edit", "Write"):
            agg = edits.setdefault(path, [0, 0])
            agg[0] += entry.get("added", 0)
            agg[1] += entry.get("removed", 0)

    read_files = [(p, loc) for p, loc in sorted(reads.items()) if p not in edits]
    edit_files = [(p, a, r, reads.get(p)) for p, (a, r) in sorted(edits.items())]
    return read_files, edit_files, agent_id, agent_type, transcript_path


def last_usage(transcript_path):
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 32768))
            chunk = f.read()
    except OSError:
        return None, None

    best_usage = None
    best_model = "unknown"
    for line in chunk.split(b"\n"):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("type") != "assistant":
            continue
        msg = obj.get("message", {})
        if not isinstance(msg, dict):
            continue
        usage = msg.get("usage")
        if usage and usage.get("output_tokens"):
            best_usage = usage
            best_model = msg.get("model", "unknown")
    return best_usage, best_model


def write_loc_summary(read_files, edit_files, request_meta):
    total_read_loc = sum(loc for _, loc in read_files) + sum(loc for _, _, _, loc in edit_files if loc is not None)
    total_added = sum(a for _, a, _, __ in edit_files)
    total_removed = sum(r for _, _, r, __ in edit_files)

    all_files = {}
    for path, loc in read_files:
        all_files[path] = {"loc": loc, "added": None, "removed": None}
    for path, added, removed, loc in edit_files:
        all_files[path] = {"loc": loc, "added": added, "removed": removed}

    def sort_key(item):
        info = item[1]
        if info["loc"] is not None and info["added"] is not None:
            return (0, item[0])
        if info["added"] is not None:
            return (1, item[0])
        return (2, item[0])

    out = []
    parts = []
    read_count = sum(1 for v in all_files.values() if v["loc"] is not None)
    if read_count:
        parts.append(f"{read_count} read ({total_read_loc:,} LOC)")
    if edit_files:
        parts.append(f"{len(edit_files)} edited (+{total_added}/-{total_removed})")
    out.append("loc: " + "  ".join(parts))
    out.append(" ")
    name_w = max((len(os.path.basename(p)) for p in all_files), default=10) + 2
    out.append(f"  {'file':<{name_w}}  {'read':>8}  changed")
    for path, info in sorted(all_files.items(), key=sort_key):
        name = os.path.basename(path)
        read_col = f"{info['loc']:,}" if info["loc"] is not None else "—"
        change_col = f"+{info['added']} / -{info['removed']}" if info["added"] is not None else "—"
        out.append(f"  {name:<{name_w}}  {read_col:>8}  {change_col}")

    try:
        with open(TEXT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
    except OSError:
        pass

    payload = {
        "updated_at": datetime.now().isoformat(),
        "request_key": request_meta.get("request_key"),
        "agent_id": request_meta.get("agent_id"),
        "agent_type": request_meta.get("agent_type"),
        "transcript_path": request_meta.get("transcript_path"),
        "files": [
            {
                "path": path,
                "read_loc": info["loc"],
                "added": info["added"],
                "removed": info["removed"],
            }
            for path, info in sorted(all_files.items(), key=sort_key)
        ],
        "totals": {
            "read_files": read_count,
            "edit_files": len(edit_files),
            "read_loc": total_read_loc,
            "added": total_added,
            "removed": total_removed,
        },
    }
    try:
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
    except OSError:
        pass


def main():
    raw = sys.stdin.read()
    try:
        hook_input = json.loads(raw)
    except Exception:
        sys.exit(0)

    transcript_path = hook_input.get("agent_transcript_path") or hook_input.get("transcript_path")
    if not transcript_path or not os.path.exists(transcript_path):
        sys.exit(0)

    usage, model = last_usage(transcript_path)
    if not usage:
        sys.exit(0)

    parts = [f"in={usage.get('input_tokens', 0):,}", f"out={usage.get('output_tokens', 0):,}"]
    cache_read = usage.get("cache_read_input_tokens", 0)
    cache_write = usage.get("cache_creation_input_tokens", 0)
    if cache_read:
        parts.append(f"cached={cache_read:,}")
    if cache_write:
        parts.append(f"cache+={cache_write:,}")
    parts.append(f"~${estimate_cost(usage, model):.4f}")
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            f.write("  ".join(parts) + "\n")
    except OSError:
        pass

    key = request_key(hook_input)
    read_files, edit_files, agent_id, agent_type, used_transcript = parse_request_locs(key)
    if read_files or edit_files:
        write_loc_summary(read_files, edit_files, {
            "request_key": key,
            "agent_id": agent_id or hook_input.get("agent_id"),
            "agent_type": agent_type or hook_input.get("agent_type"),
            "transcript_path": used_transcript or transcript_path,
        })


if __name__ == "__main__":
    main()
