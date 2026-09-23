"""COST TRUTH -- the arithmetic that decides whether a refusal was honest.

Every case here is a fixture in tmp_path: no tracked file is read or written, and no terminal is
needed (the MT5 half is a `# pragma: no cover` boundary by construction).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "desks" / "mt5" / "research"))

import cost_truth as CT  # noqa: E402

# BY PATH, NOT BY PACKAGE. `tests/scripts/__init__.py` makes `scripts` resolve to the TEST
# package whenever that directory is collected in the same session, so `from scripts
# import ...` fails in the full suite while passing on its own.
_FENCE_SPEC = importlib.util.spec_from_file_location(
    "check_cost_truth", ROOT / "scripts" / "check_cost_truth.py")
assert _FENCE_SPEC and _FENCE_SPEC.loader
FENCE = importlib.util.module_from_spec(_FENCE_SPEC)
_FENCE_SPEC.loader.exec_module(FENCE)

# ------------------------------------------------------------------------------- the readings


def test_pcts_publishes_the_distribution_not_one_number() -> None:
    got = CT.pcts([0.0, 1.0, 1.0, 2.0, 10.0])
    assert got["status"] == CT.MEASURED
    assert got["n"] == 5
    assert got["p50"] == 1.0
    assert got["max"] == 10.0
    # a zero spread is a REAL reading on a commission-only venue; its share is published
    assert got["zero_frac"] == 0.2


def test_pcts_of_nothing_is_unmeasured_never_zero() -> None:
    assert CT.pcts([])["status"] == CT.UNMEASURED
    assert "p50" not in CT.pcts([])


def test_session_of_puts_the_measured_rollover_hour_in_its_own_bucket() -> None:
    assert CT.session_of(3, 21) == "asia"
    assert CT.session_of(9, 21) == "london"
    assert CT.session_of(13, 21) == "ny"
    assert CT.session_of(19, 21) == "late"
    assert CT.session_of(21, 21) == "rollover"
    # with no measured offset nothing is stolen from the late bucket
    assert CT.session_of(21, None) == "late"


def test_charged_reading_divides_out_the_raw_regime_multiplier() -> None:
    got = CT.charged_reading(
        "AUDCAD", {"median_spread_pts": 1.0, "tick_size": 1e-5, "contract_size": 1e5},
        {"round_trip_per_lot": {"RAW": 7.416965, "ZERO": 7.266965, "WIDE": 9.216965}},
        {"spread_r": 0.0067, "swap_r": 0.0, "stop_pts": 150.2})
    # the corrected arithmetic the spine now applies: the 0.2x regime divided back out
    assert got["spine_commission_ratio"] == pytest.approx(9.6893, rel=1e-3)
    assert got["true_commission_ratio"] == pytest.approx(9.6893, rel=1e-3)
    # the ratio it replaced is kept so the 5x regression stays visible
    assert got["ratio_before_fix"] == pytest.approx(48.4464, rel=1e-3)
    assert got["commission_ratio_overcharge"] == pytest.approx(1.0)


def test_charged_reading_without_a_fusion_row_reports_none_not_a_guess() -> None:
    got = CT.charged_reading("X", {"median_spread_pts": 2.0}, None, None)
    assert got["spine_commission_ratio"] is None
    assert got["true_commission_ratio"] is None


# ------------------------------------------------------------------------------- the compare


def _quoted(p50: float, p90: float, live: float | None = None) -> dict[str, object]:
    return {"status": CT.MEASURED, "live_spread_pts": live,
            "tape": {"pooled": {"status": CT.MEASURED, "n": 1000, "p50": p50, "p90": p90}}}


def test_overcharge_is_named_with_its_ratio() -> None:
    got = CT.compare({"charged_pts": 165.0}, _quoted(1.0, 3.0), {},
                     {"status": CT.MEASURED, "p50": 1.0})
    assert got["verdict"] == CT.OVERCHARGED
    assert got["spread_charged_over_quoted"] == pytest.approx(165.0)


def test_undercharge_is_reported_with_the_same_weight() -> None:
    got = CT.compare({"charged_pts": 1.0}, _quoted(5.0, 9.0), {},
                     {"status": CT.MEASURED, "p50": 5.0})
    assert got["verdict"] == CT.UNDERCHARGED


def test_a_zero_median_falls_to_p90_before_calling_a_charge_manufactured() -> None:
    """MT5 stores a bar's spread as a WHOLE number of points: a half-point book reads 0."""
    got = CT.compare({"charged_pts": 0.5}, _quoted(0.0, 3.0), {},
                     {"status": CT.MEASURED, "p50": 0.0})
    assert got["verdict"] in (CT.OK, CT.UNDERCHARGED)
    assert got["reference_pts"] == 3.0
    # the plain median is kept beside it, because the cost BASIS is the median
    assert got["median_reference_pts"] == 0.0


