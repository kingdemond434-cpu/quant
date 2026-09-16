"""The scorecard's own falsifier: an absent artifact must never read as a zero.

THE ONE TEST THAT MATTERS is `test_every_row_is_UNMEASURED_when_no_artifact_exists`. A board that
quietly prints 0 for a dimension nobody has measured is worse than no board: 0 is a MEASUREMENT --
it says the organ ran and found nothing -- and a reader cannot tell it from the real thing. Law
L1.28a (WS-005) says absence never resolves to a clean verdict, so every one of the fourteen rows
is asserted to come back UNMEASURED, with `current is None`, naming the path it looked for.

Every other test here pins a row to a MINIMAL fixture with the field names the producing organ
actually writes, so a rename on the producer's side fails here rather than silently turning a row
into a zero on the live board.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import tier1_scorecard as sc  # noqa: E402
import universe_policy  # noqa: E402

#: Every artifact the board reads. Derived rather than listed, so a row added later cannot quietly
#: keep pointing at the live box's files while the suite believes it is sandboxed.
PATH_ATTRS = sorted(n for n, v in vars(sc).items()
                    if n.isupper() and isinstance(v, Path)
                    and n not in ("DESK", "ROOT", "REPORTS", "DATA"))


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every artifact constant at an EMPTY tmp_path. Nothing exists until a test writes it."""
    for name in PATH_ATTRS:
        monkeypatch.setattr(sc, name, tmp_path / Path(getattr(sc, name)).name)
    return tmp_path


def _write(sandbox: Path, attr: str, payload: object) -> Path:
    path = Path(getattr(sc, attr))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _lines(sandbox: Path, attr: str, rows: list[dict]) -> Path:
    path = Path(getattr(sc, attr))
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return path


# ----------------------------------------------------------------- the law: absence is a verdict
def test_every_row_is_UNMEASURED_when_no_artifact_exists(sandbox: Path) -> None:
    doc = sc.build()
    assert doc["n_rows"] == 14, "the blueprint names fourteen dimensions; the board carries 14"
    assert len(sc.SPEC) == 14
    for row in doc["rows"]:
        assert row["verdict"] == sc.UNMEASURED, row["dimension"]
        assert row["current"] is None, f"{row['dimension']} fabricated a number from nothing"
        assert row["current"] != 0, "a zero is a measurement, not an absence (L1.28a)"
        assert row["measured_at"] is None
        assert "ABSENT/UNREADABLE" in row["basis"] or row["basis"].startswith("UNMEASURED")
    assert doc["overall"] == {"at_or_above": 0, "below": 0, "unmeasured": 14,
                             "weakest_measured": [], "why": doc["overall"]["why"]}


def test_an_absent_row_names_the_path_it_looked_for(sandbox: Path) -> None:
    row = sc._r09_cost_model()
    assert "cost_surface.json" in row["basis"], "a missing file with no path named is an accusation"


def test_an_unreadable_artifact_reads_UNMEASURED_and_does_not_raise(sandbox: Path) -> None:
    Path(sc.EFFECTIVE_BREADTH).write_text("{ this is not json", encoding="utf-8")
    Path(sc.BREADTH_MANDATE).write_text("\x00\x01 garbage", encoding="utf-8")
    assert sc._r01_effective_breadth()["verdict"] == sc.UNMEASURED


def test_a_utf8_bom_is_read_rather_than_refused(sandbox: Path) -> None:
    Path(sc.BREADTH_MANDATE).write_text(
        json.dumps({"occupied": ["a", "b"], "declared_clusters": 15}), encoding="utf-8-sig")
    assert sc._r03_mechanism_clusters()["current"] == 2.0


# ------------------------------------------------------------------- one fixture per row, 1..14
def test_row01_effective_breadth_reads_the_headline_k_eff(sandbox: Path) -> None:
    _write(sandbox, "EFFECTIVE_BREADTH", {
        "generated_utc": "2026-09-16T14:00:00+00:00",
        "effective": {"effective_breadth": 18.5, "n_nominal": 40, "binding_reading": "realised"}})
    row = sc._r01_effective_breadth()
    assert row["current"] == 18.5 and row["verdict"] == sc.ABOVE
    assert row["first_target"] == 15.0 and row["max_solo_direction"] == "25-40"
    assert "effective.effective_breadth" in row["basis"]
    assert row["measured_at"] == "2026-09-16T14:00:00+00:00"


