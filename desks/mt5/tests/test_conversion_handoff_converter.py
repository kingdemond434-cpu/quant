"""The conversion-handoff converter: build_failed -> defect report, short_history -> a charged
cross-asset transplant, everything else held for a multiple-testing budget.

Every test runs on a small synthetic handoff in the writer's own shape
(`judge_coverage.write_conversion_handoff`: one JSON object, indent=1, rows last), a tmp broker
registry and tmp bar files, with the registry lookup and the donation door injected -- nothing
here reads or writes the desk's real data.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research.conversion_handoff_converter as C  # noqa: E402
import research.universe_policy as UP  # noqa: E402

REGISTRY = {
    # FX: one short-history parent and three long peers
    "USDNOK": ("Forex", "2026-06-01"), "EURUSD": ("Forex", "2015-01-01"),
    "GBPUSD": ("Forex", "2016-01-01"), "AUDUSD": ("Forex", "2017-01-01"),
    # share CFDs: one short-history parent and two long peers
    "NEWCO": ("Equities", "2026-06-01"), "AAPL": ("Equities", "2014-01-01"),
    "MSFT": ("Equities", "2015-06-01"),
}


def _bars(path: Path, start: str) -> None:
    t = pd.date_range(start, periods=48, freq="h", tz="UTC")
    pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "time": t}).to_parquet(
        path, index=False)


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    uni = tmp_path / "universe"
    uni.mkdir()
    reg = {}
    for sym, (klass, start) in REGISTRY.items():
        reg[sym] = {"symbol": sym, "asset_class": klass}
        _bars(uni / f"{sym}_H1.parquet", start)
    (uni / "universe.json").write_text(json.dumps(reg), "utf-8")
    monkeypatch.setattr(UP, "UNIVERSE", uni / "universe.json")
    monkeypatch.setattr(C, "family_owners", lambda fams: {f: f"owner/{f}.py" for f in fams})
    C._HIST_MEMO.clear()
    params: dict[str, dict[str, Any]] = {}
    donations: list[tuple[str, list[dict[str, Any]], int]] = []
    existing: set[tuple[str, str]] = set()

    def lookup(rows: Any, time_ok: Any) -> dict[str, dict[str, Any]]:
        return {str(r["cell"]): {"params": params[str(r["cell"])], "timeframe": "H1"}
                for r in rows if str(r["cell"]) in params}

    def donor(fam: str, cands: list[dict[str, Any]], tests_run: int) -> dict[str, Any]:
        donations.append((fam, cands, tests_run))
        return {"path": str(tmp_path / f"discoveries_{len(donations)}_{fam}.json"),
                "donated": len(cands)}

    def exists(fam: str, sym: str, p: Any, tf: str) -> bool:
        return (fam, sym) in existing

    w: dict[str, Any] = {"tmp": tmp_path, "uni": uni, "params": params, "donations": donations,
                         "existing": existing, "handoff": tmp_path / "conversion_handoff.json"}

    def run(**kw: Any) -> dict[str, Any]:
        args: dict[str, Any] = {
            "handoff": w["handoff"], "ledger": tmp_path / "resolved.jsonl",
            "cursor_path": tmp_path / "cursor.json",
            "report": tmp_path / "CONVERSION_HANDOFF.json",
            "defects": tmp_path / "FAMILY_BUILD_DEFECTS.json", "params_lookup": lookup,
            "exists": exists, "donor": donor, "universe": uni, "env": {}}
        args.update(kw)
        return C.run_pass(**args)

    w["run"] = run
    yield w
    C._HIST_MEMO.clear()


def _row(cell: str, reason: str, *, family: str = "carry", symbol: str = "USDNOK",
         why: str = "", parked: str = "2026-11-01T00:00:00+00:00") -> dict[str, Any]:
    return {"cell": cell, "family": family, "trial_family": family, "symbol": symbol,
            "timeframe": "H1", "reason": reason, "class": "x", "axes": ["cross_asset_transplant"],
            "missing_input": None, "why": why, "first_parked_utc": parked}


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    """The writer's exact shape: `json.dumps({...,"rows": rows}, indent=1)`."""
    path.write_text(json.dumps({"schema_version": 1, "generated_utc": "2026-11-10T07:59:10Z",
                                "n": len(rows), "rows": rows}, indent=1), "utf-8")


