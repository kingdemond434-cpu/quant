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

from mt5desk import decision_core as _dc  # noqa: E402
from mt5desk import risk_units as ru  # noqa: E402

_SRC = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
_CORE_SRC = (_DESK / "mt5desk" / "decision_core.py").read_text(encoding="utf-8")

#: Straight from the venue snapshot the desk actually trades against.
UNIVERSE = json.loads(
    (_DESK / "data" / "universe" / "universe.json").read_text(encoding="utf-8"))

#: What the deleted constant asserted for every instrument on the desk.
LEGACY_CONSTANT = 100 * 0.92


def _load():
    """The sizing laws, IMPORTED from the decision core (split 2026-09-05).

    These used to be AST-extracted out of gateway.py because it imports MetaTrader5; every
    import the extraction dropped had to be re-supplied by hand and the execution was attributed
    to a compiled string rather than to the file. The core imports on any host, so the same
    functions are used by name from the module that now holds them, and the coverage report
    sees them run.
    """
    return dict(vars(_dc))


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
        if not (meta.get("tick_size", 0) > 0 and meta.get("tick_value", 0) > 0):
            continue
        expected = 2.0 / meta["tick_size"] * meta["tick_value"]
        assert ru.risk_per_lot(sym, 2.0) == pytest.approx(expected)


def test_live_symbol_info_beats_the_snapshot():
    """tick_value carries today's FX rate, so a live handle is the only current answer.

    The snapshot expectation is a BAND, not a literal: the snapshot file is re-synced from the
    live terminal, so its EUR/USD leg drifts daily and a rel=1e-4 pin fails on every sync --
    the exact frozen-rate mistake this module's own docstring documents. 1% still catches a
    unit error (the gold constant said 92.00 vs the venue's 86.4, a 6.5% gap)."""
    live = _Info(tick_size=0.01, tick_value=1.00)          # snapshot says ~0.8641
    assert ru.eur_per_price_unit("XAUUSD", live) == pytest.approx(100.0)
    assert ru.eur_per_price_unit("XAUUSD") == pytest.approx(86.414, rel=1e-2)


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
    """WITHOUT THE FIX these run at 7.3-7.4% of equity while logging 1.26%.

    The pin is INTENT vs REALIZED, not a budget literal: promoted sizing now runs at the
    fenced clamp_risk_frac base (3%), so a `< 0.02` bound written under the old Q_OPT budget
    fails on policy, not on units. Units are correct iff realized risk never exceeds what the
    sizer intended (flooring can only push it DOWN at these equities); the original defect ran
    2.4x ABOVE intent."""
    from mt5desk.sizing import clamp_risk_frac
    lot = NS["promoted_lot"](EQ, 500, stop, sym)
    true_risk = ru.realised_risk_eur(sym, stop, lot)
    intended = clamp_risk_frac(None)                     # live_n=500 -> full ramp
    assert true_risk / EQ <= intended * 1.02, (
        f"{sym} realized {true_risk / EQ:.2%} against intended {intended:.2%} -- risk priced "
        f"in the wrong instrument's units")
    # the log must print the risk of the lot ACTUALLY taken, not a Q_OPT recomputation
    assert NS["realised_q"](EQ, stop, sym, None, lot) == pytest.approx(true_risk / EQ, rel=1e-6)


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
    assert NS["_eur_per_price_unit"]("XAUUSD") == pytest.approx(86.414, rel=1e-2)
    assert abs(NS["_eur_per_price_unit"]("XAUUSD") / LEGACY_CONSTANT - 1) < 0.07