def test_row01_falls_back_to_the_breadth_mandate_ratchet(sandbox: Path) -> None:
    _write(sandbox, "BREADTH_MANDATE", {"ratchet": {"n_eff": 3.967}})
    row = sc._r01_effective_breadth()
    assert row["current"] == 3.967 and row["verdict"] == sc.BELOW
    assert "ratchet.n_eff" in row["basis"]


def test_row02_counts_only_cells_declaring_BOTH_axes(sandbox: Path) -> None:
    _write(sandbox, "TIMEFRAME_COVERAGE", {"coverage": {"by_timeframe": {"H1": 5, "M30": 0}}})
    _write(sandbox, "SLEEVES", {"sleeves": [
        {"name": "a", "certificate": "forward_clock", "timeframe": "M5", "session": "overlap"},
        {"name": "b", "certificate": "forward_clock", "timeframe": "", "session": ""},
        {"name": "c", "timeframe": "H4", "session": "asia"}]})       # no certificate -> not a cell
    _write(sandbox, "UNIVERSAL_SURVIVORS", {"survivors": {
        "k1": {"shadow_spec": {"symbol": "EURUSD", "selector": "asia",
                               "params": {"timeframe": "H1"}}},
        "k2": {"shadow_spec": {"symbol": "USDJPY", "selector": "asia"}}}})
    row = sc._r02_certified_chart_session_axes()
    assert row["current"] == 2.0, "(M5, overlap) and (H1, asia); the axis-less rows are not guessed"
    assert "cells_without_both_axes=2" in row["basis"] and "charts_hunted=1" in row["basis"]
    assert row["verdict"] == sc.BELOW


def test_row03_prefers_the_breadth_mandate_then_the_breadth_report(sandbox: Path) -> None:
    _write(sandbox, "EFFECTIVE_BREADTH", {"clusters": {"occupied_traded": ["a", "b"],
                                                       "occupied_certified": ["b", "c"],
                                                       "declared": 15}})
    assert sc._r03_mechanism_clusters()["current"] == 3.0, "the union, not the sum"
    _write(sandbox, "BREADTH_MANDATE", {"occupied": ["a"] * 10, "declared_clusters": 15})
    row = sc._r03_mechanism_clusters()
    assert row["current"] == 10.0 and row["verdict"] == sc.AT
    assert "BREADTH_MANDATE.json occupied" in row["basis"]