def test_a_charge_against_a_book_that_quotes_zero_everywhere_is_overcharged() -> None:
    got = CT.compare({"charged_pts": 12.0}, _quoted(0.0, 0.0, 0.0), {},
                     {"status": CT.MEASURED, "p50": 0.0})
    assert got["verdict"] == CT.OVERCHARGED
    assert "manufactured" in got["why"]


def test_no_terminal_reading_is_unmeasured_not_ok() -> None:
    got = CT.compare({"charged_pts": 3.0}, {"status": CT.UNMEASURED}, {}, {"status": CT.UNMEASURED})
    assert got["verdict"] == CT.UNMEASURED


def test_commission_overcharge_is_the_rate_times_the_regime() -> None:
    """Both halves are fixed, so both read 1.0 -- and this is what holds them there: the rate
    comes from the module the desk actually prices with, not from a literal here."""
    got = CT.compare({"charged_pts": 1.0, "commission_ratio_overcharge": 1.0},
                     _quoted(1.0, 2.0), {"commission_per_lot_per_side":
                                         {"status": CT.MEASURED, "p50": 2.0}},
                     {"status": CT.MEASURED, "p50": 1.0})
    assert got["commission_model_per_side"] == pytest.approx(2.00)
    assert got["commission_rate_overcharge"] == pytest.approx(1.0)
    assert got["commission_total_overcharge"] == pytest.approx(1.0)


def test_an_overcharged_rate_and_regime_still_multiply() -> None:
    """The instrument must still be able to SEE the defect it was built for."""
    got = CT.compare({"charged_pts": 1.0, "commission_ratio_overcharge": 5.0},
                     _quoted(1.0, 2.0), {"commission_per_lot_per_side":
                                         {"status": CT.MEASURED, "p50": 1.6}},
                     {"status": CT.MEASURED, "p50": 1.0})
    assert got["commission_rate_overcharge"] == pytest.approx(2.00 / 1.6)
    assert got["commission_total_overcharge"] == pytest.approx(6.25)


# ------------------------------------------------------------------------------ the realised


def _ledger_row(**kw: object) -> dict[str, object]:
    base = {"symbol": "EURCHF", "side": 0, "entry_price": 0.9450, "sl": 0.9460, "tp": 0.9430,
            "fill_price": 0.9460, "volume": 0.03, "commission": -0.12, "swap": 0.0,
            "entry_order": 1}
    base.update(kw)
    return base


def test_direction_comes_from_the_bracket_not_the_side_field() -> None:
    # stop ABOVE entry and target BELOW -> short, whatever `side` says
    assert CT.position_direction(_ledger_row()) == -1
    assert CT.position_direction(_ledger_row(sl=0.9440, tp=0.9470)) == 1
    # with no bracket at all the measured convention stands: side 0 is short
    assert CT.position_direction({"side": 0}) == -1
    assert CT.position_direction({"side": 1}) == 1


