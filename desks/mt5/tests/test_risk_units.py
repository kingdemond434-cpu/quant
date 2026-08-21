"""One lot of an instrument risks what the VENUE says it risks, not what gold says.

THE DEFECT THESE TESTS PIN

`gateway.auto_lot`, `realised_q` and `promoted_lot` priced every sleeve's stop as
`dist * CONTRACT_OZ * FX_EUR` -- 100 ounces times a frozen EUR/USD rate -- and applied it to
whatever symbol the sleeve named. Measured on the desk's own `universe.json`, EUR risked per
price unit per lot is 0.86 on BTCUSD, 86.41 on XAUUSD, 542.40 on every JPY cross and 86,414 on
EURUSD, so the single constant 92 was wrong by 107x in one direction and 939x in the other.

It was live rather than latent. `sleeve_set` rewrites every promoted sleeve's lot field to
"auto_ramp", so the literal 0.01 that `promoter.py` writes never reaches the venue and
`promoted_lot -> auto_lot` is always the path taken. At EUR 1,683.89 a promoted CADJPY sleeve on
a 0.50 stop sized to 0.46 lot, logged EUR 21.16 at risk (1.26%, on policy) and actually risked
EUR 124.75 -- 7.41% of equity -- while `cap_by_heat` billed it gold's 0.98% and admitted three
such sleeves for a believed 2.94% book against a true 22.2%.
"""

from __future__ import annotations

import ast
import json
import math
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk import risk_units as ru  # noqa: E402

_SRC = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")

#: Straight from the venue snapshot the desk actually trades against.
UNIVERSE = json.loads(
    (_DESK / "data" / "universe" / "universe.json").read_text(encoding="utf-8"))

#: What the deleted constant asserted for every instrument on the desk.
LEGACY_CONSTANT = 100 * 0.92

#: Gold's EUR-per-price-unit, DERIVED FROM THE SNAPSHOT rather than pinned as a literal.
#:
#: This was `86.414` written out three times. That number is `tick_value / tick_size` for XAUUSD
#: in `universe.json`, and `tick_value` carries the EUR/USD rate of the day the snapshot was
#: taken -- so it moves every time the universe is refreshed. It duly broke on the refresh that
#: took EUR/USD from 1.15722 to 1.15844, failing three tests over a 0.1% FX move that is not a
#: defect in anything.
#:
#: A pin is only worth having when the pinned thing is supposed to hold still. What these tests
#: actually assert is that gold is priced FROM THE VENUE SNAPSHOT instead of from the deleted
#: `CONTRACT_OZ * FX_EUR` constant, and that survives re-derivation. `LEGACY_CONSTANT` above
#: stays a literal for exactly the opposite reason: it is a historical fact about deleted code
#: and must never track anything.
GOLD_EUR_PER_UNIT = float(UNIVERSE["XAUUSD"]["tick_value"]) / float(
    UNIVERSE["XAUUSD"]["tick_size"])

#: Same reasoning for the JPY cross used in the fallback-chain test (was pinned at `542.40`).
CADJPY_EUR_PER_UNIT = float(UNIVERSE["CADJPY"]["tick_value"]) / float(
    UNIVERSE["CADJPY"]["tick_size"])

# The re-derivation is worthless if it can silently agree with a broken snapshot, so bound it:
# gold near 1 EUR/tick at 0.01 ticks is ~86, and anything outside this band means the snapshot
# itself is wrong rather than merely current.
assert 50.0 < GOLD_EUR_PER_UNIT < 150.0, (
    f"XAUUSD tick economics out of band in universe.json: {GOLD_EUR_PER_UNIT}")


