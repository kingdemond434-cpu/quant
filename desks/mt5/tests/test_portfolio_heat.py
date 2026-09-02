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
    """Exec only the pure helpers -- gateway.py imports MetaTrader5, absent on a research box.

    The risk budget is NOT re-extracted from source. gateway.py imports it from
    gateway_config_fallback, which this box CAN import, so the namespace is seeded with the real
    values; parsing them back out of a literal would be testing a copy that no longer exists.
    """
    import json as _json
    import math as _math
    import time as _time

    from mt5desk.gateway_config_fallback import (
        BOOK_WORST_DD_R, HEAT_HARD_CEILING, HEAT_TARGET, MAX_DRAWDOWN_TOLERANCE,
        MAX_SLEEVE_HEAT_SHARE, Q_OPT)
    tree = ast.parse(_SRC)
    keep = []
    ns = {"math": _math, "json": _json, "time": _time, "BASE": _DESK,
          "Q_OPT": Q_OPT, "MAX_DRAWDOWN_TOLERANCE": MAX_DRAWDOWN_TOLERANCE,
          "_BOOK_WORST_DD_R": BOOK_WORST_DD_R, "HEAT_TARGET": HEAT_TARGET,
          "HEAT_HARD_CEILING": HEAT_HARD_CEILING,
          "MAX_SLEEVE_HEAT_SHARE": MAX_SLEEVE_HEAT_SHARE}
    wanted_fn = {"cap_by_heat", "realised_q", "auto_lot", "heat_budget", "_lot_steps",
                 "_eur_per_price_unit", "allocator_heat", "allocator_order"}
    wanted_const = {"MAX_HEAT_CEILING", "_HEAT_BASE_KEFF", "_HEAT_BASE_LEGS",
                    "_ALLOC_MAX_AGE_S",
                    "DIST_USD", "CONTRACT_OZ", "FX_EUR", "MIN_LOT_RISK_EUR",
                    "GOLD_SYMBOL"}
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
    """THE DEFECT. At EUR 1,684 the 0.01 lot floor makes each sleeve ~0.98%; ten is ~9.8%.

    THE FIXTURE FIGURE MOVED FROM 1.04% TO 0.98% AND THAT IS THE POINT, not a drift to be
    re-baselined away: gold's risk per lot was read from `CONTRACT_OZ * FX_EUR` = 92.00 and is
    now read from the broker's own tick value, 86.41. The 6.5% gap is a frozen EUR/USD rate,
    and it sized the one armed book on this desk 6.5% small. Derived from the venue rather
    than retyped, so the next FX move updates it instead of failing here.
    """
    admitted, note = NS["cap_by_heat"](_sleeves(10), 1684.0)
    q = NS["realised_q"](1684.0)
    floor_q = 0.01 * NS["DIST_USD"] * NS["_eur_per_price_unit"](NS["GOLD_SYMBOL"]) / 1684.0
    assert q == pytest.approx(floor_q, rel=1e-6), "fixture assumption about the floor changed"
    assert len(admitted) * q <= NS["heat_budget"]() + 1e-9
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
        assert len(adm) * NS["realised_q"](eq) <= NS["heat_budget"]() + 1e-9, (
            f"heat breached at equity {eq}")


def test_realised_risk_never_exceeds_the_policy_once_the_floor_clears():
    """THE LOT GRAIN MAY ONLY MAKE YOU SMALLER. `auto_lot` rounded to NEAREST, so realised risk
    could sit up to half a lot step ABOVE Q_OPT. That was absorbed while Q_OPT ran 41% under the
    heat budget; with Q_OPT derived from the drawdown tolerance the base budget IS Q_OPT x 3, so
    an upward round on each leg puts the armed book over its own cap."""
    from mt5desk.gateway_config_fallback import Q_OPT as POLICY
    floor_binds_below = 0.01 * NS["DIST_USD"] * NS["CONTRACT_OZ"] * NS["FX_EUR"] / POLICY
    for eq in (2400.0, 3000.0, 5000.0, 8000.0, 12_500.0, 25_000.0, 100_000.0):
        assert eq > floor_binds_below, "fixture: this equity is still inside the floor region"
        assert NS["realised_q"](eq) <= POLICY + 1e-9, (
            f"equity {eq:,.0f} realises {NS['realised_q'](eq):.4%} against a {POLICY:.4%} policy")


