"""
Read a Bash command the way the collab gate needs to: which repos it touches,
whether it changes anything, which files it writes, and whether it is one of
the git or deploy operations that hurt other agents in a shared tree.

This is a heuristic, deliberately biased one way: an unknown command counts as
state-changing. The cost of a false positive is one `collab intent` the agent
had to run anyway; the cost of a false negative is an agent editing a shared
tree through Bash without anyone knowing, which is the hole this closes.
Nothing here executes the command or touches the network.
"""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

HOME = Path.home()

READ_ONLY = {
    "cat", "less", "more", "head", "tail", "ls", "ll", "tree", "grep", "egrep", "fgrep",
    "rg", "ag", "wc", "file", "stat", "du", "df", "pwd", "echo", "printf", "which", "type",
    "whereis", "date", "id", "whoami", "ps", "pgrep", "jq", "yq", "diff", "cmp", "sort",
    "uniq", "cut", "tr", "column", "nl", "basename", "dirname", "realpath", "readlink",
    "sha1sum", "md5sum", "sha256sum", "true", "false", "test", "[", "sleep", "awk", "sed",
    "find", "fd", "curl", "env", "printenv", "uname", "hostname", "lsof", "ss",
    "free", "uptime", "top", "htop", "nproc", "xxd", "od", "hexdump", "strings", "tac",
    "comm", "join", "paste", "fold", "fmt", "expand", "base64", "cd", "pushd", "popd",
    "export", "set", "unset", "command", "hash", "history", "collab",
    "systemctl", "journalctl", "dpkg", "apt", "man", "help", "tldr", "zcat", "bat",
}

# Wrappers whose real command is further along the line.
WRAPPERS = {"sudo", "time", "nice", "ionice", "timeout", "nohup", "stdbuf", "env", "xargs",
            "command", "exec"}

GIT_READ_ONLY = {"status", "diff", "log", "show", "rev-parse", "ls-files", "blame", "grep",
                 "describe", "shortlog", "reflog", "cat-file", "ls-tree", "fetch",
                 "for-each-ref", "merge-base", "name-rev", "rev-list", "whatchanged",
                 "count-objects", "check-ignore", "var", "help", "version"}

DEPLOY_PATTERNS = [
    re.compile(p) for p in (
        r"(^|/)dn_deploy$", r"(^|/)chat-ship$", r"(^|/)deploy[_-][\w.-]*$",
        r"(^|/)[\w.-]*deploy[\w.-]*\.(sh|py|js|mjs)$",
    )
]

APPS = HOME / "Applications"

# Deploy commands that run from anywhere and name no path: which app they ship.
DEPLOY_REPO_HINTS = [
    (re.compile(r"(^|/)(dn[-_]deploy|deploy[-_]delta[-_]note)$"), APPS / "Delta-Note"),
    (re.compile(r"(^|/)deploy[-_]delta[-_]drills"), APPS / "Delta-Drills-Local"),
]
CHAT_SHIP_APPS = {"dn": APPS / "Delta-Note", "drills": APPS / "Delta-Drills-Local"}

OPS = {";", "&&", "||", "|", "&", "|&", "(", ")", "\n"}
REDIRECTS = {">", ">>", ">|", "&>", "&>>", "<>"}
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][\w-]*)\1")


@dataclass
class Segment:
    words: List[str]
    cwd: Path
    redirect_targets: List[Path] = field(default_factory=list)


@dataclass
class Scan:
    # repo root -> was anything in it changed by this command?
    repos: Dict[str, bool] = field(default_factory=dict)
    writes: List[Path] = field(default_factory=list)       # files the command writes
    git_risky: List[Tuple[str, str]] = field(default_factory=list)   # (repo, why)
    git_commit: List[str] = field(default_factory=list)    # repos with a commit
    deploys: List[Tuple[str, str]] = field(default_factory=list)     # (repo or '', cmd)
    collab_only: bool = False
    parse_failed: bool = False


