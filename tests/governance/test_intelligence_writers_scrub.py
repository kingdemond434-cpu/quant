"""Every module that writes under an intelligence root goes through the credential scrub.

A Google API key reached three tracked intelligence artifacts on a public repository because
the producers wrote scraped text verbatim (#246). Scrubbing three of them was not a fix: the
audit counted 189 modules touching data/intelligence. This fence finds every non-test module
that WRITES to a path under an `intelligence` directory and fails unless it scrubs -- by
calling `libs.ops.secret_scrub` (scrub / scrub_text / write_json / write_text / append_jsonl)
or a helper that does (`write_discoveries`, `save_hypothesis`).

The commit boundary scrubs again (`python -m libs.ops.secret_scrub --staged` in
ops/githooks/pre-commit, `--tree` in the VPS intelligence commit and the box's intel-ship
adoption), so a module this scan cannot see still cannot publish a literal; this test is what
keeps the producers themselves honest.

DETECTION. A path is an intelligence path when it is built from a string constant equal to
`intelligence` or containing an `intelligence/` segment, directly or through names assigned
from such paths (`INTEL = BASE / "data" / "intelligence"`, `out = INTEL / name`). A write is
`write_text` / `write_bytes`, `open(.., "w"|"a"|"x")`, `os.replace(.., dest)`, or any call whose
name says atomic / write / dump / save / persist with such a path in its first two arguments.
"""
from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: libs.ops.secret_scrub's own entry points: they count only in a module that imports them.
SCRUB_CALLS = frozenset({"scrub", "scrub_text", "write_json", "write_text", "append_jsonl"})
#: Shared helpers that scrub internally (pinned by test_the_shared_helpers_really_scrub).
SCRUBBING_HELPERS = frozenset({
    "write_discoveries",   # desks/mt5/side_channels/discovery_io.py scrubs before it stamps
    "save_hypothesis",     # desks/mt5/side_channels/base.py scrubs the YAML it dumps
})

#: Writers that touch an intelligence path but cannot carry a credential. Each needs a reason.
#: Empty today: every detected writer scrubs. A new entry names the file and why no scraped or
#: model-written text can reach what it writes.
ALLOWLIST: dict[str, str] = {}

_SEG = re.compile(r"(?:^|[/\\])intelligence(?:[/\\]|$)")
_PATH_CALLS = frozenset({"Path", "PurePath", "joinpath", "with_name", "with_suffix", "with_stem",
                         "resolve", "expanduser", "join", "str", "fspath"})
_WRITE_NAME = re.compile(r"atomic|write|dump|save|persist", re.I)


def _is_intel_literal(value: str) -> bool:
    return value == "intelligence" or bool(_SEG.search(value))


def _pathy(node: ast.AST, tainted: set[str]) -> bool:
    """Does this path-shaped expression lead under an intelligence directory?"""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str) and _is_intel_literal(node.value)
    if isinstance(node, ast.Name):
        return node.id in tainted
    if isinstance(node, ast.Attribute):
        return node.attr in tainted or (node.attr == "parent" and _pathy(node.value, tainted))
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.Add)):
        return _pathy(node.left, tainted) or _pathy(node.right, tainted)
    if isinstance(node, ast.JoinedStr):
        return any(_pathy(v.value if isinstance(v, ast.FormattedValue) else v, tainted)
                   for v in node.values)
    if isinstance(node, ast.Call):
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) \
            else ""
        if name in _PATH_CALLS:
            if isinstance(fn, ast.Attribute) and _pathy(fn.value, tainted):
                return True
            return any(_pathy(a, tainted) for a in node.args)
        return False
    if isinstance(node, (ast.Tuple, ast.List)):
        return any(_pathy(e, tainted) for e in node.elts)
    if isinstance(node, ast.IfExp):
        return _pathy(node.body, tainted) or _pathy(node.orelse, tainted)
    if isinstance(node, ast.Subscript):
        return _pathy(node.value, tainted)
    return False


def _bound(target: ast.AST) -> set[str]:
    out: set[str] = set()
    for e in ast.walk(target):
        if isinstance(e, ast.Name):
            out.add(e.id)
        elif isinstance(e, ast.Attribute):
            out.add(e.attr)
    return out


def _call_name(node: ast.Call) -> str:
    fn = node.func
    return fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else ""


def _writes_mode(node: ast.Call, args: list[ast.expr]) -> bool:
    def w(v: object) -> bool:
        return isinstance(v, str) and bool(set(v) & set("wax"))
    return (any(isinstance(a, ast.Constant) and w(a.value) for a in args)
            or any(k.arg == "mode" and isinstance(k.value, ast.Constant) and w(k.value.value)
                   for k in node.keywords))


def intelligence_writes(tree: ast.AST) -> list[int]:
    """Line numbers of calls in `tree` that write to an intelligence path."""
    tainted: set[str] = set()
    for _ in range(5):
        for n in ast.walk(tree):
            if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None \
                    and _pathy(n.value, tainted):
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                    tainted |= _bound(t)
            elif isinstance(n, (ast.For, ast.comprehension)):
                it = n.iter
                globbed = (isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute)
                           and it.func.attr in ("glob", "rglob", "iterdir")
                           and _pathy(it.func.value, tainted))
                if globbed or _pathy(it, tainted):
                    tainted |= _bound(n.target)
            elif isinstance(n, ast.withitem) and n.optional_vars is not None \
                    and isinstance(n.context_expr, ast.Call):
                c = n.context_expr
                fn = c.func
                if (isinstance(fn, ast.Name) and fn.id == "open" and c.args
                        and _pathy(c.args[0], tainted)) or (
                        isinstance(fn, ast.Attribute) and fn.attr == "open"
                        and _pathy(fn.value, tainted)):
                    tainted |= _bound(n.optional_vars)
    return sorted({n.lineno for n in ast.walk(tree)
                   if isinstance(n, ast.Call) and _is_write(n, tainted)})


