"""KNOWN-ANSWER tests for the counterfactual world: worlds built by hand, arms with an answer.

Every case here is a tape whose outcome is arithmetic, so a wrong sign or a lost cost shows up as
a number rather than as a plausible-looking report:

  * a skipped bracket that the market took straight to its target reads MISSED_TRADE_ALPHA > 0 --
    the money the veto left behind, in log-wealth;
  * the SAME tape read as a veto rule reads the rail's own sign: `mean_avoided_r` NEGATIVE,
    because the veto cost rather than saved;
  * 1.5x on a loser reads a NEGATIVE 1.5x arm and 0.5x a positive one, and the two are not
    symmetric, because log-wealth is not linear in size -- which is the whole reason sizing alpha
    is measured in log-wealth and not in R;
  * a bracket the market never reached is NOT_TRIGGERED and enters no class at all, rather than
    counting as a harmless zero;
  * under MIN_N every class is UNMEASURED with its n and no numbers;
  * the cost model that priced a row is stamped on it, and the resolution order is twin, then
    surface, then the registry baseline.
"""
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from libs.research.counterfactual_world import (
    ALPHA_CLASSES,
    MIN_N,
    MIN_N_VETO,
    NOT_TRIGGERED,
    PRICED,
    SIZE_ARMS,
    UNMEASURED,
    UNPRICED,
    Bar,
    CostModel,
    aggregate,
    bars_from_rows,
    cost_model_baseline,
    price_row,
    resolve_cost_model,
    top_decisions,
)

T0 = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
FREE = CostModel(source="test", why="frictionless so the arithmetic is checkable",
                 spread_frac=0.0, slip_frac=0.0)
#: A gold-shaped registry row: 15 points of 0.01 spread on a 100 oz contract.
META: dict[str, Any] = {"contract_size": 100.0, "tick_size": 0.01, "tick_value": 1.0,
                        "median_spread_pts": 15.0, "digits": 2}


def _bars(seq: list[tuple[float, float, float, float]]) -> list[Bar]:
    return [Bar(ts=T0 + timedelta(hours=i), open=o, high=h, low=lo, close=c)
            for i, (o, h, lo, c) in enumerate(seq)]


#: The three bars before the bracket at 2000 is reached, on every tape below: the decision bar,
#: one that approaches without triggering, and the one whose high takes the entry.
_APPROACH: list[tuple[float, float, float, float]] = [
    (1995.0, 1996.0, 1994.0, 1995.0), (1996.0, 1999.5, 1995.5, 1999.0),
]


def _winner() -> list[Bar]:
    """Triggers the 2000 buy stop and marches to the 2020 target -- and never once pulls back a
    spread, so the limit arm on this tape gets no fill."""
    seq = [*_APPROACH, (1999.0, 2002.0, 2000.2, 2001.5)]
    px = 2001.5
    for _ in range(30):
        seq.append((px, px + 2.0, px - 0.5, px + 1.5))
        px += 1.5
    return _bars(seq)


def _loser() -> list[Bar]:
    """Triggers the same bracket and walks straight down through the 1990 stop: exactly -1R."""
    seq = [*_APPROACH, (1999.0, 2002.0, 2000.2, 2000.5)]
    px = 2000.5
    for _ in range(30):
        seq.append((px, px + 0.5, px - 2.0, px - 1.5))
        px -= 1.5
    return _bars(seq)


def _pullback() -> list[Bar]:
    """Triggers, comes back through the limit's stated distance, then runs to the target."""
    seq = [*_APPROACH, (1999.0, 2002.0, 2000.2, 2001.0), (2001.0, 2001.5, 1999.0, 2000.0)]
    px = 2000.0
    for _ in range(30):
        seq.append((px, px + 2.0, px - 0.5, px + 1.5))
        px += 1.5
    return _bars(seq)


