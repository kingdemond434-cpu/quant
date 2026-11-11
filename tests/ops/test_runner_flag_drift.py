"""RUNNER FLAG DRIFT (Hourly pass idea 627, 2026-11-11).

The FrontierAudit class: a runner (a .cmd, a .ps1, an hourly `_producer` leg) calls a Python
script with a flag the script's argparse no longer declares. argparse exits 2 on an unknown flag,
so the stage never runs, and on a scheduled box task nobody sees it. This fence reads every
runner in the tree, finds each `<script>.py --flag` it passes, and checks the flag against the
option strings that script's argparse declares (read statically, by AST: nothing is imported or
run). A script that does not use argparse, or uses `parse_known_args`, is not judged here.
"""

from __future__ import annotations

import ast
import re
import subprocess
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: `<path>.py` followed by its arguments on the same line, in a .cmd or .ps1 runner.
_CALL = re.compile(r"""([\w.:\\/-]+\.py)["')]*((?:\s+(?:"[^"]*"|'[^']*'|[^\s|&>;)]+))*)""")
_FLAG = re.compile(r"^--[A-Za-z][\w-]*$")
#: hourly_cycle `_producer("leg", "path.py", "--flag", ...)`.
_PRODUCER = re.compile(
    r"""_producer\(\s*["'][\w-]+["']\s*,\s*["']([\w./-]+\.py)["']"""
    r"""((?:\s*,\s*["'][^"']*["'])*)"""
)


def _tracked(*globs: str) -> list[Path]:
    out = subprocess.run(["git", "ls-files", *globs], cwd=ROOT, capture_output=True, text=True,
                         check=True).stdout.split()  # fmt: skip
    return [ROOT / p for p in out]


def _resolve(raw: str, runner: Path) -> Path | None:
    rel = raw.replace("\\", "/").strip("\"'")
    rel = re.sub(r"^.*?(?=(desks|libs|scripts|ops|tools)/)", "", rel)
    for base in (ROOT, ROOT / "desks" / "mt5", runner.parent):
        p = base / rel
        if p.is_file():
            return p
    return None


@cache
def declared(script: Path) -> frozenset[str] | None:
    """Every option string the script's argparse declares, or None when it is not judged."""
    try:
        tree = ast.parse(script.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return None
    flags: set[str] = set()
    uses_argparse = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr in ("parse_known_args", "parse_known_intermixed_args"):
            return None
        if node.func.attr in ("parse_args", "parse_intermixed_args"):
            uses_argparse = True
        if node.func.attr == "add_argument":
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    flags.add(a.value)
                elif not isinstance(a, ast.Constant):
                    return None  # a computed option name: cannot be read statically
    if not uses_argparse:
        return None
    return frozenset(flags | {"-h", "--help"})


def _accepts(flag: str, have: frozenset[str]) -> bool:
    # argparse accepts any unambiguous prefix of a long option (allow_abbrev, the default)
    name = flag.split("=", 1)[0]
    return name in have or sum(1 for h in have if h.startswith(name)) == 1


def calls() -> list[tuple[str, Path, str]]:
    """(runner:line, script, flag) for every flag a runner passes to a judged script."""
    out = []
    for runner in _tracked("*.cmd", "*.ps1", "*.bat"):
        try:
            text = runner.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            s = line.strip()
            if s.lower().startswith(("rem ", "::", "#")):
                continue
            for m in _CALL.finditer(line):
                script = _resolve(m.group(1), runner)
                if script is None:
                    continue
                for tok in m.group(2).split():
                    tok = tok.strip("\"'")
                    if _FLAG.match(tok.split("=", 1)[0]):
                        out.append((f"{runner.relative_to(ROOT)}:{n}", script, tok))
    hc = ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py"
    text = hc.read_text(encoding="utf-8")
    for m in _PRODUCER.finditer(text):
        script = _resolve(m.group(1), hc)
        if script is None:
            continue
        n = text.count("\n", 0, m.start()) + 1
        for tok in re.findall(r"""["']([^"']*)["']""", m.group(2)):
            if _FLAG.match(tok.split("=", 1)[0]):
                out.append((f"{hc.relative_to(ROOT)}:{n}", script, tok))
    return out


def drift() -> list[str]:
    bad = []
    for where, script, flag in calls():
        have = declared(script)
        if have is not None and not _accepts(flag, have):
            bad.append(f"{where}: {script.relative_to(ROOT)} has no {flag.split('=', 1)[0]}")
    return sorted(set(bad))


def test_no_runner_passes_a_flag_its_script_does_not_declare() -> None:
    bad = drift()
    why = "runner flag drift (argparse exits 2, the stage never runs):\n"
    assert bad == [], why + "\n".join(bad)


def test_the_fence_sees_the_runners() -> None:
    """It must actually be reading something: the frontier audit's --apply calls are judged."""
    found = [c for c in calls() if "run_frontier_audit.cmd" in c[0]]
    assert len(found) >= 10
    assert sum(1 for _, s, _ in found if declared(s) is not None) >= 5


def test_the_fence_catches_the_class(tmp_path: Path) -> None:
    s = tmp_path / "x.py"
    s.write_text("import argparse\nap = argparse.ArgumentParser()\nap.add_argument('--dry')\n"
                 "ap.parse_args()\n")  # fmt: skip
    have = declared(s)
    assert have is not None
    assert not _accepts("--apply", have) and _accepts("--dry", have) and _accepts("--dr", have)
    k = tmp_path / "k.py"
    k.write_text("import argparse\nap = argparse.ArgumentParser()\nap.parse_known_args()\n")
    assert declared(k) is None
