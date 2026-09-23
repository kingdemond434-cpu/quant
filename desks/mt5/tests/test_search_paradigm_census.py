"""The census must SEE duplication, not just count names -- proved on planted proposals.

Two paradigms drawing the same (symbol, family, params) cell is one hypothesis carrying two
multiplicity charges. A census that reported "two paradigms ran" for that would be the exact
self-congratulation the item's measured gap names, so every test here plants a known overlap and
asserts the published number moves.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, ClassVar

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import search_paradigm_census as C  # noqa: E402


def _proposal(source: str, symbol: str, family: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"source": source, "symbol": symbol, "family": family, "params": params,
            "at": "2026-09-22T00:00:00+00:00", "via": "test"}


def _cells(source: str, n: int, *, offset: int = 0) -> list[dict[str, Any]]:
    return [_proposal(source, "XAUUSD", "session_range_breakout", {"rr": i + offset})
            for i in range(n)]


# --------------------------------------------------------------- the redundancy measurement
def test_two_paradigms_on_the_same_cells_drop_the_effective_count() -> None:
    """Disjoint ground reads 2.0; identical ground reads 1.0. That is the whole measure."""
    disjoint, _ = C.attribute(_cells("qd_frontier", 10) + _cells("residual_queue", 10,
                                                                 offset=100))
    same_cells = _cells("qd_frontier", 10) + [
        _proposal("residual_queue", r["symbol"], r["family"], r["params"])
        for r in _cells("qd_frontier", 10)]
    overlapped, _ = C.attribute(same_cells)

    a = C.redundancy(disjoint)
    b = C.redundancy(overlapped)

    assert a["paradigms_with_proposals"] == b["paradigms_with_proposals"] == 2
    assert a["effective_paradigms"] == pytest.approx(2.0)
    assert b["effective_paradigms"] == pytest.approx(1.0)
    # The breadth-style inverse-Herfindahl is published and CANNOT see the duplication: both
    # paradigms still hold half the volume. That is exactly why it is not the headline.
    assert a["effective_paradigms_by_volume"] == pytest.approx(2.0)
    assert b["effective_paradigms_by_volume"] == pytest.approx(2.0)

    assert a["cells_proposed_by_two_or_more"] == 0
    assert b["cells_proposed_by_two_or_more"] == 10
    assert b["duplicated_cell_share"] == pytest.approx(1.0)
    assert b["duplicated_share_by_paradigm"]["quality_diversity"] == pytest.approx(1.0)


def test_pairwise_overlap_is_directed() -> None:
    """A small paradigm wholly inside a large one is fully duplicated; the large one is not."""
    rows = _cells("qd_frontier", 20) + _cells("residual_queue", 4)
    by, _ = C.attribute(rows)
    red = C.redundancy(by)
    pair = red["pairwise"][0]
    small = "share_of_a" if pair["a"] == "residual_mining" else "share_of_b"
    large = "share_of_b" if small == "share_of_a" else "share_of_a"
    assert pair[small] == pytest.approx(1.0)
    assert pair[large] == pytest.approx(0.2)
    assert pair["jaccard"] == pytest.approx(0.2)
    assert red["effective_paradigms"] < 2.0


def test_cell_key_is_order_free_and_reads_json_params() -> None:
    a = C.cell_key("xauusd", "Momentum", {"b": 2, "a": 1})
    b = C.cell_key("XAUUSD", "momentum", json.dumps({"a": 1, "b": 2}))
    assert a == b
    assert a != C.cell_key("XAUUSD", "momentum", {"a": 1, "b": 3})


def test_the_compiler_is_not_a_paradigm_but_its_transformation_can_be() -> None:
    """A candidate queued by the intake is attributed to what DISCOVERED it, not to the door."""
    assert C._source_of({"generator": "discovery_compiler:residual"}) == "residual"
    assert C._source_of({"generator": "discovery_compiler:interaction"}) == "interaction"
    assert C._source_of({"disc_generator": "qd_frontier",
                         "generator": "discovery_compiler:interaction"}) == "qd_frontier"
    assert C._source_of({"generator": "seat:discovery_compiler",
                         "source_id": "intelligence"}) == ""


# ------------------------------------------------------------------- the NOT_SCHEDULED row
def test_a_paradigm_that_never_ran_reads_not_scheduled_with_its_organ() -> None:
    rows = C.paradigm_rows({}, *_empty())
    assert rows, "the census must publish a row per declared paradigm"
    assert len(rows) == len(C.PARADIGMS)
    for r in rows:
        assert r["status"] == "NOT_SCHEDULED"
        assert r["ran_24h"] is False
        assert r["organ"] and r["organ"] in r["why"]
        assert r["legs"]


def test_a_leg_seen_in_the_ledger_flips_the_row_to_ran() -> None:
    runs = {"qd_frontier": {"runs": 3, "last_at": "2026-09-22T10:00:00+00:00", "failures": 0,
                            "seen_in": ["compute_ledger"]}}
    by, _ = C.attribute(_cells("qd_frontier", 5))
    rows = {r["paradigm"]: r for r in C.paradigm_rows(runs, by, {})}
    assert rows["quality_diversity"]["status"] == "RAN"
    assert rows["quality_diversity"]["runs"] == 3
    assert rows["quality_diversity"]["proposals"] == 5
    assert rows["residual_mining"]["status"] == "NOT_SCHEDULED"


def test_a_leg_that_ran_and_proposed_nothing_is_its_own_verdict() -> None:
    runs = {"residual_queue": {"runs": 1, "last_at": "2026-09-22T10:00:00+00:00", "failures": 0,
                               "seen_in": ["events"]}}
    by, _ = _empty()
    row = {r["paradigm"]: r for r in C.paradigm_rows(runs, by, {})}["residual_mining"]
    assert row["status"] == "RAN_PROPOSED_NOTHING"
    assert "a run is not a proposal" in row["why"]


def _empty() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    by, _ = C.attribute([])
    return by, {}


# ----------------------------------------------------------------------- the controller leg
def test_every_active_line_gets_one_of_the_four_decisions() -> None:
    lines = [{"line": "session_range_breakout", "rows": 40, "attempts": 12, "successes": 3,
              "pending": 5, "saturation": 0.2},
             {"line": "overnight_gap_decay", "rows": 9, "attempts": 0, "successes": 0,
              "pending": 9, "saturation": 0.0},
             {"line": "dead_ground", "rows": 80, "attempts": 30, "successes": 0,
              "pending": 2, "saturation": 0.95}]
    out = C.controller_pass(lines, budget=60, seed=5)
    assert out["status"] == "MEASURED"
    assert len(out["decisions"]) == 3
    assert {d["decision"] for d in out["decisions"]} <= set(C.DECISIONS)
    assert sum(out["counts"].values()) == 3
    stop = {d["line"]: d for d in out["decisions"]}["dead_ground"]
    assert stop["decision"] == "STOP", stop
    assert "no success" in stop["why"]
    assert sum(out["budget_split"].values()) <= 60
    assert "judges" in out["authority"]


def test_no_active_line_is_unmeasured_not_zero() -> None:
    out = C.controller_pass([], budget=10)
    assert out["status"] == "UNMEASURED"
    assert "no active line of work" in out["why"]
    assert out["decisions"] == []


# ---------------------------------------------------------------- the report and the switch
def _registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """A HERMETIC registry. `connect` restores from the desk's moat backup when the file is
    absent, so a test that only set the path would silently read the real desk."""
    from libs.moat import registry as reg
    monkeypatch.setattr(reg, "BACKUP", tmp_path / "no_such_backup.sqlite")
    reg.set_path(tmp_path / "alpha_registry.sqlite")
    return reg


def _no_populations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(C, "populations_pass",
                        lambda **kw: {"status": "UNMEASURED", "why": "stubbed in test",
                                      "yields": [], "donated": 0})


def test_absent_inputs_are_unmeasured_and_the_report_is_still_written(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty desk is a verdict with a reason, never a missing file (L1.28a)."""
    _registry(tmp_path, monkeypatch)
    _no_populations(monkeypatch)
    monkeypatch.setattr(C, "INTEL_ROOTS", (tmp_path / "nowhere",))
    monkeypatch.setattr(C, "leg_runs",
                        lambda *a, **k: ({}, [C._row("compute_ledger", False, "absent in test")]))

    out = tmp_path / "SEARCH_PARADIGMS.json"
    assert C.main(["--once", "--budget-s", "20", "--out", str(out)]) == 0
    doc = json.loads(out.read_text("utf-8"))

    assert doc["counts"]["not_scheduled"] == len(C.PARADIGMS)
    assert doc["controller"]["status"] == "UNMEASURED"
    assert doc["populations"]["status"] == "UNMEASURED"
    assert doc["redundancy"]["effective_paradigms"] is None
    assert any(r["name"] == "intelligence" and r["status"] == "absent" for r in doc["inputs"])
    assert doc["summary"]