def _reversal() -> list[Bar]:
    """Runs past +1R, turns, and gives it all back through the entry: the tape on which a fixed
    stop, a trail and a partial are three different numbers."""
    seq = [*_APPROACH, (1999.0, 2002.0, 2000.2, 2001.0)]
    seq += [(2001.0 + 2 * i, 2003.0 + 2 * i, 2000.0 + 2 * i, 2002.0 + 2 * i) for i in range(7)]
    px = float(seq[-1][3])
    seq += [(px - 2 * i, px - 2 * i + 0.5, px - 2 * i - 2.5, px - 2 * i - 2.0) for i in range(20)]
    return _bars(seq)


def _flat() -> list[Bar]:
    """A market that never offers the entry at all."""
    return _bars([(1995.0, 1996.0, 1994.0, 1995.0)] * 40)


def _row(*, taken: bool, price: float = 2000.0, sl: float = 1990.0, tp: float = 2020.0,
         side: str = "buy_stop", veto: str = "regime_hibernate", size_mult: float = 1.0,
         r_realised: float | None = None, minute: datetime = T0) -> dict[str, Any]:
    chosen: dict[str, Any] = {"kind": "enter" if taken else "skip", "side": side, "price": price,
                              "sl": sl, "tp": tp, "size_mult": size_mult,
                              "execution": "pending_stop", "exit_rule": "fixed_tp",
                              "veto_reason": "" if taken else veto}
    outcome: dict[str, Any] = ({"status": "RESOLVED", "r_multiple": r_realised} if taken
                               else {"status": "NOT_APPLICABLE"})
    return {"row_id": f"{side}|{minute.isoformat()}", "minute": minute.isoformat(),
            "symbol": "XAUUSD", "sleeve": "gold_break", "side": side,
            "world_state": {"allocator": {"h": 0.02}},
            "candidate_actions": [], "chosen_action": chosen, "outcome": outcome}


def _priced(row: dict[str, Any], blk: dict[str, Any], n: int) -> list[dict[str, Any]]:
    return [{**row, "row_id": f"{row['row_id']}|{i}",
             "counterfactual_outcomes": blk} for i in range(n)]


def _arm(blk: dict[str, Any], cls: str, arm: str) -> dict[str, Any]:
    return next(a for a in blk["alternatives"] if a["class"] == cls and a["arm"] == arm)


# ------------------------------------------------------------------ missed trades and vetoes

def test_a_skipped_bracket_that_would_have_made_two_r_reads_positive_missed_trade_alpha() -> None:
    """THE KNOWN ANSWER. Entry 2000, stop 1990 (10 of risk), target 2020: the tape walks up, so
    the bracket triggers and the target prints. +2R, frictionless, and the class must say so."""
    blk = price_row(_row(taken=False), _winner(), FREE)
    assert blk["status"] == PRICED
    assert blk["baseline"]["r"] == 2.0 and blk["baseline"]["exit_reason"] == "target"
    entered = _arm(blk, "MISSED_TRADE_ALPHA", "entered")
    assert entered["r"] == 2.0 and entered["d_r"] == 2.0
    # log-wealth at h = 2%: log(1 + 0.02 * 2)
    assert entered["d_elog"] == round(math.log(1.04), 9) > 0

    agg = aggregate(_priced(_row(taken=False), blk, MIN_N))
    mt = agg["MISSED_TRADE_ALPHA"]
    assert mt["status"] == "MEASURED" and mt["alpha"] > 0
    assert mt["reads"] == "the desk's skips cost growth"
    assert mt["arms"]["entered"]["n"] == MIN_N


def test_the_same_tape_reads_the_rails_own_sign_for_the_veto_that_refused_it() -> None:
    """`missed_growth.measure_veto` reads `mean_avoided_r` and `filter_value_r` off the report,
    positive when the veto SAVED money. A veto that refused +2R saved -2R, and the two engines
    must not disagree about which way that points."""
    row = _row(taken=False, veto="regime_hibernate")
    blk = price_row(row, _winner(), FREE)
    agg = aggregate(_priced(row, blk, MIN_N_VETO))
    rail = agg["VETO_ALPHA"]["arms"]["regime_hibernate"]
    assert rail["n_vetoed_and_triggered"] == MIN_N_VETO
    assert rail["mean_avoided_r"] == -2.0
    assert rail["filter_value_r"] == -2.0 * MIN_N_VETO
    assert rail["mean"] > 0                      # this module's sign: the veto cost growth
    assert "veto with the largest bill" in agg["VETO_ALPHA"]["reads"]


