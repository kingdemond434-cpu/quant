"""Fusion's ruin line is EUR 10 in the deadman AND the gateway (zuck 2026-11-05, D-20261105-042).

The deadman halted Fusion at EUR 266 on a fixed EUR 300 floor, and gateway.py dropped every
non-gold sleeve below the same EUR 300 (PROMOTED_MIN_EQUITY), so the FX cells could not trade even
with the halt lifted (#753 audit HOLD). Both now stand down only below the ruin floor; each order
above it is judged on its own size. The 0.01-lot override still is not stamped below EUR 300.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as dc  # noqa: E402


def _deadman():
    spec = importlib.util.spec_from_file_location(
        "_fd_floor", _DESK / "proposals" / "fusion_deadman.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_one_ruin_line_in_the_deadman_and_the_gateway() -> None:
    assert dc.FUSION_RUIN_FLOOR_EUR == 10.0
    assert _deadman().EQUITY_FLOOR_EUR == dc.FUSION_RUIN_FLOOR_EUR


def test_the_gateway_keeps_promoted_sleeves_above_the_ruin_line() -> None:
    src = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    assert "if equity < FUSION_RUIN_FLOOR_EUR:" in src
    assert "if equity < PROMOTED_MIN_EQUITY:" not in src


def test_the_minlot_override_is_still_not_stamped_on_a_small_account() -> None:
    rows = [{"name": n} for n in sorted(dc.MINLOT_OVERRIDE_SLEEVES)]
    notes = dc.stamp_minlot_override(rows, frozenset(dc.MINLOT_OVERRIDE_SLEEVES), 266.0)
    assert not any(r.get("minlot_override") for r in rows)
    assert all("sized by sovereignty" in n for n in notes)
