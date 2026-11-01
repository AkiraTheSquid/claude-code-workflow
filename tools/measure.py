#!/usr/bin/env python3
"""Replay Claude Code transcripts and price each workflow lever as a counterfactual.

Usage: python3 measure.py ~/.claude/projects report.json
All costs are API list-price equivalents (USD). Prices: claude-api skill table, 2026-10-06.
Writes a JSON report to argv[2]."""
import glob, json, os, re, sys, statistics
from collections import Counter, defaultdict
from datetime import datetime

ROOT = sys.argv[1]
OUT = sys.argv[2]

# $/MTok: input, output, cache read. Writes: 5m = 1.25x input, 1h = 2x input.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-fable-5-1": (10.0, 50.0, 0.25),
    "claude-fable-5": (10.0, 50.0, 1.00),
    "claude-opus-5": (5.0, 25.0, 0.50),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20),
    "claude-sonnet-5": (2.0, 10.0, 0.20),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
}
DEFAULT_WINDOW_FIRE = 1_000_000 - 33_000      # stock 1M-context auto-compact point
TTL_1H, TTL_5M = 3600, 300
EXPLORE_TOOLS = {"Read", "Grep", "Glob"}
EXPLORE_BASH = re.compile(r"^\s*(cd [^;&]+(&&|;)\s*)?(grep|rg|find|ls|cat|head|tail|sed -n|tree|wc|fd)\b")
CLI_RE = re.compile(r"(^|[;&|]\s*|\$\(\s*)(gh|vercel|supabase|fly|flyctl|modal|stripe|gcloud|aws)\s")
# a critic.sh run, also behind timeout/nice/bash wrappers (not `cat critic.sh` etc.)
CRITIC_RE = re.compile(r"(^|[;&|\n]\s*)((timeout\s+\d+|nice(\s+-n\s+-?\d+)?|bash|sh)\s+)*\S*critic\.sh\b")
CHARS_PER_TOKEN = 3.6


def price(model):
    m = (model or "").split("[")[0]
    for k, v in PRICES.items():
        if m == k:
            return v
    return PRICES["claude-opus-5-5"]


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def load(path):
    """Return ordered events for one transcript: assistant turns (deduped), boundaries, blocks, tool results."""
    turns, seen, events = [], {}, []
    tool_names = {}
    with open(path, errors="ignore") as fh:
        for line in fh:
            if '"type":"attachment"' in line[:200] or '"file-history' in line[:40]:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            t = d.get("type")
            if t == "assistant":
                msg = d.get("message") or {}
                u = msg.get("usage")
                mid = msg.get("id") or d.get("requestId")
                if not u or not d.get("timestamp"):
                    continue
                content = msg.get("content") or []
                text = sum(len(c.get("text", "")) for c in content if isinstance(c, dict) and c.get("type") == "text")
                tool = sum(len(json.dumps(c.get("input", {}))) for c in content if isinstance(c, dict) and c.get("type") == "tool_use")
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "tool_use":
                        tool_names[c.get("id")] = (c.get("name"), c.get("input") or {}, ts(d["timestamp"]))
                if mid in seen:      # one API response is split over several lines
                    rec = seen[mid]
                    rec["text"] += text
                    rec["tool"] += tool
                    continue
                cc = u.get("cache_creation") or {}
                if "ephemeral_1h_input_tokens" not in cc and (u.get("cache_creation_input_tokens") or 0):
                    C["writes_without_ttl_split"] += 1
                rec = {
                    "kind": "turn", "t": ts(d["timestamp"]), "model": msg.get("model"),
                    "inp": u.get("input_tokens", 0) or 0,
                    "cw": u.get("cache_creation_input_tokens", 0) or 0,
                    "cw1h": cc.get("ephemeral_1h_input_tokens"),
                    "cr": u.get("cache_read_input_tokens", 0) or 0,
                    "out": u.get("output_tokens", 0) or 0,
                    "think": (u.get("output_tokens_details") or {}).get("thinking_tokens", 0) or 0,
                    "text": text, "tool": tool, "side": d.get("isSidechain", False),
                }
                seen[mid] = rec
                events.append(rec)
            elif t == "system" and d.get("subtype") == "compact_boundary":
                m = d.get("compactMetadata") or {}
                events.append({"kind": "compact", "t": ts(d["timestamp"]), "trigger": m.get("trigger"),
                               "secs": (m.get("durationMs") or 0) / 1000,
                               "pre": m.get("preTokens", 0) or 0, "post": m.get("postTokens", 0) or 0})
            elif t == "system" and d.get("subtype") == "informational" and "cache_guard" in str(d.get("content", "")):
                c = str(d.get("content"))
                mm = re.search(r"context ≈ (\d+)k", c)
                events.append({"kind": "block", "t": ts(d["timestamp"]), "ctx": int(mm.group(1)) * 1000 if mm else 0})
            elif t == "user":
                msg = d.get("message") or {}
                content = msg.get("content")
                if isinstance(content, str) and not d.get("isMeta") and d.get("timestamp"):
                    events.append({"kind": "prompt", "t": ts(d["timestamp"]), "text": content})
                elif isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "tool_result" and d.get("timestamp"):
                            body = c.get("content")
                            if isinstance(body, str):
                                n = len(body)
                            else:
                                n = sum(len(b.get("text", "")) for b in (body or []) if isinstance(b, dict) and b.get("type") == "text")
                            name, tin, t0 = tool_names.get(c.get("tool_use_id"), (None, {}, None))
                            raw = body if isinstance(body, str) else " ".join(
                                b.get("text", "") for b in (body or []) if isinstance(b, dict))
                            events.append({"kind": "result", "t": ts(d["timestamp"]), "name": name,
                                           "input": tin, "chars": n, "t0": t0,
                                           "collab": raw[:2000] if "collab: " in raw[:2000] else ""})
    events.sort(key=lambda e: e["t"])
    return events