def test_realised_is_unmeasured_under_min_deals_and_the_model_stands() -> None:
    deals = [{"sym": "EURCHF", "entry": 0, "vol": 0.01, "comm": -0.02, "swap": 0.0}]
    got = CT.realised_reading("EURCHF", deals, [], {}, {"tick_size": 1e-5})
    assert got["status"] == CT.UNMEASURED
    assert "MIN_DEALS" in got["why"]


def test_realised_commission_is_per_lot_per_side_from_the_deals() -> None:
    deals = [{"sym": "EURCHF", "entry": e, "vol": 0.03, "comm": -0.06, "swap": 0.0}
             for e in (0, 1, 0, 1, 0, 1)]
    got = CT.realised_reading("EURCHF", deals, [], {}, {"tick_size": 1e-5})
    assert got["status"] == CT.MEASURED
    assert got["commission_per_lot_per_side"]["p50"] == pytest.approx(2.0)


def test_the_r_denominator_is_the_rows_own_stop_not_risk_quote() -> None:
    """`risk_quote` holds a price distance on some rows and money on others; using it produced
    a 45R commission on EURCHF. The stop distance through tick value cannot do that."""
    deals = [{"sym": "EURCHF", "entry": e, "vol": 0.03, "comm": -0.06, "swap": 0.0}
             for e in (0, 1, 0, 1, 0, 1)]
    rows = [_ledger_row(risk_quote=0.00034) for _ in range(4)]
    info = {"trade_tick_size": 1e-5, "trade_tick_value": 1.07}
    got = CT.realised_reading("EURCHF", deals, rows, {}, {"tick_size": 1e-5}, info)
    # stop 100 pts x 1.07 EUR x 0.03 lots = 3.21 EUR of risk; 0.12 EUR of commission
    assert got["commission_swap_r"]["p50"] == pytest.approx(0.12 / (100 * 1.07 * 0.03), rel=1e-3)
    assert got["commission_swap_r"]["p50"] < 0.1


def test_a_favourable_fill_is_not_charged_as_a_cost() -> None:
    deals = [{"sym": "EURCHF", "entry": e, "vol": 0.03, "comm": -0.06, "swap": 0.0}
             for e in (0, 1, 0, 1, 0, 1)]
    # short filled 10 pts ABOVE the intended price: better, so the slip in R is negative
    rows = [_ledger_row(entry_price=0.9451) for _ in range(3)]
    intents = {1: {"intended": 0.9450}}
    got = CT.realised_reading("EURCHF", deals, rows, intents, {"tick_size": 1e-5},
                              {"trade_tick_size": 1e-5, "trade_tick_value": 1.07})
    assert got["entry_slip_r"]["p50"] < 0


# ------------------------------------------------------------------------------- the surface


def _symbol_row(symbol: str, *, slip_n: int, slip_p50: float, ref: float,
                stop: float | None) -> dict[str, object]:
    return {"symbol": symbol,
            "charged": {"stop_pts": stop},
            "compare": {"median_reference_pts": ref},
            "realised": {"status": CT.MEASURED, "n_deals": 40,
                         "entry_slip_r": {"status": CT.MEASURED, "n": slip_n, "p50": slip_p50},
                         "stop_pts_realised": {"status": CT.MEASURED, "p50": 900.0}}}


def test_the_surface_defers_a_cell_whose_slippage_is_unmeasured() -> None:
    """The consumer marks whatever it finds MEASURED and stops asking, so an unmeasured half
    must not be published as a cheap number."""
    got = CT.execution_surface([_symbol_row("AUDCAD", slip_n=1, slip_p50=0.0, ref=0.0,
                                            stop=150.0)])
    assert got["n_cells"] == 0
    assert got["n_deferred"] == 1
    assert got["deferred"][0]["status"] == CT.UNMEASURED