def test_a_veto_that_refused_a_loser_reads_the_other_way_and_is_not_hidden() -> None:
    row = _row(taken=False, veto="margin_guard")
    blk = price_row(row, _loser(), FREE)          # the tape walks down
    assert blk["baseline"]["exit_reason"] == "stop" and blk["baseline"]["r"] == -1.0
    agg = aggregate(_priced(row, blk, MIN_N_VETO))
    rail = agg["VETO_ALPHA"]["arms"]["margin_guard"]
    assert rail["mean_avoided_r"] == 1.0 and rail["filter_value_r"] > 0
    assert rail["mean"] < 0                      # the desk was RIGHT, and it still prints
    assert agg["MISSED_TRADE_ALPHA"]["alpha"] < 0
    assert agg["MISSED_TRADE_ALPHA"]["reads"] == "the desk's skips saved growth"


# ------------------------------------------------------------------ sizing

def test_one_and_a_half_x_on_a_loser_reads_negative_sizing_alpha() -> None:
    """THE KNOWN ANSWER, the other way. A taken trade that stopped out: sizing UP made it worse
    and sizing DOWN made it better, and the two are not mirror images, because the class is
    measured in log-wealth."""
    row = _row(taken=True, r_realised=-1.0)
    blk = price_row(row, _loser(), FREE)
    assert blk["baseline"]["r"] == -1.0 and blk["chosen"]["r"] == -1.0
    up, down = _arm(blk, "SIZING_ALPHA", "1.5x"), _arm(blk, "SIZING_ALPHA", "0.5x")
    assert up["d_elog"] < 0 < down["d_elog"]
    assert abs(up["d_elog"]) > abs(down["d_elog"])       # log-wealth punishes the upsize harder
    assert _arm(blk, "SIZING_ALPHA", "1.0x")["d_elog"] == 0.0

    agg = aggregate(_priced(row, blk, MIN_N))
    arms = agg["SIZING_ALPHA"]["arms"]
    assert set(arms) == {f"{m:.1f}x" for m in SIZE_ARMS}
    assert arms["1.5x"]["mean"] < 0 and arms["1.5x"]["status"] == "MEASURED"
    assert arms["1.5x"]["ci95"][1] < 0 or arms["1.5x"]["sd"] == 0.0
    assert agg["SIZING_ALPHA"]["alpha"] == arms["0.5x"]["mean"] > 0


def test_sizing_up_a_winner_reads_positive_and_the_realised_r_sits_beside_the_replay() -> None:
    row = _row(taken=True, r_realised=1.9)
    blk = price_row(row, _winner(), FREE)
    assert _arm(blk, "SIZING_ALPHA", "1.5x")["d_elog"] > 0
    # the arms are differenced against the REPLAY, and the realised R is carried beside it so a
    # reader can see how far the replay is from the tape it is standing in for
    assert blk["r_realised"] == 1.9 and blk["replay_error_r"] == round(1.9 - 2.0, 5)


# ------------------------------------------------------------------ execution and exit

def test_the_limit_arm_only_fills_when_the_market_comes_back_for_it() -> None:
    """A stated distance, and the tape decides. A market that never pulls back leaves the limit
    arm NOT_TRIGGERED rather than crediting it with a fill it never got."""
    cost = CostModel(source="test", why="one bp of spread", spread_frac=1e-4, slip_frac=0.0)
    away = price_row(_row(taken=True), _winner(), cost)
    assert _arm(away, "EXECUTION_ALPHA", "limit")["status"] == NOT_TRIGGERED
    assert _arm(away, "EXECUTION_ALPHA", "market")["status"] == PRICED
    assert away["limit_offset_spreads"] == 1.0

    # a tape that dips back through the improved level after triggering: the limit fills better
    back = price_row(_row(taken=True), _pullback(), cost)
    lim = _arm(back, "EXECUTION_ALPHA", "limit")
    assert lim["status"] == PRICED and lim["how"] == "limit_filled"
    assert lim["d_elog"] > 0                       # entered better, so it kept more of the move