def turn_cost(r, write_mult=None):
    pin, pout, pread = price(r["model"])
    if write_mult is None:
        w1h = r["cw1h"] if r["cw1h"] is not None else r["cw"]
        w5m = r["cw"] - w1h
        write = (w1h * 2.0 + w5m * 1.25) * pin
    else:
        write = r["cw"] * write_mult * pin
    return (r["inp"] * pin + write + r["cr"] * pread + r["out"] * pout) / 1e6


def ctx(r):
    return r["inp"] + r["cw"] + r["cr"]


R = defaultdict(float)
C = Counter()
cold_examples, block_outcomes = [], Counter()
active_spans = []
per_turn_costs = []
subagent = {"files": 0, "cost": 0.0, "first_ctx": []}

files = sorted(glob.glob(os.path.join(ROOT, "*", "*.jsonl")))
sub_files = sorted(glob.glob(os.path.join(ROOT, "*", "*", "subagents", "*.jsonl")))
tmin, tmax = 1e20, 0

for path in files + sub_files:
    is_sub = "/subagents/" in path
    ev = load(path)
    turns = [e for e in ev if e["kind"] == "turn" and (is_sub or not e["side"])]
    if not turns:
        continue
    tmin, tmax = min(tmin, turns[0]["t"]), max(tmax, turns[-1]["t"])
    for r in turns:
        c = turn_cost(r)
        R["actual_total"] += c
        pin, pout, pread = price(r["model"])
        w1h = r["cw1h"] if r["cw1h"] is not None else r["cw"]
        R["bucket_write"] += (w1h * 2.0 + (r["cw"] - w1h) * 1.25) * pin / 1e6
        R["bucket_read"] += r["cr"] * pread / 1e6
        R["bucket_output"] += r["out"] * pout / 1e6
        R["bucket_input"] += r["inp"] * pin / 1e6
        R["tok_output"] += r["out"]
        R["tok_think"] += r["think"]
        C["turns"] += 1
        C["model:" + str(r["model"])] += 1
    if is_sub:
        subagent["files"] += 1
        subagent["cost"] += sum(turn_cost(r) for r in turns)
        subagent["first_ctx"].append(ctx(turns[0]))
        continue
    C["sessions"] += 1
    per_turn_costs.extend(turn_cost(r) for r in turns)

    # ---- active wall-clock spans (gap < 5 min between turns = actively working)
    s = turns[0]["t"]
    prev = s
    for r in turns[1:]:
        if r["t"] - prev > 300:
            active_spans.append((s, prev + 30))
            s = r["t"]
        prev = r["t"]
    active_spans.append((s, prev + 30))

    # ---- walk events in order for the counterfactuals
    prev_t = None
    offset = 0              # tokens the stock 1M window would still be carrying
    since_compact = []      # indices of turns since last compaction (for re-read counting)
    text_tok_live = 0.0     # caveman text tokens currently in context
    explore_tok_live = 0.0
    pending_block = None
    for i, e in enumerate(ev):
        k = e["kind"]
        if k == "compact":
            C["compact_" + str(e["trigger"])] += 1
            R["compact_seconds_" + str(e["trigger"])] += e.get("secs", 0)
            if e["trigger"] == "auto":
                # stock setup would not have compacted here (unless it was past ~967k)
                if e["pre"] < DEFAULT_WINDOW_FIRE:
                    offset += max(0, e["pre"] - e["post"])
                    # the summarisation call itself: ~pre tokens read warm + summary output
                    pin, pout, pread = price("claude-opus-5-5")
                    R["compact_call_cost"] += (e["pre"] * pread + e["post"] * pout) / 1e6
            else:
                offset = 0
            text_tok_live = 0.0
            explore_tok_live = 0.0
            if pending_block:
                block_outcomes["compacted"] += 1
                pin = price("claude-opus-5-5")[0]
                # compacting cold re-processes the context once (~write price) but every later turn is small
                R["guard_saved_compacted"] += pending_block * (2.0 - 1.25) * pin / 1e6
                pending_block = None
            continue
        if k == "block":
            C["guard_blocks"] += 1
            if pending_block is None:      # a re-prompt while still blocked is the same cold episode
                C["guard_episodes"] += 1
            pending_block = e["ctx"]
            continue
        if k == "prompt":
            if re.search(r"@(~?/|[\w.-]+/)[\w./-]+", e["text"]):
                C["at_mentions"] += 1
            C["prompts"] += 1
            continue
        if k == "result":
            name, tin = e["name"], e["input"]
            toks = e["chars"] / CHARS_PER_TOKEN
            cmd = tin.get("command", "") if isinstance(tin, dict) else ""
            if name in EXPLORE_TOOLS or (name == "Bash" and EXPLORE_BASH.match(cmd or "")):
                explore_tok_live += toks
                R["explore_tokens"] += toks
                C["explore_calls"] += 1
            if name == "Bash" and re.search(r"\bgraphify (query|path|explain)\b", cmd or ""):
                C["graphify_calls"] += 1
            if name == "Bash" and CLI_RE.search(cmd or ""):
                C["cli_calls"] += 1
                C["cli:" + CLI_RE.search(cmd).group(2)] += 1
            if name == "Bash" and re.search(r"(^|\s)collab\s", cmd or ""):
                C["collab_calls"] += 1
            if name and name.startswith("mcp__"):
                C["mcp_calls"] += 1
                C["mcp:" + name.split("__")[1]] += 1
            if name == "Bash" and CRITIC_RE.search(cmd or ""):
                C["critic_runs"] += 1
                if e["t0"]:
                    R["critic_seconds"] += max(0.0, e["t"] - e["t0"])
            msg = e["collab"]
            if msg:
                for key, pat in (("collab_refused_owned", " is owned by agent "),
                                 ("collab_refused_intent", "before changing anything"),
                                 ("collab_refused_joined", "a new agent joined"),
                                 ("collab_refused_deploy_hold", "another agent has a deploy hold"),
                                 ("collab_refused_git", "collab: refused in ")):
                    if pat in msg:
                        C[key] += 1
            continue
        if k != "turn" or e["side"]:
            continue
        r = e
        pin, pout, pread = price(r["model"])
        gap = r["t"] - prev_t if prev_t else 0
        prev_t = r["t"]
        context = ctx(r)

        if pending_block is not None:
            if r["cw"] > 0.5 * pending_block:
                block_outcomes["resent"] += 1
            else:
                block_outcomes["cleared_or_small"] += 1
                R["guard_saved_cleared"] += pending_block * 2.0 * pin / 1e6
            pending_block = None

        # cold rebuilds that actually happened
        if gap > TTL_1H and r["cw"] >= 60_000:
            C["cold_rebuilds_paid"] += 1
            R["cold_rebuild_cost"] += r["cw"] * 2.0 * pin / 1e6
            R["cold_rebuild_vs_warm"] += r["cw"] * (2.0 * pin - pread) / 1e6

        # 1h TTL vs stock 5m TTL: a 5-60 min gap re-writes the whole context at 1.25x
        w1h = r["cw1h"] if r["cw1h"] is not None else r["cw"]
        actual_cache = (w1h * 2.0 + (r["cw"] - w1h) * 1.25) * pin + r["cr"] * pread
        if TTL_5M < gap <= TTL_1H:
            cf_cache = (r["cw"] + r["cr"]) * 1.25 * pin
            C["gaps_5_60"] += 1
        else:
            cf_cache = r["cw"] * 1.25 * pin + r["cr"] * pread
        R["ttl_actual"] += actual_cache / 1e6
        R["ttl_cf5m"] += cf_cache / 1e6

        # stock compaction window: carry `offset` extra tokens on every turn
        if context + offset > DEFAULT_WINDOW_FIRE:
            offset = 0
        if offset:
            rate = 2.0 * pin if gap > TTL_1H else pread   # carried tokens: warm read unless the cache went cold
            R["window_extra"] += offset * rate / 1e6
            R["window_extra_cold" if gap > TTL_1H else "window_extra_warm"] += offset * rate / 1e6
            C["window_turns_affected"] += 1
        R["window_ctx_sum"] += context
        R["window_ctx_sum_cf"] += context + offset
        C["main_turns"] += 1
        C["ctx_ge_200k"] += context >= 200_000
        C["ctx_cf_ge_200k"] += (context + offset) >= 200_000

        # caveman counterfactual: extra prose output + its re-reads on later turns
        nonthink = max(0, r["out"] - r["think"])
        share = r["text"] / (r["text"] + r["tool"]) if (r["text"] + r["tool"]) else 0
        text_tok = nonthink * share
        R["text_tokens"] += text_tok
        R["text_out_cost"] += text_tok * pout / 1e6
        R["text_reread_cost"] += text_tok_live * pread / 1e6
        text_tok_live += text_tok
        R["explore_reread_cost"] += explore_tok_live * pread / 1e6

    if pending_block is not None:      # blocked, then the session was never resumed
        block_outcomes["abandoned"] += 1
        R["guard_saved_cleared"] += pending_block * 2.0 * price("claude-opus-5-5")[0] / 1e6