def test_the_surface_publishes_spread_plus_signed_slip_and_excludes_commission() -> None:
    got = CT.execution_surface([_symbol_row("XAUUSD", slip_n=5, slip_p50=0.008, ref=5.0,
                                            stop=1000.0)])
    row = got["net_alpha"][0]
    assert row["cost_r"] == pytest.approx(5.0 / 1000.0 + 0.008)
    assert "commission" in row["excludes"] and "market_impact" in row["excludes"]
    assert row["cost_r_is_bound"] is True


def test_the_surface_never_publishes_a_negative_cost() -> None:
    got = CT.execution_surface([_symbol_row("XAUUSD", slip_n=6, slip_p50=-0.05, ref=5.0,
                                            stop=1000.0)])
    assert got["net_alpha"][0]["cost_r"] == 0.0
    assert got["net_alpha"][0]["slip_r_median"] == pytest.approx(-0.05)


def test_the_surface_falls_back_to_the_desks_own_stops() -> None:
    got = CT.execution_surface([_symbol_row("CHFNOK", slip_n=8, slip_p50=0.0, ref=9.0,
                                            stop=None)])
    row = got["net_alpha"][0]
    assert row["stop_pts"] == pytest.approx(900.0)
    assert "own live trades" in row["stop_basis"]


# ------------------------------------------------------------------------------- the re-judge


def _cost_dead(symbol: str, net: float, comm: float, spread: float) -> dict[str, object]:
    return {"key": f"cell.{symbol}", "symbol": symbol, "family": "discovered",
            "gross": 0.2, "net": net,
            "terms": {"commission": {"value": comm, "status": "MODELLED"},
                      "spread_slippage": {"value": spread, "status": "MODELLED"}}}


def test_a_refusal_made_on_an_overcharged_commission_is_restored() -> None:
    doc = {"cost_dead": [_cost_dead("AUDCAD", -0.209, 0.3246, 0.0067)]}
    got = CT.rejudge(doc, None, {"AUDCAD": {"commission_total_overcharge": 5.625}})
    row = got["rows"][0]
    assert row["commission_measured"] == pytest.approx(0.3246 / 5.625)
    assert row["net_on_measured_cost"] > 0
    assert row["restored_to_queue"] is True
    assert got["n_restored_to_queue"] == 1


def test_the_rejudge_is_two_sided_and_can_raise_a_cost() -> None:
    """EURCHF's measured execution cost is HIGHER than the model charged. A re-judge that only
    ever lowered the bill would be an argument, not a measurement."""
    doc = {"cost_dead": [_cost_dead("EURCHF", -0.05, 0.01, 0.0084)]}
    got = CT.rejudge(doc, None, {"EURCHF": {"commission_total_overcharge": 1.0}},
                     {"EURCHF": 0.0253})
    row = got["rows"][0]
    assert row["spread_measured"] == pytest.approx(0.0253)
    assert row["net_on_measured_cost"] < row["net_as_charged"]
    assert row["restored_to_queue"] is False


def test_a_refusal_that_survives_measured_costs_earns_its_place() -> None:
    doc = {"cost_dead": [_cost_dead("AUDCAD", -0.9, 0.3246, 0.0067)]}
    got = CT.rejudge(doc, None, {"AUDCAD": {"commission_total_overcharge": 5.625}})
    assert got["n_restored_to_queue"] == 0
    assert "earns its place" in got["rows"][0]["why"]


def test_every_restored_cell_is_billed_as_missed_growth() -> None:
    doc = {"cost_dead": [_cost_dead("AUDCAD", -0.209, 0.3246, 0.0067)]}
    judged = CT.rejudge(doc, None, {"AUDCAD": {"commission_total_overcharge": 5.625}})
    lines = CT.missed_lines(judged, "2026-09-23T02:50:51+00:00")
    assert len(lines) == 1
    assert lines[0]["rail"] == "cost_truth_overcharge"
    assert lines[0]["two_sided"] is True
    assert lines[0]["refused_since"] == "2026-09-23T02:50:51+00:00"
    assert lines[0]["value"] > 0