def _is_write(n: ast.Call, tainted: set[str]) -> bool:
    """Is this call a write whose destination is an intelligence path?"""
    fn = n.func
    name = _call_name(n)
    if isinstance(fn, ast.Attribute):
        if name in ("write_text", "write_bytes"):
            return _pathy(fn.value, tainted)
        if name == "open" and _pathy(fn.value, tainted):
            return _writes_mode(n, n.args)
    if isinstance(fn, ast.Name) and name == "open" and n.args and _pathy(n.args[0], tainted):
        return _writes_mode(n, n.args[1:])
    if name in ("replace", "rename") and len(n.args) > 1 and _pathy(n.args[1], tainted):
        return True
    return bool(name and name != "dumps" and _WRITE_NAME.search(name)
                and any(_pathy(a, tainted) for a in n.args[:2]))


def _imports_scrub(tree: ast.AST) -> set[str]:
    """Local names bound to libs.ops.secret_scrub's entry points (aliases included)."""
    names: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module == "libs.ops.secret_scrub":
            names |= {a.asname or a.name for a in n.names if a.name in SCRUB_CALLS}
    return names


def _scrubs(tree: ast.AST) -> bool:
    imported = _imports_scrub(tree)
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        name = _call_name(n)
        if name in SCRUBBING_HELPERS or (name in imported and isinstance(n.func, ast.Name)):
            return True
    return False


def _candidates() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", "--", "*.py"], cwd=ROOT,
                         capture_output=True, check=True).stdout.decode().split("\0")
    return [f for f in out if f and "/tests/" not in f and not f.startswith("tests/")
            and "intelligence" in (ROOT / f).read_text("utf-8", errors="replace")]


def producers() -> dict[str, list[int]]:
    """Every tracked non-test module that writes under an intelligence directory."""
    found: dict[str, list[int]] = {}
    for rel in _candidates():
        try:
            tree = ast.parse((ROOT / rel).read_text("utf-8"))
        except SyntaxError:
            continue
        lines = intelligence_writes(tree)
        if lines:
            found[rel] = lines
    return found


def test_the_detector_sees_the_shapes_producers_use() -> None:
    src = '''
from pathlib import Path
BASE = Path(__file__).parent
INTEL = BASE / "data" / "intelligence"
SEAT = INTEL / "kimi"
def a(rows):
    (SEAT / "d.json").write_text("x")
def b():
    with open(BASE / "data/intelligence/x.jsonl", "a") as fh:
        fh.write("y")
def c(tmp):
    import os
    os.replace(tmp, SEAT / "z.json")
def d(rows):
    _atomic(INTEL / "q.json", rows)
def e():
    (BASE / "reports" / "r.json").write_text("not intelligence")
'''
    hits = intelligence_writes(ast.parse(src))
    assert len(hits) == 4, hits


def test_every_intelligence_writer_goes_through_the_scrub() -> None:
    found = producers()
    assert len(found) >= 60, f"only {len(found)} producers found: the detector rotted"
    offenders = []
    for rel, lines in sorted(found.items()):
        if rel in ALLOWLIST:
            continue
        if not _scrubs(ast.parse((ROOT / rel).read_text("utf-8"))):
            offenders.append(f"{rel}:{lines[0]}")
    assert not offenders, (
        "these modules write under an intelligence directory without libs.ops.secret_scrub "
        f"(scrub the payload, or write through write_json / write_discoveries): {offenders}")


def test_the_allowlist_is_short_justified_and_live() -> None:
    assert len(ALLOWLIST) <= 5
    for rel, why in ALLOWLIST.items():
        assert why.strip(), rel
        assert (ROOT / rel).exists(), f"allowlisted {rel} no longer exists: drop it"


def test_the_shared_helpers_really_scrub() -> None:
    for rel, fn in (("desks/mt5/side_channels/discovery_io.py", "write_discoveries"),
                    ("desks/mt5/side_channels/base.py", "save_hypothesis")):
        tree = ast.parse((ROOT / rel).read_text("utf-8"))
        defs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == fn]
        assert defs, (rel, fn)
        assert any(isinstance(c, ast.Call) and _call_name(c) in ("scrub", "scrub_text")
                   for c in ast.walk(defs[0])), f"{rel}:{fn} no longer scrubs"


def test_the_commit_boundary_scrubs() -> None:
    hook = (ROOT / "ops" / "githooks" / "pre-commit").read_text("utf-8")
    assert "libs.ops.secret_scrub --staged" in hook
    vps = (ROOT / "ops" / "run_seed_miners_hourly.sh").read_text("utf-8")
    assert vps.index("libs.ops.secret_scrub --tree") < vps.index('git add -- "${INTEL_PATHS[@]}"')
    box = (ROOT / "desks" / "mt5" / "scripts" / "intel_ship_adopt.ps1").read_text("utf-8")
    assert "libs.ops.secret_scrub" in box


def test_the_vps_commit_scrubs_only_changed_intelligence_files() -> None:
    vps = (ROOT / "ops" / "run_seed_miners_hourly.sh").read_text("utf-8")
    block = vps[vps.index("CREDENTIAL SCRUB BEFORE STAGING"):vps.index('git add -- "${INTEL_PATHS')]
    assert "git diff --name-only -z" in block and "git ls-files --others" in block
    assert "xargs -0 -r" in block