def test_every_exit_rule_is_priced_and_the_trail_beats_a_fixed_stop_on_a_reversal() -> None:
    """The tape runs to +1.5R and then reverses through the entry: the fixed bracket gives it all
    back to the stop, the trail keeps a R behind the high, and the partial banks half at +1R."""
    blk = price_row(_row(taken=True, tp=2100.0), _reversal(), FREE)
    arms = {a["arm"]: a for a in blk["alternatives"] if a["class"] == "EXIT_ALPHA"}
    assert set(arms) == {"fixed_tp", "trail", "hold", "partial"}
    assert all(a["status"] == PRICED for a in arms.values())
    assert arms["fixed_tp"]["r"] < 0 and arms["fixed_tp"]["exit_reason"] == "stop"
    assert arms["trail"]["r"] > arms["fixed_tp"]["r"]
    assert arms["trail"]["exit_reason"] == "trail_stop"
    assert arms["partial"]["r"] > arms["fixed_tp"]["r"]      # half was banked at +1R
    assert arms["trail"]["d_elog"] > 0


# ------------------------------------------------------------------ what is NOT priced

def test_a_bracket_the_market_never_offered_is_not_a_zero() -> None:
    blk = price_row(_row(taken=False), _flat(), FREE)
    assert blk["status"] == NOT_TRIGGERED and blk["alternatives"] == []
    assert "no P&L in either direction" in blk["why"]
    agg = aggregate([{"counterfactual_outcomes": blk}] * 50)
    assert agg["n_priced"] == 0
    assert agg["row_status"][NOT_TRIGGERED] == 50
    for cls in ALPHA_CLASSES:
        assert agg[cls]["status"] == UNMEASURED and agg[cls]["n"] == 0


def test_a_row_with_no_stop_or_no_side_is_unpriced_and_says_why() -> None:
    bars = _winner()
    assert price_row(_row(taken=False, sl=2000.0), bars, FREE)["status"] == UNPRICED
    no_side = _row(taken=False)
    no_side["side"] = ""
    no_side["chosen_action"]["side"] = ""
    blk = price_row(no_side, bars, FREE)
    assert blk["status"] == UNPRICED and "nothing to replay" in blk["why"]


def test_a_tape_that_does_not_reach_the_decision_is_no_bars_and_never_a_zero() -> None:
    assert price_row(_row(taken=False), [], FREE)["status"] == "NO_BARS"
    blk = price_row(_row(taken=False), _winner()[:6], FREE)
    assert blk["status"] == "NO_BARS" and "PENDING, not zero" in blk["why"]


def test_a_thin_sample_is_unmeasured_with_its_n_and_no_numbers() -> None:
    row = _row(taken=True, r_realised=-1.0)
    blk = price_row(row, _loser(), FREE)
    agg = aggregate(_priced(row, blk, MIN_N - 1))
    sizing = agg["SIZING_ALPHA"]
    assert sizing["status"] == UNMEASURED and sizing["alpha"] is None
    for arm in sizing["arms"].values():
        assert arm["status"] == UNMEASURED and arm["mean"] is None and arm["ci95"] is None
        assert arm["n"] == MIN_N - 1 and str(MIN_N) in arm["why"]
    # a veto reason needs MORE than a class does, because a reason is a RULE
    veto_row = _row(taken=False)
    veto_blk = price_row(veto_row, _winner(), FREE)
    thin = aggregate(_priced(veto_row, veto_blk, MIN_N_VETO - 1))
    assert thin["VETO_ALPHA"]["arms"]["regime_hibernate"]["status"] == UNMEASURED
    assert thin["VETO_ALPHA"]["arms"]["regime_hibernate"]["verdict"] == "UNDETERMINED"


# ------------------------------------------------------------------ the cost model