def _ledger(w: dict[str, Any]) -> list[dict[str, Any]]:
    p = w["tmp"] / "resolved.jsonl"
    return [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]


def test_streams_the_writers_shape_and_jsonl(tmp_path: Path) -> None:
    rows = [_row(f"C{i}", "never_fires") for i in range(2500)]
    p = tmp_path / "h.json"
    _write(p, rows)
    got = list(C.iter_handoff(p, chunk=4096))
    assert [r["cell"] for r in got] == [r["cell"] for r in rows]
    assert C.handoff_header(p)["n"] == 2500
    q = tmp_path / "h.jsonl"
    q.write_text("\n".join(json.dumps(r) for r in rows[:7]) + "\n", "utf-8")
    assert C.handoff_header(q)["format"] == "jsonl"
    assert len(list(C.iter_handoff(q))) == 7


def test_build_failed_is_a_defect_report_with_no_trial(world: dict[str, Any]) -> None:
    _write(world["handoff"], [
        _row("A1", "build_failed", family="fam_a", symbol="EURUSD",
             why="KeyError: 'atr_14' on EURUSD after 120 bars"),
        _row("A2", "build_failed", family="fam_a", symbol="GBPUSD",
             why="KeyError: 'atr_14' on GBPUSD after 37 bars"),
        _row("A3", "build_failed", family="fam_a", symbol="GBPUSD", why="ZeroDivisionError"),
        _row("B1", "build_failed", family="fam_b", symbol="AUDUSD", why="boom"),
    ])
    doc = world["run"]()
    rep = json.loads((world["tmp"] / "FAMILY_BUILD_DEFECTS.json").read_text("utf-8"))
    assert rep["build_failed_rows"] == 4
    assert [r["family"] for r in rep["ranked"]] == ["fam_a", "fam_b"]
    top = rep["ranked"][0]
    assert top["count"] == 3 and top["owner"] == "owner/fam_a.py"
    assert top["messages"][0]["count"] == 2          # the two KeyErrors fold into one defect
    assert set(top["messages"][0]["sample_cells"]) == {"A1", "A2"}
    assert "<SYM>" in top["messages"][0]["signature"]
    led = _ledger(world)
    assert len(led) == 4 and {r["status"] for r in led} == {C.DEFECT_REPORTED}
    assert all(r["trials_charged"] == 0 for r in led)
    assert world["donations"] == []
    assert doc["trials_charged"]["this_pass"] == 0
    assert doc["counts"]["build_failed"] == {C.DEFECT_REPORTED: 4}
    # a second pass re-reports the census but resolves nothing twice
    world["run"]()
    assert len(_ledger(world)) == 4


def test_short_history_transplants_to_a_same_class_peer_and_charges_one_trial(
        world: dict[str, Any]) -> None:
    world["params"]["P1"] = {"lookback": 20}
    _write(world["handoff"], [_row("P1", "short_history_after_cut", family="carry")])
    doc = world["run"]()
    assert len(world["donations"]) == 1
    fam, cands, tests_run = world["donations"][0]
    assert fam == "carry" and tests_run == 1 and len(cands) == 1
    c = cands[0]
    assert c["symbol"] == "EURUSD"                 # the longest same-class history
    assert c["family"] == "carry" and c["params"] == {"lookback": 20}
    assert c["lineage"]["parent_cell"] == "P1"
    assert c["cell"] == C._cell_id("EURUSD", "carry", {"lookback": 20}, "H1")
    (rec,) = _ledger(world)
    assert rec["status"] == C.CONVERTED and rec["parent_cell"] == "P1"
    assert rec["child_ids"] == [c["cell"]] and rec["trials_charged"] == 1
    assert rec["trial_family"] == "carry"
    assert doc["trials_charged"]["this_pass_by_family"] == {"carry": 1}


