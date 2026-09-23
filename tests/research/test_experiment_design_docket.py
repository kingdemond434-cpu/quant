"""THE EVSI SCORER MEETS THE REAL DOCKET.

`experiment_design.run()` scored four hand-typed rows while the gauntlet published thousands of
cells its build budget did not reach (`NOT_RUN_BUILD_BUDGET_DEFERRED`, 7,648 measured
2026-09-02). Pinned here:

  * the queue is built from those deferred cells when the report is on disk, priced at the
    gauntlet's own ~22s per cell (cited from external_gauntlet.py) or at the report's own
    prewarm measurement when it carries one;
  * P(changes the decision) is P(certify | family) from the cells the same report judged, and the
    value is the family's survivors' expected value -- UNMEASURED is scored at 0 and SAID, never
    invented;
  * every row carries its rotation rank beside its EVSI rank: the view sits BESIDE the builder's
    order, it does not replace it;
  * the four hand-typed experiments remain, as a fallback labelled as such, when the report is
    absent or carries no deferred cell.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_expdesign_docket", _ROOT / "desks" / "mt5" / "research" / "experiment_design.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def ed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    mod = _load()
    monkeypatch.setattr(mod, "GATES_EXTERNAL", tmp_path / "universal_gates_external.json")
    monkeypatch.setattr(mod, "REPORT", tmp_path / "EXPERIMENT_DESIGN.json")
    return mod


def _judged(sym: str, fam: str, passed: bool, ev: float | None = None) -> dict:
    stages = {"expected_value": {"passed": passed, "ev": ev}} if ev is not None else {}
    return {"cell": f"{sym}.{fam}.p=x", "sym": sym, "family": fam, "days": 200,
            "passed": passed, "stages": stages}


def _deferred(sym: str, fam: str) -> dict:
    return {"cell": f"{sym}.{fam}.rr=1.5_wb=12", "sym": sym, "family": fam, "days": 0,
            "passed": None, "stages": {},
            "downstream_status": "NOT_RUN_BUILD_BUDGET_DEFERRED",
            "why": "the sweep's fresh-build budget was exhausted before this cell was computed."}


def _report(ed, verdicts: list[dict], **extra) -> None:
    ed.GATES_EXTERNAL.write_text(json.dumps({"swept_at": "2026-09-08T12:00:00+00:00",
                                             "verdicts": verdicts, **extra}), "utf-8")


# --------------------------------------------------------------------------- the real docket

def test_the_queue_is_built_from_the_deferred_cells_priced_at_the_cited_cell_cost(ed) -> None:
    _report(ed, [
        _judged("EURUSD", "session_range_breakout", True, ev=0.30),
        _judged("GBPUSD", "session_range_breakout", True, ev=0.10),
        _judged("USDJPY", "session_range_breakout", False),
        _judged("XAUUSD", "carry", False),
        _deferred("AUDNZD", "session_range_breakout"),          # rotation rank 0
        _deferred("EURCHF", "carry"),                           # rotation rank 1
        _deferred("NZDCAD", "overnight_gap_decay"),             # rotation rank 2: nothing judged
    ])
    doc = ed.run()
    assert doc["queue_basis"] == "GAUNTLET_DEFERRED_CELLS"
    assert doc["n_scored"] == 3
    names = {r["name"] for r in doc["evsi"]}
    assert names == {"gauntlet_cell:AUDNZD.session_range_breakout.rr=1.5_wb=12",
                     "gauntlet_cell:EURCHF.carry.rr=1.5_wb=12",
                     "gauntlet_cell:NZDCAD.overnight_gap_decay.rr=1.5_wb=12"}
    assert "recertify_unrunnable_certificates" not in names, "the hand-typed rows are not mixed in"
    dk = doc["docket"]
    assert dk["status"] == "MEASURED" and dk["n_deferred"] == 3
    assert dk["cost_s_per_cell"] == ed.GAUNTLET_CELL_BUILD_S == 22.0
    assert "external_gauntlet.py:66-67" in dk["cost_basis"]
    for row in dk["rows"]:
        assert row["cost_hours"] == pytest.approx(22.0 / 3600.0)


def test_p_and_value_come_from_the_cells_the_same_report_judged(ed) -> None:
    _report(ed, [
        _judged("EURUSD", "session_range_breakout", True, ev=0.30),
        _judged("GBPUSD", "session_range_breakout", True, ev=0.10),
        _judged("USDJPY", "session_range_breakout", False),
        _judged("XAUUSD", "carry", False),
        _deferred("AUDNZD", "session_range_breakout"),
        _deferred("EURCHF", "carry"),
        _deferred("NZDCAD", "overnight_gap_decay"),
    ])
    dk = ed.run()["docket"]
    by = {r["sym"]: r for r in dk["rows"]}
    # session_range_breakout: 2 of 3 judged passed -> (2+1)/(3+2); value = mean(0.30, 0.10)
    assert by["AUDNZD"]["p_changes_decision"] == pytest.approx(3 / 5)
    assert by["AUDNZD"]["decision_value"] == pytest.approx(0.20)
    # carry: 0 of 1 passed -> (0+1)/(1+2); no survivor ev -> the report-wide mean
    assert by["EURCHF"]["p_changes_decision"] == pytest.approx(1 / 3)
    assert by["EURCHF"]["decision_value"] == pytest.approx(0.20)
    # a family nothing judged: the pooled rate (2 of 4) -> (2+1)/(4+2)
    assert by["NZDCAD"]["p_changes_decision"] == pytest.approx(3 / 6)
    assert dk["family_rates"]["session_range_breakout"] == {
        "judged": 3, "passed": 2, "p_certify": 0.6, "mean_ev": 0.2}
    assert "_pooled" not in dk["family_rates"] and dk["pooled_rate"]["judged"] == 4


def test_no_survivor_ev_anywhere_is_scored_at_zero_and_said_not_invented(ed) -> None:
    _report(ed, [_judged("EURUSD", "carry", True),          # passed, but no ev on the row
                 _deferred("EURCHF", "carry")])
    dk = ed.run()["docket"]
    assert dk["rows"][0]["decision_value"] == 0.0
    assert "UNMEASURED" in dk["value_basis"] and "1 cell(s) scored at 0.0" in dk["value_basis"]


def test_rows_are_evsi_ordered_and_keep_their_rotation_rank_beside_it(ed) -> None:
    _report(ed, [
        _judged("A", "strong", True, ev=0.50), _judged("B", "strong", True, ev=0.50),
        _judged("C", "weak", False), _judged("D", "weak", False), _judged("E", "weak", False),
        _deferred("W1", "weak"), _deferred("W2", "weak"),      # rotation ranks 0, 1
        _deferred("S1", "strong"),                             # rotation rank 2
    ])
    dk = ed.run()["docket"]
    assert [r["sym"] for r in dk["rows"]] == ["S1", "W1", "W2"], "strong family first by EVSI"
    assert [r["rotation_rank"] for r in dk["rows"]] == [2, 0, 1]
    assert [r["evsi_rank"] for r in dk["rows"]] == [0, 1, 2]
    assert dk["head_overlap"]["cells_in_both_heads"] == 3, "with 3 cells both heads are the docket"
    assert dk["n_rows"] == 3 and dk["order"].startswith("EVSI descending")


def test_the_report_s_own_prewarm_measurement_beats_the_cited_constant(ed) -> None:
    _report(ed, [_judged("A", "f", True, ev=0.2), _deferred("B", "f")],
            prewarm={"warmed": 40, "seconds": 1200.0})
    dk = ed.run()["docket"]
    assert dk["cost_s_per_cell"] == 30.0
    assert dk["cost_basis"].startswith("measured: 1200s over 40 cell(s)")


def test_the_published_head_is_bounded_but_the_full_ranking_is_counted(ed, monkeypatch) -> None:
    monkeypatch.setattr(ed, "PUBLISHED_ROWS", 5)
    _report(ed, [_judged("A", "f", True, ev=0.2)] + [_deferred(f"S{i}", "f") for i in range(12)])
    doc = ed.run()
    assert doc["n_scored"] == 12 and len(doc["evsi"]) == 5
    assert doc["docket"]["n_rows"] == 12 and doc["docket"]["n_published"] == 5
    assert len(doc["docket"]["rows"]) == 5


def test_every_docket_experiment_is_a_falsifier_so_the_design_chooses_one(ed) -> None:
    _report(ed, [_judged("A", "f", True, ev=0.2), _deferred("B", "f")])
    doc = ed.run()
    assert doc["design"]["status"] == "CHOSEN"
    assert doc["design"]["choice"].startswith("gauntlet_cell:B.f")
    assert "survives the ten gates" in doc["design"]["falsifies"]


# --------------------------------------------------------------------------- the fallback

def test_an_absent_report_falls_back_to_the_four_hand_typed_rows_labelled_as_such(ed) -> None:
    doc = ed.run()
    assert doc["queue_basis"] == "HAND_TYPED_FALLBACK"
    assert "absent" in doc["queue_why"]
    assert {r["name"] for r in doc["evsi"]} == {e.name for e in ed.HAND_TYPED}
    assert doc["docket"]["status"] == "FALLBACK" and doc["docket"]["basis"] == "HAND_TYPED_FALLBACK"


def test_a_report_with_nothing_deferred_also_falls_back_and_says_why(ed) -> None:
    _report(ed, [_judged("A", "f", True, ev=0.2)])
    doc = ed.run()
    assert doc["queue_basis"] == "HAND_TYPED_FALLBACK"
    assert "carries no NOT_RUN_BUILD_BUDGET_DEFERRED cell" in doc["queue_why"]
    assert doc["n_scored"] == 4


def test_main_writes_the_report_and_prints_the_docket(ed, capsys) -> None:
    _report(ed, [_judged("A", "f", True, ev=0.2), _deferred("B", "f")])
    assert ed.main() == 0
    out = capsys.readouterr().out
    assert "experiment design [GAUNTLET_DEFERRED_CELLS]" in out
    assert "docket: 1 deferred cell(s) at 22.0s each" in out
    written = json.loads(ed.REPORT.read_text("utf-8"))
    assert written["docket"]["rows"][0]["cell"] == "B.f.rr=1.5_wb=12"