def test_the_cost_model_that_priced_a_row_is_stamped_on_it() -> None:
    model = cost_model_baseline("XAUUSD", META, price=2000.0)
    blk = price_row(_row(taken=True), _winner(), model)
    stamped = blk["cost_model"]
    assert stamped["source"] == "costs_baseline" and "honest baseline" in stamped["why"]
    # 15 pts x 0.01 x the honest 2.0 multiplier, over a 2000 price
    assert stamped["spread_frac"] == round(15.0 * 0.01 * 2.0 / 2000.0, 9)
    assert stamped["commission_frac"] > 0
    assert aggregate([{"counterfactual_outcomes": blk}])["cost_model_sources"] == \
        {"costs_baseline": 1}
    # and it costs money: the same tape priced free keeps more of the move
    free = price_row(_row(taken=True), _winner(), FREE)
    assert free["baseline"]["r"] > blk["baseline"]["r"]


def test_the_twin_outranks_the_surface_which_outranks_the_registry() -> None:
    surface = {"n_fills": 120, "mean_slip_measured": 2e-4, "note": "fitted on 120 fills"}
    twin = {"recalibration": {"symbols": {"XAUUSD": {
                "slip": {"n": 60, "applied_frac": 5e-4, "why": "raised on 60 cases"},
                "fill": {"applied_shift": -0.05}}}},
            "sim_costs": {"XAUUSD": {"spread_frac": 1.5e-4}}}
    both = resolve_cost_model("XAUUSD", twin=twin, surface=surface, meta=META, price=2000.0)
    assert both.source == "execution_twin" and both.slip_frac == 5e-4
    assert both.commission_frac > 0                 # the registry still supplies the commission
    assert resolve_cost_model("XAUUSD", surface=surface, meta=META,
                              price=2000.0).source == "fill_surface"
    assert resolve_cost_model("XAUUSD", meta=META, price=2000.0).source == "costs_baseline"
    # nothing at all: it charges zero and ANNOUNCES it rather than inventing a spread
    nothing = resolve_cost_model("XAUUSD")
    assert nothing.source == "none" and nothing.spread_frac == 0.0
    assert "rather than inventing one" in nothing.why


def test_a_thin_twin_cell_does_not_outrank_the_surface() -> None:
    twin = {"recalibration": {"symbols": {"XAUUSD": {"slip": {"n": 3, "applied_frac": 5e-4}}}}}
    surface = {"n_fills": 120, "mean_slip_measured": 2e-4, "note": "fitted"}
    assert resolve_cost_model("XAUUSD", twin=twin, surface=surface,
                              meta=META, price=2000.0).source == "fill_surface"


# ------------------------------------------------------------------ the report's own reading

def test_the_top_decisions_are_ordered_by_how_much_they_moved() -> None:
    big = _row(taken=False, minute=T0)
    small = _row(taken=False, price=2000.0, sl=1990.0, tp=2001.0, minute=T0)
    rows = [{**big, "row_id": "big",
             "counterfactual_outcomes": price_row(big, _winner(), FREE)},
            {**small, "row_id": "small",
             "counterfactual_outcomes": price_row(small, _winner(), FREE)}]
    top = top_decisions(rows, k=2)
    assert [t["row_id"] for t in top] == ["big", "small"]
    assert top[0]["best_class"] == "MISSED_TRADE_ALPHA" and top[0]["cost_model"] == "test"
    assert top_decisions(rows, k=1) == top[:1]


def test_the_sign_convention_is_stated_on_the_report_itself() -> None:
    agg = aggregate([])
    assert "ALTERNATIVE minus the DESK" in agg["sign"]
    assert set(ALPHA_CLASSES) <= set(agg)
    assert all(agg[c]["status"] == UNMEASURED for c in ALPHA_CLASSES)


def test_bars_are_read_from_mappings_and_tuples_alike() -> None:
    rows = [{"time": T0.isoformat(), "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5},
            {"time": "not a time", "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5},
            (T0 + timedelta(hours=1), 1.5, 2.5, 1.0, 2.0)]
    bars = bars_from_rows(rows)
    assert [b.close for b in bars] == [1.5, 2.0]
    assert bars[0].ts < bars[1].ts
