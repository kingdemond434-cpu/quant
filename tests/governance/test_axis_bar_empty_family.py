"""An empty trial family has no multiplicity bar, and must not crash the organ that asks for one.

THE DEFECT (measured 2026-08-29). `scripts/finalize_axis_screens.py::_bar` computed
``_norm_ppf(0.05 / (2 * m))`` with no guard on ``m``. An axis whose report contains trials but
none carrying both a ``verdict`` and a non-zero ``n`` screens to an empty list, so ``m`` reached
zero for real and the organ died with ZeroDivisionError partway down its axis loop. Everything
ORDERED AFTER the empty axis was silently never finalized -- on this box that was 28 further
axes including cme, cot_positioning, crossasset, energy, equity, fed, index and metal, every one
of them MT5 ground, skipped for days because a retired crypto axis crashed first.

WHY ``inf`` AND NOT ``0``. Zero is the other way to stop the arithmetic raising, and it is the
dangerous one: a t-bar of 0 admits every trial in a family the desk never measured. L1.57 is
explicit that a verdict over an empty population is vacuous and never a pass, and this is the
failure direction no downstream gate re-checks -- a falsely admitted axis arrives at the forward
queue looking exactly like a real one.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    spec = importlib.util.spec_from_file_location(
        "finalize_axis_screens", _ROOT / "scripts" / "finalize_axis_screens.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_empty_family_does_not_raise() -> None:
    assert _load()._bar(0) == math.inf, "the exact input that killed the organ mid-loop"


def test_empty_family_bar_admits_nothing() -> None:
    """The whole point: unmeasured must fail closed, not open."""
    bar = _load()._bar(0)
    for plausible_t in (0.0, 1.96, 2.5, 3.2, 1e9):
        assert not plausible_t > bar, (
            f"t={plausible_t} cleared the bar of an EMPTY family -- a bar of 0 would have "
            "admitted every one of these")


@pytest.mark.parametrize("m", [1, 2, 6, 48, 1000])
def test_non_empty_families_are_unchanged(m: int) -> None:
    """One-way fix: this may only ever refuse MORE, never pass more."""
    mod = _load()
    assert mod._bar(m) == round(abs(mod._norm_ppf(0.05 / (2 * m))), 2)


def test_bar_is_monotone_in_trial_count() -> None:
    """More trials means a harsher bar; the empty case sits above all of them, not below."""
    mod = _load()
    bars = [mod._bar(m) for m in (1, 2, 10, 100)]
    assert bars == sorted(bars), "Sidak/Bonferroni bar must rise with the trial count"
    assert mod._bar(0) > bars[-1]