def test_row04_classifies_survivor_symbols_through_universe_policy(
        sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(universe_policy, "asset_class_of",
                        lambda s: {"EURUSD": "forex", "XAUUSD": "metals"}.get(s, ""))
    _write(sandbox, "UNIVERSAL_SURVIVORS", {"swept_at": "2026-09-16T15:00:00+00:00", "survivors": {
        "a": {"shadow_spec": {"symbol": "EURUSD"}},
        "b": {"shadow_spec": {"symbol": "XAUUSD"}},
        "c": {"sym": "NOTREAL"}}})
    row = sc._r04_asset_classes()
    assert row["current"] == 2.0, "an unclassified symbol is counted as unclassified, not a class"
    assert "unclassified=1" in row["basis"] and row["verdict"] == sc.BELOW


def test_row05_takes_the_MINIMUM_of_the_measured_pit_readings(sandbox: Path) -> None:
    _write(sandbox, "PIT_CENSUS", {"at": "2026-09-16T19:00:00+00:00", "canaries": {"green": True},
                                   "census": {"sidecars": 4, "stamped": 3}})
    _write(sandbox, "LAKE_PROMOTION", {"silver_share": 0.0})
    row = sc._r05_pit_compliance()
    assert row["current"] == 0.0, "a lake that stamps nothing is not 75% point-in-time clean"
    assert "binding=lake silver_share" in row["basis"] and "canaries.green=True" in row["basis"]
    assert row["verdict"] == sc.BELOW


def test_row06_attributes_live_deals_to_sleeves_or_certificates(sandbox: Path) -> None:
    _write(sandbox, "SLEEVES", {"sleeves": [{"name": "gold_asia"}]})
    _write(sandbox, "UNIVERSAL_SURVIVORS", {"survivors": {"external.XAUUSD.srb": {}}})
    _lines(sandbox, "LIVE_LEDGER", [
        {"sleeve": "gold_asia", "time": "2026-09-16T09:00:00+00:00"},
        {"sleeve": "external.XAUUSD.srb", "time": "2026-09-16T09:10:00+00:00"},
        {"sleeve": "[sl 4278.35]", "time": "2026-09-16T09:20:00+00:00"},
        {"sleeve": "", "time": "2026-09-16T09:30:00+00:00"}])
    row = sc._r06_live_attribution()
    assert row["current"] == 50.0 and row["verdict"] == sc.BELOW
    assert "2/4" in row["basis"] and row["measured_at"] == "2026-09-16T09:30:00+00:00"


def test_row06_an_empty_ledger_is_UNMEASURED_and_never_one_hundred(sandbox: Path) -> None:
    Path(sc.LIVE_LEDGER).write_text("", encoding="utf-8")
    row = sc._r06_live_attribution()
    assert row["verdict"] == sc.UNMEASURED and row["current"] is None
    assert "no deals to attribute" in row["basis"]


def test_row07_sums_failing_organs_and_failed_or_timed_out_legs(sandbox: Path) -> None:
    _write(sandbox, "PROCESS_HEALTH", {"at": "2026-09-12T07:15:01+00:00",
                                       "counts": {"FAILING": 7, "NOT_SCHEDULED": 1, "OK": 15}})
    _write(sandbox, "SYNC_MARKER", {"last_cycle": "2026-09-16T13:53:37+00:00",
                                    "daily": {"status": "TIMEOUT"},
                                    "search": {"status": "LEG_FAILED"},
                                    "tape": {"exit_code": 0}})
    row = sc._r07_silent_failures()
    assert row["current"] == 10.0 and row["verdict"] == sc.BELOW
    assert row["lower_is_better"] is True and "legs=2" in row["basis"]


def test_row08_joins_certificates_to_forward_clocks_on_symbol_and_selector(sandbox: Path) -> None:
    _write(sandbox, "UNIVERSAL_SURVIVORS", {"survivors": {
        "a": {"shadow_spec": {"symbol": "XAUUSD", "selector": "asia"}},
        "b": {"shadow_spec": {"symbol": "EURNZD", "selector": "london_am"}}}})
    _write(sandbox, "SHADOW_STATE", {"XAUUSD.asia.MACRO_FAV": {"n": 14, "exp_r": 0.1},
                                     "updated_at": "2026-09-16T17:00:00+00:00"})
    row = sc._r08_forward_lineage()
    assert row["current"] == 50.0 and "1/2" in row["basis"] and row["verdict"] == sc.BELOW


def test_row09_cost_maturity_climbs_only_as_dimensions_appear(sandbox: Path) -> None:
    _write(sandbox, "COST_SURFACE", {"symbols": {"EURUSD": {"hours": {"7": {"p50": 1.0}}}}})
    assert sc._r09_cost_model()["current"] == 1.0
    _write(sandbox, "COST_SURFACE", {"symbols": {"EURUSD": {"hours": {"7": {}},
                                                            "by_regime": {"bull": 1}}}})
    assert sc._r09_cost_model()["current"] == 2.0
    _write(sandbox, "COST_SURFACE", {"symbols": {"EURUSD": {"hours": {"7": {}},
                                                            "by_regime": {}, "by_sleeve": {}}}})
    row = sc._r09_cost_model()
    assert row["current"] == 3.0 and row["verdict"] == sc.ABOVE


def test_row10_counts_the_edge_fields_the_causal_graph_actually_carries(sandbox: Path) -> None:
    _write(sandbox, "WORLD_CAUSAL_GRAPH", {
        "generated_at": "2026-09-16T12:32:52+00:00", "edges_admitted": 0, "chains_seeded": 14,
        "conditioning": {"US500": ["VIX"]},
        "recorded_not_admitted": [{"src": "US500", "dst": "USDKRW", "lag": 5, "stability": 1.0,
                                   "state_dependence": 0.046, "conditional": None}]})
    row = sc._r10_cross_asset()
    assert row["current"] == 3.0 and row["verdict"] == sc.ABOVE
    assert "edges_admitted=0" in row["basis"], "the reader must see that nothing was admitted"
    _write(sandbox, "WORLD_CAUSAL_GRAPH", {"recorded_not_admitted": [{"src": "a", "dst": "b"}]})
    assert sc._r10_cross_asset()["current"] == 1.0


def test_row10_falls_back_to_the_counts_only_cross_asset_graph(sandbox: Path) -> None:
    _write(sandbox, "CROSS_ASSET_GRAPH", {"generated_at": "2026-09-08T18:02:32+00:00", "edges": 26})
    row = sc._r10_cross_asset()
    assert row["current"] == 1.0 and "counts only, no edge list" in row["basis"]


def test_row11_macro_needs_per_country_blocks_and_sensitivities_to_climb(sandbox: Path) -> None:
    _write(sandbox, "MACRO_STATE", {"updated": "2026-09-10T22:55:59+00:00",
                                    "series": {"INDPRO": {}, "CPIAUCSL": {}},
                                    "differentials": {"US10Y": 4.8}})
    assert sc._r11_macro()["current"] == 1.0, "one country's differentials is not a country block"
    _write(sandbox, "MACRO_STATE", {"series": {"INDPRO": {}},
                                    "differentials": {"US10Y": 4.8, "DE10Y": 2.1}})
    assert sc._r11_macro()["current"] == 2.0
    _write(sandbox, "STATE_VECTOR", {"factors": {"carry": 0.2}})
    row = sc._r11_macro()
    assert row["current"] == 3.0 and "sensitivities=True" in row["basis"]


def test_row12_allocator_needs_a_pass_hysteresis_and_a_posterior(sandbox: Path) -> None:
    _write(sandbox, "PF_ALLOCATION", {"proof": {"passed": True, "why": "dynamic beat the bench"}})
    assert sc._r12_allocator()["current"] == 1.0, "a pass with no hysteresis is authority once"
    _write(sandbox, "PF_ALLOCATION", {"generated_utc": "2026-09-16T16:35:34+00:00",
                                      "proof": {"passed": True,
                                                "why": "holds authority: keeps it while > 0.017"}})
    assert sc._r12_allocator()["current"] == 2.0
    _write(sandbox, "ALLOCATOR_PROOF", {"passed": True, "hysteresis": {"holding_global": True},
                                        "scores": {"posterior": 0.034, "equal_weight": 0.011}})
    row = sc._r12_allocator()
    assert row["current"] == 3.0 and "ALLOCATOR_PROOF.json" in row["basis"]


def test_row13_counts_dated_tape_files_and_never_reads_moat_counts_as_days(sandbox: Path) -> None:
    root = Path(sc.TAPE_TICKS)
    for symbol in ("XAUUSD", "EURUSD"):
        (root / symbol).mkdir(parents=True)
        for stem in ("2026-09-14", "2026-09-15", "20260915", "latest"):
            (root / symbol / f"{stem}.parquet").write_bytes(b"")
    _write(sandbox, "MOAT_COVERAGE", {"built_at": "2026-09-16T16:35:25+00:00", "window_days": 7,
                                      "coverage": {"XAUUSD": 16},
                                      "newest_tape_write": "2026-09-16"})
    row = sc._r13_moat_days()
    assert row["current"] == 2.0, "16 files in a 7-day window is not 16 days; two dates is two days"
    assert row["verdict"] == sc.BELOW and "newest_tape_write=2026-09-16" in row["basis"]


def test_row14_backlog_is_waiting_plus_lost_and_lower_is_better(sandbox: Path) -> None:
    _write(sandbox, "ROW_CONVERSION", {"summary": {"backlog": 50208, "backlog_share": 0.33}})
    assert sc._r14_conversion_backlog()["current"] == 50208.0
    _write(sandbox, "CANDIDATE_CONSERVATION", {"at": "2026-09-16T18:57:43+00:00",
                                               "n_waiting": 5, "n_lost": 2})
    row = sc._r14_conversion_backlog()
    assert row["current"] == 7.0 and row["verdict"] == sc.BELOW and row["lower_is_better"] is True
    _write(sandbox, "CANDIDATE_CONSERVATION", {"n_waiting": 0, "n_lost": 0})
    assert sc._r14_conversion_backlog()["verdict"] == sc.AT


# ---------------------------------------------------------------------------- verdicts and board
@pytest.mark.parametrize(("current", "target", "lower", "expected"), [
    (16.0, 15.0, False, sc.ABOVE), (15.0, 15.0, False, sc.AT), (14.0, 15.0, False, sc.BELOW),
    (0.0, 0.0, True, sc.AT), (3.0, 0.0, True, sc.BELOW), (1.0, 5.0, True, sc.ABOVE),
    (None, 15.0, False, sc.UNMEASURED), (15.0, None, False, sc.UNMEASURED),
])
def test_verdict_logic(current: float | None, target: float | None, lower: bool,
                       expected: str) -> None:
    assert sc._verdict(current, target, lower) == expected


def test_overall_counts_and_names_the_three_weakest_MEASURED_rows() -> None:
    rows = [sc._mk("effective_breadth_n_eff", 1.0, "x"),          # gap 0.93
            sc._mk("pit_compliance_pct", 0.0, "x"),               # gap 1.00
            sc._mk("live_trade_attribution_pct", 4.64, "x"),      # gap 0.95
            sc._mk("allocator_maturity", 3.0, "x"),               # ABOVE
            sc._mk("macro_intelligence", 2.0, "x"),               # AT
            sc._mk("cost_model_maturity", None, "x")]             # UNMEASURED
    overall = sc._overall(rows)
    assert (overall["at_or_above"], overall["below"], overall["unmeasured"]) == (2, 3, 1)
    assert overall["weakest_measured"] == ["pit_compliance_pct", "live_trade_attribution_pct",
                                           "effective_breadth_n_eff"]
    assert "1 are UNMEASURED -- each of those names the artifact path" in overall["why"]
    assert "pit_compliance_pct at 0.0 pct against a first target of 100.0" in overall["why"]
    assert overall["why"].count(";") == 2, "the paragraph names exactly the three weakest"


def test_the_printed_board_is_exactly_sixteen_lines(sandbox: Path) -> None:
    lines = sc.render(sc.build())
    assert len(lines) == 16, "a header, the fourteen rows, and the overall count"
    assert lines[0].startswith("dimension") and lines[-1].startswith("AT/ABOVE")
    assert max(len(line) for line in lines) <= 100


def test_write_is_atomic_and_leaves_no_temporary_behind(sandbox: Path) -> None:
    doc = sc.build()
    assert sc.write(doc) is True
    out = Path(sc.OUT)
    assert json.loads(out.read_text(encoding="utf-8"))["n_rows"] == 14
    assert not list(out.parent.glob(f"{out.name}.tmp*")), "a half-written board must never survive"


def test_dry_run_prints_the_board_and_writes_nothing(sandbox: Path,
                                                    capsys: pytest.CaptureFixture[str]) -> None:
    assert sc.main(["--dry-run"]) == 0
    assert not Path(sc.OUT).exists()
    assert len(capsys.readouterr().out.strip().splitlines()) == 16


def test_main_writes_the_artifact_when_not_dry_run(sandbox: Path,
                                                   capsys: pytest.CaptureFixture[str]) -> None:
    assert sc.main([]) == 0
    capsys.readouterr()
    doc = json.loads(Path(sc.OUT).read_text(encoding="utf-8"))
    assert [r["dimension"] for r in doc["rows"]] == list(sc.SPEC)
    assert doc["authority"].startswith("MEASUREMENT ONLY")


def test_a_row_builder_that_raises_becomes_UNMEASURED_not_a_crashed_cycle(
        monkeypatch: pytest.MonkeyPatch, sandbox: Path) -> None:
    def _boom() -> dict:
        raise RuntimeError("something nobody predicted")

    monkeypatch.setattr(sc, "BUILDERS", (_boom, sc._r01_effective_breadth))
    doc = sc.build()
    assert doc["rows"][0]["verdict"] == sc.UNMEASURED
    assert "RuntimeError: something nobody predicted" in doc["rows"][0]["basis"]
