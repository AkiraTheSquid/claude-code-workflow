#!/usr/bin/env python3
"""
PostToolUse hook: accumulates per-file LOC stats for the current request.
Appends one JSON entry per tool call to ~/.claude/request_locs.jsonl.
Stop/SubagentStop hooks read and clear only the matching request bucket.
"""
import json
import os
import sys
from datetime import datetime

ACCUM_FILE = os.path.expanduser("~/.claude/request_locs.jsonl")


def count_loc(path):
    try:
        with open(path, "r", errors="replace") as f:
            return sum(1 for line in f if line.strip())
    except OSError:
        return 0


def request_key(hook_input):
    agent_id = hook_input.get("agent_id")
    if agent_id:
        return f"agent:{agent_id}"
    transcript_path = hook_input.get("agent_transcript_path") or hook_input.get("transcript_path")
    if transcript_path:
        return f"transcript:{transcript_path}"
    return "session:unknown"


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not path:
        sys.exit(0)

    entry = {
        "tool": tool_name,
        "path": path,
        "request_key": request_key(hook_input),
        "agent_id": hook_input.get("agent_id"),
        "agent_type": hook_input.get("agent_type"),
        "transcript_path": hook_input.get("agent_transcript_path") or hook_input.get("transcript_path"),
        "ts": datetime.now().isoformat(),
    }

    if tool_name == "Read":
        entry["loc"] = count_loc(path)
    elif tool_name == "Edit":
        old_n = len(tool_input.get("old_string", "").splitlines())
        new_n = len(tool_input.get("new_string", "").splitlines())
        entry["added"] = max(0, new_n - old_n)
        entry["removed"] = max(0, old_n - new_n)
    elif tool_name == "Write":
        entry["added"] = len([l for l in tool_input.get("content", "").splitlines() if l.strip()])
        entry["removed"] = 0
    else:
        sys.exit(0)

    try:
        with open(ACCUM_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


if __name__ == "__main__":
    main()
