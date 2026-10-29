"""Pre-registration joins verdicts, or says POST_HOC by name. Every write here goes to tmp_path.

Measured 2026-09-30 (`reports/six_event_trace.md`, event 2): 3,948 cards and 108,189 graph rows,
and not one row carried a card's hash. Three faults, pinned separately so none returns alone:

  1. NO WRITER -- `record_verdicts` had no production caller; the graph's last fate was a
     hand-run backfill on 2026-09-03. `record_gauntlet_verdicts` is the writer now.
  2. NO CARRIER -- cards were written per donated row, which is not the cell the judge builds.
     `register_docket` cards the EXECUTABLE cell, on the docket, before the judge reads it.
  3. NO KEY -- a card named no cell. `spec_id` is the graph's own node id of the spec.

And the rule that outlives them: a verdict with no earlier card is recorded POST_HOC with
`prereg_hash: null` -- never dropped, never silently treated as pre-registered, never backfilled.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research import hypothesis_graph as hg  # noqa: E402
from libs.research import prereg_join as pj  # noqa: E402
from libs.research import preregistration as pr  # noqa: E402

T0, T1, T2 = ("2026-10-01T00:00:00+00:00", "2026-10-01T01:00:00+00:00",
              "2026-10-01T02:00:00+00:00")


def _row(sym: str = "EURUSD", fam: str = "carry", **params: Any) -> dict[str, Any]:
    return {"symbol": sym, "family": fam, "params": dict(params) or {"k": 1}}


def _spec(row: dict[str, Any]) -> dict[str, Any]:
    spec = pr.judged_spec(row)
    assert spec is not None
    return spec


@pytest.fixture
def ledger(tmp_path: Path) -> Path:
    return tmp_path / "preregistrations.jsonl"


@pytest.fixture
def graph(tmp_path: Path) -> hg.Graph:
    return hg.Graph(tmp_path / "hypothesis_graph.jsonl")


# ---------------------------------------------------------------- 1. cards before judgement
def test_the_docket_is_carded_before_judgement_in_one_verifiable_batch(ledger: Path) -> None:
    rows = [_row(k=1), _row(k=2), _row(k=1)]            # a duplicate spec shares one card
    out = pr.register_docket(rows, path=ledger)
    assert out["new_specs"] == 2 and out["rows"] == 3
    cards = [json.loads(ln) for ln in ledger.read_text("utf-8").splitlines()]
    assert len(cards) == 1 and cards[0]["kind"] == pr.BATCH_KIND
    card = cards[0]
    # the hash is the content's: spec commitments plus the judge's pinned test plan
    assert pr.row_hash(card) == card["prereg_hash"] == out["batch_hash"]
    assert card["test_plan"]["sha"] not in ("", "UNREADABLE")
    assert set(card["specs"]) == {hg.node_id_for_spec(_spec(r)) for r in rows}
    for r in rows:
        assert r["prereg_status"] == pr.PREREGISTERED and r["prereg_hash"] == card["prereg_hash"]
        assert r["spec_id"] == hg.node_id_for_spec(_spec(r))
    # `check` verifies a batch card by its own recipe -- a tampered spec list is a mismatch
    assert pr.check([{"prereg_hash": card["prereg_hash"]}], path=ledger)["ok"]


def test_a_carded_spec_reuses_its_card_and_writes_nothing_new(ledger: Path) -> None:
    first = pr.register_docket([_row(k=1)], path=ledger)
    again = [_row(k=1)]
    out = pr.register_docket(again, path=ledger)
    assert out["already"] == 1 and out["new_specs"] == 0 and out["batch_hash"] is None
    assert again[0]["prereg_hash"] == first["batch_hash"]
    assert len(ledger.read_text("utf-8").splitlines()) == 1


def test_a_cell_judged_before_any_card_is_never_carded_afterwards(ledger: Path) -> None:
    """A card written after the evidence would make the NEXT re-judgement read as
    pre-registered -- the exact forgery. The row says RETROSPECTIVELY_UNPREREGISTERED."""
    row = _row(k=9)
    out = pr.register_docket([row], judged={hg.node_id_for_spec(_spec(row))}, path=ledger)
    assert out["retrospective"] == 1 and out["new_specs"] == 0
    assert row["prereg_status"] == pr.RETROSPECTIVELY_UNPREREGISTERED
    assert row["prereg_hash"] is None and not ledger.exists()


def test_the_card_names_the_cell_the_judge_builds_including_a_row_level_chart() -> None:
    """`external_gauntlet.main` folds a non-H1 row `timeframe` into params. A card keyed any
    other way names a cell the judge never builds."""
    row = {"symbol": "XAUUSD", "family": "carry", "params": {"k": 1}, "timeframe": "m15"}
    assert _spec(row)["params"] == {"k": 1, "timeframe": "M15"}
    h1 = {"symbol": "XAUUSD", "family": "carry", "params": {"k": 1}, "timeframe": "H1"}
    assert _spec(h1)["params"] == {"k": 1}
    assert pr.judged_spec({"family": "carry"}) is None


def test_a_donated_candidate_card_carries_its_spec_and_keeps_its_old_hash(ledger: Path) -> None:
    c = {"title": "t", "mechanism": "m", "family": "carry", "symbol": "EURUSD",
         "params": {"hold_bars": 8}, "evidence": {"screen": "s"}}
    h, why = pr.register_candidate(c, source="t", path=ledger)
    assert why is None and h == pr.card_hash(pr.from_candidate(c))    # hash unchanged
    card = json.loads(ledger.read_text("utf-8"))
    assert card["spec_id"] == hg.node_id_for_spec(c)
    assert pr.spec_index(ledger)[card["spec_id"]][1] == h


# ------------------------------------------------------------- 2. verdicts reach the graph
def _verdict(row: dict[str, Any], passed: bool | None, **extra: Any) -> dict[str, Any]:
    spec = _spec(row)
    return {"cell": f"{spec['sym']}.{spec['family']}.{json.dumps(spec['params'])}",
            "sym": spec["sym"], "family": spec["family"], "passed": passed,
            "terminal_gate": extra.pop("terminal_gate", "deflated_sharpe"),
            "stages": extra.pop("stages", {"deflated_sharpe": {"passed": passed}}), **extra}


def _record(verdicts: list[dict[str, Any]], rows: list[dict[str, Any]], graph: hg.Graph,
            ledger: Path, at: str) -> dict[str, Any]:
    specs = {v["cell"]: _spec(r) for v, r in zip(verdicts, rows, strict=True)}
    return hg.record_gauntlet_verdicts(verdicts, specs, graph=graph, prereg_path=ledger, at=at)


def test_every_verdict_is_stamped_and_recorded_pass_reject_and_unknown(
        graph: hg.Graph, ledger: Path) -> None:
    rows = [_row(k=1), _row(k=2), _row(k=3)]
    pr.register_docket(rows, path=ledger, now=_dt(T0))
    vs = [_verdict(rows[0], True), _verdict(rows[1], False),
          _verdict(rows[2], None, terminal_gate="UNKNOWN")]
    out = _record(vs, rows, graph, ledger, T1)
    assert out["recorded"] == 3 and out[pr.PREREGISTERED] == 3 and out["join_rate"] == 1.0
    cur = graph.current()
    fates = {}
    for v in vs:
        node = cur[v["spec_id"]]
        assert node["prereg_status"] == pr.PREREGISTERED
        assert node["prereg_hash"] == rows[0]["prereg_hash"] == v["prereg_hash"]
        fates[v["passed"]] = node["fate"]
    assert fates == {True: hg.CERTIFIED, False: hg.FAILED, None: hg.JUDGED}


def test_a_verdict_with_no_card_is_post_hoc_with_a_null_hash_and_still_recorded(
        graph: hg.Graph, ledger: Path) -> None:
    row = _row(k=5)
    v = _verdict(row, False)
    out = _record([v], [row], graph, ledger, T1)
    assert out["recorded"] == 1 and out[pr.POST_HOC] == 1 and out["join_rate"] == 0.0
    node = graph.current()[v["spec_id"]]
    assert node["fate"] == hg.FAILED and node["prereg_status"] == pr.POST_HOC
    assert "prereg_hash" in node and node["prereg_hash"] is None      # present, and null
    assert v["prereg_hash"] is None and v["prereg_status"] == pr.POST_HOC


def test_a_card_written_after_the_first_judgement_never_makes_a_rejudgement_preregistered(
        graph: hg.Graph, ledger: Path) -> None:
    row = _row(k=7)
    _record([_verdict(row, False)], [row], graph, ledger, T0)          # judged, no card
    pr.register_docket([row], path=ledger, now=_dt(T1))               # carded AFTER
    v = _verdict(row, True)
    _record([v], [row], graph, ledger, T2)                             # re-judged later
    assert v["prereg_status"] == pr.POST_HOC and v["prereg_hash"] is None


def test_a_hash_the_verdict_claims_is_not_trusted_without_an_earlier_card(
        graph: hg.Graph, ledger: Path) -> None:
    row = _row(k=8)
    v = _verdict(row, True, prereg_hash="deadbeefdeadbeef", prereg_status=pr.PREREGISTERED)
    _record([v], [row], graph, ledger, T1)
    assert v["prereg_status"] == pr.POST_HOC and v["prereg_hash"] is None


def test_deferred_cells_are_stamped_but_get_no_fate(graph: hg.Graph, ledger: Path) -> None:
    """`passed: None` with no stages is "work not yet done, never a verdict" in the judge's
    own words: stamped so the report row carries the join, but never a fate on the graph."""
    row = _row(k=4)
    v = _verdict(row, None, stages={}, downstream_status="NOT_RUN_BUILD_BUDGET_DEFERRED")
    out = _record([v], [row], graph, ledger, T1)
    assert out["not_a_verdict"] == 1 and out["recorded"] == 0 and out["join_rate"] is None
    assert v["prereg_status"] == pr.POST_HOC and not graph.rows()


def test_an_unchanged_verdict_is_not_restated(graph: hg.Graph, ledger: Path) -> None:
    row = _row(k=6)
    pr.register_docket([row], path=ledger, now=_dt(T0))
    assert _record([_verdict(row, False)], [row], graph, ledger, T1)["recorded"] == 1
    again = _record([_verdict(row, False)], [row], graph, ledger, T2)
    assert again["recorded"] == 0 and again["unchanged"] == 1
    assert len(graph.rows()) == 1


def test_a_verdict_that_names_no_params_is_counted_never_guessed(
        graph: hg.Graph, ledger: Path) -> None:
    v = {"cell": "X.carry.p=?", "sym": "X", "family": "carry", "passed": False,
         "stages": {"g": {"passed": False}}}
    out = hg.record_gauntlet_verdicts([v], {}, graph=graph, prereg_path=ledger, at=T1)
    assert out["no_spec"] == 1 and out[pr.POST_HOC] == 1 and not graph.rows()
    assert v["prereg_hash"] is None and v["spec_id"] is None


# ------------------------------------------------ the gate-ledger fallback, one graph writer
def test_the_gate_ledger_is_recorded_once_and_rows_the_judge_stamped_are_skipped(
        tmp_path: Path, graph: hg.Graph, ledger: Path) -> None:
    carded, bare, judged_in_process = _row(k=1), _row(k=2), _row(k=3)
    pr.register_docket([carded], path=ledger, now=_dt(T0))
    gl = tmp_path / "gate_verdict_ledger.jsonl"
    rows = [{"at": T1, "cell": "c1", "graph_id": hg.node_id_for_spec(_spec(carded)),
             "sym": "EURUSD", "family": "carry", "passed": False, "terminal_gate": "dsr"},
            {"at": T1, "cell": "c2", "graph_id": hg.node_id_for_spec(_spec(bare)),
             "sym": "EURUSD", "family": "carry", "passed": False, "terminal_gate": "UNKNOWN"},
            {"at": T1, "cell": "c3", "graph_id": hg.node_id_for_spec(_spec(judged_in_process)),
             "sym": "EURUSD", "family": "carry", "passed": True, "terminal_gate": "PASSED",
             "prereg_hash": None, "prereg_status": pr.POST_HOC}]
    gl.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    cursor = tmp_path / "cursor.json"
    kw: dict[str, Any] = {"graph": graph, "gate_ledger": gl, "cursor": cursor,
                          "seen_cells": tmp_path / "absent.json", "prereg_path": ledger}
    out = pj.record_gate_ledger(specs=[carded, bare, judged_in_process], **kw)
    assert out["stamped_by_judge"] == 1 and out["recorded"] == 2
    cur = graph.current()
    a = cur[rows[0]["graph_id"]]
    b = cur[rows[1]["graph_id"]]
    assert a["prereg_status"] == pr.PREREGISTERED and a["at"] == T1 and a["fate"] == hg.FAILED
    assert b["prereg_status"] == pr.POST_HOC and b["fate"] == hg.JUDGED     # UNKNOWN != fail
    assert rows[2]["graph_id"] not in cur
    assert json.loads(cursor.read_text("utf-8"))["offset"] == gl.stat().st_size
    assert pj.record_gate_ledger(specs=[], **kw)["rows"] == 0            # cursor holds


def test_no_gate_ledger_is_unmeasured_not_clean(tmp_path: Path, graph: hg.Graph) -> None:
    out = pj.record_gate_ledger(graph=graph, gate_ledger=tmp_path / "none.jsonl",
                                cursor=tmp_path / "c.json", seen_cells=tmp_path / "s.json")
    assert str(out["status"]).startswith("UNMEASURED")


def test_judged_id_join_streams_history_and_preserves_prior_fates(tmp_path, graph, monkeypatch):
    node = hg.Node("EURUSD", "carry", {"k": 1}, fate=hg.FAILED, at=T0)
    graph.append(node)
    graph.append(hg.Node("EURUSD", "carry", {"k": 1}, fate=hg.BORN, at=T1))
    other = hg.Node("USDJPY", "carry", {"k": 2}, fate=hg.JUDGED, at=T0)
    graph.append(other)
    monkeypatch.setattr(graph, "rows", lambda: pytest.fail("materialized full graph"))
    assert pj.judged_spec_ids(graph, gate_ledger=tmp_path / "absent") == {node.id, other.id}


def test_already_recorded_gate_rows_do_not_load_graph_or_cards(tmp_path, graph, monkeypatch):
    gate = tmp_path / "gate.jsonl"
    gate.write_text(json.dumps({"prereg_status": pr.POST_HOC, "cell": "old"}) + "\n")
    cursor = tmp_path / "cursor.json"
    monkeypatch.setattr(graph, "current", lambda: pytest.fail("loaded graph for zero new verdicts"))
    monkeypatch.setattr(pr, "spec_index", lambda *args: pytest.fail("loaded cards for zero work"))
    result = pj.record_gate_ledger(graph=graph, gate_ledger=gate, cursor=cursor)
    assert result["stamped_by_judge"] == 1
    assert result["recorded"] == result["verdicts"] == 0
    assert result["join_rate"] is None
    assert json.loads(cursor.read_text())["offset"] == gate.stat().st_size


def test_streamed_judged_ids_preserve_frozen_snapshot(tmp_path, graph):
    first = hg.Node("EURUSD", "carry", {"k": 1}, fate=hg.FAILED)
    graph.append(first)
    frozen = graph.snapshot()
    later = hg.Node("USDJPY", "carry", {"k": 2}, fate=hg.JUDGED)
    graph.append(later)
    assert pj.judged_spec_ids(frozen, gate_ledger=tmp_path / "absent") == {first.id}


def test_malformed_graph_keeps_only_independent_gate_evidence(tmp_path, graph):
    graph.append(hg.Node("EURUSD", "carry", {"k": 1}, fate=hg.FAILED))
    with graph.path.open("a") as output:
        output.write("broken json\n")
    gate = tmp_path / "gate.jsonl"
    gate.write_text(json.dumps({"graph_id": "independent"}) + "\n")
    assert pj.judged_spec_ids(graph, gate_ledger=gate) == {"independent"}


def test_the_docket_writer_counts_first_seen_cells_as_judged(
        tmp_path: Path, graph: hg.Graph, ledger: Path) -> None:
    row = _row(k=11)
    seen = tmp_path / "seen.json"
    seen.write_text(json.dumps({"CELL-11": T0}), "utf-8")
    out = pj.preregister_docket([row], graph=graph, gate_ledger=tmp_path / "none.jsonl",
                                seen_cells=seen, cell_id=lambda s: "CELL-11",
                                prereg_path=ledger)
    assert out["retrospective"] == 1 and not ledger.exists()


# -------------------------------------------------------------- 4. the fence measures it
def _check_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "check_preregistration_under_test", _ROOT / "scripts" / "check_preregistration.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_fence_rederives_the_join_rate_and_catches_a_false_stamp(
        tmp_path: Path, graph: hg.Graph, ledger: Path) -> None:
    mod = _check_module()
    carded, bare = _row(k=1), _row(k=2)
    pr.register_docket([carded], path=ledger, now=_dt(T0))
    _record([_verdict(carded, False), _verdict(bare, False)], [carded, bare], graph, ledger, T1)
    j = mod.join_census(graph=graph.path, gate_ledger=tmp_path / "none.jsonl", ledger=ledger)
    assert j["judged_cells"] == 2 and j["joined"] == 1 and j["join_rate"] == 0.5
    assert j["false_preregistered_stamps"] == 0
    # a row that CLAIMS a card came first, when the ledger says otherwise, is a forgery
    forged = hg.Node(symbol="EURUSD", family="carry", params={"k": 99}, fate=hg.FAILED, at=T1,
                     prereg_hash="0" * 16, prereg_status=pr.PREREGISTERED)
    graph.append(forged)
    j = mod.join_census(graph=graph.path, gate_ledger=tmp_path / "none.jsonl", ledger=ledger)
    assert j["false_preregistered_stamps"] == 1 and j["judged_cells"] == 3


def test_the_join_rate_is_a_ratchet_metric() -> None:
    spec = importlib.util.spec_from_file_location(
        "check_ratchets_under_test", _ROOT / "scripts" / "check_ratchets.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "prereg_join_rate" in mod._METRICS
    assert mod._METRICS["prereg_join_rate"][0] == "desks/mt5/reports/PREREG_COVERAGE.json"
    assert mod._prereg_join_rate({"join": {"join_rate": 0.25}}) == pytest.approx(0.25)
    assert mod._prereg_join_rate({"join": {"join_rate": None}}) is None
    assert mod._prereg_join_rate(None) is None


def _dt(iso: str) -> Any:
    from datetime import datetime
    return datetime.fromisoformat(iso)
