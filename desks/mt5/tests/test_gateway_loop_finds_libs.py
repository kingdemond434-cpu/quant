"""The gateway process can import `libs` -- the one package its sizing depends on.

MEASURED 2026-09-08, in the gateway log, every minute:

    sizing: proof unreadable (ModuleNotFoundError: No module named 'libs.portfolio')
    release-refusal record failed (non-fatal) [gold_afternoon]: ... 'libs.research'

`run_gateway_loop.py` put only the DESK root on sys.path. `libs/` lives beside `desks/`, not
inside it, so every `from libs.*` in the gateway raised -- and every one of those imports is
wrapped in an except that keeps the money path alive, so the gateway ran for weeks on base
sizing, never reading the allocator's certificate, with nothing louder than a log line.

The message said `libs.portfolio`, not `libs`: SOME `libs` was resolving. The box carries
untracked copies of desk files beside the tracked ones, so a stale partial `libs/` under the desk
root is the likely shadow, and the fix puts the repo root at index 0 -- ahead of the desk root --
so the real package wins whatever else is lying around.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
LOOP = (_DESK / "research" / "run_gateway_loop.py").read_text("utf-8")


def test_the_repo_root_is_put_on_the_path_ahead_of_the_desk_root() -> None:
    root_line = "sys.path.insert(0, str(Path(__file__).resolve().parents[3]))"
    desk_line = "sys.path.insert(0, str(Path(__file__).resolve().parent.parent))"
    assert root_line in LOOP
    assert desk_line in LOOP
    # both are index-0 inserts, so the LATER one ends up first: the root insert must follow
    assert LOOP.index(desk_line) < LOOP.index(root_line)


def test_the_root_insert_happens_before_the_gateway_is_imported() -> None:
    assert LOOP.index("parents[3]") < LOOP.index("from mt5desk import gateway")


def test_parents_3_from_the_loop_file_is_the_repo_root() -> None:
    """A miscount here silently puts the wrong directory first and fixes nothing."""
    loop = _DESK / "research" / "run_gateway_loop.py"
    assert loop.resolve().parents[3] == _ROOT
    assert (_ROOT / "libs" / "__init__.py").exists()
    assert (_ROOT / "libs" / "portfolio" / "allocator_proof.py").exists()
    assert (_ROOT / "libs" / "research" / "decision_ledger.py").exists()


def test_with_the_root_first_the_gateway_s_own_imports_resolve() -> None:
    """The three imports the gateway log showed failing, resolved the way the loop now does it."""
    saved = list(sys.path)
    try:
        sys.path.insert(0, str(_DESK))
        sys.path.insert(0, str(_ROOT))
        for mod in ("libs.portfolio.allocator_proof", "libs.portfolio.allocator_blend",
                    "libs.research.decision_ledger", "libs.ops.release"):
            sys.modules.pop(mod, None)
            assert importlib.import_module(mod) is not None, mod
    finally:
        sys.path[:] = saved


def test_nothing_at_the_repo_root_shadows_a_bare_desk_import() -> None:
    """Putting the root FIRST is only safe if no desk module does `import config` / `import data`
    / `import scripts`... bare -- the repo root has directories by those names. Checked once by
    hand on 2026-09-08; pinned here so a future bare import fails loudly instead of resolving to
    a namespace package of the wrong directory."""
    import re
    root_dirs = {p.name for p in _ROOT.iterdir() if p.is_dir() and not p.name.startswith(".")}
    root_dirs -= {"desks", "libs"}          # `libs` is the point; `desks` is never bare-imported
    pat = re.compile(r"^\s*(?:import|from)\s+(" + "|".join(map(re.escape, sorted(root_dirs)))
                     + r")(?:\s|\.|$)", re.M)
    # `scripts` IS A NAMESPACE PACKAGE ON BOTH SIDES, SO IT CANNOT SHADOW. Neither the repo's
    # scripts/ nor desks/mt5/scripts/ has an __init__.py, so `scripts` resolves to the union of
    # the two and a submodule from either is found whichever comes first on sys.path. Research
    # organs import root fences that way (allocator_liveness -> scripts.check_allocator_join,
    # asia_plane -> scripts.check_source_routes, certificate_truth -> scripts.external_gauntlet).
    # Such an import is safe exactly while that holds and the named module exists in the union;
    # both are checked here, so an __init__.py appearing on either side fails this test again.
    scripts_dirs = (_ROOT / "scripts", _DESK / "scripts")
    assert not any((d / "__init__.py").exists() for d in scripts_dirs), (
        "an __init__.py in a scripts/ dir turns the namespace union into shadowing")
    sub = re.compile(r"^\s*(?:from\s+scripts\.(\w+)\s+import|from\s+scripts\s+import\s+(\w+))")

    def _namespace_safe(stmt: str) -> bool:
        m = sub.match(stmt)
        name = m and (m.group(1) or m.group(2))
        return bool(name) and any((d / f"{name}.py").exists() for d in scripts_dirs)

    offenders = []
    for py in list((_DESK / "mt5desk").glob("*.py")) + list((_DESK / "research").glob("*.py")):
        text = py.read_text("utf-8", errors="replace")
        for m in pat.finditer(text):
            line = text[m.start():text.find("\n", m.start())]
            if m.group(1) == "scripts" and _namespace_safe(line):
                continue
            offenders.append(f"{py.relative_to(_DESK)}: {m.group(0).strip()}")
    assert not offenders, offenders