# ---------------------------------------------------------------------------
# Repo discovery without a subprocess: this runs on every Bash call.
# ---------------------------------------------------------------------------

_root_cache: Dict[str, Optional[str]] = {}


def repo_root(path: Path) -> Optional[str]:
    """Worktree root containing `path`, or None. $HOME itself never counts."""
    try:
        probe = path if path.is_dir() else path.parent
        probe = probe.resolve()
    except OSError:
        return None
    key = str(probe)
    if key in _root_cache:
        return _root_cache[key]
    found = None
    for candidate in [probe, *probe.parents]:
        if candidate == HOME or candidate == Path("/"):
            break
        if (candidate / ".git").exists():
            found = str(candidate)
            break
    _root_cache[key] = found
    return found


# ---------------------------------------------------------------------------
# Tokenising
# ---------------------------------------------------------------------------

def _strip_heredocs(command: str) -> str:
    """Drop heredoc bodies: they are data, and their quotes break shlex."""
    lines = command.split("\n")
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        delims = [m.group(2) for m in HEREDOC.finditer(line)]
        i += 1
        for delim in delims:
            while i < len(lines) and lines[i].strip() != delim:
                i += 1
            i += 1
    return "\n".join(out)


def _tokens(command: str) -> List[str]:
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=";&|()<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def _expand(word: str, cwd: Path) -> Path:
    word = os.path.expandvars(word)
    path = Path(word).expanduser()
    return path if path.is_absolute() else cwd / path


def _looks_like_path(word: str) -> bool:
    return (word.startswith(("/", "~", "./", "../", "$HOME")) or "/" in word) \
        and not word.startswith(("http://", "https://", "-")) and len(word) < 400


def segments(command: str, cwd: Path) -> List[Segment]:
    toks = _tokens(_strip_heredocs(command))
    segs, words, redirects, here = [], [], [], cwd
    i = 0
    while i < len(toks):
        tok = toks[i]
        if tok in OPS or (set(tok) <= set(";&|()") and tok):
            if words:
                segs.append(Segment(words, here, redirects))
                here = _after_cd(words, here)
            words, redirects = [], []
        elif tok in REDIRECTS or (set(tok) <= set("<>&|") and ">" in tok):
            target = toks[i + 1] if i + 1 < len(toks) else ""
            i += 1
            if target and not target.isdigit() and not target.startswith("/dev/") \
                    and target not in ("&", "-"):
                redirects.append(_expand(target, here))
        elif tok in ("<", "<<", "<<<"):
            i += 1  # input redirect: the next token is a source, not an argument
        else:
            # A trailing fd number glued before a redirect (`2>`) arrives as its own word.
            if tok.isdigit() and i + 1 < len(toks) and toks[i + 1].startswith(">"):
                pass
            else:
                words.append(tok)
        i += 1
    if words:
        segs.append(Segment(words, here, redirects))
    return segs


def _after_cd(words: List[str], here: Path) -> Path:
    if words and words[0] in ("cd", "pushd") and len(words) > 1:
        return _expand(words[1], here)
    if words and words[0] in ("cd",) and len(words) == 1:
        return HOME
    return here


def _strip_wrappers(words: List[str]) -> List[str]:
    out = list(words)
    while out:
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", out[0]):
            out = out[1:]
            continue
        head = Path(out[0]).name
        if head in WRAPPERS and len(out) > 1:
            out = out[1:]
            while out and (out[0].startswith("-") or re.match(r"^\d+[smhd]?$", out[0])):
                out = out[1:]
            continue
        break
    return out


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _git_parts(words: List[str], here: Path) -> Tuple[Path, List[str]]:
    rest, where = words[1:], here
    while rest and rest[0].startswith("-"):
        if rest[0] == "-C" and len(rest) > 1:
            where = _expand(rest[1], where)
            rest = rest[2:]
        elif rest[0] in ("-c", "--git-dir", "--work-tree") and len(rest) > 1:
            rest = rest[2:]
        else:
            rest = rest[1:]
    return where, rest