# union of active spans across sessions -> achieved parallelism
active_spans.sort()
union, cur_s, cur_e, total = 0.0, None, None, 0.0
for s, e in active_spans:
    total += e - s
    if cur_e is None or s > cur_e:
        if cur_e is not None:
            union += cur_e - cur_s
        cur_s, cur_e = s, e
    else:
        cur_e = max(cur_e, e)
if cur_e is not None:
    union += cur_e - cur_s

pts = sorted([(s_, 1) for s_, _ in active_spans] + [(e_, -1) for _, e_ in active_spans])
level, last, multi = 0, None, 0.0
for t_, d_ in pts:
    if last is not None and level >= 2:
        multi += t_ - last
    level += d_
    last = t_
R["hours_2plus_sessions"] = multi / 3600
report = {
    "window_days": (tmax - tmin) / 86400,
    "from": datetime.fromtimestamp(tmin).isoformat()[:10],
    "to": datetime.fromtimestamp(tmax).isoformat()[:10],
    "R": dict(R), "C": dict(C),
    "block_outcomes": dict(block_outcomes),
    "active_hours_sum": total / 3600, "active_hours_union": union / 3600,
    "median_turn_cost": statistics.median(per_turn_costs) if per_turn_costs else 0,
    "mean_turn_cost": statistics.mean(per_turn_costs) if per_turn_costs else 0,
    "subagent": {"files": subagent["files"], "cost": subagent["cost"],
                 "median_first_ctx": statistics.median(subagent["first_ctx"]) if subagent["first_ctx"] else 0},
}
json.dump(report, open(OUT, "w"), indent=1, default=float)
print(json.dumps(report, indent=1, default=float)[:6000])