def _load():
    """Exec the pure sizing helpers; gateway.py imports MetaTrader5."""
    from mt5desk.gateway_config_fallback import (
        BOOK_WORST_DD_R, MAX_DRAWDOWN_TOLERANCE, Q_OPT)
    tree = ast.parse(_SRC)
    ns = {"math": math, "Q_OPT": Q_OPT,
          "MAX_DRAWDOWN_TOLERANCE": MAX_DRAWDOWN_TOLERANCE,
          "_BOOK_WORST_DD_R": BOOK_WORST_DD_R}
    wanted_fn = {"realised_q", "auto_lot", "_lot_steps", "promoted_lot",
                 "heat_budget", "cap_by_heat", "_eur_per_price_unit",
                 "min_lot_risk_eur"}
    wanted_const = {"DIST_USD", "CONTRACT_OZ", "FX_EUR", "MIN_LOT_RISK_EUR",
                    "MAX_HEAT_CEILING", "_HEAT_BASE_KEFF", "_HEAT_BASE_LEGS",
                    "GOLD_SYMBOL"}
    keep = [n for n in tree.body
            if (isinstance(n, ast.FunctionDef) and n.name in wanted_fn)
            or (isinstance(n, ast.Assign) and any(
                getattr(t, "id", "") in wanted_const for t in n.targets))]
    exec(compile(ast.Module(body=keep, type_ignores=[]), "<gw>", "exec"), ns)
    return ns


NS = _load()
EQ = 1683.89


class _Info:
    """A live `symbol_info` stand-in, duck-typed exactly as the gateway passes it."""

    def __init__(self, tick_size, tick_value, vmin=0.01, vstep=0.01):
        self.trade_tick_size = tick_size
        self.trade_tick_value = tick_value
        self.volume_min = vmin
        self.volume_step = vstep


# ------------------------------------------------- the conversion itself

def test_the_venue_disagrees_with_the_constant_by_orders_of_magnitude():
    """If this ever collapses toward 92 the universe snapshot has been broken, not the desk."""
    per_unit = {s: ru.eur_per_price_unit(s) for s in ("BTCUSD", "XAUUSD", "CADJPY", "EURUSD")}
    assert per_unit["BTCUSD"] < 1.0 < per_unit["XAUUSD"] < per_unit["CADJPY"] < per_unit["EURUSD"]
    # Five orders of magnitude between the cheapest and the dearest price unit on this desk.
    assert per_unit["EURUSD"] / per_unit["BTCUSD"] > 10_000


def test_risk_per_lot_is_the_tick_arithmetic_and_nothing_else():
    for sym, meta in UNIVERSE.items():
        if not (meta["tick_size"] > 0 and meta["tick_value"] > 0):
            continue
        expected = 2.0 / meta["tick_size"] * meta["tick_value"]
        assert ru.risk_per_lot(sym, 2.0) == pytest.approx(expected)


def test_live_symbol_info_beats_the_snapshot():
    """tick_value carries today's FX rate, so a live handle is the only current answer."""
    live = _Info(tick_size=0.01, tick_value=1.00)          # snapshot says 0.864140
    assert ru.eur_per_price_unit("XAUUSD", live) == pytest.approx(100.0)
    assert ru.eur_per_price_unit("XAUUSD") == pytest.approx(GOLD_EUR_PER_UNIT, rel=1e-4)


def test_an_unpriceable_instrument_refuses_rather_than_defaulting():
    """THE WHOLE POINT. A fallback to gold's constants returns a plausible number for an
    instrument nobody measured, and the caller cannot tell that from a measurement (L1.28a)."""
    with pytest.raises(ru.RiskUnitUnmeasured):
        ru.risk_per_lot("NOSUCHPAIR", 1.0)
    with pytest.raises(ru.RiskUnitUnmeasured):
        ru.eur_per_price_unit("DEAD", _Info(tick_size=0.0, tick_value=0.0))
    with pytest.raises(ru.RiskUnitUnmeasured):
        ru.risk_per_lot("XAUUSD", 0.0)


def test_lots_snap_down_never_up():
    """Rounding up re-introduces the overshoot the step function exists to prevent."""
    for sym, stop in (("XAUUSD", 19.1), ("CADJPY", 0.5), ("EURUSD", 0.004)):
        budget = 21.39
        lot = ru.lot_for_risk(sym, stop, budget)
        assert ru.realised_risk_eur(sym, stop, lot) <= budget + 1e-9 or lot == pytest.approx(0.01)
        assert round(lot / 0.01) == pytest.approx(lot / 0.01, abs=1e-6)


def test_the_floor_can_exceed_the_budget_and_says_so():
    """A policy number the venue silently overrides is not a policy."""
    lot = ru.lot_for_risk("XAUUSD", 53.40, 1.0)      # budget far under one min lot
    assert lot == pytest.approx(0.01)
    assert ru.realised_risk_eur("XAUUSD", 53.40, lot) > 1.0


# ------------------------------------------------- the gateway is wired to it