def test_an_existing_peer_rule_is_skipped_for_the_next_peer(world: dict[str, Any]) -> None:
    world["params"]["P1"] = {"lookback": 20}
    world["existing"].add(("carry", "EURUSD"))
    _write(world["handoff"], [_row("P1", "short_history_after_cut")])
    world["run"]()
    assert world["donations"][0][1][0]["symbol"] == "GBPUSD"


def test_per_pass_cap_defers_and_the_next_pass_picks_them_up(world: dict[str, Any]) -> None:
    rows = []
    for i in range(5):
        world["params"][f"P{i}"] = {"lookback": 10 + i}
        rows.append(_row(f"P{i}", "short_history_after_cut"))
    _write(world["handoff"], rows)
    d1 = world["run"](max_per_pass=2)
    assert d1["counts"]["short_history_after_cut"] == {C.CONVERTED: 2, C.DEFERRED_BUDGET: 3}
    assert d1["deferred_backlog"]["rows"] == 3
    assert not any(r["status"] == C.DEFERRED_BUDGET for r in _ledger(world))
    d2 = world["run"](max_per_pass=2)
    assert d2["counts"]["short_history_after_cut"] == {C.CONVERTED: 4, C.DEFERRED_BUDGET: 1}
    d3 = world["run"](max_per_pass=2)
    assert d3["counts"]["short_history_after_cut"] == {C.CONVERTED: 5}
    conv = [r for r in _ledger(world) if r["status"] == C.CONVERTED]
    assert sorted(r["cell"] for r in conv) == [f"P{i}" for i in range(5)]
    assert sum(t for _, _, t in world["donations"]) == 5


def test_per_family_daily_cap(world: dict[str, Any]) -> None:
    for i in range(3):
        world["params"][f"P{i}"] = {"lookback": 10 + i}
    _write(world["handoff"], [_row(f"P{i}", "short_history_after_cut") for i in range(3)])
    d1 = world["run"](max_per_family_day=2)
    assert d1["counts"]["short_history_after_cut"] == {C.CONVERTED: 2, C.DEFERRED_BUDGET: 1}
    assert d1["deferred_backlog"]["capped_by_family"] == {"carry": 1}
    d2 = world["run"](max_per_family_day=2)        # same UTC day: still capped
    assert d2["counts"]["short_history_after_cut"] == {C.CONVERTED: 2, C.DEFERRED_BUDGET: 1}


def test_never_fires_and_the_held_reasons_are_untouched(world: dict[str, Any]) -> None:
    _write(world["handoff"], [_row("N1", "never_fires"), _row("N2", "too_rare"),
                              _row("N3", "build_input_missing")])
    doc = world["run"]()
    assert not (world["tmp"] / "resolved.jsonl").exists() or _ledger(world) == []
    assert world["donations"] == []
    held = doc["awaiting_multiple_testing_budget"]
    assert held["by_reason"] == {"never_fires": 1, "too_rare": 1, "build_input_missing": 1}
    assert doc["counts"]["never_fires"] == {C.AWAITING_BUDGET: 1}


def test_lockbox_consumed_history_is_not_convertible_and_cites_the_law(
        world: dict[str, Any]) -> None:
    world["params"]["L1"] = {"lookback": 5}
    _write(world["handoff"], [_row("L1", "lockbox_consumed_history")])
    doc = world["run"]()
    (rec,) = _ledger(world)
    assert rec["status"] == C.NOT_CONVERTIBLE and "LAWS" in rec["why"]
    assert world["donations"] == []
    assert doc["lockbox"]["decision"] == C.NOT_CONVERTIBLE


