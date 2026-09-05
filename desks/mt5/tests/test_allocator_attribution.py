"""The weekly growth table: what made us richer, in what unit, on how much evidence.

    "Portfolio growth attribution: dlogW = Alpha + Selection + State + Sizing + Diversification
     + Execution + Exit + Costs + Veto, so every week you can answer what actually made us
     richer."                                                    -- the principal, 2026-09-05
    "Information attribution per data source: dElog_DataSource; kill dead information."

`allocator_attribution` computed the nine terms and exposed only `main()`: no scheduler, no
machine reader, no entry term, no per-sleeve row and no source ledger. These pin the organ it
became -- and, above all, the ARITHMETIC, because a decomposition that does not add up to a
measured number is a story:

  * the ledger's own dlogW is the heat-weighted realised return per scored day, and the last
    allocator pass of a day speaks for that day;
  * every term priced in log-wealth per day is subtracted from it and the gap is RESIDUAL --
    named, reported, never distributed. Sum + residual == dlogW exactly;
  * a term priced in R, in heat or as a ratio stays OUT of the identity and says why: converting
    it would balance the sum by changing units mid-sum;
  * ENTRY reads the adverse excursion the desk has recorded and never billed, heat-weighted when
    there is a funded book and honest about it when there is not;
  * a data source with trials and no growth in the funded book is named DEAD INFORMATION, and a
    cold source is UNMEASURED rather than killed for being new;
  * `run()` takes no arguments, writes both artifacts, and a second pass changes nothing.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import allocator_attribution as attr  # noqa: E402

UNMEASURED = attr.UNMEASURED
#: The forecast log is read by WINDOW, not by fixture date: `load_forecasts(days)` keeps rows
#: newer than now - days. So the fixture days are the ten ending yesterday -- a hard-coded month
#: would make these tests pass in the week they were written and read UNMEASURED ever after.
DAYS = [(datetime.now(UTC).date() - timedelta(days=i)).isoformat() for i in range(10, 0, -1)]
#: The fixture book and what it earned. 0.10 x (+0.5) + 0.05 x (-0.2) = +0.04 per day, every day,
#: so the ledger's dlogW is a number a reader can check by hand.
BOOK = {"A": 0.10, "B": 0.05}
REALISED_R = {"A": 0.5, "B": -0.2}
DLOGW = 0.10 * 0.5 + 0.05 * -0.2
EXPECTED = 0.002
HEAT, FLOOR, CEILING = 0.15, 0.20, 0.30


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A desk tree with a forecast log and a realised series, and nothing else.

    Every other ledger is written by the test that is about it, so a term can never read as
    measured because a neighbouring fixture happened to leave a file behind.
    """
    (tmp_path / "reports").mkdir()
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(attr, "BASE", tmp_path)
    monkeypatch.setattr(attr, "FORECASTS", tmp_path / "data" / "pf_forecast_log.jsonl")
    monkeypatch.setattr(attr, "LIVE", tmp_path / "data" / "live_ledger.jsonl")
    monkeypatch.setattr(attr, "OUT", tmp_path / "reports" / "allocator_attribution.json")
    monkeypatch.setattr(attr, "WEEKLY_OUT",
                        tmp_path / "reports" / "GROWTH_ATTRIBUTION_WEEKLY.json")
    monkeypatch.setattr(attr, "_heat_bars", lambda: (FLOOR, CEILING, "test"))
    monkeypatch.setattr(attr, "realized_daily",
                        lambda: ({s: dict.fromkeys(DAYS, r) for s, r in REALISED_R.items()},
                                 "shadow_forward"))
    (tmp_path / "data" / "pf_forecast_log.jsonl").write_text("\n".join(
        json.dumps({"t": f"{d}T12:00:00+00:00", "book": BOOK,
                    "expected_log_per_day": EXPECTED, "expected_cvar_per_day": -0.01,
                    "total_heat": HEAT, "regime": {"bull": 1.0}}) for d in DAYS), "utf-8")
    return tmp_path


def _report(desk: Path, name: str, doc: Any) -> None:
    (desk / "reports" / name).write_text(json.dumps(doc), "utf-8")


def _priced_terms(desk: Path) -> None:
    """Give three of the four log-wealth terms a ledger, so the identity has something to close
    over: selection (the proof's contest), veto (the rail ledger), sizing (the forecast log)."""
    _report(desk, "ALLOCATOR_PROOF.json",
            {"passed": True, "scores": {"dynamic": {"mean_log_growth": 0.003},
                                        "equal_weight": {"mean_log_growth": 0.002}}})
    _report(desk, "MISSED_GROWTH.json",
            {"rails": {"state_gate": {"verdict": "EARNS_ITS_PLACE", "value_logw_per_day": 0.0005}}})


