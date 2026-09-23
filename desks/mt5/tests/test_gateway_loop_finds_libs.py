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
    offenders = []
    for py in list((_DESK / "mt5desk").glob("*.py")) + list((_DESK / "research").glob("*.py")):
        for m in pat.finditer(py.read_text("utf-8", errors="replace")):
            offenders.append(f"{py.relative_to(_DESK)}: {m.group(0).strip()}")
    assert not offenders, offenders