# ---------------------------------------------------------------------------------- plumbing


def test_bars_per_symbol_is_derived_and_floors_when_memory_is_unreadable(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CT, "free_bytes", lambda: (None, "no counter"))
    cap, why = CT.bars_per_symbol(54)
    assert cap == CT.MIN_BARS_PER_SYMBOL
    assert "floor" in why
    monkeypatch.setattr(CT, "free_bytes", lambda: (8.0e9, "test"))
    cap2, _ = CT.bars_per_symbol(54)
    assert CT.MIN_BARS_PER_SYMBOL <= cap2 <= CT.MAX_BARS_PER_SYMBOL


def test_main_publishes_without_a_terminal_and_never_crashes(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CT, "UNIVERSE", tmp_path / "universe.json")
    monkeypatch.setattr(CT, "FUSION_COST", tmp_path / "FUSION_COST.json")
    monkeypatch.setattr(CT, "COST_TO_EDGE", tmp_path / "COST_TO_EDGE.json")
    monkeypatch.setattr(CT, "NET_EDGE", tmp_path / "NET_EDGE.json")
    monkeypatch.setattr(CT, "RANKS", tmp_path / "ranks.json")
    monkeypatch.setattr(CT, "LIVE_LEDGER", tmp_path / "live_ledger.jsonl")
    monkeypatch.setattr(CT, "INTENTS", tmp_path / "intents.jsonl")
    monkeypatch.setattr(CT, "QUOTES", tmp_path / "quotes.json")
    monkeypatch.setattr(CT, "CURSOR", tmp_path / "cursor.json")
    monkeypatch.setattr(CT, "MISSED", tmp_path / "missed.jsonl")
    monkeypatch.setattr(CT, "EXEC_SURFACE", tmp_path / "EXECUTION_COST_SURFACE.json")
    monkeypatch.setattr(CT, "VENUE_SURFACE", tmp_path / "COST_SURFACE.json")
    monkeypatch.setattr(CT, "SPREAD_PROVENANCE", tmp_path / "SPREAD_PROVENANCE.json")
    monkeypatch.setattr(CT, "VERIFIED", tmp_path / "spread_repair_verified.json")
    monkeypatch.setattr(CT, "SLEEVE_REGISTRY", tmp_path / "sleeve_registry.json")
    (tmp_path / "universe.json").write_text(json.dumps(
        {"EURCHF": {"median_spread_pts": 0.5, "tick_size": 1e-5, "contract_size": 1e5}}), "utf-8")
    (tmp_path / "live_ledger.jsonl").write_text(
        json.dumps({"symbol": "EURCHF", "side": 0, "entry_price": 0.945, "sl": 0.946,
                    "volume": 0.03, "commission": -0.12, "swap": 0.0}) + "\n", "utf-8")
    out, md = tmp_path / "COST_TRUTH.json", tmp_path / "COST_TRUTH.md"
    rc = CT.main(["--once", "--budget-s", "5", "--no-terminal",
                  "--out", str(out), "--md", str(md)])
    assert rc == 0
    rep = json.loads(out.read_text("utf-8"))
    assert rep["terminal_status"] == CT.UNMEASURED
    assert rep["n_symbols"] == 1
    assert rep["symbols"][0]["quoted"]["status"] == CT.UNMEASURED
    assert md.read_text("utf-8").startswith("# COST TRUTH")


# -------------------------------------------------------------------------------- the fence


def _report(at: str, *, symbols: list[dict[str, object]], comm: float = 5.625) -> dict[str, object]:
    return {"at": at, "overcharge_tolerance": 1.5, "stale_after_s": 4 * 3600,
            "n_symbols": len(symbols), "terminal_status": CT.MEASURED,
            "commission": {"total_overcharge": comm}, "symbols": symbols}