def _git(words: List[str], seg: Segment, scan: Scan) -> Tuple[Path, bool]:
    where, rest = _git_parts(words, seg.cwd)
    sub = rest[0] if rest else ""
    args = rest[1:]
    root = repo_root(where)
    flags = set(a for a in args if a.startswith("-"))
    paths = [a for a in args if not a.startswith("-")]
    if sub in GIT_READ_ONLY:
        return where, False
    if sub == "config" and (flags & {"--get", "--get-all", "--get-regexp", "-l", "--list"}
                            or (len(paths) == 1 and not flags)):
        return where, False
    if sub == "remote" and (not paths or paths[0] in ("show", "get-url")):
        return where, False
    if sub == "branch" and not flags & {"-d", "-D", "-m", "-M", "--delete", "--move"} and not paths:
        return where, False
    if sub == "stash" and (args[:1] in (["list"], ["show"])):
        return where, False
    if sub == "worktree" and args[:1] == ["list"]:
        return where, False
    if sub == "tag" and (not paths or flags & {"-l", "--list"}):
        return where, False

    risky = None
    if sub == "stash":
        risky = "`git stash` sweeps every agent's uncommitted work out of the shared tree"
    elif sub == "add" and (flags & {"-A", "--all", "-u", "--update"} or "." in paths or ":/" in paths):
        risky = "`git add -A`/`.` stages other agents' in-flight edits; stage explicit paths"
    elif sub == "commit" and (flags & {"-a", "--all"} or any(re.match(r"^-[a-zA-Z]*a", f) for f in flags)):
        risky = "`git commit -a` commits other agents' in-flight edits; stage explicit paths"
    elif sub == "reset" and "--hard" in flags:
        risky = "`git reset --hard` destroys other agents' uncommitted work"
    elif sub == "clean":
        risky = "`git clean` deletes other agents' untracked files"
    elif sub in ("checkout", "restore") and ("." in paths or ":/" in paths):
        risky = f"`git {sub} .` throws away other agents' uncommitted edits"
    elif sub == "switch" or (sub == "checkout" and "-b" in flags) or (
            sub == "checkout" and paths and "--" not in args
            and not any(_expand(p, where).exists() for p in paths)):
        risky = "switching branch in a shared worktree moves every agent's files under them; " \
                "use `agent-worktree new <name>` for a separate branch"
    if risky and root:
        scan.git_risky.append((root, risky))

    if sub in ("add", "rm", "mv", "restore", "checkout") and root:
        for p in paths:
            if p != "--":
                scan.writes.append(_expand(p, where))
    if sub == "commit" and root:
        scan.git_commit.append(root)
    if sub == "push" and root:
        scan.deploys.append((root, " ".join(words)[:160]))
    return where, True


