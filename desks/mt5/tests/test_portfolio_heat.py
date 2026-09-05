"""No sleeve is sized against the account; only the book is.

The gateway had NO portfolio cap. Promoted sleeves each take a fixed 0.01 lot -- 1.04% of equity
at EUR 1,684 -- and `load_sleeves()` returned every LIVE one with no count or aggregate limit.
The shadow set is ten sleeves, so ten promotions meant ~10% of the account at risk in a single
morning. Per-sleeve risk control is not risk control: correlated sleeves fire together in exactly
the regimes that hurt.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk import decision_core as _dc  # noqa: E402

_SRC = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")


def _load():
    """The heat cap and the sizing laws, IMPORTED from the decision core (split 2026-09-05).

    They used to be AST-extracted out of gateway.py, which imports MetaTrader5. The risk budget
    is still NOT re-extracted from source: the core imports it from gateway_config_fallback,
    which this box CAN import, so the values here are the real ones. The two drawdown inputs
    the derivation test reads are supplied beside the module's own names.
    """
    from mt5desk.gateway_config_fallback import BOOK_WORST_DD_R, MAX_DRAWDOWN_TOLERANCE
    ns = dict(vars(_dc))
    ns.update({"MAX_DRAWDOWN_TOLERANCE": MAX_DRAWDOWN_TOLERANCE,
               "_BOOK_WORST_DD_R": BOOK_WORST_DD_R})
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
    # THE INVARIANT IS THE BUDGET, NOT THE COUNT. This read `< 10` when the budget was 3.81%,
    # where ten 1.04% sleeves could not fit. Under the principal's stated 20% they do -- and that
    # is the budget working, not failing: what a heat cap forbids is total risk growing with the
    # sleeve count, which the line above already asserts. Pinning a count pins the test to one
    # budget instead of to the property.
    assert len(admitted) <= 10
    # NOTHING IS DEFERRED HERE ANY MORE and that is correct: ten sleeves at ~0.98% total 9.8%,
    # which fits inside the stated 20%. The note is asserted where the budget actually binds
    # (test_dropped_sleeves_are_named_not_silent); asserting it here would require the budget to
    # be small enough to drop something, which is a fixture wish, not a property.
    assert note is None or "PORTFOLIO HEAT CAP" in note


def test_dropped_sleeves_are_named_not_silent():
    """A silently shortened book is indistinguishable from one that had nothing to trade."""
    # Enough sleeves to actually breach the STATED budget: at EUR 1,684 each costs ~1.04%, so
    # ten fit inside 20% and thirty do not. This test is about the NOTE, so it must cause a drop.
    sleeves = _sleeves(30)
    admitted, note = NS["cap_by_heat"](sleeves, 1684.0)
    assert note and "deferring" in note
    # NAME WHATEVER WAS ACTUALLY DROPPED. This asserted "s9" -- the sleeve the 3.81% budget
    # happened to defer -- so it was pinned to a budget rather than to the property, and moving
    # the budget broke a test about LOGGING. The property is that every dropped sleeve is
    # identifiable from the line.
    dropped = [x["name"] for x in sleeves if x not in admitted]
    assert dropped, "the budget did not bind; the note is untested"
    for name in dropped:
        assert name in note, f"{name} was deferred and does not appear in the log line"


def test_the_validated_gold_book_is_never_amputated_by_the_cap():
    """THE CAP MUST NOT DISMEMBER THE PROVEN BOOK. At EUR 1,684 each sleeve is 1.04%, so the
    three armed gold legs are 3.12% of equity. A 3% cap -- the first value tried -- dropped
    gold_afternoon, sacrificing a leg with walk-forward evidence and human authorisation to a
    round number. The budget is set so the validated core fits and ADDITIONS must be earned."""
    gold = [{"name": "gold_asia"}, {"name": "gold_london_am"}, {"name": "gold_afternoon"}]
    admitted, note = NS["cap_by_heat"](list(gold), 1684.0)
    # SET, NOT SEQUENCE. The property is that the armed book is never AMPUTATED; the order
    # within it is now decided by marginal dE[log W] (gateway.allocator_order), which is the
    # whole point of ranking by what a sleeve is worth instead of where the caller put it.
    # Asserting a sequence here pinned the test to the old age-ordering it was written under.
    assert {s["name"] for s in admitted} == {g["name"] for g in gold}, (
        "the armed gold book does not fit inside MAX_PORTFOLIO_HEAT at live equity")
    assert note is None


def test_promoted_sleeves_are_what_gets_deferred():
    """sleeve_set() puts gold first, so order preservation means unproven sleeves are dropped
    first -- the correct seniority."""
    sleeves = [{"name": "gold_asia"}, {"name": "gold_london_am"}, {"name": "gold_afternoon"}]
    # 27 promoted sleeves, not 7: the budget has to BIND for seniority to be observable, and at
    # EUR 1,684 under the stated 20% budget ten sleeves fit comfortably.
    sleeves += [{"name": f"promoted_{i}"} for i in range(27)]
    admitted, note = NS["cap_by_heat"](sleeves, 1684.0)
    names = [s["name"] for s in admitted]
    assert set(names[:3]) == {"gold_asia", "gold_london_am", "gold_afternoon"}
    assert len(admitted) < len(sleeves), "the budget did not bind; seniority is untested"
    # The proven book comes first AS A SET -- its internal order is the allocator's marginal
    # ranking, not a fixed list, so pinning the sequence would test the ranking rather than the
    # seniority this test is about.
    assert set(names[:3]) == {"gold_asia", "gold_london_am", "gold_afternoon"}, (
        "the proven book must be admitted before any unproven sleeve")
    assert note and "promoted_" in note


def test_a_validated_leg_is_not_dropped_over_a_rounding_edge():
    """MEASURED 2026-09-02: the armed gold book priced at 20.3% against a 20.0% budget and
    gold_afternoon -- a validated, human-armed session -- was deferred over three tenths of one
    point. The cost is not the 0.3%, it is a whole session of the day going untraded, and the
    leg's price floats with its stop distance (the same book was 13.1% earlier that afternoon).
    """
    q = NS["realised_q"](1684.0)
    budget = NS["heat_budget"]()
    # A book that lands just over the budget, inside the slide.
    n = int(budget // q) + 1
    over = _sleeves(n)
    admitted, _note = NS["cap_by_heat"](over, 1684.0)
    assert len(admitted) * q > budget, "the fixture did not actually exceed the budget"
    assert len(admitted) == n, "a leg was dropped inside the slide band"


def test_the_slide_is_a_tolerance_and_never_a_new_budget():
    """A book genuinely far over budget is still trimmed -- otherwise the slide IS the budget."""
    far = _sleeves(60)
    admitted, note = NS["cap_by_heat"](far, 1684.0)
    q = NS["realised_q"](1684.0)
    assert len(admitted) < 60 and note
    assert len(admitted) * q <= NS["heat_budget"]() + NS["HEAT_SLIDE"] + 1e-9


def test_the_slide_can_never_lift_the_book_past_the_hard_bar():
    """THE 30% CEILING IS ABSOLUTE. The slide is applied against min(budget + slide, ceiling),
    so no future widening of it can reach the bar the principal set."""
    assert NS["heat_budget"]() + NS["HEAT_SLIDE"] <= NS["MAX_HEAT_CEILING"] + 1e-12
    for k_eff in (None, 2.26, 5.12, 9.0, 40.0):
        admitted, _ = NS["cap_by_heat"](_sleeves(80), 1684.0, k_eff=k_eff)
        used = len(admitted) * NS["realised_q"](1684.0)
        assert used <= NS["MAX_HEAT_CEILING"] + 1e-9, f"k_eff={k_eff} breached the hard bar"


def test_the_note_names_the_slide_so_the_band_is_never_invisible():
    _admitted, note = NS["cap_by_heat"](_sleeves(60), 1684.0)
    assert note and "slide" in note and "ceiling" in note


def test_a_small_account_gets_fewer_sleeves_not_more_risk():
    """The 0.01 floor makes each sleeve a LARGER fraction as equity falls, so a sleeve-COUNT cap
    would let total risk grow silently on a shrinking account. A heat budget cannot."""
    big, _ = NS["cap_by_heat"](_sleeves(10), 8000.0)
    small, _ = NS["cap_by_heat"](_sleeves(10), 600.0)
    assert len(small) < len(big)
    for eq in (600.0, 1684.0, 8000.0):
        adm, _ = NS["cap_by_heat"](_sleeves(10), eq)
        # The admission limit is the budget PLUS the slide (see HEAT_SLIDE): a validated leg is
        # not dropped over a rounding edge. The property this test exists for is unchanged --
        # total risk still cannot grow as equity falls -- and the hard ceiling still binds.
        assert len(adm) * NS["realised_q"](eq) <= (
            NS["heat_budget"]() + NS["HEAT_SLIDE"] + 1e-9), f"heat breached at equity {eq}"


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
    # The BASE is the principal's stated portfolio budget since 2026-09-02; the drawdown
    # derivation still governs per-trade sizing and is asserted in its own test above.
    assert base == pytest.approx(NS["HEAT_TARGET"], rel=1e-6)
    # THE CEILING NOW BINDS INSIDE THE MEASURABLE RANGE. base x sqrt(5.12/2.26) is 30.1%, above
    # MAX_HEAT_CEILING, so the scaling law is asserted where it is free and the ceiling where it
    # is not -- rather than asserting an uncapped figure the function is right to refuse.
    mid = 2.26 * 1.2
    assert NS["heat_budget"](mid) == pytest.approx(
        min(base * (mid / 2.26) ** 0.5, NS["MAX_HEAT_CEILING"]), rel=1e-6)
    assert NS["heat_budget"](9.0) >= NS["heat_budget"](5.12) >= base
    assert NS["heat_budget"](9.0) == pytest.approx(NS["MAX_HEAT_CEILING"], rel=1e-9), (
        "breadth may earn heat up to the hard ceiling and never past it")


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
    assert q_star == pytest.approx(0.0127, abs=0.0005), "the per-trade derivation still holds"

    # THE PORTFOLIO BUDGET IS NOW A STATED NUMBER, and this test's job changed with it. It used
    # to assert budget == q* x legs; the principal set a 20% portfolio target on 2026-09-02, so
    # the budget is that and the derivation above governs PER-TRADE sizing only.
    assert NS["heat_budget"](None) == pytest.approx(NS["HEAT_TARGET"], rel=1e-9)

    # WHAT THE STATED BUDGET COSTS AGAINST THE DERIVED ONE, asserted so it can never be quietly
    # forgotten: on THIS book's measured 33.7R worst run, the derived 3.81% spends exactly the
    # 35% tolerance, and the stated 20% spends ~90%. The gap is the price of the decision, and it
    # is a fact about the three-leg CORRELATED gold book -- twenty independent sleeves do not all
    # lose together, which is why heat_policy ramps the allocator's floor with measured breadth
    # rather than asserting 20% on day one.
    derived = q_star * NS["_HEAT_BASE_LEGS"]
    dd = lambda h: 1.0 - (1.0 - h / NS["_HEAT_BASE_LEGS"]) ** NS["_BOOK_WORST_DD_R"]  # noqa: E731
    assert dd(derived) == pytest.approx(NS["MAX_DRAWDOWN_TOLERANCE"], abs=0.005)
    assert dd(NS["HEAT_TARGET"]) > 0.85, (
        "the stated budget's drawdown cost on this book must stay visible in a test")


def test_the_armed_gold_book_fits_at_live_equity():
    """REGRESSION. Multiplying q* by k_eff instead of the validated LEG COUNT double-counted the
    diversification already inside the -33.7R summed series and returned 2.87% -- below the 3.12%
    the gold book actually runs, amputating the book the budget is calibrated on."""
    gold = [{"name": f"gold_{w}"} for w in ("asia", "london_am", "afternoon")]
    admitted, note = NS["cap_by_heat"](list(gold), 1684.0)
    assert len(admitted) == 3 and note is None
