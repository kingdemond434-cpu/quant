"""Tests for the daily execution-economics organ (libs/execution/economics + its script).

THE HAND-BUILT NET-APR FIXTURE, stated here so the expected number is derivable by hand and not
merely reproduced by the code under test:

    gross funding captured      +120.00
    futures commission           -18.00
    SPOT commission               -6.00      (the R0027 leg -- futures-only fee reads miss this)
    slippage vs mid              -24.00
    funding paid                 -12.00
    -------------------------------------
    NET                          +60.00
    capital deployed          100,000.00     over a 1.0-day window
    NET APR = 60 / 100000 * 365 * 100     =   21.90 %

Four properties are pinned besides the arithmetic:
  * an ABSENT input reads NOT-READABLE-HERE and never 0.0 -- a zero in an execution report is a
    claim that money did not move;
  * churn fires on a re-open inside the entry gate's own minimum hold and stays quiet on a normal
    hold;
  * the unexplained residual crosses its DEFECT bar exactly at `carry_bleed_report.alert_frac` of
    the funding harvest;
  * every threshold this organ applies is READ from its owner (run_reality_gap /
    run_cashcarry_executor / carry_bleed_report) and re-declared nowhere.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from libs.execution import economics
from libs.execution.carry_accounting import carry_bleed_report
from libs.execution.economics import (
    MEASURED,
    NOT_READABLE,
    Term,
    build_decomposition,
    unmeasured_term,
)

ROOT = Path(__file__).resolve().parents[2]
LIB_SRC = ROOT / "libs/execution/economics.py"
SCRIPT_SRC = ROOT / "scripts/run_execution_economics.py"
REALITY_GAP_SRC = ROOT / "scripts/run_reality_gap.py"
EXECUTOR_SRC = ROOT / "scripts/run_cashcarry_executor.py"

_SPEC = importlib.util.spec_from_file_location("run_execution_economics", SCRIPT_SRC)
assert _SPEC is not None and _SPEC.loader is not None
SCRIPT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(SCRIPT)

_SRC = "test fixture"
NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


def _term(name: str, usd: float) -> Term:
    return Term(name=name, usd=usd, status=MEASURED, source=_SRC)


def _fixture_decomposition(**overrides: Term) -> economics.Decomposition:
    kwargs: dict[str, Any] = {
        "gross_funding": _term("gross_funding_captured", 120.0),
        "funding_paid": _term("funding_paid", 12.0),
        "futures_commission": _term("futures_commission", 18.0),
        "spot_commission": _term("spot_commission", 6.0),
        "slippage": _term("slippage_vs_mid", 24.0),
        "funding_net_fallback": _term("funding_net", 108.0),
        "capital_usd": 100_000.0,
        "capital_source": _SRC,
        "window_days": 1.0,
    }
    kwargs.update(overrides)
    return build_decomposition(**kwargs)


# ---------------------------------------------------------------------------------------------
# 1. NET APR ARITHMETIC -- exact on the docstring's fixture
# ---------------------------------------------------------------------------------------------
def test_net_apr_arithmetic_is_exact_on_the_hand_built_fixture() -> None:
    dec = _fixture_decomposition()
    assert dec.net_usd == pytest.approx(60.0)
    assert dec.net_status == MEASURED
    assert dec.net_apr_pct is not None
    assert round(dec.net_apr_pct, 6) == 21.9
    assert dec.net_bps_of_capital is not None
    assert round(dec.net_bps_of_capital, 6) == 6.0        # 60 on 100k = 6 bps for the window
    assert dec.unmeasured_terms == ()


def test_every_term_is_labelled_with_its_status_and_source() -> None:
    for term in _fixture_decomposition().terms:
        row = term.as_dict()
        assert row["status"] in (MEASURED, economics.UNMEASURED)
        assert row["source"]


def test_funding_split_is_crosschecked_against_the_venue_aggregate() -> None:
    assert _fixture_decomposition().funding_split_crosscheck.startswith("OK:")
    # A split that disagrees with income_summary means one of the two reads was truncated.
    disagree = _fixture_decomposition(funding_net_fallback=_term("funding_net", 99.0))
    assert disagree.funding_split_crosscheck.startswith("DISAGREE")


def test_losing_the_funding_split_does_not_lose_the_net() -> None:
    """income_summary nets FUNDING_FEE; when the row split fails the harvest is carried whole."""
    dec = _fixture_decomposition(
        gross_funding=unmeasured_term("gross_funding_captured", _SRC, "row read failed"),
        funding_paid=unmeasured_term("funding_paid", _SRC, "row read failed"))
    assert dec.net_usd == pytest.approx(60.0)             # 108 net funding - 18 - 6 - 24
    assert "gross_funding_captured" in dec.unmeasured_terms


def test_an_unmeasured_cost_makes_the_net_an_upper_bound_not_a_smaller_number() -> None:
    dec = _fixture_decomposition(
        spot_commission=unmeasured_term("spot_commission", _SRC, "spot venue unreadable"))
    assert dec.net_status == economics.UPPER_BOUND
    assert dec.net_usd == pytest.approx(66.0)             # the omitted cost is NOT invented as 0
    assert "spot_commission" in dec.unmeasured_terms


def test_a_measured_but_lower_bound_cost_also_bounds_the_net() -> None:
    partial = Term("spot_commission", 6.0, MEASURED, _SRC, bound=economics.LOWER_BOUND,
                   coverage=0.5)
    assert _fixture_decomposition(spot_commission=partial).net_status == economics.UPPER_BOUND


# ---------------------------------------------------------------------------------------------
# 2. ABSENT INPUT READS NOT-READABLE-HERE, NEVER 0.0
# ---------------------------------------------------------------------------------------------
def _all_absent() -> economics.Decomposition:
    absent = {name: unmeasured_term(name, _SRC, "artifact absent on this machine") for name in
              ("gross_funding_captured", "funding_paid", "futures_commission",
               "spot_commission", "slippage_vs_mid", "funding_net")}
    return build_decomposition(
        gross_funding=absent["gross_funding_captured"], funding_paid=absent["funding_paid"],
        futures_commission=absent["futures_commission"],
        spot_commission=absent["spot_commission"], slippage=absent["slippage_vs_mid"],
        funding_net_fallback=absent["funding_net"], capital_usd=None,
        capital_source=NOT_READABLE, window_days=1.0)


def test_absent_input_reads_not_readable_here_and_never_zero() -> None:
    dec = _all_absent()
    assert dec.net_usd is None
    assert dec.net_status == economics.UNMEASURED
    assert dec.net_apr_pct is None
    row = dec.as_dict()
    assert row["net_reads"] == NOT_READABLE
    assert row["net_apr_reads"] == NOT_READABLE
    for term in row["terms"]:
        assert term["usd"] is None
        assert term["reads"] == NOT_READABLE
        assert term["reads"] != 0.0


def test_no_rendered_cell_of_an_absent_report_is_a_zero() -> None:
    """The whole point: a reader must not be able to find a 0 anywhere in an unmeasured report."""
    rendered = _all_absent().as_dict()
    numbers = [term["reads"] for term in rendered["terms"]] + [rendered["net_reads"]]
    assert all(value == NOT_READABLE for value in numbers)


def test_unreadable_source_constant_returns_none_rather_than_a_plausible_default(
        tmp_path: Path) -> None:
    missing = tmp_path / "no_such_module.py"
    assert economics.read_source_constant(missing, "_COST_BAND") is None
    renamed = tmp_path / "renamed.py"
    renamed.write_text("_SOMETHING_ELSE = 1.5\n", "utf-8")
    assert economics.read_source_constant(renamed, "_COST_BAND") is None


def test_source_constant_reads_negative_literals() -> None:
    """`_FUNDING_PANIC = -0.0005` is a UnaryOp, not a Constant -- a naive reader returns None."""
    assert economics.read_source_constant(EXECUTOR_SRC, "_FUNDING_PANIC") == pytest.approx(-0.0005)


def test_naive_timestamps_are_refused_rather_than_assumed_utc() -> None:
    rows = [{"event": "close", "symbol": "AAA", "opened": "2026-08-05T00:00:00",
             "closed": "2026-08-05T06:00:00", "held_hours": 6.0, "notional": 100.0}]
    trip = economics.parse_trips(rows)[0]
    assert trip.opened is None and trip.closed is None
    assert economics.in_window([trip], NOW - timedelta(days=1), NOW) == []
    with pytest.raises(ValueError, match="timezone-aware"):
        economics.window_bounds(datetime(2026, 8, 5, 12, 0), 1.0)


def test_slippage_is_unmeasured_not_zero_when_no_trip_carries_tca() -> None:
    rows = [{"event": "close", "symbol": "AAA", "opened": "2026-08-04T00:00:00+00:00",
             "closed": "2026-08-05T00:00:00+00:00", "held_hours": 24.0, "notional": 1000.0}]
    usd, coverage = economics.slippage_usd(economics.parse_trips(rows))
    assert usd is None
    assert coverage == 0.0


# ---------------------------------------------------------------------------------------------
# 3. CHURN -- fires on a re-open inside the gate's minimum hold, quiet on a normal hold
# ---------------------------------------------------------------------------------------------
def _trade(event: str, symbol: str, opened: datetime, closed: datetime | None = None,
           **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"event": event, "symbol": symbol, "opened": opened.isoformat(),
                           "notional": 1000.0, "funding_rate": 0.0005,
                           "spot_slip_bps": 2.0, "fut_slip_bps": 1.0}
    if closed is not None:
        row["closed"] = closed.isoformat()
        row["held_hours"] = (closed - opened).total_seconds() / 3600.0
    row.update(extra)
    return row


MIN_HOLD = 24.0          # the fixtures' stand-in for the executor's _MIN_HOLD_H
DEFAULT_RT = 39.5        # the fixtures' stand-in for the executor's _DEFAULT_RT_BPS


def test_churn_fires_on_a_reopen_inside_the_minimum_hold() -> None:
    opened = NOW - timedelta(hours=30)
    closed = NOW - timedelta(hours=6)                    # a 24h hold -- the HOLD itself is fine
    rows = [_trade("open", "AAA", opened),
            _trade("close", "AAA", opened, closed),
            _trade("open", "AAA", closed + timedelta(hours=2))]   # re-entered 2h later
    trips = economics.in_window(economics.parse_trips(rows), NOW - timedelta(days=1), NOW)
    rows_out = economics.churn_report(rows, trips, min_hold_h=MIN_HOLD, window_days=1.0,
                                      default_rt_bps=DEFAULT_RT)
    assert len(rows_out) == 1
    assert rows_out[0].verdict == "CHURN"
    assert rows_out[0].reopens_inside_min_hold == 1
    assert "re-open" in rows_out[0].why


def test_churn_is_quiet_on_a_normal_hold_with_no_fast_reentry() -> None:
    opened = NOW - timedelta(hours=40)
    closed = NOW - timedelta(hours=6)                    # 34h hold, no re-open afterwards
    rows = [_trade("open", "AAA", opened), _trade("close", "AAA", opened, closed)]
    trips = economics.in_window(economics.parse_trips(rows), NOW - timedelta(days=1), NOW)
    rows_out = economics.churn_report(rows, trips, min_hold_h=MIN_HOLD, window_days=1.0,
                                      default_rt_bps=DEFAULT_RT)
    assert rows_out[0].verdict == "OK"
    assert rows_out[0].reopens_inside_min_hold == 0
    assert rows_out[0].short_hold_trips == 0
    # A MEASURED ZERO, not NOT-READABLE-HERE. The holds were readable and none of them churned,
    # so $0.00 is a fact backed by a predicate -- refusing to state it would understate a clean
    # symbol exactly as badly as a fabricated zero overstates a blind one.
    assert rows_out[0].churn_cost_usd == 0.0
    assert rows_out[0].as_dict()["churn_cost_reads"] == 0.0


def test_churn_fires_on_a_hold_shorter_than_the_gate_floor() -> None:
    opened = NOW - timedelta(hours=8)
    rows = [_trade("open", "AAA", opened), _trade("close", "AAA", opened, NOW - timedelta(hours=1))]
    trips = economics.in_window(economics.parse_trips(rows), NOW - timedelta(days=1), NOW)
    row = economics.churn_report(rows, trips, min_hold_h=MIN_HOLD, window_days=1.0,
                                default_rt_bps=DEFAULT_RT)[0]
    assert row.verdict == "CHURN"
    assert row.short_hold_trips == 1
    # cost = 1000 notional x (|2| + |1|) bps = $0.30, i.e. 3 bps of the symbol's notional
    assert row.churn_cost_usd == pytest.approx(0.30)
    assert row.churn_cost_bps == pytest.approx(3.0)
    assert row.round_trips_per_day == pytest.approx(1.0)


def test_churn_cost_falls_back_to_the_executors_pessimistic_default_when_tca_is_absent() -> None:
    opened = NOW - timedelta(hours=8)
    close = _trade("close", "AAA", opened, NOW - timedelta(hours=1))
    close.pop("spot_slip_bps")
    rows = [_trade("open", "AAA", opened), close]
    trips = economics.in_window(economics.parse_trips(rows), NOW - timedelta(days=1), NOW)
    row = economics.churn_report(rows, trips, min_hold_h=MIN_HOLD, window_days=1.0,
                                 default_rt_bps=DEFAULT_RT)[0]
    assert row.churn_cost_usd == pytest.approx(1000.0 * DEFAULT_RT / 1e4)


def test_funding_capture_horizon_is_none_without_positive_funding() -> None:
    """A carry with no premium never repays its round trip -- there is no finite horizon."""
    assert economics.funding_capture_horizon_h(3.0, 0.0) is None
    assert economics.funding_capture_horizon_h(3.0, -0.0002) is None
    assert economics.funding_capture_horizon_h(None, 0.0005) is None
    # 3 bps of cost against 5 bps per 8h of funding = 4.8h to repay
    assert economics.funding_capture_horizon_h(3.0, 0.0005) == pytest.approx(4.8)


def test_a_symbol_with_no_readable_hold_reads_not_readable_here() -> None:
    opened = NOW - timedelta(hours=8)
    close = _trade("close", "AAA", opened, NOW - timedelta(hours=1))
    close.pop("held_hours")
    trips = economics.in_window(economics.parse_trips([close]), NOW - timedelta(days=1), NOW)
    row = economics.churn_report([close], trips, min_hold_h=MIN_HOLD, window_days=1.0,
                                 default_rt_bps=DEFAULT_RT)[0]
    assert row.verdict == NOT_READABLE
    assert row.avg_hold_h is None
    assert row.as_dict()["avg_hold_reads"] == NOT_READABLE
    # ... and with no readable hold the churn COST is unmeasured too, never a comforting zero
    assert row.churn_cost_usd is None
    assert row.as_dict()["churn_cost_reads"] == NOT_READABLE


# ---------------------------------------------------------------------------------------------
# 4. THE RESIDUAL crosses its DEFECT threshold exactly at the desk's own bar
# ---------------------------------------------------------------------------------------------
def test_residual_defect_bar_is_carry_bleed_reports_own_alert_frac() -> None:
    frac = economics.bleed_alert_frac()
    assert frac == inspect.signature(carry_bleed_report).parameters["alert_frac"].default


def test_residual_crosses_the_defect_threshold_at_the_bar_and_not_below() -> None:
    frac = economics.bleed_alert_frac()
    assert frac is not None
    harvest = 100.0
    just_under = economics.residual_report(
        leak={"basis": 0.0, "fut_fees": 10.0, "residual": frac * harvest - 0.01},
        funding=harvest, alert_frac=frac, scope="test")
    assert just_under.verdict == "OK"
    at_bar = economics.residual_report(
        leak={"basis": 0.0, "fut_fees": 10.0, "residual": frac * harvest},
        funding=harvest, alert_frac=frac, scope="test")
    assert at_bar.verdict == "DEFECT"
    assert at_bar.threshold_usd == pytest.approx(frac * harvest)


def test_residual_defect_is_two_sided() -> None:
    """A large POSITIVE unexplained number is a broken hedge, not luck (carry_bleed_report)."""
    frac = economics.bleed_alert_frac()
    assert frac is not None
    for sign in (1.0, -1.0):
        report = economics.residual_report(leak={"residual": sign * 60.0}, funding=100.0,
                                           alert_frac=frac, scope="test")
        assert report.verdict == "DEFECT"


def test_residual_with_no_harvest_makes_any_unexplained_dollar_a_defect() -> None:
    report = economics.residual_report(leak={"residual": -0.5}, funding=0.0, alert_frac=0.5,
                                       scope="test")
    assert report.verdict == "DEFECT"
    assert "NO funding harvest" in report.why


def test_residual_is_never_scored_clean_when_it_cannot_be_measured() -> None:
    for leak, funding in ((None, 100.0), ({}, 100.0), ({"residual": 5.0}, None)):
        report = economics.residual_report(leak=leak, funding=funding, alert_frac=0.5,
                                           scope="test")
        assert report.verdict == NOT_READABLE
        assert report.as_dict()["verdict"] != "OK"
    absent_bar = economics.residual_report(leak={"residual": 5.0}, funding=100.0, alert_frac=None,
                                           scope="test")
    assert absent_bar.verdict == NOT_READABLE


def test_a_defect_residual_drives_the_overall_status() -> None:
    residual = economics.residual_report(leak={"residual": 90.0}, funding=100.0, alert_frac=0.5,
                                         scope="test")
    assert economics.overall_status([], residual) == "DEFECT"
    clean = economics.residual_report(leak={"residual": 1.0}, funding=100.0, alert_frac=0.5,
                                      scope="test")
    assert economics.overall_status([], clean) == economics.UNMEASURED   # never a silent OK


# ---------------------------------------------------------------------------------------------
# 5. NO THRESHOLD IS DUPLICATED -- every band is READ from its owner
# ---------------------------------------------------------------------------------------------
def _module_level_numbers(path: Path) -> dict[str, float]:
    """Every module-level `NAME = <numeric literal>` -- the shape a copied threshold takes."""
    out: dict[str, float] = {}
    for node in ast.parse(path.read_text("utf-8")).body:
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.USub):
            value = value.operand
        if not isinstance(value, ast.Constant) or isinstance(value.value, bool) \
                or not isinstance(value.value, (int, float)):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                out[target.id] = float(value.value)
    return out


def test_cost_bands_are_run_reality_gaps_own_values() -> None:
    assert economics.read_source_constant(REALITY_GAP_SRC, "_COST_BAND") == SCRIPT.COST_BAND
    assert economics.read_source_constant(REALITY_GAP_SRC, "_COST_BREAK") == SCRIPT.COST_BREAK
    assert SCRIPT.COST_BAND == 1.5 and SCRIPT.COST_BREAK == 3.0    # the 1.5x GAP / 3.0x BREAK


def test_hold_and_roundtrip_constants_are_the_executors_own_values() -> None:
    assert economics.read_source_constant(EXECUTOR_SRC, "_MIN_HOLD_H") == SCRIPT.MIN_HOLD_H
    assert economics.read_source_constant(EXECUTOR_SRC, "_DEFAULT_RT_BPS") == SCRIPT.DEFAULT_RT_BPS
    assert economics.read_source_constant(
        EXECUTOR_SRC, "_MIN_FILLS_FOR_REALISED") == SCRIPT.MIN_FILLS_FOR_REALISED
    assert SCRIPT.MIN_HOLD_H is not None and SCRIPT.MIN_HOLD_H > 0


def test_no_owned_threshold_is_re_declared_in_this_organ() -> None:
    """A second copy of a threshold is how one desk ends up with two answers to one question.

    Scans BOTH new files for a module-level numeric constant carrying any owner's value. The read
    sites are `Call` nodes (`read_source_constant(...)`), so a genuine read never trips this and
    only a hand-copied literal can.
    """
    owned = {
        "_COST_BAND": economics.read_source_constant(REALITY_GAP_SRC, "_COST_BAND"),
        "_COST_BREAK": economics.read_source_constant(REALITY_GAP_SRC, "_COST_BREAK"),
        "_MIN_HOLD_H": economics.read_source_constant(EXECUTOR_SRC, "_MIN_HOLD_H"),
        "_DEFAULT_RT_BPS": economics.read_source_constant(EXECUTOR_SRC, "_DEFAULT_RT_BPS"),
        "_MIN_FILLS_FOR_REALISED": economics.read_source_constant(
            EXECUTOR_SRC, "_MIN_FILLS_FOR_REALISED"),
        "alert_frac": economics.bleed_alert_frac(),
    }
    assert all(v is not None for v in owned.values()), owned
    for path in (LIB_SRC, SCRIPT_SRC):
        for name, value in _module_level_numbers(path).items():
            for owner, owned_value in owned.items():
                assert value != owned_value, (
                    f"{path.name}:{name} = {value} re-declares {owner}; read it from its owner")


def test_the_bands_this_organ_applies_are_parameters_with_no_defaults() -> None:
    """The lib cannot be called while inventing a band: they are required keyword arguments."""
    for func, params in ((economics.drift_verdict, ("band", "break_at")),
                         (economics.cost_drift, ("band", "break_at", "min_n")),
                         (economics.churn_report, ("min_hold_h", "default_rt_bps"))):
        signature = inspect.signature(func)
        for param in params:
            assert signature.parameters[param].default is inspect.Parameter.empty


# ---------------------------------------------------------------------------------------------
# COST-MODEL DRIFT -- the same verdicts run_reality_gap gives, at symbol grain
# ---------------------------------------------------------------------------------------------
def _cost_model(bps: float) -> dict[str, Any]:
    return {"symbols": {"AAA": {"pair": {"500": {"pair_roundtrip_bps": bps}}}}}


def _drift_rows(realised_leg_bps: float, modelled: float) -> list[economics.DriftRow]:
    opened = NOW - timedelta(hours=30)
    rows = [_trade("close", "AAA", opened, NOW - timedelta(hours=i),
                   spot_slip_bps=realised_leg_bps, fut_slip_bps=0.0) for i in (1, 2, 3)]
    trips = economics.in_window(economics.parse_trips(rows), NOW - timedelta(days=1), NOW)
    return economics.cost_drift(trips, _cost_model(modelled), band=1.5, break_at=3.0, min_n=3)


def test_cost_drift_uses_the_gap_and_break_bands_it_is_given() -> None:
    assert _drift_rows(4.0, 4.0)[0].verdict == "OK"          # 1.0x
    assert _drift_rows(8.0, 4.0)[0].verdict == "GAP"         # 2.0x -- past 1.5, under 3.0
    assert _drift_rows(20.0, 4.0)[0].verdict == "BREAK"      # 5.0x
    assert _drift_rows(4.0, 0.0)[0].verdict == "NO-DATA"     # modelled ~0 -> ratio undefined


def test_cost_drift_is_no_data_when_either_side_is_absent() -> None:
    row = _drift_rows(4.0, 4.0)[0]
    assert row.ratio == pytest.approx(1.0)
    missing_model = economics.cost_drift(
        economics.in_window(economics.parse_trips(
            [_trade("close", "AAA", NOW - timedelta(hours=30), NOW - timedelta(hours=1))]),
            NOW - timedelta(days=1), NOW),
        {}, band=1.5, break_at=3.0, min_n=1)[0]
    assert missing_model.verdict == "NO-DATA"
    assert missing_model.as_dict()["modelled_reads"] == NOT_READABLE


def test_realised_rt_bps_needs_the_executors_minimum_sample() -> None:
    trips = economics.parse_trips([_trade("close", "AAA", NOW - timedelta(hours=30), NOW)])
    assert economics.realised_rt_bps(trips, min_n=3) is None
    assert economics.realised_rt_bps(trips, min_n=1) == pytest.approx(3.0)


# ---------------------------------------------------------------------------------------------
# CAPITAL BASE + ACTION RANKING
# ---------------------------------------------------------------------------------------------
def test_capital_base_takes_the_larger_reading_so_apr_can_only_shrink() -> None:
    value, source = economics.capital_base(1000.0, 4000.0)
    assert value == 4000.0 and "live" in source
    assert economics.capital_base(None, None) == (None, NOT_READABLE)
    assert economics.capital_base(1000.0, None)[0] == 1000.0


def test_time_weighted_capital_excludes_untimed_rows_rather_than_zeroing_them() -> None:
    start, end = NOW - timedelta(hours=24), NOW
    rows = [_trade("close", "AAA", NOW - timedelta(hours=12), NOW)]       # 1000 for 12 of 24h
    trips = economics.parse_trips(rows)
    assert economics.time_weighted_capital(trips, start, end) == pytest.approx(500.0)
    assert economics.time_weighted_capital([], start, end) is None


def test_actions_rank_measured_bps_first_and_never_drop_the_blind_ones() -> None:
    ranked = economics.rank_actions([
        economics.Action("small", 2.0, "fix", "ev"),
        economics.Action("blind", None, "fix", "ev", status="UNQUANTIFIED"),
        economics.Action("large", 40.0, "fix", "ev"),
    ])
    assert [a.label for a in ranked] == ["large", "small", "blind"]
    assert ranked[-1].as_dict()["recoverable_reads"] == NOT_READABLE


# ---------------------------------------------------------------------------------------------
# THE R0027 WIRING -- spot commission, and the read that lies by omission
# ---------------------------------------------------------------------------------------------
def _spot_fill(commission: float, asset: str = "USDT", when: int = 1_000) -> dict[str, Any]:
    return {"id": when, "time": when, "commission": commission, "commissionAsset": asset}


def test_spot_commission_sums_per_fill_commission_like_the_reconciliation_does() -> None:
    term = SCRIPT._spot_commission_term(
        {"AAA": [_spot_fill(0.10), _spot_fill(0.15, when=1_001)]}, 0, 10_000, n_trips=2)
    assert term.status == MEASURED
    assert term.usd == pytest.approx(0.25)
    assert term.bound == economics.EXACT


def test_spot_commission_zero_fills_against_real_trips_is_a_failed_read_not_zero_dollars() -> None:
    """`my_trades` swallows its errors and returns [] -- so [] against traded symbols is a hole."""
    term = SCRIPT._spot_commission_term({"AAA": []}, 0, 10_000, n_trips=4)
    assert term.status == economics.UNMEASURED
    assert term.usd is None
    assert term.as_dict()["reads"] == NOT_READABLE


def test_spot_commission_with_no_venue_is_unmeasured_and_names_r0027() -> None:
    term = SCRIPT._spot_commission_term(None, 0, 10_000, n_trips=4)
    assert term.status == economics.UNMEASURED
    assert "R0027" in term.note


def test_spot_commission_in_a_foreign_asset_is_counted_but_bounds_the_number() -> None:
    term = SCRIPT._spot_commission_term(
        {"AAA": [_spot_fill(0.10), _spot_fill(0.0004, asset="BNB", when=1_001)]},
        0, 10_000, n_trips=1)
    assert term.usd == pytest.approx(0.10)               # the BNB fee is NOT valued at zero
    assert term.bound == economics.LOWER_BOUND
    assert "not valued" in term.note


def test_spot_commission_partial_symbol_coverage_is_a_lower_bound() -> None:
    term = SCRIPT._spot_commission_term(
        {"AAA": [_spot_fill(0.10)], "BBB": []}, 0, 10_000, n_trips=2)
    assert term.bound == economics.LOWER_BOUND
    assert term.coverage == pytest.approx(0.5)


def test_spot_commission_with_no_fills_and_no_trips_is_a_measured_zero() -> None:
    """Asked and answered: no trading in the window means $0.00 of spot fees, not a refusal.

    The distinction from the failed-read case above is `n_trips`: zero fills against round trips
    the tape says happened is a hole; zero fills against zero round trips is an idle window.
    """
    term = SCRIPT._spot_commission_term({"AAA": []}, 0, 10_000, n_trips=0)
    assert term.status == MEASURED
    assert term.usd == 0.0
    assert term.bound == economics.LOWER_BOUND
    assert "not what this reader assumed" in term.note


def test_income_split_separates_funding_captured_from_funding_paid() -> None:
    rows = [{"incomeType": "FUNDING_FEE", "income": "12.0", "time": 100},
            {"incomeType": "FUNDING_FEE", "income": "-4.0", "time": 200},
            {"incomeType": "COMMISSION", "income": "-3.0", "time": 300},
            {"incomeType": "FUNDING_FEE", "income": "99.0", "time": 9_999}]   # outside the window
    captured, paid, commission = SCRIPT._income_split(rows, 0, 1_000)
    assert (captured, paid, commission) == (12.0, 4.0, 3.0)
    assert SCRIPT._income_split(None, 0, 1_000) == (None, None, None)


def test_the_week_anchored_aggregate_is_refused_by_the_shorter_window() -> None:
    """A WEEK of funding served as a DAY's harvest would inflate the day's APR sevenfold.

    `income_summary` is anchored at ONE `since_ms` -- the longest window's start -- so it is
    window-scoped for that window and for no other. The shorter window must read
    NOT-READABLE-HERE rather than borrow it.
    """
    now = NOW
    summary = {"funding": 108.0}
    kwargs: dict[str, Any] = {
        "rows": [], "rows_source": "fixture", "income_rows": None, "income_summary": summary,
        "spot_fills": None, "deployed_now": 5000.0, "cost_model": None,
    }
    day = SCRIPT._build_window("trailing_day", 1.0, now, summary_covers_window=False, **kwargs)
    week = SCRIPT._build_window("trailing_week", 7.0, now, summary_covers_window=True, **kwargs)
    day_net = next(t for t in day.decomposition.terms if t.name == "funding_net")
    week_net = next(t for t in week.decomposition.terms if t.name == "funding_net")
    assert day_net.status == economics.UNMEASURED
    assert "anchored at the longest window" in day_net.note
    assert week_net.usd == pytest.approx(108.0)
    assert day.decomposition.net_usd is None            # no harvest -> no net, never a zero
    assert week.decomposition.net_status == economics.UPPER_BOUND


def test_the_script_self_test_proves_its_own_arithmetic() -> None:
    assert SCRIPT._self_test() == 0
