#!/usr/bin/env python3
"""What Claude did with each Codex /critic finding: fixed, left, or disputed.

    python3 critic_verdicts.py [~/.claude/projects] [--out DIR] [--jobs 2] [--per 5] [--limit N]

1. Finds every critic.sh run in the transcripts and Codex's findings for it (also
   when the run was backgrounded and read back later, or viewed through tail/jq).
2. Sends each run's findings plus the text Claude wrote afterwards, up to your
   next prompt, to `claude -p --model sonnet`, which labels every finding.
3. Prints the shares, overall and by severity.

The labelling calls use your own Claude plan (~$0.01 of API-equivalent per run),
so keep --jobs at 2. Results go to DIR/verdicts.jsonl (default ./critic_verdicts);
re-running skips runs already labelled. That folder holds transcript excerpts:
keep it out of git.

Limits: labels come from Claude's text, not its edits, so a finding fixed without
comment counts as no verdict. If two critic runs overlap in one session, text
after the second is credited to the second only. A run is labelled once your next
prompt, a re-run, or an hour of session idle ends it, so live sessions wait for a later run.
"""
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

# a critic.sh run, also behind timeout/nice/bash wrappers (not `cat critic.sh` etc.)
CRITIC = re.compile(r'(^|[;&|\n]\s*)((timeout\s+\d+|nice(\s+-n\s+-?\d+)?|bash|sh)\s+)*\S*critic\.sh\b')
SEV = re.compile(r'"severity"\s*:\s*"(high|medium|low)"\s*,\s*"title"\s*:\s*"((?:[^"\\]|\\.)+)"')
LINE = re.compile(r'^\s*-?\s*\[?(high|medium|low)\]?\s+(.+?)\s+::', re.M)  # jq one-line summaries
BG = re.compile(r'Output is being written to: (\S+\.output)')
KEY = re.compile(r'codex|critic|agree|disput|reject|declin|wrong|fix|address|resolv|skip|defer|valid|real|false positive|finding', re.I)
VERDICTS = ['fixed', 'partly_fixed', 'agreed_not_fixed', 'disputed', 'unaddressed']

SYSTEM = """You label how a coding agent (Claude) responded to each finding from a code reviewer (Codex).
For every run you get Codex's numbered findings and the text Claude wrote afterwards (its narration and
its report to the user). Label each finding with exactly one verdict:
- fixed: Claude agreed the finding is real and changed the code for it.
- partly_fixed: Claude accepted part of it, or fixed a narrower version, and rejected the rest.
- agreed_not_fixed: Claude agreed it is real (or plausible) but did not change code: deferred, logged,
  out of scope, left for later, documented as a known limitation, or just noted.
- disputed: Claude judged the finding wrong, not a real problem, already handled, intended behaviour,
  or not worth acting on, and did not change code for it.
- unaddressed: the text never says what happened to this finding (also use this if it is ambiguous).
Group statements count ("all six fixed", "fixed the two mediums, the low is wrong") — map them onto the
numbered findings by severity/order when the mapping is clear; otherwise unaddressed.
Return ONLY a JSON array, no prose: [{"id": <run id>, "v": [{"n": <finding number>, "verdict": "<one of
the five>", "why": "<=12 words of evidence from Claude's text"}]}]"""


def text_of(content):
    if isinstance(content, list):
        return '\n'.join(x.get('text', '') for x in content if isinstance(x, dict))
    return str(content or '')


def has_findings(text):
    return 'correctness_findings' in text or bool(SEV.search(text) or LINE.search(text))