# --------------------------------------------------------------------------- the ledger's dlogW
def test_the_ledgers_own_dlogw_is_heat_weighted_realised_return_per_scored_day(
        desk: Path) -> None:
    forecasts = attr.load_forecasts(30)
    realized, _ = attr.realized_daily()
    per_day = attr.daily_book_growth(forecasts, realized)
    assert set(per_day) == set(DAYS)
    for v in per_day.values():
        assert v == pytest.approx(DLOGW)


def test_the_last_allocator_pass_of_a_day_speaks_for_that_day(desk: Path) -> None:
    """Several passes a day is normal; summing their books would count one day's R once per
    pass and make a busy day look like a profitable one."""
    (desk / "data" / "pf_forecast_log.jsonl").write_text("\n".join(
        json.dumps({"t": f"{DAYS[-1]}T{h:02d}:00:00+00:00", "book": book,
                    "expected_log_per_day": EXPECTED, "total_heat": HEAT})
        for h, book in ((6, {"A": 1.0}), (12, {"A": 1.0}), (18, BOOK))), "utf-8")
    per_day = attr.daily_book_growth(attr.load_forecasts(30), attr.realized_daily()[0])
    assert per_day == {DAYS[-1]: pytest.approx(DLOGW)}


# --------------------------------------------------------------------------- the identity
def test_the_terms_in_the_identity_plus_the_residual_equal_the_ledgers_dlogw(desk: Path) -> None:
    _priced_terms(desk)
    w = attr.weekly_table(days=30)
    ident = w["identity"]
    assert ident["closes"] is True
    assert w["dlogw_per_day"]["value"] == pytest.approx(DLOGW)
    assert w["dlogw_per_day"]["n"] == len(DAYS)
    summed = sum(float(w["terms"][k]["value"]) for k in ident["terms_in_identity"])
    assert summed == pytest.approx(ident["terms_summed_logw_per_day"], abs=1e-12)
    assert summed + float(ident["residual"]["value"]) == pytest.approx(DLOGW, abs=1e-9)
    # and the terms are the ones actually priced in log-wealth per day, by name
    assert set(ident["terms_in_identity"]) == {"alpha", "selection", "sizing", "veto"}
    assert w["terms"]["alpha"]["value"] == pytest.approx(DLOGW - EXPECTED)
    assert w["terms"]["selection"]["value"] == pytest.approx(0.001)
    assert w["terms"]["veto"]["value"] == pytest.approx(0.0005)
    # the anti-timidity ledger: the book sat under the floor, so the missing heat's growth is a
    # charge. Reported to 8 decimals by its own term, which is why the tolerance is absolute.
    assert w["terms"]["sizing"]["value"] == pytest.approx((FLOOR - HEAT) * EXPECTED / HEAT,
                                                          abs=1e-8)


def test_the_residual_is_named_and_says_what_is_in_it(desk: Path) -> None:
    _priced_terms(desk)
    res = attr.weekly_table(days=30)["identity"]["residual"]
    assert res["name"] == "UNDISTRIBUTED"
    assert "EXPECTED" in res["why"], "the residual must name the book's own expected growth"
    assert "never distributed" in attr.weekly_table(days=30)["identity"]["rule"]


def test_a_measured_term_in_another_unit_stays_out_of_the_identity_and_says_why(
        desk: Path) -> None:
    """The state term is a total-variation drift of the regime mix. It is a real, measured
    number and it is not log-wealth; adding it would balance the sum by changing units."""
    _priced_terms(desk)
    w = attr.weekly_table(days=30)
    state = w["terms"]["state"]
    assert isinstance(state["value"], float)
    assert state["unit"] == "regime total variation"
    assert state["in_identity"] is False
    assert "exchange rate" in state["out_of_identity_why"]
    assert "state" in w["identity"]["terms_out_of_identity"]


def test_an_absent_ledger_reads_unmeasured_with_its_path_and_never_a_zero(desk: Path) -> None:
    w = attr.weekly_table(days=30)
    for name in ("selection", "diversification", "exit", "cost"):
        t = w["terms"][name]
        assert t["value"] == UNMEASURED, name
        assert t["why"], name
        assert t["in_identity"] is False, name
    assert "EXIT_ACCOUNTS.json" in w["terms"]["exit"]["why"]
    assert "FILL_SURFACE.json" in w["terms"]["cost"]["why"]
    assert set(w["unmeasured"]) >= {"selection", "diversification", "exit", "cost"}