def test_the_gold_book_survives_the_cap_at_every_equity_above_the_floor():
    """The regression the rounding fix exists to prevent, stated as the invariant it protects:
    three armed legs, each at or below policy, must always fit a budget of policy x 3."""
    gold = [{"name": "gold_asia"}, {"name": "gold_london_am"}, {"name": "gold_afternoon"}]
    for eq in (1684.0, 2400.0, 3000.0, 5000.0, 8000.0, 12_500.0, 25_000.0, 100_000.0):
        admitted, note = NS["cap_by_heat"](list(gold), eq)
        assert len(admitted) == 3, f"gold amputated at equity {eq:,.0f}: {note}"


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


def test_a_flat_budget_would_cap_the_book_forever():
    """WHY THE BUDGET IS NOT A CONSTANT. realised_q converges to Q_OPT once equity clears the
    0.01-lot floor, so a fixed budget admits the same sleeve count at EUR 25,000 and at EUR
    100,000 -- and at a million. The book would stop widening permanently, the opposite of safe
    aggressive growth.

    Both equities are taken well ABOVE the floor deliberately. Near it, lot rounding dominates:
    EUR 2,343 rounds 1.69 lots-of-0.01 UP to 2 and realises 1.50% against Q_OPT's 1.27%, so a
    comparison there measures the rounding grain rather than the plateau it means to show."""
    q_big = NS["realised_q"](100_000.0)
    q_mid = NS["realised_q"](25_000.0)
    assert q_mid == pytest.approx(q_big, abs=5e-4), "premise: realised_q has converged by here"
    flat = NS["heat_budget"](2.26)
    assert int(flat / q_big) == int(flat / q_mid), (
        "premise changed: a flat budget no longer plateaus")
    # with correlation-awareness, more independent bets buy more room at the SAME equity
    assert int(NS["heat_budget"](5.12) / q_big) > int(NS["heat_budget"](2.26) / q_big)


def test_heat_scales_with_independence_not_sleeve_count():
    """Five genuinely independent sleeves are safer at 6% than three correlated ones at 4%.
    Drawdown scales as H/sqrt(k_eff), so holding drawdown fixed lets H grow with sqrt(k_eff)."""
    base = NS["heat_budget"](2.26)
    q_star = 1.0 - (1.0 - NS["MAX_DRAWDOWN_TOLERANCE"]) ** (1.0 / NS["_BOOK_WORST_DD_R"])
    assert base == pytest.approx(q_star * NS["_HEAT_BASE_LEGS"], rel=1e-6)
    assert NS["heat_budget"](5.12) == pytest.approx(base * (5.12 / 2.26) ** 0.5, rel=1e-6)
    assert NS["heat_budget"](9.0) > NS["heat_budget"](5.12) > base


def test_unmeasured_correlation_gets_the_BASE_budget_never_the_ceiling():
    """THE LOAD-BEARING DEFAULT. Shadow started 2026-08-16, so there is no live cross-sleeve
    correlation yet. Treating 'not yet measured' as 'independent' is the one assumption that lets
    a correlated book size like a diversified one -- and that discovers its real correlation
    during the drawdown instead of before it."""
    base = NS["heat_budget"](2.26)
    for bad in (None, float("nan"), 0.0, 0.9):
        assert NS["heat_budget"](bad) == pytest.approx(base, abs=1e-9)
        assert NS["heat_budget"](bad) < NS["MAX_HEAT_CEILING"]


def test_the_ceiling_binds_however_good_diversification_looks():
    """Correlations rise in exactly the regime the budget would be spent, and a measured k_eff is
    an estimate taken in calm."""
    assert NS["heat_budget"](1000.0) == pytest.approx(NS["MAX_HEAT_CEILING"], abs=1e-9)


def test_the_budget_is_solved_from_the_stated_drawdown_tolerance():
    """The budget answers a question about THIS book -- 35% tolerance against its measured -33.7R
    -- rather than being a round number. q* = 1-(1-tol)^(1/dd_r), times the validated leg count."""
    q_star = 1.0 - (1.0 - NS["MAX_DRAWDOWN_TOLERANCE"]) ** (1.0 / NS["_BOOK_WORST_DD_R"])
    assert q_star == pytest.approx(0.0127, abs=0.0005)
    assert NS["heat_budget"](None) == pytest.approx(q_star * NS["_HEAT_BASE_LEGS"], rel=1e-9)


def test_the_armed_gold_book_fits_at_live_equity():
    """REGRESSION. Multiplying q* by k_eff instead of the validated LEG COUNT double-counted the
    diversification already inside the -33.7R summed series and returned 2.87% -- below the 3.12%
    the gold book actually runs, amputating the book the budget is calibrated on."""
    gold = [{"name": f"gold_{w}"} for w in ("asia", "london_am", "afternoon")]
    admitted, note = NS["cap_by_heat"](list(gold), 1684.0)
    assert len(admitted) == 3 and note is None
