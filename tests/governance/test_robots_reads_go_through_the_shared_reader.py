"""LAW: every robots.txt read goes through libs/data/robots_body.py, which fails CLOSED.

`urllib.robotparser.RobotFileParser` parses whatever body came back, and an HTML page served 200
at /robots.txt (soft 404, WAF/challenge page, homepage after a redirect) parses to NO rules, which
means allow-all. Four audit holds of that one defect class in one day (#1341) are why this is a
law test, not a review note. The shared reader refuses an HTML body, treats 401/403/429/451 as a
hard stop and only 404/410 as empty rules.

A non-test .py file VIOLATES when it
  (a) constructs a `RobotFileParser` itself (only the shared reader may), or
  (b) holds a "/robots.txt" URL or path literal without importing `libs.data.robots_body`.

ALLOWLIST below: files this branch could not migrate, each with its reason. The list only
shrinks: an entry whose file no longer violates fails this test until it is removed.
"""
from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = "libs/data/robots_body.py"
_URL = re.compile(r"(?:https?://\S*)?/robots\.txt")

#: path -> why it still reads robots.txt on its own. Remove the entry when the file migrates.
ALLOWLIST: dict[str, str] = {
    "desks/mt5/research/deep_forest_miner.py":
        "already fail-closed (the model reader); open PRs #1320/#1181/#1168/#1038 change it",
    "desks/mt5/research/asia_collector.py":
        "already fail-closed (HTML refused, 401/403/429/451 stop); open PR #942 changes it",
}


def _is_test(rel: str) -> bool:
    parts = rel.split("/")
    return "tests" in parts or parts[-1].startswith("test_") or parts[-1] == "conftest.py"


def _imports_shared(node: ast.AST) -> bool:
    if isinstance(node, ast.ImportFrom):
        if node.module == "libs.data.robots_body":
            return True
        return node.module == "libs.data" and any(a.name == "robots_body" for a in node.names)
    if isinstance(node, ast.Import):
        return any(a.name == "libs.data.robots_body" for a in node.names)
    return False


def violations(rel: str, source: str) -> list[str]:
    """Why `rel` reads robots.txt around the shared reader; empty when it does not."""
    if rel == SHARED:
        return []
    tree = ast.parse(source)
    ctor: list[int] = []
    urls: list[int] = []
    shared = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else (
                fn.attr if isinstance(fn, ast.Attribute) else "")
            if name == "RobotFileParser":
                ctor.append(node.lineno)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _URL.fullmatch(node.value):
                urls.append(node.lineno)
        elif _imports_shared(node):
            shared = True
    out = [f"{rel}:{n}: constructs RobotFileParser outside {SHARED}" for n in ctor]
    if urls and not shared:
        out += [f"{rel}:{n}: robots.txt URL without importing libs.data.robots_body"
                for n in urls]
    return out


def _tree_files() -> list[str]:
    got = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout.split()
    return [f for f in got if not _is_test(f)]


def _scan() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for rel in _tree_files():
        try:
            src = (ROOT / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            bad = violations(rel, src)
        except SyntaxError:
            continue
        if bad:
            found[rel] = bad
    return found


def test_every_robots_read_goes_through_the_shared_reader() -> None:
    found = _scan()
    rogue = {k: v for k, v in found.items() if k not in ALLOWLIST}
    assert not rogue, ("robots.txt read around libs/data/robots_body.py (an HTML body would "
                       "read as allow-all):\n" + "\n".join(x for v in rogue.values() for x in v))


def test_the_allowlist_only_shrinks() -> None:
    found = _scan()
    stale = sorted(k for k in ALLOWLIST if k not in found)
    assert not stale, f"migrated or gone, remove from ALLOWLIST: {stale}"
    assert all(why.strip() for why in ALLOWLIST.values())


def test_the_detector_catches_the_defect_shapes() -> None:
    bad = ("import urllib.robotparser\n"
           "def f(h):\n"
           "    rp = urllib.robotparser.RobotFileParser()\n"
           "    rp.set_url(f'https://{h}/robots.txt')\n")
    assert len(violations("x/mod.py", bad)) == 2
    assert violations("x/mod.py", "from urllib.robotparser import RobotFileParser\n"
                                   "rp = RobotFileParser()\n")
    assert violations("x/mod.py", "u = base + '/robots.txt'\n")
    assert violations("x/mod.py", "U = 'https://example.org/robots.txt'\n")
    ok = ("from libs.data.robots_body import robots_rules_or_refusal\n"
          "def f(h):\n"
          "    return robots_rules_or_refusal(200, None, get(f'https://{h}/robots.txt'))\n")
    assert violations("x/mod.py", ok) == []
    assert violations("x/mod.py", "from libs.data import robots_body as rb\n"
                                  "u = h + '/robots.txt'\n") == []
    # Prose that merely names a robots file is not a read.
    assert violations("x/mod.py", "NOTE = 'bis.org/robots.txt carries Disallow: /doclist/'\n") == []