def _sym(symbol: str, charged: float, ref: float, verdict: str,
         ratio: float | None) -> dict[str, object]:
    return {"symbol": symbol, "compare": {"charged_pts": charged, "reference_pts": ref,
                                          "reference_basis": "test", "verdict": verdict,
                                          "spread_charged_over_quoted": ratio}}


def test_fence_passes_unmeasured_when_the_box_has_no_artifact(tmp_path: Path) -> None:
    got = FENCE.judge(None, None, None)
    assert got["verdict"] == FENCE.UNMEASURED
    assert got["exit"] == 0


def test_fence_fails_on_a_new_overcharged_symbol(tmp_path: Path) -> None:
    rep = _report(datetime.now(tz=UTC).isoformat(),
                  symbols=[_sym("GBPCHF", 165.0, 1.0, "OVERCHARGED", 165.0)])
    got = FENCE.judge(rep, {"overcharged_symbols": [], "commission_total_overcharge": 5.625},
                      None)
    assert got["verdict"] == FENCE.OVERCHARGED
    assert got["exit"] == 2
    assert got["new_since_declaration"] == ["GBPCHF"]


def test_fence_passes_a_declared_symbol_and_fails_a_rising_commission(tmp_path: Path) -> None:
    rep = _report(datetime.now(tz=UTC).isoformat(),
                  symbols=[_sym("GBPCHF", 165.0, 1.0, "OVERCHARGED", 165.0)])
    declared = {"overcharged_symbols": ["GBPCHF"], "commission_total_overcharge": 5.625}
    assert FENCE.judge(rep, declared, None)["exit"] == 0
    worse = _report(datetime.now(tz=UTC).isoformat(),
                    symbols=[_sym("GBPCHF", 165.0, 1.0, "OVERCHARGED", 165.0)], comm=9.0)
    got = FENCE.judge(worse, declared, None)
    assert got["verdict"] == FENCE.RATCHET_UP
    assert got["exit"] == 2


def test_fence_fails_a_stale_artifact(tmp_path: Path) -> None:
    old = (datetime.now(tz=UTC) - timedelta(hours=9)).isoformat()
    got = FENCE.judge(_report(old, symbols=[_sym("EURCHF", 0.5, 3.0, "OK", 0.16)]), {}, None)
    assert got["verdict"] == FENCE.STALE
    assert got["exit"] == 2


def test_fence_lowers_the_ratchet_when_the_debt_shrinks(tmp_path: Path) -> None:
    path = tmp_path / "ratchet.json"
    declared = {"overcharged_symbols": ["GBPCHF", "CADCHF"],
                "commission_total_overcharge": 5.625}
    path.write_text(json.dumps(declared), "utf-8")
    rep = _report(datetime.now(tz=UTC).isoformat(),
                  symbols=[_sym("GBPCHF", 165.0, 1.0, "OVERCHARGED", 165.0)])
    verdict = FENCE.judge(rep, declared, None)
    assert verdict["exit"] == 0
    assert FENCE.rewrite_ratchet(path, verdict, declared) is True
    assert json.loads(path.read_text("utf-8"))["overcharged_symbols"] == ["GBPCHF"]


def test_fence_never_raises_the_ratchet_itself(tmp_path: Path) -> None:
    path = tmp_path / "ratchet.json"
    declared = {"overcharged_symbols": [], "commission_total_overcharge": 5.625}
    path.write_text(json.dumps(declared), "utf-8")
    rep = _report(datetime.now(tz=UTC).isoformat(),
                  symbols=[_sym("GBPCHF", 165.0, 1.0, "OVERCHARGED", 165.0)])
    verdict = FENCE.judge(rep, declared, None)
    assert verdict["exit"] == 2
    assert FENCE.rewrite_ratchet(path, verdict, declared) is False
    assert json.loads(path.read_text("utf-8"))["overcharged_symbols"] == []


# ------------------------------------------------- the registry repair, verified symbol by symbol


def _prov(old: float, new: float, symbol: str = "GBPCHF") -> dict[str, object]:
    return {"by_symbol": {symbol: {"old": old, "new": new, "bucket": "corrected"}},
            "applied": False}