@pytest.mark.parametrize("sym,stop", [("CADJPY", 0.50), ("USDJPY", 0.60), ("EURUSD", 0.0040)])
def test_non_gold_sleeves_are_sized_in_their_own_currency(sym, stop):
    """WITHOUT THE FIX these run at 7.3-7.4% of equity while logging 1.26%."""
    lot = NS["promoted_lot"](EQ, 500, stop, sym)
    true_risk = ru.realised_risk_eur(sym, stop, lot)
    assert true_risk / EQ < 0.02, f"{sym} sized to {true_risk / EQ:.2%} of equity"
    assert NS["realised_q"](EQ, stop, sym) == pytest.approx(true_risk / EQ, rel=1e-6)


def test_realised_q_tells_the_truth_for_every_instrument():
    """`realised_q` is what the heat cap bills and what the log prints. If it disagrees with the
    venue's own arithmetic, both the cap and the operator are reading fiction."""
    for sym, stop in (("XAUUSD", 53.40), ("CADJPY", 0.50), ("EURUSD", 0.0040)):
        lot = NS["auto_lot"](EQ, stop, sym)
        assert NS["realised_q"](EQ, stop, sym) == pytest.approx(
            ru.realised_risk_eur(sym, stop, lot) / EQ, rel=1e-6)


def test_gold_is_unchanged_within_the_stale_fx_constant():
    """The gold book is the only armed one, so its numbers may only move by the amount the
    frozen FX rate was actually wrong -- 92 against a measured 86.41, i.e. 6.5%."""
    assert NS["_eur_per_price_unit"]("XAUUSD") == pytest.approx(GOLD_EUR_PER_UNIT, rel=1e-4)
    assert abs(NS["_eur_per_price_unit"]("XAUUSD") / LEGACY_CONSTANT - 1) < 0.07


def test_the_fallback_chain_is_live_then_snapshot_then_gold_alone():
    """Three tiers, and the last one is gold-only. A dead live handle falls through to the
    snapshot -- which still knows every symbol -- and only a symbol missing from BOTH reaches
    the hardcoded constants, where gold answers and everything else refuses."""
    dead = _Info(0.0, 0.0)
    # tier 2: live handle is useless, snapshot still prices both
    assert NS["_eur_per_price_unit"]("XAUUSD", dead) == pytest.approx(GOLD_EUR_PER_UNIT, rel=1e-4)
    assert NS["_eur_per_price_unit"]("CADJPY", dead) == pytest.approx(
        CADJPY_EUR_PER_UNIT, rel=1e-4)
    # tier 3: absent from the snapshot too -- and it is not gold, so it refuses
    with pytest.raises(ru.RiskUnitUnmeasured):
        NS["_eur_per_price_unit"]("NOSUCHPAIR", dead)


def test_gold_alone_survives_a_total_loss_of_tick_data(monkeypatch):
    """Gold's contract economics are hardcoded CORRECTLY, so they remain the honest last resort
    for gold alone -- and for nothing else."""
    def _blind(symbol, info=None):
        raise ru.RiskUnitUnmeasured("no tick data anywhere")
    monkeypatch.setattr(ru, "eur_per_price_unit", _blind)
    assert NS["_eur_per_price_unit"]("XAUUSD") == pytest.approx(92.0)
    with pytest.raises(ru.RiskUnitUnmeasured):
        NS["_eur_per_price_unit"]("CADJPY")


def test_an_unpriceable_sleeve_does_not_trade():
    with pytest.raises(ru.RiskUnitUnmeasured):
        NS["auto_lot"](EQ, 0.5, "NOSUCHPAIR")


# ------------------------------------------------- the heat cap bills per sleeve

def test_the_cap_charges_each_sleeve_its_own_q():
    """ONE q times a COUNT cannot see a heterogeneous book. Three gold legs at their real
    2026-08-14 stops genuinely total 6.7% against a 3.81% budget."""
    gold = [{"name": f"gold_{w}", "symbol": "XAUUSD", "dist": d}
            for w, d in (("asia", 53.40), ("london_am", 27.91), ("afternoon", 48.64))]
    admitted, note = NS["cap_by_heat"](gold, EQ, k_eff=None)
    assert len(admitted) < len(gold)
    assert "totalling" in note and "deferring" in note
    # The admitted set must fit the budget, measured the same way the sizer measures it.
    used = sum(NS["realised_q"](EQ, s["dist"], s["symbol"]) for s in admitted)
    assert used <= NS["heat_budget"](None) + 1e-12