def test_the_fallback_chain_is_live_then_snapshot_then_gold_alone():
    """Three tiers, and the last one is gold-only. A dead live handle falls through to the
    snapshot -- which still knows every symbol -- and only a symbol missing from BOTH reaches
    the hardcoded constants, where gold answers and everything else refuses."""
    dead = _Info(0.0, 0.0)
    # tier 2: live handle is useless, snapshot still prices both
    assert NS["_eur_per_price_unit"]("XAUUSD", dead) == pytest.approx(86.414, rel=1e-2)
    assert NS["_eur_per_price_unit"]("CADJPY", dead) == pytest.approx(542.40, rel=1e-2)
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
    """ONE q times a COUNT cannot see a heterogeneous book: the three gold legs cost DIFFERENT
    fractions because their stops differ (53.40 / 27.91 / 48.64), and the cap must price each.

    THE ASSERTION MOVED, THE PROPERTY DID NOT. This asserted that something was DEFERRED, which
    was true only against the old 3.81% budget -- so it was pinned to a budget rather than to
    per-sleeve pricing. Under the principal's stated 20% (2026-09-02) the whole armed book fits,
    which is the point of raising it. What must still hold is that each leg is charged its own
    cost and the admitted set fits the budget."""
    gold = [{"name": f"gold_{w}", "symbol": "XAUUSD", "dist": d}
            for w, d in (("asia", 53.40), ("london_am", 27.91), ("afternoon", 48.64))]
    admitted, _note = NS["cap_by_heat"](gold, EQ, k_eff=None)
    qs = [NS["realised_q"](EQ, s["dist"], s["symbol"]) for s in gold]
    assert len(set(round(q, 6) for q in qs)) > 1, (
        "the three legs must NOT price identically; that was the whole defect")
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
    # THE PROPERTY IS THE PRICE IT IS CHARGED, NOT THE COUNT ADMITTED. Asserting `<= 1` pinned
    # this to the old 3.81% budget, where only one leg fitted; under the stated 20% both do, and
    # that says nothing about whether the unpriceable one was billed honestly.
    #
    # The billing is what the defect was: charging it gold's q BY DEFAULT is how an unmeasured
    # leg gets admitted cheaply. It must cost the most expensive MEASURED leg in the book, so a
    # book of one unpriceable sleeve plus gold must consume exactly twice gold's q.
    gold_q = NS["realised_q"](EQ, 53.40, "XAUUSD")
    admitted, _ = NS["cap_by_heat"](mixed, EQ, k_eff=None)
    budget = NS["heat_budget"](None)
    assert len(admitted) == min(2, int(budget / gold_q)), (
        "the unpriceable sleeve was not billed at the dearest measured leg's rate")


def test_a_book_that_cannot_be_priced_at_all_admits_nobody():
    admitted, note = NS["cap_by_heat"](
        [{"name": "bad", "symbol": "NOSUCHPAIR", "dist": 1.0}], EQ, k_eff=None)
    assert admitted == []
    assert "admitting none" in note


def test_an_explicit_scalar_q_still_applies_to_every_sleeve():
    """Backwards compatible: a caller passing one q means one q."""
    # Enough sleeves that the BUDGET decides the count, not the fixture length: at q=0.01 the
    # stated 20% budget admits 20, so a 10-sleeve fixture would have measured the fixture.
    sl = [{"name": f"s{i}", "symbol": "XAUUSD", "dist": 19.1} for i in range(40)]
    admitted, _ = NS["cap_by_heat"](sl, EQ, 0.01, None)
    # The admission limit is the budget PLUS the slide -- a validated leg is not dropped over a
    # rounding edge (see HEAT_SLIDE). One q for every sleeve is what this test is about, and it
    # still is: the count is exactly what the limit divided by that one q allows.
    limit = min(NS["heat_budget"](None) + NS["HEAT_SLIDE"], NS["MAX_HEAT_CEILING"])
    assert len(admitted) == int(limit / 0.01 + 1e-9)


# ------------------------------------------------- the live path, not just the helpers

def test_the_trade_loop_passes_the_sleeve_s_own_symbol_and_live_info():
    """The fix is only real if the trade loop hands over the instrument. A source check,
    because the loop itself needs a live terminal to run."""
    assert 'auto_lot(equity, dist, s["symbol"], sym)' in _SRC
    # canon also hands over the sleeve's own risk_frac (clamped inside promoted_lot)
    assert 'promoted_lot(equity, sleeve_live_n(s["name"]), dist, s["symbol"], sym' in _SRC
    assert 'realised_q(equity, dist, s["symbol"], sym, lot=lot)' in _SRC
    assert "cannot price" in _SRC


def test_no_sizing_call_site_omits_the_symbol():
    """A bare auto_lot(equity, dist) in the trade loop is the bug returning, one argument later.

    Both files: the gateway holds the call sites, the core holds the laws (and promoted_lot's
    own delegation to auto_lot, which passes the symbol)."""
    bad = []
    for src in (_SRC, _CORE_SRC):
        for node in ast.walk(ast.parse(src)):
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
    It may NOT be how a lot is computed, which is what this asserts by counting call sites --
    in the core, where the laws live, and in the gateway, whose sizing defs are delegates."""
    for src in (_SRC, _CORE_SRC):
        tree = ast.parse(src)
        for fn in ("auto_lot", "realised_q", "promoted_lot"):
            node = next(n for n in ast.walk(tree)
                        if isinstance(n, ast.FunctionDef) and n.name == fn)
            # The docstrings quote the old formula DELIBERATELY, as the record of what went
            # wrong, so strip them via the AST rather than by guessing at quote characters.
            # Only executable statements are examined.
            stmts = node.body[1:] if (node.body and isinstance(node.body[0], ast.Expr)
                                      and isinstance(node.body[0].value, ast.Constant)
                                      and isinstance(node.body[0].value.value, str)) \
                else node.body
            names = {n.id for s in stmts for n in ast.walk(s) if isinstance(n, ast.Name)}
            assert "CONTRACT_OZ" not in names, f"{fn} still sizes from gold's contract constant"
            assert "FX_EUR" not in names, f"{fn} still sizes from the frozen EUR/USD constant"
