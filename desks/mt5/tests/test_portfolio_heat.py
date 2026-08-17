"""No sleeve is sized against the account; only the book is.

The gateway had NO portfolio cap. Promoted sleeves each take a fixed 0.01 lot -- 1.04% of equity
at EUR 1,684 -- and `load_sleeves()` returned every LIVE one with no count or aggregate limit.
The shadow set is ten sleeves, so ten promotions meant ~10% of the account at risk in a single
morning. Per-sleeve risk control is not risk control: correlated sleeves fire together in exactly
the regimes that hurt.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

_SRC = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")


def _load():
    """Exec only the pure helpers -- gateway.py imports MetaTrader5, absent on a research box."""
    tree = ast.parse(_SRC)
    keep, ns = [], {}
    wanted_fn = {"cap_by_heat", "realised_q", "auto_lot"}
    wanted_const = {"MAX_PORTFOLIO_HEAT", "Q_OPT", "DIST_USD", "CONTRACT_OZ", "FX_EUR",
                    "MIN_LOT_RISK_EUR"}
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in wanted_fn:
            keep.append(n)
        elif isinstance(n, ast.Assign) and any(
                getattr(t, "id", "") in wanted_const for t in n.targets):
            keep.append(n)
    exec(compile(ast.Module(body=keep, type_ignores=[]), "<gw>", "exec"), ns)
    return ns


NS = _load()


def _sleeves(n):
    return [{"name": f"s{i}"} for i in range(n)]


def test_ten_sleeves_cannot_risk_ten_percent():
    """THE DEFECT. At EUR 1,684 the 0.01 lot floor makes each sleeve 1.04%; ten is 10.4%."""
    admitted, note = NS["cap_by_heat"](_sleeves(10), 1684.0)
    q = NS["realised_q"](1684.0)
    assert q == pytest.approx(0.0104, abs=0.0005), "fixture assumption about the floor changed"
    assert len(admitted) * q <= NS["MAX_PORTFOLIO_HEAT"] + 1e-9
    assert len(admitted) < 10
    assert note and "PORTFOLIO HEAT CAP" in note


def test_dropped_sleeves_are_named_not_silent():
    """A silently shortened book is indistinguishable from one that had nothing to trade."""
    _, note = NS["cap_by_heat"](_sleeves(10), 1684.0)
    assert "deferring" in note
    assert "s9" in note, "the deferred sleeves must be identifiable from the log line"


def test_the_validated_gold_book_is_never_amputated_by_the_cap():
    """THE CAP MUST NOT DISMEMBER THE PROVEN BOOK. At EUR 1,684 each sleeve is 1.04%, so the
    three armed gold legs are 3.12% of equity. A 3% cap -- the first value tried -- dropped
    gold_afternoon, sacrificing a leg with walk-forward evidence and human authorisation to a
    round number. The budget is set so the validated core fits and ADDITIONS must be earned."""
    gold = [{"name": "gold_asia"}, {"name": "gold_london_am"}, {"name": "gold_afternoon"}]
    admitted, note = NS["cap_by_heat"](list(gold), 1684.0)
    assert [s["name"] for s in admitted] == [g["name"] for g in gold], (
        "the armed gold book does not fit inside MAX_PORTFOLIO_HEAT at live equity")
    assert note is None


def test_promoted_sleeves_are_what_gets_deferred():
    """sleeve_set() puts gold first, so order preservation means unproven sleeves are dropped
    first -- the correct seniority."""
    sleeves = [{"name": "gold_asia"}, {"name": "gold_london_am"}, {"name": "gold_afternoon"}]
    sleeves += [{"name": f"promoted_{i}"} for i in range(7)]
    admitted, note = NS["cap_by_heat"](sleeves, 1684.0)
    names = [s["name"] for s in admitted]
    assert names[:3] == ["gold_asia", "gold_london_am", "gold_afternoon"]
    assert all(not n.startswith("promoted_") for n in names), (
        "an unproven sleeve was admitted while the budget was already spent on the proven book")
    assert note and "promoted_" in note


def test_a_small_account_gets_fewer_sleeves_not_more_risk():
    """The 0.01 floor makes each sleeve a LARGER fraction as equity falls, so a sleeve-COUNT cap
    would let total risk grow silently on a shrinking account. A heat budget cannot."""
    big, _ = NS["cap_by_heat"](_sleeves(10), 8000.0)
    small, _ = NS["cap_by_heat"](_sleeves(10), 600.0)
    assert len(small) < len(big)
    for eq in (600.0, 1684.0, 8000.0):
        adm, _ = NS["cap_by_heat"](_sleeves(10), eq)
        assert len(adm) * NS["realised_q"](eq) <= NS["MAX_PORTFOLIO_HEAT"] + 1e-9, (
            f"heat breached at equity {eq}")


def test_a_book_inside_the_budget_is_untouched():
    admitted, note = NS["cap_by_heat"](_sleeves(2), 8000.0)
    assert len(admitted) == 2 and note is None


def test_degenerate_inputs_do_not_open_the_gate():
    assert NS["cap_by_heat"]([], 1684.0) == ([], None)
    admitted, _ = NS["cap_by_heat"](_sleeves(3), 0.0)
    assert len(admitted) == 3, "zero equity must not silently change sizing; the caller halts"


def test_the_cap_is_actually_applied_in_the_trading_path():
    """A helper nothing calls is not a cap. Pins the wiring, not just the function."""
    assert re.search(r"sleeves,\s*heat_note\s*=\s*cap_by_heat\(", _SRC), (
        "cap_by_heat is defined but never applied to the sleeve list")
    assert "log(heat_note)" in _SRC, "the cap fires without recording that it fired"