def test_the_dlogw_is_unmeasured_when_no_forecast_book_joins_a_realised_day(
        desk: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(attr, "realized_daily", lambda: ({}, UNMEASURED))
    w = attr.weekly_table(days=30)
    assert w["dlogw_per_day"]["value"] == UNMEASURED
    assert w["identity"]["closes"] is False
    assert w["identity"]["residual"]["value"] == UNMEASURED, (
        "a residual computed against an unmeasured total would be a number about nothing")


# --------------------------------------------------------------------------- the tenth term
def test_entry_is_the_adverse_excursion_the_entries_paid_weighted_by_the_funded_book(
        desk: Path) -> None:
    _report(desk, "EXCURSIONS.json", {"sleeves": {
        "A": {"n": 20, "median_mae_r": 0.5, "median_mfe_r": 1.2},
        "B": {"n": 30, "median_mae_r": 0.2, "median_mfe_r": 0.9},
        "C": {"n": 2, "median_mae_r": 9.0, "median_mfe_r": 0.1}}})
    _report(desk, "pf_allocation.json", {"book": BOOK})
    t = attr._entry_term()
    assert t["value"] == pytest.approx(-(0.10 * 0.5 + 0.05 * 0.2))
    assert t["unit"] == "log-wealth of adverse excursion per trade"
    assert t["in_identity"] is False, "intra-trade drawdown is not a realised loss"
    assert t["n_sleeves_funded"] == 2 and t["thin_sleeves"] == ["C"]
    assert next(iter(t["worst_entries"])) == "A", "the worst entry must lead the list"


def test_entry_without_a_funded_book_reports_r_per_trade_and_says_it_is_unweighted(
        desk: Path) -> None:
    _report(desk, "EXCURSIONS.json", {"sleeves": {
        "A": {"n": 20, "median_mae_r": 0.5}, "B": {"n": 30, "median_mae_r": 0.3}}})
    t = attr._entry_term()
    assert t["unit"] == "R per trade"
    assert t["value"] == pytest.approx(-0.4)
    assert "no funded book" in t["why"]


def test_entry_is_unmeasured_when_no_sleeve_has_enough_excursions(desk: Path) -> None:
    _report(desk, "EXCURSIONS.json", {"sleeves": {"A": {"n": 2, "median_mae_r": 4.0}}})
    t = attr._entry_term()
    assert t["value"] == UNMEASURED and str(attr.MIN_ENTRY_TRADES) in t["why"]


def test_entry_is_on_the_weekly_table_beside_the_nine(desk: Path) -> None:
    _report(desk, "EXCURSIONS.json", {"sleeves": {"A": {"n": 20, "median_mae_r": 0.5}}})
    w = attr.weekly_table(days=30)
    assert tuple(w["terms"]) == ("alpha", "selection", "state", "sizing", "diversification",
                                 "entry", "execution", "exit", "cost", "veto")
    assert isinstance(w["terms"]["entry"]["value"], float)


# --------------------------------------------------------------------------- per sleeve
def test_the_per_sleeve_rows_say_which_sleeve_made_the_book_richer(desk: Path) -> None:
    ps = attr.weekly_table(days=30)["per_sleeve"]
    assert ps["n_sleeves"] == 2 and ps["unit"] == attr.LOGW
    assert ps["sleeves"]["A"]["value"] == pytest.approx(0.10 * 0.5)
    assert ps["sleeves"]["B"]["value"] == pytest.approx(0.05 * -0.2)
    assert ps["sleeves"]["A"]["mean_heat"] == pytest.approx(0.10)
    assert ps["sleeves"]["A"]["mean_r"] == pytest.approx(0.5)
    assert ps["sleeves"]["A"]["n"] == len(DAYS)
    assert ps["best"][0] == "A" and ps["worst"][-1] == "B"
    total = sum(r["value"] for r in ps["sleeves"].values())
    assert total == pytest.approx(DLOGW), "the sleeve rows must add up to the book's own dlogW"


def test_per_sleeve_is_unmeasured_rather_than_empty_when_nothing_joins(
        desk: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(attr, "realized_daily", lambda: ({}, UNMEASURED))
    ps = attr.weekly_table(days=30)["per_sleeve"]
    assert ps["value"] == UNMEASURED and ps["n_sleeves"] == 0


# --------------------------------------------------------------------------- dead information
def test_a_source_with_trials_and_no_growth_is_named_dead_information(desk: Path) -> None:
    _report(desk, "RESEARCH_PNL.json", {"sources": {
        "alpha_evolution": {"arm": "new_mechanism", "trials": 900, "certified": 9,
                            "growth_per_day": 0.02, "cost_units": 8100.0},
        "world_crawler": {"arm": "external_screen", "trials": 400, "certified": 0,
                          "growth_per_day": 0.0, "cost_units": 4000.0},
        "repo_miner": {"arm": "external_screen", "trials": 200, "certified": 1,
                       "growth_per_day": -0.0001, "cost_units": 2000.0},
        "deep_forest_jp": {"arm": "external_screen", "trials": 3, "certified": 0,
                           "growth_per_day": 0.0, "cost_units": 30.0}},
        "unattributed_growth_per_day": 0.004})
    info = attr.information_attribution()
    assert info["dead_information"] == ["repo_miner", "world_crawler"]
    assert info["pays"] == ["alpha_evolution"]
    assert info["unmeasured"] == ["deep_forest_jp"], (
        "a source with three trials is cold, not dead: killing it for being new is how a desk "
        "stops finding anything")
    assert info["sources"]["alpha_evolution"]["delta_elogw_per_day"] == pytest.approx(0.02)
    assert info["sources"]["alpha_evolution"]["roi_growth_per_cost_unit"] is not None
    assert info["sources"]["world_crawler"]["unit"] == attr.LOGW
    assert str(attr.MIN_SOURCE_TRIALS) in info["sources"]["deep_forest_jp"]["why"]
    assert info["unattributed_growth_per_day"] == pytest.approx(0.004)


def test_information_attribution_without_the_research_pnl_is_unmeasured_not_empty(
        desk: Path) -> None:
    info = attr.information_attribution()
    assert info["value"] == UNMEASURED
    assert info["n_sources"] == 0 and info["dead_information"] == []
    assert "RESEARCH_PNL.json" in info["why"]


# --------------------------------------------------------------------------- the pass
def test_run_takes_no_arguments_writes_both_artifacts_and_is_idempotent(desk: Path) -> None:
    """`daily_cycle._state_research_feedback` calls `mod.run()` with nothing, once a day, and may
    re-run the step after a partial day. Neither may change what the artifacts say."""
    _priced_terms(desk)
    out = attr.run()
    daily = desk / "reports" / "allocator_attribution.json"
    weekly = desk / "reports" / "GROWTH_ATTRIBUTION_WEEKLY.json"
    assert daily.exists() and weekly.exists()
    first = {k: json.loads(p.read_text("utf-8")) for k, p in (("d", daily), ("w", weekly))}
    attr.run()
    second = {k: json.loads(p.read_text("utf-8")) for k, p in (("d", daily), ("w", weekly))}

    def _stable(doc: Any) -> Any:
        if isinstance(doc, dict):
            return {k: _stable(v) for k, v in doc.items() if k != "generated_utc"}
        if isinstance(doc, list):
            return [_stable(v) for v in doc]
        return doc

    assert _stable(first) == _stable(second)
    assert out["dlogw_per_day"] == pytest.approx(DLOGW)
    assert out["residual"] is not None and out["n_sleeves_attributed"] == 2
    assert set(out["measured"]) >= {"alpha", "selection", "sizing", "veto"}


def test_the_weekly_report_carries_the_governance_rules_and_a_trailing_window(desk: Path) -> None:
    out = attr.run(days=30, week_days=7)
    w = out["weekly"]
    assert list(w["rules"]) == list(attr.GOVERNANCE_RULES)
    assert w["window_days"] == 7 and w["trailing"]["window_days"] == 30
    assert set(w["trailing"]["terms"]) == set(w["terms"]), (
        "the trailing table must be the SAME terms at a different n, not a different table")


def test_the_daily_artifact_keeps_its_pinned_nine_term_shape(desk: Path) -> None:
    """The nine-term dict is a contract other readers pin. The tenth term rides beside it."""
    doc = attr.build(30)
    assert tuple(doc["growth_decomposition"]["terms"]) == (
        "alpha", "selection", "state", "sizing", "diversification", "execution", "exit",
        "cost", "veto")
    assert "entry" in doc and "per_sleeve" in doc and "information" in doc