def test_resolution_is_idempotent_and_never_charges_twice(world: dict[str, Any]) -> None:
    world["params"]["P1"] = {"lookback": 20}
    _write(world["handoff"], [_row("P1", "short_history_after_cut")])
    world["run"]()
    d2 = world["run"]()
    assert len(world["donations"]) == 1
    assert d2["trials_charged"]["this_pass"] == 0
    assert d2["trials_charged"]["lifetime"] == 1
    assert len(_ledger(world)) == 1
    # the judge re-parks the same cell later: a NEW handoff row, the SAME child -- no new charge
    _write(world["handoff"], [_row("P1", "short_history_after_cut",
                                   parked="2026-11-09T00:00:00+00:00")])
    d3 = world["run"]()
    assert len(world["donations"]) == 1
    assert d3["trials_charged"]["this_pass"] == 0
    last = _ledger(world)[-1]
    assert last["status"] == C.CONVERTED and last["trials_charged"] == 0
    assert last["child_ids"] == _ledger(world)[0]["child_ids"]


def test_two_lane_rule_for_single_name_equities(world: dict[str, Any]) -> None:
    world["params"]["E1"] = {"lookback": 20}
    world["params"]["E2"] = {"lookback": 20}
    _write(world["handoff"], [
        _row("E1", "short_history_after_cut", family="momentum", symbol="NEWCO"),
        _row("E2", "short_history_after_cut", family="cross_sectional_class_momentum",
             symbol="NEWCO"),
    ])
    world["run"]()
    led = {r["cell"]: r for r in _ledger(world)}
    assert led["E1"]["status"] == C.NOT_CONVERTIBLE and "two-lane" in led["E1"]["why"]
    assert led["E2"]["status"] == C.CONVERTED
    (fam, cands, n), = world["donations"]
    assert fam == "cross_sectional_class_momentum" and n == 1
    assert cands[0]["symbol"] == "AAPL"
    # and an FX parent is never transplanted onto a share CFD, whatever the family
    peers, _ = C.ranked_peers("USDNOK", "cross_sectional_class_momentum", "H1",
                              universe=world["uni"],
                              now=datetime(2026, 11, 11, tzinfo=UTC))
    assert peers and not any(UP.is_equity(p) for p in peers)


def test_tiny_budget_writes_a_partial_report_and_a_cursor(world: dict[str, Any]) -> None:
    rows = [_row(f"N{i:05d}", "never_fires") for i in range(3000)]
    _write(world["handoff"], rows)
    ticks = iter(range(10_000))
    doc = world["run"](budget_s=2.0, clock=lambda: float(next(ticks)))
    assert doc["partial"] is True
    assert doc["handoff"]["complete"] is False
    assert doc["handoff"]["rows_read"] < 3000
    assert (world["tmp"] / "CONVERSION_HANDOFF.json").exists()
    assert (world["tmp"] / "cursor.json").exists()
    assert json.loads((world["tmp"] / "FAMILY_BUILD_DEFECTS.json").read_text())["partial"]


def test_tiny_budget_in_the_transplant_loop_keeps_the_cursor_on_the_unworked_row(
        world: dict[str, Any]) -> None:
    for i in range(3):
        world["params"][f"P{i}"] = {"lookback": 10 + i}
    _write(world["handoff"], [_row(f"P{i}", "short_history_after_cut") for i in range(3)])
    t = {"n": 0.0}

    def clock() -> float:
        t["n"] += 0.5
        return t["n"]

    # a 1.7 s working budget on a clock that moves 0.5 s a call: the stream, the lookup and the
    # first transplant fit, the second does not
    doc = world["run"](budget_s=2.0, clock=clock)
    assert doc["partial"] is True
    done = {r["cell"] for r in _ledger(world)}
    assert done == {"P0"}
    cur = json.loads((world["tmp"] / "cursor.json").read_text())
    assert cur["cursor_cell"] == max(done)
    world["run"]()                                    # a full pass finishes the rest
    assert {r["cell"] for r in _ledger(world)} == {"P0", "P1", "P2"}


def test_the_cycle_cap_bounds_the_work_budget() -> None:
    assert C._budget_s(420.0, {"QUANT_LEG_BUDGET_S": "100"}) == pytest.approx(85.0)
    assert C._budget_s(420.0, {}) == pytest.approx(420.0 * C.BUDGET_SHARE)
