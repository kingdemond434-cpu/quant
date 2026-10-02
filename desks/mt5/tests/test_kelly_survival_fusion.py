"""The Fusion gold book obeys the survival-constrained growth solve (principal 2026-09-30).

A window the solve funds at 0 is not emitted; any other window carries `kelly_lots`, which
`bracket_lane_lot` sends. No solve (None) leaves the roster exactly as it was.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as dc  # noqa: E402


def _gold(sleeves: list[dict]) -> dict[str, dict]:
    return {s["window"]: s for s in sleeves if s.get("symbol") == "XAUUSD" and "window" in s}


def test_no_solve_leaves_the_gold_book_as_it_was() -> None:
    before, _ = dc.roster({}, [])
    after, _ = dc.roster({}, [], None)
    assert before == after
    assert all("kelly_lots" not in s for s in after)


def test_a_zero_window_stands_aside_and_the_rest_carry_their_lots() -> None:
    labels = [label for label, _sig, _rng in dc.GOLD_WINDOWS]
    kelly = {labels[0]: 0.01, labels[1]: 0.0}
    sleeves, notes = dc.roster({}, [], kelly)
    gold = _gold(sleeves)
    assert gold[labels[0]]["kelly_lots"] == 0.01
    assert labels[1] not in gold
    assert any("stands aside" in n and "KELLY_SURVIVAL" in n for n in notes)
    for label in labels[2:]:
        assert "kelly_lots" not in gold[label]


def test_the_gateway_sends_the_solves_lot() -> None:
    gw = pytest.importorskip("mt5desk.gateway", reason="needs MetaTrader5")
    lot, why = gw.bracket_lane_lot({"lot": "auto", "kelly_lots": 0.03}, 600.0, 19.1, "XAUUSD")
    assert lot == 0.03 and "kelly_survival" in why
    lot, _ = gw.bracket_lane_lot({"lot": "auto", "kelly_lots": 0.004}, 600.0, 19.1, "XAUUSD")
    assert lot == 0.01            # never below the venue minimum