def runs(root):
    """Every critic run: the command's output, later reads of it, and Claude's text until your next prompt."""
    out = []
    for path in sorted(glob.glob(os.path.join(root, '*', '*.jsonl'))):
        pending, cur = {}, None
        idle = time.time() - os.path.getmtime(path) > 3600  # session over, nothing more coming
        for line in open(path, errors='ignore'):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            m = d.get('message') or {}
            c = m.get('content')
            blocks = [b for b in c if isinstance(b, dict)] if isinstance(c, list) else []
            if d.get('type') == 'assistant':
                for b in blocks:
                    if b.get('type') == 'tool_use' and CRITIC.search(str((b.get('input') or {}).get('command', ''))):
                        if cur is not None:
                            cur['closed'] = True  # a re-run ends the earlier run's window
                        key = f"{os.path.basename(path)}:{b['id']}"
                        cur = {'id': hashlib.sha1(key.encode()).hexdigest()[:12], 'result': '', 'later': [], 'after': [],
                               'closed': False}
                        pending[b['id']] = cur
                        out.append(cur)
                    elif b.get('type') == 'text' and cur is not None:
                        cur['after'].append(b['text'])
            elif d.get('type') == 'user' and not d.get('isMeta'):
                prompt = isinstance(c, str) or (any(b.get('type') == 'text' for b in blocks)
                                                and not any(b.get('type') == 'tool_result' for b in blocks))
                text = c if isinstance(c, str) else ' '.join(b.get('text', '') for b in blocks)
                if prompt and '<task-notification>' in text:
                    if cur is not None and has_findings(text):
                        cur['later'].append(text)
                    continue  # a background job finishing is not your next prompt
                if prompt:
                    if cur is not None:
                        cur['closed'] = True
                    cur = None
                    continue
                for b in blocks:
                    if b.get('type') != 'tool_result':
                        continue
                    r = text_of(b.get('content'))
                    if b.get('tool_use_id') in pending:
                        pending[b['tool_use_id']]['result'] = r
                    elif cur is not None and has_findings(r):
                        cur['later'].append(r)  # backgrounded run, read back from its output file
        if cur is not None and idle:
            cur['closed'] = True
    return out


def parse(text):
    """Codex's correctness_findings from its JSON (whole object or bare list), else None."""
    text = re.sub(r'^\s*\d+:', '', text, flags=re.M)  # line-numbered views
    dec = json.JSONDecoder()
    for opener in '{[':
        i = text.find(opener)
        while i != -1:
            try:
                obj, _ = dec.raw_decode(text[i:])
                if isinstance(obj, dict) and 'correctness_findings' in obj:
                    return obj['correctness_findings']
                if isinstance(obj, list) and obj and isinstance(obj[0], dict) and 'severity' in obj[0]:
                    return obj
            except ValueError:
                pass
            i = text.find(opener, i + 1)
    return None


def findings(run):
    """(findings, exact): exact when parsed from Codex's whole JSON, not pieced together by regex."""
    f = parse(run['result'])
    for t in run['later']:
        if f is None:
            f = parse(t)
    m = BG.search(run['result'])
    if f is None and m and os.path.exists(m.group(1)):
        f = parse(open(m.group(1), errors='ignore').read())
    if f is not None:
        return f, True
    seen = {}  # partial view (tail/grep/jq of the output); may merge several outputs
    for t in [run['result']] + run['later']:
        for s, title in SEV.findall(t) + LINE.findall(t):
            seen.setdefault(title, {'severity': s, 'title': title})
    return (list(seen.values()) or None), False


def items(root):
    found, clean, unread, still_open = [], 0, 0, 0
    for r in runs(root):
        if not r['closed']:
            still_open += 1  # no prompt after it yet: Claude may still be reacting
            continue
        f, exact = findings(r)
        if f is None:
            unread += 1  # blocked, empty diff, cancelled, or output no longer on disk
            continue
        if not f:
            clean += 1
            continue
        texts = r['after']
        react = '\n---\n'.join(texts[:3] + [t for t in texts[3:] if KEY.search(t)])
        if len(react) > 6000:
            react = react[:2500] + '\n[...]\n' + react[-3500:]
        found.append({'id': r['id'], 'react': react, 'exact': exact,
                      'findings': [{'n': j + 1, 'severity': x.get('severity'), 'title': x.get('title'),
                                    'why': (x.get('why') or '')[:300]} for j, x in enumerate(f)]})
    print(f"critic runs: {len(found)} with findings, {clean} clean, {unread} unreadable, "
          f"{still_open} not finished yet")
    return found


