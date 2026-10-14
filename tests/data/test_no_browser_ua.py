"""No non-test code carries a browser or named-crawler User-Agent (auditor ruling 2026-10-14).

The desk identifies itself as itself: `libs.data.polite_fetch.DESK_UA`. A browser string
("Mozilla/5.0 ... Chrome/... Safari/...") or another company's crawler name in a request is
impersonation, and a refusal of the honest name is recorded as a hold, never routed around with a
disguise. This scan reads every tracked non-test .py file's STRING LITERALS (by AST, so comments
explaining the rule do not trip it) and fails on any browser or crawler UA token. Probe scripts,
retired scripts and code templates are included: a probe that reaches a site is a fetcher.

The ONLY allow-list entry is the detection code itself -- the token tuple in polite_fetch that
`honest_headers` matches against.
"""
from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: Browser engines/products and other companies' crawlers, as they appear in a UA string.
UA_TOKEN = re.compile(
    r"mozilla/|chrome/\d|chromium/\d|crios/\d|safari/\d|applewebkit|gecko/\d|firefox/\d"
    r"|\bedg/\d|\bedge/\d|\bopr/\d|\bopera/\d|opera mini|presto/\d|msie \d|trident/\d"
    r"|googlebot|adsbot-google|bingbot|baiduspider|yandexbot|duckduckbot|applebot"
    r"|facebookexternalhit|petalbot|bytespider", re.I)

#: (file, assignment target) whose string elements ARE the detector's token list.
ALLOWED_ASSIGNMENTS = {("libs/data/polite_fetch.py", "IMPERSONATION_UA_TOKENS")}


def _is_test(rel: str) -> bool:
    parts = rel.split("/")
    name = parts[-1]
    return ("tests" in parts[:-1] or name.startswith("test_") or name.endswith("_test.py")
            or name == "conftest.py")


def _tracked_py() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files", "-z", "--", "*.py"], cwd=ROOT,
                             capture_output=True, check=True, timeout=60).stdout
        files = [f for f in out.decode("utf-8", "replace").split("\0") if f]
    except (OSError, subprocess.SubprocessError):
        files = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.py")
                 if ".git" not in p.parts and ".claude" not in p.parts]
    return sorted(f for f in files if not _is_test(f))


def _allowed_nodes(tree: ast.AST, rel: str) -> set[int]:
    keep: set[int] = set()
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for t in targets:
            if isinstance(t, ast.Name) and (rel, t.id) in ALLOWED_ASSIGNMENTS:
                keep.update(id(n) for n in ast.walk(node))
    return keep


def browser_ua_literals(rel: str, src: str) -> list[int]:
    """Line numbers of string literals in `src` that carry a browser/crawler UA token."""
    if not UA_TOKEN.search(src):
        return []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return [0]
    allowed = _allowed_nodes(tree, rel)
    return sorted({n.lineno for n in ast.walk(tree)
                   if isinstance(n, ast.Constant) and isinstance(n.value, str)
                   and id(n) not in allowed and UA_TOKEN.search(n.value)})


def test_no_non_test_file_carries_a_browser_ua() -> None:
    hits: dict[str, list[int]] = {}
    scanned = 0
    for rel in _tracked_py():
        p = ROOT / rel
        if not p.is_file():
            continue                      # sparse checkout: not on disk here
        scanned += 1
        lines = browser_ua_literals(rel, p.read_text(encoding="utf-8", errors="replace"))
        if lines:
            hits[rel] = lines
    assert scanned > 100, f"scanned only {scanned} files -- the walk is broken, not the code clean"
    assert not hits, ("browser/crawler User-Agent literals in non-test code (use "
                      f"libs.data.polite_fetch.DESK_UA): {hits}")


def test_the_scanner_catches_what_it_must_and_spares_the_detector() -> None:
    assert browser_ua_literals("x.py", 'UA = "Mozilla/5.0 (X11) AppleWebKit/537.36"\n') == [1]
    assert browser_ua_literals("x.py", 'h = {"User-Agent": "Googlebot/2.1"}\n') == [1]
    assert browser_ua_literals("x.py", 'h = {"User-Agent": "Opera/9.80 Presto/2.12"}\n') == [1]
    assert browser_ua_literals("x.py", 'tpl = """\\nua = \\"Chrome/125.0\\"\\n"""\n') == [1]
    # a comment is not a literal, and "operations" is not Opera
    assert browser_ua_literals("x.py", '# Mozilla/5.0 was here\nx = "operations"\n') == []
    detector = 'IMPERSONATION_UA_TOKENS = ("mozilla/", "googlebot")\n'
    assert browser_ua_literals("libs/data/polite_fetch.py", detector) == []
    assert browser_ua_literals("libs/data/other.py", detector) == [1]
