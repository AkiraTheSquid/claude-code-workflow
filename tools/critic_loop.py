#!/usr/bin/env python3
"""How much time and Claude usage the /critic loop adds.

    python3 critic_loop.py [~/.claude/projects] [--since 2026-09-20]

A "critic loop" runs from the first critic.sh call in a turn until your next
prompt: waiting on Codex, reconciling, fixing, re-verifying, and also whatever
the agent does after that before handing back (commit, deploy, reply). So both
numbers are upper bounds.

Prints:
  - share of all Claude usage (API-priced) and active time spent in critic loops
  - per task: (whole task) / (time before the first critic call), i.e. how much
    longer a task took because the critic ran
"""
import datetime as dt
import glob
import json
import os
import re
import sys
from collections import Counter

# $/MTok: input, output, cache read. Cache writes: 1.25x input (5 min), 2x (1 h).
PRICES = {
    'claude-opus-5-5': (4, 20, .20), 'claude-fable-5-1': (10, 50, .25),
    'claude-sonnet-5-5': (2, 10, .20), 'claude-sonnet-5': (2, 10, .20),
    'claude-haiku-5-5': (.10, .50, .01), 'claude-opus-5': (5, 25, .50),
    'claude-opus-4-8': (5, 25, .50), 'claude-haiku-4-5-20251001': (1, 5, .10),
}
# a critic.sh run, also behind timeout/nice/bash wrappers (not `cat critic.sh` etc.)
CRITIC = re.compile(r'(^|[;&|\n]\s*)((timeout\s+\d+|nice(\s+-n\s+-?\d+)?|bash|sh)\s+)*\S*critic\.sh\b')
UNPRICED = Counter()  # turns whose model has no price above (left out of usage)
ACTIVE_GAP = 300  # gaps longer than this are idle time, not work


def ts(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()


def turn_cost(m):
    u = m.get('usage') or {}
    i, o, r = PRICES[m['model']]
    w1h = (u.get('cache_creation') or {}).get('ephemeral_1h_input_tokens') or 0
    w5m = (u.get('cache_creation_input_tokens') or 0) - w1h
    return ((u.get('input_tokens') or 0) * i + w5m * 1.25 * i + w1h * 2 * i
            + (u.get('cache_read_input_tokens') or 0) * r
            + (u.get('output_tokens') or 0) * o) / 1e6


def events(path, since):
    """(time, kind, cost, calls_critic); kind: 'a' assistant, 'p' your prompt, 'r' tool result."""
    out, seen = [], set()
    for line in open(path, errors='ignore'):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        t = d.get('timestamp')
        if not t or ts(t) < since:
            continue
        m = d.get('message') or {}
        blocks = m.get('content') if isinstance(m.get('content'), list) else []
        blocks = [b for b in blocks if isinstance(b, dict)]
        if d.get('type') == 'assistant':
            cost = 0
            if m.get('usage') and m.get('id') not in seen:
                seen.add(m['id'])  # one API response is split over several lines
                if m.get('model') in PRICES:
                    cost = turn_cost(m)
                elif m.get('model') != '<synthetic>':
                    UNPRICED[m.get('model')] += 1
            critic = any(b.get('type') == 'tool_use'
                         and CRITIC.search(str((b.get('input') or {}).get('command', '')))
                         for b in blocks)
            out.append((ts(t), 'a', cost, critic))
        elif d.get('type') == 'user' and not d.get('isMeta'):
            prompt = isinstance(m.get('content'), str) or (
                any(b.get('type') == 'text' for b in blocks)
                and not any(b.get('type') == 'tool_result' for b in blocks))
            out.append((ts(t), 'p' if prompt else 'r', 0, False))
    return sorted(out)


def main():
    args = sys.argv[1:]
    since = ts('2026-09-20T00:00:00Z')
    if '--since' in args:
        k = args.index('--since')
        since = ts(args[k + 1] + 'T00:00:00Z')
        del args[k:k + 2]
    root = os.path.expanduser(args[0] if args else '~/.claude/projects')

    total_cost = total_active = loop_cost = loop_active = 0.0
    tasks = []  # (active seconds before the first critic call, after it)
    for path in glob.glob(os.path.join(root, '*', '*.jsonl')):
        prev, phase, pre, post = None, 0, 0.0, 0.0  # phase 1: before critic, 2: in loop
        for t, kind, cost, critic in events(path, since) + [(float('inf'), 'p', 0, False)]:
            gap = t - prev if prev is not None else 0
            active = gap if 0 < gap < ACTIVE_GAP else 0
            prev = t
            if kind == 'p':
                if phase == 2 and pre > 0:
                    tasks.append((pre, post))
                phase, pre, post = 1, 0.0, 0.0
                if t != float('inf'):
                    total_active += active
                continue
            total_cost += cost
            total_active += active
            if phase == 2:
                loop_cost += cost
                loop_active += active
                post += active
            else:
                pre += active
                if critic:
                    phase = 2

    if not total_cost or not total_active:
        print("no priced, timed turns found")
        return
    if UNPRICED:
        print("warning: unpriced models left out:", dict(UNPRICED))
    print(f"critic loops: {len(tasks)} tasks")
    print(f"  Claude usage in loops: ${loop_cost:,.0f} of ${total_cost:,.0f} "
          f"= {loop_cost / total_cost:.1%} (upper bound)")
    print(f"  active time in loops: {loop_active / 3600:.1f} h of {total_active / 3600:.1f} h "
          f"= {loop_active / total_active:.1%} (upper bound)")
    if tasks:
        r = sorted((a + b) / a for a, b in tasks)
        q = lambda p: r[int(p * (len(r) - 1))]
        agg = sum(a + b for a, b in tasks) / sum(a for a, _ in tasks)
        print(f"  task length vs. without the loop: {agg:.2f}x overall, "
              f"median {q(.5):.2f}x (p25 {q(.25):.2f}x, p75 {q(.75):.2f}x)")


if __name__ == '__main__':
    main()