def _file_writes(cmd: str, args: List[str], seg: Segment) -> Tuple[bool, List[Path]]:
    """(is this segment state-changing, files it writes)."""
    paths = [a for a in args if not a.startswith("-")]
    if cmd == "sed" or cmd == "perl":
        inplace = any(a == "-i" or a.startswith("-i") or a.startswith("--in-place") for a in args)
        if not inplace:
            return False, []
        files = [p for p in paths[1:]] if cmd == "sed" and not any(
            a in ("-e", "-f") for a in args) else paths
        return True, [_expand(p, seg.cwd) for p in files if _expand(p, seg.cwd).exists()]
    if cmd == "awk":
        return ("-i" in args), []
    if cmd in ("find", "fd"):
        return bool(set(args) & {"-delete", "-exec", "-execdir", "-ok", "-fprint", "-x", "-X"}), []
    if cmd == "curl":
        out = any(a in ("-o", "-O", "--output", "--remote-name") for a in args)
        return out, []
    if cmd == "wget":  # writes a file by default unless told to print to stdout
        return not any(a in ("-O-", "-qO-", "--spider") for a in args), []
    if cmd == "sort" and any(a == "-o" or a.startswith("--output") for a in args):
        i = args.index("-o") if "-o" in args else -1
        return True, [_expand(args[i + 1], seg.cwd)] if 0 <= i < len(args) - 1 else []
    if cmd == "tee":
        return True, [_expand(p, seg.cwd) for p in paths]
    if cmd in ("rm", "touch", "truncate", "shred", "unlink", "rmdir", "mkdir", "chmod", "chown"):
        return True, [_expand(p, seg.cwd) for p in paths]
    if cmd in ("cp", "mv", "install", "ln", "rsync"):
        targets = [_expand(p, seg.cwd) for p in paths]
        if cmd == "mv":
            return True, targets
        return True, targets[-1:]
    if cmd in ("systemctl", "apt", "dpkg") and any(a in ("start", "stop", "restart", "install",
                                                         "remove", "enable", "disable") for a in args):
        return True, []
    return cmd not in READ_ONLY, []


def scan(command: str, cwd: str) -> Scan:
    result = Scan()
    here = Path(cwd or HOME)
    try:
        segs = segments(command, here)
    except ValueError:
        result.parse_failed = True
        segs = [Segment(command.split(), here)]

    collab_only = True
    for seg in segs:
        words = _strip_wrappers(seg.words)
        if not words:
            continue
        cmd = Path(words[0]).name
        where = seg.cwd
        if cmd not in ("collab", "cd", "pushd", "popd", "echo", "true", ":"):
            collab_only = False

        if cmd == "git":
            where, mutating = _git(words, seg, result)
            writes = []
        else:
            mutating, writes = _file_writes(cmd, words[1:], seg)
            if any(p.search(words[0]) for p in DEPLOY_PATTERNS) or (
                    cmd in ("vercel",) and ("--prod" in words or "deploy" in words)) or (
                    cmd in ("fly", "flyctl") and "deploy" in words) or (
                    cmd in ("npm", "pnpm", "yarn", "bun") and "deploy" in " ".join(words[1:3])):
                hinted = next((str(r) for rx, r in DEPLOY_REPO_HINTS if rx.search(words[0])), "")
                if cmd == "chat-ship" and len(words) > 1 and words[1] in CHAT_SHIP_APPS:
                    hinted = str(CHAT_SHIP_APPS[words[1]])
                root = repo_root(where) or (repo_root(Path(hinted)) if hinted else None) or ""
                result.deploys.append((root, " ".join(words)[:160]))
                if root:
                    result.repos[root] = True
                mutating = True

        # A redirect changes the file it names, not the repo the command ran in:
        # `cd app && git log > /tmp/x` reads the app and writes outside it.
        if seg.redirect_targets:
            collab_only = False
            writes = writes + list(seg.redirect_targets)
            for target in seg.redirect_targets:
                root = repo_root(target)
                if root:
                    result.repos[root] = True

        result.writes.extend(writes)
        touched: Set[str] = set()
        base = repo_root(where)
        if base:
            touched.add(base)
        for word in words[1:]:
            if _looks_like_path(word):
                root = repo_root(_expand(word, seg.cwd))
                if root:
                    touched.add(root)
        for target in writes:
            root = repo_root(target)
            if root:
                touched.add(root)
        for root in touched:
            result.repos[root] = result.repos.get(root, False) or (mutating and cmd != "collab")

    result.collab_only = collab_only
    for i, (root, cmd) in enumerate(result.deploys):
        if not root:
            # A deploy script run from ~ (`dn_deploy beta`) names no path; fall
            # back to whichever single repo the command touched, if any.
            if len(result.repos) == 1:
                result.deploys[i] = (next(iter(result.repos)), cmd)
    return result