def _quoted_row(symbol: str, p50: float, p90: float,
                live: float | None = None) -> dict[str, object]:
    return {"symbol": symbol,
            "compare": {"median_reference_pts": p50, "quoted_p50_pts": p50,
                        "quoted_p90_pts": p90, "quoted_live_pts": live}}


def test_a_correction_that_moves_toward_the_quote_is_verified() -> None:
    got = CT.repair_verification(_prov(165.0, 3.0), [_quoted_row("GBPCHF", 1.0, 3.0)])
    assert got["n_toward"] == 1 and got["verified_symbols"] == ["GBPCHF"]
    assert got["rows"][0]["err_before"] == pytest.approx(164.0)
    assert got["rows"][0]["err_after"] == pytest.approx(2.0)


def test_a_correction_that_moves_away_from_the_quote_is_refused() -> None:
    """The gate has to be able to say no, or it is a rubber stamp with a measurement attached."""
    got = CT.repair_verification(_prov(3.0, 90.0), [_quoted_row("GBPCHF", 2.0, 4.0)])
    assert got["n_away"] == 1 and got["verified_symbols"] == []
    assert got["away_symbols"] == ["GBPCHF"]


def test_a_symbol_with_no_measured_quote_is_unverified_and_not_applied() -> None:
    got = CT.repair_verification(_prov(165.0, 3.0), [])
    assert got["n_unverified"] == 1 and got["verified_symbols"] == []
    assert got["rows"][0]["verdict"] == "UNVERIFIED"


def test_the_complete_map_is_read_not_the_truncated_list() -> None:
    """`SPREAD_PROVENANCE.corrected` is capped at 60 rows and the report says so itself."""
    prov = {"by_symbol": {f"S{i}": {"old": 10.0, "new": 1.0, "bucket": "corrected"}
                          for i in range(70)},
            "corrected": [{"symbol": "S0", "old": 10.0, "new": 1.0}]}
    rows = [_quoted_row(f"S{i}", 1.0, 2.0) for i in range(70)]
    assert CT.repair_verification(prov, rows)["n_pending"] == 70


def test_the_repair_gate_blocks_when_its_input_cannot_be_read(tmp_path: Path) -> None:
    """A gate that cannot be read must block, never wave through."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "repair_universe_spreads",
        ROOT / "desks" / "mt5" / "scripts" / "repair_universe_spreads.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._verified(None) is None                      # no gate asked for
    assert mod._verified(tmp_path / "absent.json") == set()  # unreadable -> applies nothing
    good = tmp_path / "v.json"
    good.write_text(json.dumps({"verified_symbols": ["GBPCHF", "CADCHF"]}), "utf-8")
    assert mod._verified(good) == {"GBPCHF", "CADCHF"}


def test_the_cost_wire_is_a_declared_edge_the_watchdog_checks() -> None:
    """The spine read a path nothing wrote for weeks. A declared edge is what ends that class."""
    from libs.ops.control_plane import edges as edg
    arts = {e.artifact: e for e in edg.REQUIRED_EDGES}
    exec_edge = arts["desks/mt5/reports/EXECUTION_COST_SURFACE.json"]
    assert exec_edge.producer == "leg:cost_truth" and exec_edge.consumer == "leg:net_edge"
    venue = arts["desks/mt5/reports/COST_SURFACE.json"]
    assert venue.consumer == "leg:cost_truth"
    # and both ends must actually name the path, which is what check_edge_paths verifies
    organ = (ROOT / "desks" / "mt5" / "research" / "cost_truth.py").read_text("utf-8")
    spine = (ROOT / "desks" / "mt5" / "research" / "net_edge_spine.py").read_text("utf-8")
    assert "EXECUTION_COST_SURFACE.json" in organ and "EXECUTION_COST_SURFACE.json" in spine
    assert "COST_SURFACE.json" in organ
