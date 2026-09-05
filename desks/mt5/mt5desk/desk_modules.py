"""Import a DESK research module without depending on sys.path order.

WHY THIS EXISTS (2026-08-30)

Seven EURCHF forward sleeves sat at BLOCKED_INPUTS_UNAVAILABLE for a day, accruing no evidence,
every one reporting:

    ModuleNotFoundError: No module named 'research.carry_state'

The module was never missing. `desks/mt5/research/carry_state.py` was on the box the whole time.
THE NAME `research` IS CLAIMED BY TWO PACKAGES:

    libs/research/            portfolio, allocation, panels        (has __init__.py)
    desks/mt5/research/       carry_state, edge_search, verdicts   (has __init__.py)

Both are regular packages, so `import research` binds to WHICHEVER DIRECTORY COMES FIRST on
sys.path, and that order is decided by the entry point. When anything placed `libs` first, every
desk research module became unimportable at once -- and the failure surfaced as "runtime inputs
unavailable", which reads like missing DATA rather than a path collision. That is why it survived
a fix: `edge_search` was already patched to try both relative and top-level forms, and neither
helps, because the collision happens one level up at `research` itself.

Resolving BY LOCATION cannot be broken by path order, by a new entry point, or by whatever a
future caller happens to put on sys.path first.

ORDER OF ATTEMPTS, cheapest first: the ordinary import is tried before the file-path load, and its
result is ACCEPTED ONLY IF it actually came from the desk's directory -- otherwise a same-named
module from the other package would be returned as if it were this one.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_RESEARCH = Path(__file__).resolve().parents[1] / "research"
_PREFIX = "mt5_desk_research."


def desk_research(name: str) -> ModuleType:
    """The desk's `research/<name>.py`, however sys.path happens to be arranged.

    Raises ModuleNotFoundError only when the FILE is genuinely absent -- the one case that is a
    real missing-module error rather than a collision wearing its clothes.
    """
    cached = sys.modules.get(_PREFIX + name)
    if cached is not None:
        return cached

    for candidate in (f"research.{name}", name):
        try:
            mod = importlib.import_module(candidate)
        except ImportError:
            continue
        origin = getattr(mod, "__file__", "") or ""
        if origin and Path(origin).resolve().parent == _RESEARCH:
            return mod

    path = _RESEARCH / f"{name}.py"
    if not path.exists():
        raise ModuleNotFoundError(
            f"{name} is not a desk research module: {path} does not exist")
    spec = importlib.util.spec_from_file_location(_PREFIX + name, path)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    # REGISTER BEFORE EXECUTING, so a module that imports itself transitively finds the partially
    # initialised object instead of recursing until the stack ends.
    sys.modules[_PREFIX + name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(_PREFIX + name, None)
        raise
    return mod