def test_dry_run_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _registry(tmp_path, monkeypatch)
    _no_populations(monkeypatch)
    monkeypatch.setattr(C, "INTEL_ROOTS", (tmp_path / "nowhere",))
    monkeypatch.setattr(C, "leg_runs", lambda *a, **k: ({}, []))
    out = tmp_path / "nowhere.json"
    assert C.main(["--dry-run", "--budget-s", "20", "--out", str(out)]) == 0
    assert not out.exists()


def test_the_donation_is_refused_for_the_wrong_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    """A single-name equity may be MEASURED and may never be donated as a hypothesis."""
    import research.universe_policy as up

    monkeypatch.setattr(C, "_frames", lambda s: ({}, None, "stubbed"))
    monkeypatch.setattr(up, "may_hypothesise", lambda s: False)

    class _Res:
        proposals: ClassVar[list[tuple[str, str]]] = [("expr", "gp")]
        yields: ClassVar[dict[str, Any]] = {}
        failures: ClassVar[list[str]] = []

        def yield_rows(self) -> list[dict[str, Any]]:
            return []

    import libs.research.search_populations as sp
    monkeypatch.setattr(sp, "run", lambda ctx, **kw: _Res())
    out = C.populations_pass(symbol="Apple", budget_s=1.0, draws=1)
    assert out["donated"] == 0
    assert out["donation"].get("refused_wrong_lane") == 1


def test_rows_cap_is_derived_and_floored() -> None:
    cap, why = C.rows_cap()
    assert cap >= C.ROWS_FLOOR
    assert "floor" in why or "floor stands" in why
