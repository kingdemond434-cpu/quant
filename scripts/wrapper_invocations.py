"""Read every Python organ a Windows wrapper or installer launches, statically.

Shared by tests/ops/test_wrapper_organ_flags.py (flags vs the organ's argparse),
tests/ops/test_mt5_tasks_run_interactive.py (MT5 organs vs the task principal) and
scripts/task_time_limits.py (ExecutionTimeLimit vs measured run time). Nothing here imports or
runs an organ: wrappers are tokenised, organs are read from their AST.
"""
from __future__ import annotations

import ast
import re
import subprocess
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_WRAPPER_SUFFIXES = (".cmd", ".ps1", ".bat")
_SKIP_PARTS = {"_retired", ".git", ".venv", "node_modules"}
#: where `-m pkg.mod` resolves from: the repo root and the desk root (PYTHONPATH on the box).
_MODULE_ROOTS = ("", "desks/mt5/")
_TERMINATORS = {">>", ">", "2>&1", "1>&2", "2>", "|", "||", "&&", "&", ";", ")", "2>>"}


def _tracked(suffixes: tuple[str, ...]) -> list[str]:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True,
                             text=True, timeout=60, check=True).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        out = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file()]
    return [p for p in out if p.endswith(suffixes) and not (_SKIP_PARTS & set(p.split("/")))
            and (ROOT / p).is_file()]  # a sparse checkout lists files it does not hold


@cache
def _py_index() -> dict[str, list[str]]:
    """basename -> tracked .py paths, for suffix resolution of a wrapper's path."""
    idx: dict[str, list[str]] = {}
    for p in _tracked((".py",)):
        idx.setdefault(p.rsplit("/", 1)[-1], []).append(p)
    return idx


def resolve_script(raw: str) -> str | None:
    """A wrapper's path token -> the ONE tracked .py it names, or None when it names none."""
    tok = raw.strip("\"'").replace("\\", "/")
    parts = [p for p in tok.split("/") if p and "$" not in p and "%" not in p and "{" not in p]
    if not parts:
        return None
    cands = _py_index().get(parts[-1], [])
    for n in range(len(parts), 0, -1):  # the longest suffix that matches exactly one file
        suffix = "/".join(parts[-n:])
        hits = [c for c in cands if c == suffix or c.endswith("/" + suffix)]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1 and n == len(parts):
            return None  # ambiguous even at full depth: not ours to guess
    return None


def resolve_module(mod: str) -> str | None:
    rel = mod.replace(".", "/")
    tracked = set(_tracked((".py",)))
    for base in _MODULE_ROOTS:
        for cand in (f"{base}{rel}.py", f"{base}{rel}/__main__.py"):
            if cand in tracked:
                return cand
    return None


def _join_continuations(text: str) -> list[tuple[int, str]]:
    """Logical lines (1-based start line, text): cmd `^` and PowerShell backtick joined."""
    out: list[tuple[int, str]] = []
    buf, start = "", 0
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.rstrip()
        if not buf:
            start = i
        if stripped.endswith(("^", "`")):
            buf += stripped[:-1] + " "
            continue
        out.append((start, buf + line))
        buf = ""
    if buf:
        out.append((start, buf))
    return out


def _is_comment(line: str, suffix: str) -> bool:
    s = line.strip().lower()
    if suffix == ".ps1":
        return s.startswith("#")
    return s.startswith(("rem ", "rem\t", "::", "@rem ")) or s == "rem"


def _tokens_after(line: str, end: int) -> list[str]:
    """Shell-ish tokens from `end` to the end of the enclosing string (or of the line)."""
    # Which quoted string (if any) holds position `end - 1`? One with a span that runs PAST the
    # .py is an argument string (`-Argument '... x.py --a >> log'`), and its close ends the args;
    # one that closes exactly at the .py is just a quoted path, and args continue outside it.
    quote = ""
    for ch in line[:end]:
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
    rest = line[end:]
    if quote:
        close = rest.find(quote)
        if close == 0:
            rest = rest[1:]  # a quoted path: args follow on the line
        elif close > 0:
            rest = rest[:close]
    toks: list[str] = []
    for tok in re.findall(r'"[^"]*"|\'[^\']*\'|\S+', rest):
        if tok in _TERMINATORS or tok.startswith((">>", "2>", "|")):
            break
        toks.append(tok.strip("\"'"))
    return toks


_PY_RE = re.compile(r"[^\s\"'(]*?\.py\b")
_MOD_RE = re.compile(r"(?:^|\s)-m\s+([A-Za-z_][\w.]*)")


def invocations(rel: str) -> list[tuple[int, str, list[str]]]:
    """(line, script, flags) for every Python organ a wrapper launches."""
    suffix = "." + rel.rsplit(".", 1)[-1].lower()
    text = (ROOT / rel).read_text("utf-8", errors="replace")
    found: list[tuple[int, str, list[str]]] = []
    for lineno, line in _join_continuations(text):
        if _is_comment(line, suffix):
            continue
        if suffix == ".ps1":
            line = line.split(" #", 1)[0] if " #" in line and "'" not in line else line
        hits: list[tuple[int, str]] = []
        for m in _PY_RE.finditer(line):
            tok = m.group(0)
            if tok.lower().endswith((".python.py",)) or "*" in tok:
                continue
            script = resolve_script(tok)
            if script:
                hits.append((m.end(), script))
        for m in _MOD_RE.finditer(line):
            script = resolve_module(m.group(1))
            if script:
                hits.append((m.end(), script))
        for end, script in hits:
            flags = [t.split("=", 1)[0] for t in _tokens_after(line, end)
                     if t.startswith("--") and len(t) > 2 and not re.search(r"[$%{]", t)]
            found.append((lineno, script, flags))
    return found


@cache
def accepted(script: str) -> tuple[str, frozenset[str]]:
    """('argparse', options) | ('lenient', {}) | ('literal', source string literals)."""
    src = (ROOT / script).read_text("utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return "lenient", frozenset()
    opts: set[str] = set()
    has_parser = lenient = False
    literals: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.add(node.value)
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name == "ArgumentParser":
            has_parser = True
        elif name in {"parse_known_args", "parse_known_intermixed_args"}:
            lenient = True
        elif name == "add_argument":
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                        and a.value.startswith("-"):
                    opts.add(a.value)
            for kw in node.keywords:
                if kw.arg == "nargs" and isinstance(kw.value, ast.Attribute) \
                        and kw.value.attr == "REMAINDER":
                    lenient = True
    if lenient:
        return "lenient", frozenset()
    if has_parser or opts:
        return "argparse", frozenset(opts | {"--help"})
    return "literal", frozenset(literals)


def flag_ok(flag: str, kind: str, opts: frozenset[str]) -> bool:
    if kind == "lenient":
        return True
    if kind == "literal":
        return any(flag in s for s in opts)
    if flag in opts:
        return True
    longs = [o for o in opts if o.startswith("--") and o.startswith(flag)]
    return len(longs) == 1  # argparse allow_abbrev: a unique prefix is accepted


def mismatches() -> list[str]:
    bad = []
    for rel in _tracked(_WRAPPER_SUFFIXES):
        for lineno, script, flags in invocations(rel):
            kind, opts = accepted(script)
            for flag in flags:
                if not flag_ok(flag, kind, opts):
                    bad.append(f"{rel}:{lineno} passes {flag} to {script}, which does not "
                               f"accept it ({kind})")
    return bad
