"""The Execution Digital Twin's arithmetic, on known-answer fixtures.

Pinned here:

  * the join links an intent to its outcome by `intent_id` when both carry one, else by
    (symbol, side, lots, time within the window), each outcome used once; a deal joins by ticket
    and resolves a resting order's fill from the position's entry price; a resting order with no
    deal is UNFILLED only once it is old enough, and unresolved before that;
  * a venue reject is a reject with its MT5 reason, never a fill, and the reject model smooths
    with Laplace while reporting the raw k/n and refusing a rate under MIN_N;
  * fill calibration on a known answer: predicted 0.8 realised 0.5 -> Brier 0.34, ECE 0.30;
  * slippage calibration reports bias and MAE with n per bucket and UNMEASURED under MIN_N;
  * the recalibration's verdicts and its ASYMMETRY: three cases cannot lower a cost, three
    hundred can; twenty can raise one; a thin favourable sample is HELD; predicted 0.8 fill
    realised 0.5 -> SIM_TOO_OPTIMISTIC; demo cases are excluded;
  * execution choice value in R per (symbol, algo) against the market baseline, UNMEASURED with
    one algorithm; latency / spread expansion UNMEASURED when nothing records them; the impact
    proxy's slope is positive when slip grows with size; a case survives a row round trip.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from libs.execution import digital_twin as dt

T0 = datetime(2026, 9, 5, 9, 0, tzinfo=UTC)
PX = 3000.0


def _intent(i: int, *, symbol: str = "XAUUSD", side: str = "buy", lot: float = 0.1,
            retcode: int | None = 10009, sl_frac: float = 0.004, spread: float = 0.3,
            at: datetime | None = None, **extra: Any) -> dict[str, Any]:
    t = at if at is not None else T0 + timedelta(minutes=i)
    row: dict[str, Any] = {"time": t.isoformat(timespec="seconds"), "sleeve": "A",
                           "symbol": symbol, "side": side, "lot": lot, "intended": PX,
                           "sl": PX * (1 - sl_frac) if side.startswith("buy") else
                           PX * (1 + sl_frac), "tp": PX * 1.01, "ticket": 1000 + i,
                           "retcode": retcode, "decision_bid": PX - spread, "decision_ask": PX,
                           "spread_at_decision": spread}
    row.update(extra)
    return row


def _outcome(i: int, *, algo: str = "market", expected: float = 1e-4, realised: float | None = 2e-4,
             filled_frac: float = 1.0, p_fill: float = 1.0, lots: float = 0.1,
             side: str = "buy", symbol: str = "XAUUSD", offset_s: float = 2.0,
             **extra: Any) -> dict[str, Any]:
    t = T0 + timedelta(minutes=i, seconds=offset_s)
    row: dict[str, Any] = {"at": t.isoformat(), "algo": algo, "symbol": symbol, "side": side,
                           "lots": lots, "filled_lots": lots * filled_frac,
                           "expected_cost": expected, "realised_cost": realised,
                           "filled_frac": filled_frac, "expected_p_fill": p_fill,
                           "utility": 0.1, "n_fills": 1 if filled_frac > 0 else 0}
    row.update(extra)
    return row


def _market_cases(n: int, *, expected: float = 1e-4, realised: float = 2e-4,
                  symbol: str = "XAUUSD", algo: str = "market", start: int = 0
                  ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ints = [_intent(start + i, symbol=symbol) for i in range(n)]
    outs = [_outcome(start + i, algo=algo, expected=expected, realised=realised, symbol=symbol)
            for i in range(n)]
    return ints, outs


def _resting_cases(n: int, k_filled: int, *, p_pred: float = 0.8, age_days: float = 5.0
                   ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], datetime]:
    """n pending-stop intents, the first k_filled with a deal at the trigger, all old enough
    to be resolved as of `asof`."""
    ints = [_intent(i, side="buy_stop", retcode=10008, order_type="pending_stop",
                    predicted_p_fill=p_pred) for i in range(n)]
    deals = [{"order": 1000 + i, "entry_price": PX, "fill_price": PX * 1.002, "volume": 0.1,
              "account_kind": "live", "symbol": "XAUUSD", "side": 0} for i in range(k_filled)]
    return ints, deals, T0 + timedelta(days=age_days)


# ------------------------------------------------------------------------------------ the join
def test_join_prefers_intent_id_then_falls_back_to_symbol_side_lot_time() -> None:
    ints = [_intent(0, intent_id="id-0"), _intent(1), _intent(2)]
    outs = [_outcome(0, intent_id="id-0", realised=5e-4),
            _outcome(1, realised=3e-4),
            _outcome(2, offset_s=dt.JOIN_WINDOW_S + 30, realised=9e-4)]  # outside the window
    cases = dt.join_cases(ints, outs)
    assert [c.join_key for c in cases] == ["intent_id", "fuzzy", "none"]
    assert cases[0].actual_slip_frac == pytest.approx(5e-4)
    assert cases[1].actual_slip_frac == pytest.approx(3e-4)
    assert cases[1].predicted_slip_frac == pytest.approx(1e-4)
    assert cases[1].predicted_p_fill == 1.0 and cases[1].algo == "market"
    # a market DONE with no outcome row is a fill whose slip is UNMEASURED, not zero
    assert cases[2].filled is True and cases[2].actual_slip_frac is None
    assert cases[2].joined_outcome is False
    # state at decision is on the case: spread as a fraction, stop as a fraction, session
    assert cases[0].spread_frac == pytest.approx(0.3 / PX)
    assert cases[0].stop_frac == pytest.approx(0.004)
    assert cases[0].session == "london" and cases[0].hour == 9
    assert cases[0].realised_cost_r == pytest.approx(5e-4 / 0.004)


def test_an_outcome_is_never_joined_twice() -> None:
    ints = [_intent(0, at=T0), _intent(1, at=T0 + timedelta(seconds=10))]
    outs = [_outcome(0, offset_s=5.0)]
    cases = dt.join_cases(ints, outs)
    assert [c.joined_outcome for c in cases] == [True, False]


def test_a_deal_resolves_a_resting_order_and_age_resolves_the_rest() -> None:
    ints, deals, asof = _resting_cases(3, 1)
    cases = dt.join_cases(ints, [], deals, asof=asof)
    filled, old_unfilled, _ = cases
    assert filled.join_key == "ticket" and filled.filled is True
    assert filled.actual_slip_frac == pytest.approx(0.0)          # filled at the trigger
    assert filled.account_kind == "live" and filled.predicted_slip_frac == 0.0
    assert old_unfilled.filled is False and old_unfilled.filled_frac == 0.0
    # the same intents seen an hour later are unresolved, not unfilled
    fresh = dt.join_cases(ints, [], deals, asof=T0 + timedelta(hours=1))
    assert fresh[1].filled is None
    # and with no deal ledger supplied at all nothing can be called unfilled
    none = dt.join_cases(ints, [], None, asof=asof)
    assert none[1].filled is None


def test_a_reject_is_a_reject_with_its_reason() -> None:
    ints = [_intent(0, retcode=10019), _intent(1, retcode=None), _intent(2)]
    cases = dt.join_cases(ints, [])
    assert cases[0].rejected and cases[0].reject_reason == "no_money"
    assert cases[0].filled is False and cases[0].actual_slip_frac is None
    assert cases[1].rejected and cases[1].reject_reason == "no_result"
    assert not cases[2].rejected and cases[2].reject_reason == ""


def test_a_case_survives_the_row_round_trip() -> None:
    ints, outs = _market_cases(1)
    c = dt.join_cases(ints, outs)[0]
    row = c.to_row()
    assert row["size_bucket"] == "s<=0.2" and row["spread_bucket"] == "tight<=1bp"
    back = dt.case_from_row(row)
    assert back == c and back.resolution == c.resolution


# ------------------------------------------------------------------------- calibration tables
def test_fill_calibration_known_answer() -> None:
    ints, deals, asof = _resting_cases(100, 50, p_pred=0.8)
    cases = dt.join_cases(ints, [], deals, asof=asof)
    fc = dt.fill_calibration(cases)
    assert fc["status"] == dt.MEASURED and fc["n"] == 100
    assert fc["brier"] == pytest.approx(0.34, abs=1e-6)          # 0.5*0.04 + 0.5*0.64
    assert fc["ece"] == pytest.approx(0.30, abs=1e-6)
    top = next(b for b in fc["bins"] if b["lo"] == 0.8)
    assert top["n"] == 100 and top["realised_rate"] == 0.5 and top["status"] == dt.MEASURED
    assert all(b["status"] == dt.UNMEASURED and b["realised_rate"] is None
               for b in fc["bins"] if b["lo"] != 0.8)
    assert fc["by_order_type"]["pending_stop"]["k"] == 50


def test_fill_calibration_is_unmeasured_under_min_n() -> None:
    ints, deals, asof = _resting_cases(5, 2)
    fc = dt.fill_calibration(dt.join_cases(ints, [], deals, asof=asof))
    assert fc["status"] == dt.UNMEASURED and fc["brier"] is None and fc["ece"] is None


def test_slippage_calibration_bias_mae_and_thin_buckets() -> None:
    ints, outs = _market_cases(40, expected=1e-4, realised=3e-4)
    i2, o2 = _market_cases(3, expected=1e-4, realised=0.0, symbol="EURUSD", start=100)
    cases = dt.join_cases(ints + i2, outs + o2)
    sc = dt.slippage_calibration(cases)
    gold = sc["by_symbol"]["XAUUSD"]
    assert gold["n"] == 40 and gold["status"] == dt.MEASURED
    assert gold["bias"] == pytest.approx(2e-4) and gold["mae"] == pytest.approx(2e-4)
    assert gold["mean_actual"] == pytest.approx(3e-4)
    eur = sc["by_symbol"]["EURUSD"]
    assert eur["n"] == 3 and eur["status"] == dt.UNMEASURED and eur["bias"] is None
    assert sc["by_session"]["london"]["n"] == 43
    assert sc["overall"]["ci95"][0] <= sc["overall"]["bias"] <= sc["overall"]["ci95"][1]


def test_reject_model_smooths_and_refuses_thin_cells() -> None:
    ints = [_intent(i, retcode=(10019 if i < 2 else 10009)) for i in range(20)]
    ints += [_intent(100 + i, symbol="EURUSD", retcode=10004) for i in range(3)]
    rm = dt.reject_model(dt.join_cases(ints, []))
    gold = rm["by_symbol"]["XAUUSD"]
    assert gold["n"] == 20 and gold["k"] == 2 and gold["status"] == dt.MEASURED
    assert gold["rate"] == 0.1 and gold["p_smoothed"] == pytest.approx(3 / 22, abs=1e-6)
    assert gold["ci95"][0] < 0.1 < gold["ci95"][1]
    eur = rm["by_symbol"]["EURUSD"]
    assert eur["n"] == 3 and eur["k"] == 3 and eur["rate"] is None
    assert eur["status"] == dt.UNMEASURED and eur["p_smoothed"] == pytest.approx(0.8, abs=1e-6)
    assert rm["reasons"] == {"requote": 3, "no_money": 2}
    assert "XAUUSD|london|tight<=1bp|s<=0.2" in rm["cells"]


def test_latency_and_spread_expansion_are_unmeasured_until_recorded() -> None:
    ints, outs = _market_cases(20)
    cases = dt.join_cases(ints, outs)
    lat = dt.latency_summary(cases)
    assert lat["status"] == dt.UNMEASURED and "latency_ms" in lat["why"]
    se = dt.spread_expansion(cases)
    assert se["status"] == dt.UNMEASURED and "spread_at_fill" in se["why"]
    # and measured once the fields exist
    ints2 = [_intent(i, latency_ms=40.0 + i) for i in range(20)]
    outs2 = [_outcome(i, spread_at_fill=0.6) for i in range(20)]
    cases2 = dt.join_cases(ints2, outs2)
    lat2 = dt.latency_summary(cases2)
    assert lat2["status"] == dt.MEASURED and lat2["p50"] == pytest.approx(49.5)
    se2 = dt.spread_expansion(cases2)
    assert se2["status"] == dt.MEASURED and se2["mean_ratio"] == pytest.approx(2.0)
    assert se2["share_above_1p5"] == 1.0


def test_impact_proxy_slope_is_positive_when_slip_grows_with_size() -> None:
    ints, outs = [], []
    for i in range(30):
        lots = 0.05 + 0.05 * (i % 6)
        ints.append(_intent(i, lot=lots))
        outs.append(_outcome(i, lots=lots, realised=1e-4 + 1e-3 * lots))
    ip = dt.impact_proxy(dt.join_cases(ints, outs))
    assert ip["slope"]["status"] == dt.MEASURED and ip["slope"]["slope_per_lot"] > 0
    assert ip["by_size_bucket"]["s<=0.2"]["status"] == dt.MEASURED
    assert ip["by_symbol"]["XAUUSD"]["slope"]["slope_per_lot"] == pytest.approx(1e-3, rel=1e-3)


# ---------------------------------------------------------------------------- recalibration
def test_recalibration_verdicts_and_the_asymmetry_on_slippage() -> None:
    sim = {"XAUUSD": dt.SimCost(slip_frac=2e-4, p_fill=1.0, spread_frac=1e-4)}
    # 300 cases with no slip against a modelled 2e-4: thick, clear -> lowered
    ints, outs = _market_cases(300, realised=0.0)
    thick = dt.recalibration(dt.join_cases(ints, outs), sim)["symbols"]["XAUUSD"]
    assert thick["verdict"] == dt.SIM_TOO_PESSIMISTIC
    assert thick["slip"]["applied_frac"] == 0.0 and not thick["slip"]["held"]
    assert thick["slippage_multiplier"] == pytest.approx(1e-4 / (1e-4 + 4e-4))
    # 3 cases with the same evidence: UNMEASURED, and the cost is NOT lowered
    ints, outs = _market_cases(3, realised=0.0)
    thin = dt.recalibration(dt.join_cases(ints, outs), sim)["symbols"]["XAUUSD"]
    assert thin["verdict"] == dt.UNMEASURED and thin["slip"]["realised_frac"] is None
    assert thin["slip"]["applied_frac"] == pytest.approx(2e-4)
    assert thin["slippage_multiplier"] == pytest.approx(1.0)
    # 20 favourable cases: measured, verdict says pessimistic, but the cost is HELD
    ints, outs = _market_cases(20, realised=0.0)
    held = dt.recalibration(dt.join_cases(ints, outs), sim)["symbols"]["XAUUSD"]
    assert held["verdict"] == dt.SIM_TOO_PESSIMISTIC and held["slip"]["held"]
    assert held["slip"]["applied_frac"] == pytest.approx(2e-4)
    assert held["slippage_multiplier"] == pytest.approx(1.0)
    # 20 unfavourable cases: thin evidence RAISES the cost on the point estimate
    ints, outs = _market_cases(20, realised=5e-4)
    up = dt.recalibration(dt.join_cases(ints, outs), sim)["symbols"]["XAUUSD"]
    assert up["verdict"] == dt.SIM_TOO_OPTIMISTIC and not up["slip"]["held"]
    assert up["slip"]["applied_frac"] == pytest.approx(5e-4)
    assert up["slippage_multiplier"] == pytest.approx((1e-4 + 1e-3) / (1e-4 + 4e-4))
    # a realised slip inside the interval around the modelled one is CALIBRATED and untouched
    ints, outs = [], []
    for i in range(40):
        ints.append(_intent(i))
        outs.append(_outcome(i, realised=2e-4 + (1e-4 if i % 2 else -1e-4)))
    cal = dt.recalibration(dt.join_cases(ints, outs), sim)["symbols"]["XAUUSD"]
    assert cal["verdict"] == dt.CALIBRATED
    assert cal["slip"]["applied_frac"] == pytest.approx(2e-4)


def test_recalibration_fill_probability_predicted_0p8_realised_0p5_is_too_optimistic() -> None:
    ints, deals, asof = _resting_cases(100, 50, p_pred=0.8)
    rc = dt.recalibration(dt.join_cases(ints, [], deals, asof=asof))["symbols"]["XAUUSD"]
    assert rc["verdict"] == dt.SIM_TOO_OPTIMISTIC
    f = rc["fill"]
    assert f["n"] == 100 and f["k"] == 50 and f["realised_rate"] == 0.5
    assert f["predicted_mean"] == pytest.approx(0.8)
    assert f["shift"] == pytest.approx(-0.3) and f["applied_shift"] == pytest.approx(-0.3)
    assert not f["held"]
    # more fills than predicted on a thin sample: measured, but the raise is held
    ints, deals, asof = _resting_cases(20, 20, p_pred=0.5)
    up = dt.recalibration(dt.join_cases(ints, [], deals, asof=asof))["symbols"]["XAUUSD"]
    assert up["fill"]["verdict"] == dt.SIM_TOO_PESSIMISTIC and up["fill"]["held"]
    assert up["fill"]["applied_shift"] == 0.0


def test_recalibration_excludes_demo_cases_and_counts_them() -> None:
    ints, deals, asof = _resting_cases(30, 30)
    for d in deals[:20]:
        d["account_kind"] = "demo"
    rc = dt.recalibration(dt.join_cases(ints, [], deals, asof=asof))
    assert rc["n_demo_excluded"] == 20 and rc["n_cases"] == 10
    assert rc["symbols"]["XAUUSD"]["slip"]["n"] == 10
    assert rc["counts"][dt.UNMEASURED] + rc["counts"][dt.CALIBRATED] \
        + rc["counts"][dt.SIM_TOO_OPTIMISTIC] + rc["counts"][dt.SIM_TOO_PESSIMISTIC] == 1


def test_recalibration_without_a_spread_reports_slip_to_add_and_no_multiplier() -> None:
    ints, outs = _market_cases(20, realised=5e-4)
    rc = dt.recalibration(dt.join_cases(ints, outs))["symbols"]["XAUUSD"]
    assert rc["slippage_multiplier"] is None and "no spread_frac" in rc["multiplier_basis"]
    assert rc["slip"]["applied_frac"] == pytest.approx(5e-4)


# ------------------------------------------------------------------------- the choice value
def test_execution_choice_value_scores_algorithms_against_market_in_r() -> None:
    ints, outs = _market_cases(20, realised=2e-4)
    i2, o2 = _market_cases(20, realised=1e-4, algo="twap", start=50)
    i3, o3 = _market_cases(3, realised=0.0, algo="sniper", start=200)
    ecv = dt.execution_choice_value(dt.join_cases(ints + i2 + i3, outs + o2 + o3))
    gold = ecv["symbols"]["XAUUSD"]
    assert gold["comparison"] == dt.MEASURED and gold["best_measured"] == "twap"
    mk, tw, sn = gold["algos"]["market"], gold["algos"]["twap"], gold["algos"]["sniper"]
    assert mk["realised_cost_r"] == pytest.approx(2e-4 / 0.004)
    assert tw["value_vs_market_r"] == pytest.approx(1e-4 / 0.004)
    assert tw["fill_rate"] == 1.0 and mk["value_vs_market_r"] is None
    assert sn["status"] == dt.UNMEASURED and sn["value_vs_market_r"] is None
    # one measured algorithm is no comparison
    only = dt.execution_choice_value(dt.join_cases(ints, outs))["symbols"]["XAUUSD"]
    assert only["comparison"] == dt.UNMEASURED and "needs two" in only["why"]


def test_buckets_and_sessions_are_the_declared_bands() -> None:
    assert [dt.session_of(h) for h in (0, 7, 13, 17, 22, 23)] == \
        ["asia", "london", "overlap", "newyork", "late", "late"]
    assert dt.size_bucket(0.01) == "xs<=0.05" and dt.size_bucket(5.0) == "l>1"
    assert dt.spread_bucket(None) == "unknown" and dt.spread_bucket(2e-3) == "extreme>10bp"
