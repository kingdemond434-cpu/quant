"""The cell-conversion audit: every derived source gets a verdict, absence reads UNMEASURED, an
output no converter takes reads NOT_WIRED, the converter charges tests_run per trial_family
through the real donation door, and the two-lane rule holds at that door.

The converter tests run the real `proposer_common.donate` into a tmp intelligence root and read
the charge back with the real `experiment_ledger._proposer_counts`; pre-registration and the
registry write are stubbed so nothing here touches the desk's own ledgers.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research.cell_conversion_audit as A  # noqa: E402
import research.issue_board as IB  # noqa: E402
import research.proposer_common as PC  # noqa: E402
import research.universe_policy as UP  # noqa: E402

NOW = datetime(2026, 11, 11, 14, 0, tzinfo=UTC)


# ------------------------------------------------------------------ derivation and verdicts
@pytest.fixture(scope="module")
def audit() -> dict[str, Any]:
    """One measure-only pass over this tree (nothing donated, nothing written)."""
    return A.build(now=datetime.now(UTC), do_convert=False, budget_s=120)


def test_every_derived_source_gets_a_verdict(audit: dict[str, Any]) -> None:
    assert audit["sources"], "the audit derived no source at all"
    for s in audit["sources"]:
        assert s["verdict"] in A.VERDICTS, s
        if s["verdict"] in (A.NOT_WIRED, A.PARTIAL):
            assert s["loss_stage"], f"{s['source']} is {s['verdict']} with no named loss stage"
    classes = {s["class"] for s in audit["sources"]}
    assert {"leg", "seat", "handoff", "idea_queue", "data"} <= classes
    for key in ("parked", "converted", "still_parked", "oldest_parked_age_h", "stages",
                "converted_ideas", "issues", "totals"):
        assert key in audit
    assert audit["parked"] == audit["converted"] + audit["still_parked"]


def test_every_not_wired_or_partial_source_has_an_issue_row(audit: dict[str, Any]) -> None:
    keys = {i["key"] for i in audit["issues"]}
    for s in audit["sources"]:
        if s["verdict"] in (A.NOT_WIRED, A.PARTIAL):
            assert f"cell_conversion:{s['source']}" in keys


def test_new_idea_emitting_leg_is_covered(audit: dict[str, Any]) -> None:
    """THE META-TEST. Every hourly leg whose code holds a door into the gauntlet's intake, or
    declares an idea-shaped output, must be an audited source. A leg added tomorrow that donates
    and is not covered fails here -- the classifier, not a list, decides coverage."""
    audited = {s["source"] for s in audit["sources"]}
    missing = []
    for leg, code in A.hourly_legs().items():
        if code is None or code.stem in A.DOOR_MODULES:
            continue
        text = code.read_text("utf-8", errors="replace")
        if "donate(" in text or "enqueue_candidate(" in text:
            assert A.classify(text, code.stem)["emitter"], f"{leg}: donor not classified"
        if A.classify(text, code.stem)["emitter"] and f"leg:{leg}" not in audited:
            missing.append(leg)
    assert not missing, f"idea-emitting legs the audit does not cover: {missing}"


def test_the_audit_is_itself_an_hourly_leg_with_a_department_and_layer() -> None:
    import research.hourly_cycle as HC

    from libs.research.layers import LEG_LAYER
    assert "cell_conversion_audit" in A.hourly_legs()
    assert HC.LEG_DEPARTMENT.get("cell_conversion_audit") == "discovery"
    assert "cell_conversion_audit" in HC.LEG_BUDGET_SEC
    assert LEG_LAYER.get("cell_conversion_audit")


def test_absent_artifacts_read_unmeasured(tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    row = A.seat_measure("deepseek", None, [], NOW)
    assert row["verdict"] == A.UNMEASURED and row["emitted"] == A.UNMEASURED
    assert A.handoff_stock(tmp_path / "nope.json")["status"] == A.UNMEASURED
    for name in ("MINER_CANDIDATES", "MERGE_REPORT", "JUDGE_COVERAGE", "JUDGING_RATE"):
        monkeypatch.setattr(A, name, tmp_path / f"{name}.json")
    stages = A.stage_flow(NOW, None)
    assert stages and all(s["state"] == A.UNMEASURED and s["count"] == A.UNMEASURED
                          for s in stages)
    v, _ = A.docket_measure("x.json", None)
    assert v == A.UNMEASURED
    v, _ = A.producer_measure("x", None)
    assert v == A.UNMEASURED


def test_a_seat_with_zero_rows_is_not_a_clean_verdict() -> None:
    row = A.seat_measure("kimi", {"kimi": {"rows": 0, "candidates": 0, "deepening": 0}}, [],
                         NOW, NOW)
    assert row["verdict"] == A.UNMEASURED and row["emitted"] == 0


def test_partial_seat_names_the_loss_stage() -> None:
    st = {"rows": 10, "candidates": 12, "deepening": 4, "converted_rows": 5,
          "valid_refusals": 1, "invalid_cells": 0}
    row = A.seat_measure("world", {"world": st}, [], NOW, NOW)
    assert row["verdict"] == A.PARTIAL
    assert row["share_converted"] == round(5 / 9, 6)
    assert "deepening" in row["loss_stage"]


def test_output_that_reaches_no_converter_is_not_wired(tmp_path: Path) -> None:
    code = tmp_path / "idea_maker.py"
    code.write_text('OUT = HYP / "fresh_ideas.json"\n'
                    'def main():\n    OUT.write_text("[]")\n', "utf-8")
    info = A.classify(code.read_text("utf-8"), code.stem)
    assert info["emitter"] and info["doors"] == [] and info["outputs"] == ["fresh_ideas.json"]
    row = A.emitter_row("leg:idea_maker", "leg", code, info, per_source={}, merge=None,
                        breadth=None, docket_names=["miner_candidates.json"], corpus={},
                        now=NOW)
    assert row["verdict"] == A.NOT_WIRED and row["loss_stage"] == "no converter"
    # the same output read by a module that holds a door is wired
    corpus = {"desks/mt5/research/reader.py": 'X = "fresh_ideas.json"\ndonate("s", [], 1)\n'}
    row = A.emitter_row("leg:idea_maker", "leg", code, info, per_source={}, merge=None,
                        breadth=None, docket_names=[], corpus=corpus, now=NOW)
    assert row["verdict"] == A.UNMEASURED and row["readers"]
    # a report-shaped output (ALL-CAPS) is not an idea intake
    assert A.declared_outputs('OUT = R / "CANDIDATE_CONSERVATION.json"\n') == []


def test_unread_artifact_is_not_wired_and_docket_sources_are_measured(tmp_path: Path) -> None:
    p = tmp_path / "orphan_candidates.json"
    p.write_text("[]", "utf-8")
    row = A.artifact_row(p, ["miner_candidates.json"], None, {}, NOW)
    assert row["verdict"] == A.NOT_WIRED
    merge = {"per_source": {"miner_candidates.json": 7}, "source_state":
             {"miner_candidates.json": "FRESH"}, "merged_at": "x"}
    v, kw = A.docket_measure("miner_candidates.json", merge)
    assert v == A.CONVERTING and kw["converted"] == 7


def test_merge_sources_are_derived_from_the_docket_door() -> None:
    names = A.merge_sources()
    assert "miner_candidates.json" in names and "deepened_candidates.json" in names


def test_data_source_with_no_consuming_family_is_not_wired() -> None:
    ds = {"id": "axis:obscure", "tokens": ["zz_obscure_series_qq"], "kind": "axis"}
    assert A.data_row(ds, "def family_x(): pass", None)["verdict"] == A.NOT_WIRED
    ds2 = {"id": "axis:cot", "tokens": ["cot"], "kind": "axis"}
    assert A.data_row(ds2, "x = cot_positioning(df)", None)["verdict"] == A.CONVERTING
    lake = {"id": "lake:abc", "tokens": ["abc"], "kind": "lake", "path": Path("abc.parquet")}
    assert A.data_row(lake, "", None)["verdict"] == A.UNMEASURED
    assert A.data_row(lake, "", {"packs": ["zzz"]})["verdict"] == A.NOT_WIRED
    assert A.data_row(lake, "", {"packs": ["abc"]})["verdict"] == A.CONVERTING


def test_a_stage_that_stops_moving_reads_stalled(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    mc = tmp_path / "mc.json"
    mc.write_text(json.dumps({"hypotheses": [], "rows_accounted": 100,
                              "executable_candidates": 50}), "utf-8")
    for name in ("MERGE_REPORT", "JUDGE_COVERAGE", "JUDGING_RATE"):
        monkeypatch.setattr(A, name, tmp_path / f"{name}.json")
    monkeypatch.setattr(A, "MINER_CANDIDATES", mc)
    first = A.stage_flow(NOW, None)
    assert first[0]["state"] == "FIRST_READING"
    again = A.stage_flow(NOW, {"stages": first})
    assert again[1]["state"] == "STALLED"
    issues = A.issues_for([], again)
    assert any(i["key"] == "cell_conversion:stage:compiled_cells" for i in issues)


# ------------------------------------------------------------------ the idea queue
def test_idea_queue_rows_parse_and_closed_rows_are_not_open(tmp_path: Path) -> None:
    q = tmp_path / "IDEA_QUEUE.md"
    q.write_text("# IDEA_QUEUE\n| rank | date | owner | item | evidence | score | status |\n"
                 "|---|---|---|---|---|---|---|\n"
                 "| 1 | 2026-10-01 | x | session breakout on eurusd | e | H | queued |\n"
                 "| 2 | 2026-10-02 | x | thing | e | M | DONE 10-05 |\n", "utf-8")
    rows = A.idea_rows(q)
    assert [r["idea_id"] for r in rows] == ["IQ-1", "IQ-2"]
    assert rows[0]["open"] and not rows[1]["open"]


# ------------------------------------------------------------------ the converter
@pytest.fixture()
def door(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The real donate, aimed at a tmp intelligence root, with its two side ledgers stubbed."""
    intel = tmp_path / "desk" / "data" / "intelligence"
    intel.mkdir(parents=True)
    monkeypatch.setattr(PC, "INTEL", intel)
    monkeypatch.setattr(PC, "_record_in_registry", lambda source, cands: None)
    monkeypatch.setattr(PC, "_preregister", lambda source, cands: {
        "preregistered": 0, "failed": 0, "already": 0, "reasons": {}, "failures": []})
    monkeypatch.setattr(A, "LEDGER", tmp_path / "ledger.jsonl")
    import research.miner_candidate_compiler as MCC
    # the compiler expands each donated cell to two (chart x session stand-in): the charge must
    # be the expanded count, never the pre-expansion one
    monkeypatch.setattr(MCC, "expand_axes", lambda cells: [c for c in cells for _ in (0, 1)])
    monkeypatch.setattr(A, "lane_ok", lambda sym, fam: (True, ""))
    return intel


