"""FENCE -- an append handle held open across a loop can be writing into an orphaned inode.

THE CLASS, PAID FOR 2026-08-28. Both FX Blue harvesters reported row 50 while their output
held 28 rows. `desks/mt5/data/` is git-TRACKED and this box's automation (auto_push every ten
minutes, the hourly cycle) checks files out from under long-running processes: the file was
UNLINKED and replaced, and both processes carried on appending to inodes with no name. Nothing
errored, nothing warned, and a reader saw a clean short file. ~500 harvested records were lost.

WHAT IS AND IS NOT VULNERABLE. `open(p, "a")` per record is safe: every call re-resolves the
path, so a checkout costs at most the record in flight. What is unsafe is a handle held open
ACROSS a loop -- the handle is bound to the inode, not the name, and the longer the loop runs
the more of the run lands nowhere. That is the shape this fence looks for, and it is a shape,
not a path, so it catches the next instance in a directory nobody has thought about yet.

The repair is always the same: append to a staging file OUTSIDE the tracked tree and publish
to the tracked artifact in one pass at the end, so the window a checkout can eat is a single
rename -- and the staging file makes an interrupted run replayable.

Exit 0 = no held-open appender loops. Exit 1 = at least one; each is printed with its repair.
"""
from __future__ import annotations

import ast
import subprocess
import sys
import warnings
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOTS = ("desks", "libs", "scripts")
#: A writer already on the staging-then-publish pattern names its staging file outside the
#: tracked tree; the marker below is how it declares that, so a repaired writer stops reporting.
EXEMPT_MARKER = "ORPHAN-SAFE"


def _is_append_open(node: ast.AST) -> bool:
    """True for open(p, 'a'...) and p.open('a'...), the two spellings this repo uses."""
    if not isinstance(node, ast.Call):
        return False
    args = list(node.args)
    kws = {k.arg: k.value for k in node.keywords}
    mode = None
    if isinstance(node.func, ast.Name) and node.func.id == "open":
        mode = args[1] if len(args) > 1 else kws.get("mode")
    elif isinstance(node.func, ast.Attribute) and node.func.attr == "open":
        mode = args[0] if args else kws.get("mode")
    else:
        return False
    return isinstance(mode, ast.Constant) and isinstance(mode.value, str) and "a" in mode.value


#: A LOOP ALONE IS NOT THE DEFECT -- writing a list out in milliseconds cannot be interrupted by
#: a checkout in any meaningful sense, and a fence that reports 58 of those is a fence nobody
#: reads. The exposure is a loop that WAITS: network, sleep, subprocess, or a nested LLM/miner
#: call. Those hold the inode for minutes to hours, which is exactly the window the ten-minute
#: auto_push and the hourly cycle occupy. Narrowing on slow work is what makes this actionable.
SLOW = ("sleep", "urlopen", "request", "get(", "post(", "session", "subprocess", "run(",
        "fetch", "_get", "check_output", "communicate", "Popen", "call_llm", "ask_")


def _body_loops(body: list[ast.stmt]) -> bool:
    for stmt in body:
        for n in ast.walk(stmt):
            if not isinstance(n, (ast.For, ast.While, ast.AsyncFor)):
                continue
            inner = "\n".join(ast.unparse(b) for b in n.body)
            if any(tok in inner for tok in SLOW):
                return True
    return False


def scan(path: Path) -> list[tuple[int, str]]:
    try:
        with warnings.catch_warnings():
            # A scanned file's own SyntaxWarning is not this fence's verdict, and under
            # `filterwarnings = error` it would abort the scan on an unrelated module.
            warnings.simplefilter("ignore")
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.With, ast.AsyncWith)):
            continue
        if not any(_is_append_open(item.context_expr) for item in node.items):
            continue
        if _body_loops(node.body):
            hits.append((node.lineno, ast.unparse(node.items[0].context_expr)[:90]))
    return hits


def _tracked_basenames() -> set[str]:
    """Only a TRACKED target can be unlinked out from under a running writer.

    A gitignored artifact has no checkout to eat it, so reporting one is noise -- it is how this
    fence's first draft returned two retired crypto collectors writing to `data/*` (ignored) and
    buried the one real instance. The test is deliberately COARSE: a module qualifies if any
    string constant in it is the basename of a tracked file. That can over-report (a module that
    merely mentions such a name) and cannot under-report, which is the only direction a fence may
    be wrong in.
    """
    out = subprocess.run(["git", "ls-files"], cwd=BASE, capture_output=True,
                         text=True, check=True).stdout
    return {line.rsplit("/", 1)[-1] for line in out.splitlines() if line}


def _writes_tracked(src: str, tracked: set[str]) -> bool:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(src)
    except SyntaxError:
        return True  # unparseable: fail toward reporting
    return any(isinstance(n, ast.Constant) and isinstance(n.value, str)
               and n.value.rsplit("/", 1)[-1] in tracked
               for n in ast.walk(tree))


def main() -> int:
    tracked = _tracked_basenames()
    findings: list[str] = []
    for root in ROOTS:
        for py in sorted((BASE / root).rglob("*.py")):
            if "/tests/" in str(py) or py.name.startswith("test_"):
                continue
            src = py.read_text(encoding="utf-8", errors="replace")
            if EXEMPT_MARKER in src:
                continue
            if not _writes_tracked(src, tracked):
                continue
            for lineno, expr in scan(py):
                findings.append(f"{py.relative_to(BASE)}:{lineno}  {expr}")
    if not findings:
        print("orphanable writers: OK -- no append handle is held open across a loop")
        return 0
    print(f"ORPHANABLE WRITERS: {len(findings)} held-open append handle(s) across a loop")
    for f in findings:
        print(f"  {f}")
    print("\nREPAIR: append to a staging file OUTSIDE the tracked tree, publish to the tracked")
    print("artifact in one pass at the end. Declare the repair with the marker "
          f"{EXEMPT_MARKER} in the module so this fence stops reporting it.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