def test_a_cheap_sleeve_is_not_billed_at_an_expensive_one_s_rate():
    """The timidity half of the same defect: a JPY cross whose min lot risks EUR 2.71 was
    charged gold's floor-driven q and deferred for heat it never used."""
    cheap = [{"name": "CADJPY_asia", "symbol": "CADJPY", "dist": 0.50},
             {"name": "USDJPY_asia", "symbol": "USDJPY", "dist": 0.60}]
    admitted, note = NS["cap_by_heat"](cheap, EQ, k_eff=None)
    assert len(admitted) == 2, note


def test_an_unpriceable_sleeve_is_not_the_cheapest_thing_in_the_book():
    """Charging it gold's q by default is how an unmeasured leg gets admitted first."""
    mixed = [{"name": "bad", "symbol": "NOSUCHPAIR", "dist": 1.0},
             {"name": "gold_asia", "symbol": "XAUUSD", "dist": 53.40}]
    admitted, _ = NS["cap_by_heat"](mixed, EQ, k_eff=None)
    assert len(admitted) <= 1


def test_a_book_that_cannot_be_priced_at_all_admits_nobody():
    admitted, note = NS["cap_by_heat"](
        [{"name": "bad", "symbol": "NOSUCHPAIR", "dist": 1.0}], EQ, k_eff=None)
    assert admitted == []
    assert "admitting none" in note


def test_an_explicit_scalar_q_still_applies_to_every_sleeve():
    """Backwards compatible: a caller passing one q means one q."""
    sl = [{"name": f"s{i}", "symbol": "XAUUSD", "dist": 19.1} for i in range(10)]
    admitted, _ = NS["cap_by_heat"](sl, EQ, 0.01, None)
    assert len(admitted) == int(NS["heat_budget"](None) / 0.01)


# ------------------------------------------------- the live path, not just the helpers

def test_the_trade_loop_passes_the_sleeve_s_own_symbol_and_live_info():
    """The fix is only real if the trade loop hands over the instrument. A source check,
    because the loop itself needs a live terminal to run."""
    assert 'auto_lot(equity, dist, s["symbol"], sym)' in _SRC
    assert 'promoted_lot(equity, sleeve_live_n(s["name"]), dist, s["symbol"], sym)' in _SRC
    assert 'realised_q(equity, dist, s["symbol"], sym)' in _SRC
    assert "cannot price" in _SRC


def test_no_sizing_call_site_omits_the_symbol():
    """A bare auto_lot(equity, dist) in the trade loop is the bug returning, one argument later."""
    tree = ast.parse(_SRC)
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", "")
        if name == "auto_lot" and len(node.args) < 3:
            bad.append(("auto_lot", node.lineno))
        if name == "promoted_lot" and len(node.args) < 4:
            bad.append(("promoted_lot", node.lineno))
    # promoted_lot's own body calls auto_lot(equity, dist_usd, symbol, info) -- 4 args, fine.
    assert not bad, f"sizing call without a symbol: {bad}"


def test_the_legacy_constants_are_not_on_the_sizing_path():
    """CONTRACT_OZ * FX_EUR may survive as gold's documented fallback and as MIN_LOT_RISK_EUR.
    It may NOT be how a lot is computed, which is what this asserts by counting call sites."""
    tree = ast.parse(_SRC)
    for fn in ("auto_lot", "realised_q", "promoted_lot"):
        node = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == fn)
        # The docstrings quote the old formula DELIBERATELY, as the record of what went wrong,
        # so strip them via the AST rather than by guessing at quote characters. Only executable
        # statements are examined.
        stmts = node.body[1:] if (node.body and isinstance(node.body[0], ast.Expr)
                                  and isinstance(node.body[0].value, ast.Constant)
                                  and isinstance(node.body[0].value.value, str)) else node.body
        names = {n.id for s in stmts for n in ast.walk(s) if isinstance(n, ast.Name)}
        assert "CONTRACT_OZ" not in names, f"{fn} still sizes from gold's contract constant"
        assert "FX_EUR" not in names, f"{fn} still sizes from the frozen EUR/USD constant"