def _cand(sym: str, fam: str, k: int) -> dict[str, Any]:
    return {"symbol": sym, "family": fam, "params": {"k": k}, "origin": f"IQ-{k}",
            "origin_class": "idea_queue", "title": "t", "mechanism": "a named mechanism"}


def test_converter_charges_tests_run_per_family(door: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    cands = [_cand("EURUSD", "session_range_breakout", 1),
             _cand("GBPUSD", "session_range_breakout", 2),
             _cand("XAUUSD", "overnight_gap_decay", 3)]
    rep = A.convert(cands, NOW)
    assert rep["donated"] == 3
    assert rep["tests_run_by_family"] == {"session_range_breakout": 4, "overnight_gap_decay": 2}
    files = sorted((door / A.SEAT).glob("discoveries_*.json"))
    assert len(files) == 2, "one donation file per trial_family"
    for f in files:
        doc = json.loads(f.read_text("utf-8"))
        fams = {r["family"] for r in doc["discoveries"]}
        assert len(fams) == 1 and doc["tests_run"] == rep["tests_run_by_family"][fams.pop()]
    import libs.research.experiment_ledger as EL
    monkeypatch.setattr(EL, "DESK", door.parents[1])
    total, by_fam = EL._proposer_counts()
    assert by_fam.get("session_range_breakout") == 4 and by_fam.get("overnight_gap_decay") == 2
    assert total >= 6
    # a converted cell is never donated, or charged, twice
    again = A.convert(cands, NOW + timedelta(hours=1))
    assert again["donated"] == 0 and again["already_converted"] == 3
    assert again["tests_run_total"] == 0
    assert len(list((door / A.SEAT).glob("discoveries_*.json"))) == 2


def test_converter_bounds_defer_rather_than_drop(door: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(A, "MAX_CELLS_PER_FAMILY_PER_PASS", 2)
    rep = A.convert([_cand("EURUSD", "trend_ma_cross", k) for k in range(5)], NOW,
                    dry_run=True)
    assert rep["donated"] == 2 and rep["deferred_over_bound"] == 3


def test_share_cfd_lane_is_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    lanes = {"AAPL": UP.EVENT, "EURUSD": UP.HYPOTHESIS, "MYSTERY": UP.UNCLASSIFIED}
    monkeypatch.setattr(UP, "lane", lambda s: lanes.get(s, UP.UNCLASSIFIED))
    monkeypatch.setattr(UP, "is_equity", lambda s: s == "AAPL")
    xs = sorted(UP.CROSS_SECTIONAL_FAMILIES)[0]
    assert A.lane_ok("EURUSD", "session_range_breakout")[0]
    assert A.lane_ok("AAPL", xs)[0]
    ok, why = A.lane_ok("AAPL", "session_range_breakout")
    assert not ok and "CROSS_SECTIONAL" in why
    # the news-lane families are not a door for THIS converter: class books only
    ok, _ = A.lane_ok("AAPL", sorted(UP.NEWS_LANE_FAMILIES)[0])
    assert not ok
    assert not A.lane_ok("MYSTERY", "session_range_breakout")[0]


def test_lane_refusals_are_counted_and_never_donated(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(A, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(UP, "lane", lambda s: UP.EVENT if s == "AAPL" else UP.HYPOTHESIS)
    monkeypatch.setattr(UP, "is_equity", lambda s: s == "AAPL")
    rep = A.convert([_cand("AAPL", "session_range_breakout", 1),
                     _cand("EURUSD", "session_range_breakout", 2)], NOW, dry_run=True)
    assert rep["donated"] == 1 and sum(rep["lane_refused"].values()) == 1


# ------------------------------------------------------------------ the board
def test_issue_board_collects_the_audit_issues(tmp_path: Path) -> None:
    rep = tmp_path / A.OUT.relative_to(ROOT)
    rep.parent.mkdir(parents=True)
    rows = A.issues_for([A._row("leg:x", "leg", A.NOT_WIRED, loss_stage="no converter",
                                why="w")], [])
    rep.write_text(json.dumps({"issues": rows}), "utf-8")
    got = IB.cell_conversion_issues(tmp_path)
    assert [i.key for i in got] == ["cell_conversion:leg:x"]
    assert any(c[0] == "cell_conversion_audit" for c in IB.CADENCE)