def render(item):
    lines = [f"### RUN id={item['id']}", "Codex findings:"]
    for f in item['findings']:
        lines.append(f"{f['n']}. [{f['severity']}] {f['title']}" + (f" — {f['why']}" if f['why'] else ''))
    return '\n'.join(lines + ["Claude's text afterwards:", item['react'] or '(none)'])


def label(batch, cwd):
    r = subprocess.run(
        ['claude', '-p', '--model', 'sonnet', '--tools', '', '--no-session-persistence',
         '--setting-sources', 'local', '--system-prompt', SYSTEM, '--output-format', 'json'],
        input='\n\n'.join(render(i) for i in batch), capture_output=True, text=True, cwd=cwd, timeout=600)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout)[-300:])
    text = json.loads(r.stdout).get('result', '')
    if 'limit' in text.lower() and '[' not in text:
        raise RuntimeError('usage limit: ' + text[:200])
    return json.loads(text[text.find('['):text.rfind(']') + 1])


def valid(row, want):
    """Every finding labelled exactly once, with a known verdict."""
    k = want.get(row.get('id') if isinstance(row, dict) else None)
    v = row.get('v') if k else None
    return (isinstance(v, list) and all(isinstance(x, dict) for x in v)
            and sorted(x.get('n') for x in v if isinstance(x.get('n'), int)) == list(range(1, k + 1))
            and all(x.get('verdict') in VERDICTS for x in v))


def summary(todo, path, exact_only):
    sev = {i['id']: [f['severity'] for f in i['findings']] for i in todo if i['exact'] or not exact_only}
    total, by = Counter(), defaultdict(Counter)
    print('runs with exact Codex JSON:' if exact_only else 'all runs, incl. findings pieced together by regex:')
    for row in map(json.loads, open(path)):
        if row['id'] not in sev:
            continue
        for v in row['v']:
            total[v['verdict']] += 1
            by[sev[row['id']][v['n'] - 1]][v['verdict']] += 1
    n = sum(total.values())
    said = n - total['unaddressed']
    if not said:
        print('no labelled findings')
        return
    print(f"{n} findings; Claude stated a verdict on {said} ({said / n:.0%})")
    for k in VERDICTS[:-1]:
        print(f"  {k:17} {total[k]:4}  {total[k] / said:6.1%} of stated")
    for s in ('high', 'medium', 'low'):
        b = by[s]
        m = sum(b.values()) - b['unaddressed']
        if m:
            print(f"  {s:6} n={m:3}  " + '  '.join(f"{k} {b[k] / m:.0%}" for k in VERDICTS[:-1]))


def main():
    args = sys.argv[1:]

    def opt(k, d):
        if k not in args:
            return d
        i = args.index(k)
        v = args[i + 1]
        del args[i:i + 2]
        return v
    out_dir = os.path.abspath(opt('--out', 'critic_verdicts'))
    jobs, per, limit = int(opt('--jobs', 2)), int(opt('--per', 5)), int(opt('--limit', 10**9))
    root = os.path.expanduser(args[0] if args else '~/.claude/projects')
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, 'verdicts.jsonl')

    todo = items(root)
    done = {json.loads(l)['id'] for l in open(path)} if os.path.exists(path) else set()
    new = [i for i in todo if i['id'] not in done][:limit]
    batches = [new[k:k + per] for k in range(0, len(new), per)]
    print(f"labelling {len(new)} runs in {len(batches)} calls, {jobs} at a time", flush=True)
    with ThreadPoolExecutor(jobs) as ex, open(path, 'a') as out:
        futures = [ex.submit(label, b, out_dir) for b in batches]
        for b, fut in zip(batches, futures):
            try:
                rows = fut.result()
            except Exception as err:  # failed batches are retried on the next run
                print('batch failed:', str(err)[:200], flush=True)
                if 'usage limit' in str(err):
                    ex.shutdown(cancel_futures=True)
                    break
                continue
            want = {i['id']: len(i['findings']) for i in b}
            for row in rows:
                if valid(row, want):
                    out.write(json.dumps(row) + '\n')
            out.flush()
    summary(todo, path, exact_only=True)
    summary(todo, path, exact_only=False)


if __name__ == '__main__':
    main()
