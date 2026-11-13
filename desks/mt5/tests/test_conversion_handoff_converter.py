"""The conversion-handoff converter: build_failed -> defect report, short_history -> a charged
cross-asset transplant, never_fires -> relaxed children, too_rare -> a coarser chart or a pooled
class book, build_input_missing -> a data-gap report and a retry, all under a trial budget derived
from the judge's measured capacity; every row ends with an outcome.

Every test runs on a small synthetic handoff in the writer's own shape
(`judge_coverage.write_conversion_handoff`: one JSON object, indent=1, rows last), a tmp broker
registry and tmp bar files, with the registry lookup and the donation door injected -- nothing
here reads or writes the desk's real data.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
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

#: A fixed clock at the start of a UTC day: 24 passes left, so the per-pass budget is a 24th.
NOW = datetime(2026, 11, 11, 0, 30, tzinfo=UTC)

#: The family registry's grids, injected: one relaxable threshold, one with exit params only.
SPACES: dict[str, tuple[dict[str, list[Any]], dict[str, Any]]] = {
    "fam_z": ({"z_thresh": [1.0, 1.5, 2.0, 2.5], "rr": [1.5, 2.0]}, {"z_thresh": 2.0, "rr": 2.0}),
    "fam_exit_only": ({"rr": [1.5, 2.0], "ttl_bars": [12, 24]}, {"rr": 2.0}),
}

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

    present: dict[str, bool | None] = {}
    capacity = tmp_path / "capacity"
    capacity.mkdir()
    w: dict[str, Any] = {"tmp": tmp_path, "uni": uni, "params": params, "donations": donations,
                         "existing": existing, "handoff": tmp_path / "conversion_handoff.json",
                         "present": present, "capacity": capacity, "now": NOW}

    def run(**kw: Any) -> dict[str, Any]:
        args: dict[str, Any] = {
            "handoff": w["handoff"], "ledger": tmp_path / "resolved.jsonl",
            "cursor_path": tmp_path / "cursor.json",
            "report": tmp_path / "CONVERSION_HANDOFF.json",
            "defects": tmp_path / "FAMILY_BUILD_DEFECTS.json",
            "gaps": tmp_path / "BUILD_INPUT_GAPS.json", "params_lookup": lookup,
            "exists": exists, "donor": donor, "universe": uni, "env": {},
            "capacity_dir": capacity, "param_space": lambda f: SPACES.get(f, ({}, {})),
            "input_present": lambda lab: present.get(lab, False), "now": w["now"]}
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


def test_no_reason_is_held_any_more(world: dict[str, Any]) -> None:
    world["params"]["N1"] = {"z_thresh": 2.0}
    world["params"]["N2"] = {"lookback": 5}
    _write(world["handoff"], [_row("N1", "never_fires", family="fam_z"),
                              _row("N2", "too_rare"), _row("N3", "build_input_missing")])
    doc = world["run"]()
    assert "awaiting_multiple_testing_budget" not in doc
    assert doc["counts"]["never_fires"] == {C.CONVERTED: 1}
    assert doc["counts"]["too_rare"] == {C.CONVERTED: 1}
    assert doc["counts"]["build_input_missing"] == {C.AWAITING_INPUT: 1}
    assert doc["accounting"]["every_row_accounted"] is True


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


# ---- never_fires -> relaxed_threshold ---------------------------------------------------------

def test_never_fires_mints_two_relaxed_children_along_the_family_grid(
        world: dict[str, Any]) -> None:
    world["params"]["N1"] = {"z_thresh": 2.0, "rr": 2.0}
    _write(world["handoff"], [_row("N1", "never_fires", family="fam_z", symbol="EURUSD")])
    doc = world["run"]()
    (fam, cands, tests_run), = world["donations"]
    assert fam == "fam_z" and tests_run == 2 and len(cands) == 2
    # the next grid step toward firing, then the loosest grid value; rr (an exit) untouched
    assert [c["params"]["z_thresh"] for c in cands] == [1.5, 1.0]
    assert all(c["params"]["rr"] == 2.0 for c in cands)
    assert all(c["symbol"] == "EURUSD" and c["family"] == "fam_z" for c in cands)
    assert all(c["lineage"]["parent_cell"] == "N1" for c in cands)
    assert all(c["lineage"]["route"] == C.ROUTE_RELAXED for c in cands)
    (rec,) = _ledger(world)
    assert rec["status"] == C.CONVERTED and rec["trials_charged"] == 2
    assert rec["child_ids"] == [c["cell"] for c in cands]
    assert doc["conversions"]["this_pass"] == {"never_fires": {"fam_z": 2}}


def test_never_fires_with_no_relaxable_param_is_not_convertible_and_counted(
        world: dict[str, Any]) -> None:
    world["params"]["X1"] = {"rr": 2.0}
    world["params"]["X2"] = {"lookback": 3}
    _write(world["handoff"], [_row("X1", "never_fires", family="fam_exit_only"),
                              _row("X2", "never_fires", family="carry")])
    doc = world["run"]()
    assert world["donations"] == []
    led = _ledger(world)
    assert {r["status"] for r in led} == {C.NOT_CONVERTIBLE}
    assert all("no relaxable entry param" in r["why"] for r in led)
    assert doc["counts"]["never_fires"] == {C.NOT_CONVERTIBLE: 2}
    assert sum(doc["not_convertible_reasons"].values()) == 2


def test_relaxation_directions() -> None:
    kids, _ = C.relaxed_children({"lo_q": 0.05, "hi_q": 0.95},
                                 {"lo_q": [0.05, 0.1], "hi_q": [0.9, 0.95]})
    assert [(k["param"], k["to"]) for k in kids] == [("hi_q", 0.9), ("lo_q", 0.1)]
    kids, _ = C.relaxed_children({"dispersion": "high"}, {"dispersion": ["any", "high"]})
    assert [k["to"] for k in kids] == ["any"]
    kids, why = C.relaxed_children({"z_thresh": 1.0}, {"z_thresh": [1.0, 2.0]})
    assert kids == [] and "no relaxable" in str(why)


# ---- too_rare -> coarser_timeframe / cross_sectional_pool -----------------------------------

def test_too_rare_goes_one_rung_up_the_chart_ladder(world: dict[str, Any]) -> None:
    world["params"]["R1"] = {"lookback": 7}
    _write(world["handoff"], [_row("R1", "too_rare", family="carry", symbol="EURUSD")])
    world["run"]()
    (_fam, cands, n), = world["donations"]
    assert n == 1 and cands[0]["timeframe"] == "H4"
    assert cands[0]["params"] == {"lookback": 7, "timeframe": "H4"}
    assert cands[0]["symbol"] == "EURUSD" and cands[0]["lineage"]["route"] == C.ROUTE_COARSER
    assert cands[0]["cell"] == C._cell_id("EURUSD", "carry", cands[0]["params"], "H4")
    assert cands[0]["cell"].startswith("EURUSD@H4.")


def test_too_rare_in_a_class_book_pools_onto_a_same_class_peer(world: dict[str, Any]) -> None:
    fam = "cross_sectional_class_momentum"
    world["params"]["R2"] = {"lookback_d": 20}
    world["params"]["R3"] = {"lookback_d": 20}
    _write(world["handoff"], [_row("R2", "too_rare", family=fam, symbol="NEWCO"),
                              _row("R3", "too_rare", family="momentum", symbol="NEWCO")])
    world["run"]()
    (got, cands, n), = world["donations"]
    assert got == fam and n == 1
    assert cands[0]["symbol"] == "AAPL" and cands[0]["lineage"]["route"] == C.ROUTE_POOL
    led = {r["cell"]: r for r in _ledger(world)}
    # the two-lane law: a share CFD outside the class books is never converted
    assert led["R3"]["status"] == C.NOT_CONVERTIBLE and "two-lane" in led["R3"]["why"]


# ---- build_input_missing -> data-gap report and retry ---------------------------------------

def _gap_row(cell: str, inputs: list[str]) -> dict[str, Any]:
    r = _row(cell, "build_input_missing", family="carry", symbol="EURUSD")
    r["missing_input"] = {"kind": "inputs", "inputs": inputs}
    r.pop("why")
    return r


def test_build_input_missing_is_a_ranked_gap_then_converts_when_the_input_exists(
        world: dict[str, Any]) -> None:
    world["params"]["G1"] = {"lookback": 9}
    _write(world["handoff"], [_gap_row("G1", ["bars:GBPJPY_H1.parquet"]),
                              _gap_row("G2", ["bars:GBPJPY_H1.parquet", "surface:XAUUSD"]),
                              _gap_row("G3", ["surface:XAUUSD"])])
    d1 = world["run"]()
    assert world["donations"] == [] and d1["trials_charged"]["this_pass"] == 0
    assert d1["counts"]["build_input_missing"] == {C.AWAITING_INPUT: 3}
    gaps = json.loads((world["tmp"] / "BUILD_INPUT_GAPS.json").read_text("utf-8"))
    assert sorted((g["input"], g["cells_blocked"]) for g in gaps["ranked"]) == [
        ("bars:GBPJPY_H1.parquet", 2), ("surface:XAUUSD", 2)]
    assert gaps["build_input_missing_rows"] == 3
    assert all(r["next_step"] for r in _ledger(world))
    # inside 24h nothing is re-checked, and the rows stay retryable, not resolved
    world["present"]["bars:GBPJPY_H1.parquet"] = True
    d2 = world["run"]()
    assert d2["counts"]["build_input_missing"] == {C.AWAITING_INPUT: 3}
    assert world["donations"] == []
    # after 24h: G1's one input exists, so the same rule is minted and charged once
    world["now"] = NOW + timedelta(hours=25)
    d3 = world["run"]()
    (_fam, cands, n), = world["donations"]
    assert n == 1 and cands[0]["cell"] == C._cell_id("EURUSD", "carry", {"lookback": 9}, "H1")
    assert cands[0]["lineage"]["route"] == C.ROUTE_RESTORED
    assert d3["counts"]["build_input_missing"] == {C.CONVERTED: 1, C.AWAITING_INPUT: 2}


# ---- the trial budget ---------------------------------------------------------------------

def _capacity(root: Path, *, judged: int, sweep_s: float, created: int | None,
              at: str = "2026-11-11T00:00:00+00:00") -> None:
    (root / "JUDGING_THROUGHPUT.json").write_text(json.dumps(
        {"at": at, "status": "MEASURED", "queue": {"judged_last_sweep": judged}}), "utf-8")
    (root / "JUDGE_RESIDENT.json").write_text(json.dumps({"last_sweep_s": sweep_s}), "utf-8")
    if created is not None:
        (root / "JUDGING_RATE.json").write_text(json.dumps({"created_per_day": created}),
                                                "utf-8")


def test_budget_is_derived_from_the_measured_spare_capacity(tmp_path: Path) -> None:
    _capacity(tmp_path, judged=38_620, sweep_s=11_994.8, created=16_333)
    b = C.trial_budget(tmp_path, now=NOW)
    measured = int(38_620 * 86_400 / 11_994.8)
    assert b["status"] == "MEASURED" and b["capacity"]["per_day"] == measured
    assert b["per_day"] == measured - 16_333
    assert b["per_pass"] == -(-b["per_day"] // 24)          # 24 passes left at 00:30 UTC
    # what was charged today comes off the top, spread over the passes left
    late = C.trial_budget(tmp_path, now=NOW.replace(hour=22), charged_today=1_000)
    assert late["per_pass"] == -(-(b["per_day"] - 1_000) // 2)


def test_a_measured_rate_below_the_judge_floor_is_never_fed_past_capacity(tmp_path: Path) -> None:
    """The floor is the judge's target, not its capacity: a child is charged at donation, so
    feeding above capacity would raise every lane's bar with cells nobody tests."""
    _capacity(tmp_path, judged=100_000, sweep_s=86_400.0, created=10_000)
    b = C.trial_budget(tmp_path, now=NOW)
    assert b["capacity_per_day"] == 100_000 and b["per_day"] == 90_000
    assert b["judge_gap_per_day"] == C.JUDGE_VOLUME_FLOOR_PER_DAY - 100_000


def test_absent_or_stale_capacity_is_unmeasured_with_the_fallback(
        tmp_path: Path, world: dict[str, Any]) -> None:
    b = C.trial_budget(tmp_path, now=NOW)
    assert b["status"] == C.UNMEASURED and b["per_day"] == C.FALLBACK_TRIALS_PER_DAY
    assert "UNMEASURED" in b["basis"]
    _capacity(tmp_path, judged=38_620, sweep_s=11_994.8, created=0,
              at="2026-10-01T00:00:00+00:00")
    assert C.trial_budget(tmp_path, now=NOW)["status"] == C.UNMEASURED
    _write(world["handoff"], [])
    doc = world["run"]()
    assert doc["trial_budget"]["status"] == C.UNMEASURED
    assert doc["trial_budget"]["applied_per_pass"] == C.FALLBACK_TRIALS_PER_DAY // 24


def test_the_pass_takes_the_measured_budget(world: dict[str, Any]) -> None:
    _capacity(world["capacity"], judged=38_620, sweep_s=11_994.8, created=16_333)
    _write(world["handoff"], [])
    doc = world["run"]()
    tb = doc["trial_budget"]
    assert tb["status"] == "MEASURED" and tb["applied_per_pass"] == tb["per_pass"] > 10_000
    assert doc["projection"]["budget_per_day"] == tb["per_day"]


def test_round_robin_keeps_the_big_family_from_starving_the_small_one(
        world: dict[str, Any]) -> None:
    rows = []
    for i in range(10):
        world["params"][f"A{i}"] = {"z_thresh": 2.0, "k": i}
        rows.append(_row(f"A{i}", "never_fires", family="fam_z", symbol="EURUSD"))
    for i in range(2):
        world["params"][f"B{i}"] = {"lookback": i}
        rows.append(_row(f"B{i}", "too_rare", family="carry", symbol="EURUSD"))
    _write(world["handoff"], rows)
    doc = world["run"](max_per_pass=6)
    charged = {fam: n for fam, _, n in world["donations"]}
    # both of the small family's rows convert in the same pass the big one is capped in
    assert charged == {"carry": 2, "fam_z": 4}
    assert doc["counts"]["too_rare"] == {C.CONVERTED: 2}
    assert doc["counts"]["never_fires"][C.DEFERRED_BUDGET] == 8
    assert doc["deferred_backlog"]["by_reason"] == {"never_fires": 8}
    assert doc["projection"]["backlog_trials_by_reason"] == {"never_fires": 16}
    assert C.round_robin({"a": [1, 2, 3], "b": [9]}, 3) == [1, 9, 2]  # type: ignore[list-item]


def test_trials_are_charged_per_family_through_one_donation_each(world: dict[str, Any]) -> None:
    world["params"]["N1"] = {"z_thresh": 2.5}
    world["params"]["S1"] = {"lookback": 20}
    world["params"]["R1"] = {"lookback": 4}
    _write(world["handoff"], [_row("N1", "never_fires", family="fam_z", symbol="EURUSD"),
                              _row("S1", "short_history_after_cut", family="carry"),
                              _row("R1", "too_rare", family="carry", symbol="GBPUSD")])
    doc = world["run"]()
    by_fam = {fam: (len(c), n) for fam, c, n in world["donations"]}
    assert by_fam == {"fam_z": (2, 2), "carry": (2, 2)}      # one file per family, exact count
    assert doc["trials_charged"]["this_pass_by_family"] == {"carry": 2, "fam_z": 2}
    assert doc["conversions"]["this_pass"] == {
        "never_fires": {"fam_z": 2}, "short_history_after_cut": {"carry": 1},
        "too_rare": {"carry": 1}}
    led = _ledger(world)
    assert sum(r["trials_charged"] for r in led) == 4
    again = world["run"]()                                    # nothing is ever charged twice
    assert again["trials_charged"]["this_pass"] == 0
    assert again["trials_charged"]["lifetime"] == 4


def test_an_unknown_reason_is_counted_unhandled_never_skipped(world: dict[str, Any]) -> None:
    _write(world["handoff"], [_row("U1", "brand_new_reason"), _row("U2", "brand_new_reason"),
                              _row("L1", "lockbox_consumed_history")])
    doc = world["run"]()
    assert doc["counts"]["brand_new_reason"] == {C.UNHANDLED_REASON: 2}
    assert doc["unhandled_reasons"]["rows"] == 2
    assert doc["unhandled_reasons"]["by_reason"] == {"brand_new_reason": 2}
    assert doc["accounting"]["every_row_accounted"] is True
    assert doc["accounting"]["rows_read"] == 3


STEER = [{"name": "gold", "symbol_prefixes": ["XAU"]},
         {"name": "indices", "asset_classes": ["indices", "index"]},
         {"name": "usd_jpy_eur_crosses", "currency_set": ["USD", "JPY", "EUR"]},
         {"name": "asia_window", "text_tokens": ["asia", "tokyo", "sydney"]}]


def test_steer_groups_name_gold_indices_the_three_crosses_and_asia() -> None:
    from research import conversion_handoff_steer as S
    cls = {"US500": "indices", "GER40": "indices"}.get

    def g(sym: str, family: str = "carry") -> str:
        return S.steer_group({"symbol": sym, "family": family, "cell": "c"}, STEER,
                             lambda s: cls(s) or "forex")

    assert g("XAUUSD") == "gold" and g("XAUEUR") == "gold"
    assert g("US500") == "indices" and g("GER40") == "indices"
    assert g("USDJPY") == g("EURUSD") == g("EURJPY") == "usd_jpy_eur_crosses"
    assert g("USDNOK") == g("USDCHF") == S.UNSTEERED
    assert g("USDNOK", family="asia_range_fade") == "asia_window"
    # the repository's steer file carries the same four groups, in this order
    assert [x["name"] for x in S.load_steer()] == [x["name"] for x in STEER]
    assert S.load_steer(Path("/nonexistent/steer.json")) == []


def test_the_steer_serves_the_cross_first_and_reports_breadth_per_class(
        world: dict[str, Any]) -> None:
    for cell, sym in (("P0", "USDNOK"), ("P1", "EURUSD")):
        world["params"][cell] = {"lookback": 20}
    _write(world["handoff"], [_row("P0", "short_history_after_cut", symbol="USDNOK"),
                              _row("P1", "short_history_after_cut", symbol="EURUSD")])
    doc = world["run"](max_per_pass=1, steer=STEER)
    (rec,) = [r for r in _ledger(world) if r["status"] == C.CONVERTED]
    assert rec["cell"] == "P1"                       # the steered cross went first
    b = doc["breadth"]
    assert b["steer"] == [x["name"] for x in STEER]
    assert b["selected_by_group"] == {"unsteered": 1, "usd_jpy_eur_crosses": 1}
    assert b["converted_by_steer_group"] == {"usd_jpy_eur_crosses": {"parents": 1,
                                                                     "child_cells": 1}}
    assert b["converted_by_asset_class"] == {"forex": {"parents": 1, "child_cells": 1}}
    # nothing dropped: the unsteered row is deferred, then converted on the next pass
    assert doc["counts"]["short_history_after_cut"] == {C.CONVERTED: 1, C.DEFERRED_BUDGET: 1}
    world["run"](max_per_pass=1, steer=STEER)
    assert sorted(r["cell"] for r in _ledger(world) if r["status"] == C.CONVERTED) == ["P0", "P1"]


def test_an_empty_steer_keeps_the_old_order(world: dict[str, Any]) -> None:
    for cell in ("P0", "P1"):
        world["params"][cell] = {"lookback": 20}
    _write(world["handoff"], [_row("P0", "short_history_after_cut", symbol="USDNOK"),
                              _row("P1", "short_history_after_cut", symbol="EURUSD")])
    doc = world["run"](max_per_pass=1, steer=[])
    (rec,) = [r for r in _ledger(world) if r["status"] == C.CONVERTED]
    assert rec["cell"] == "P0"
    assert doc["breadth"]["selected_by_group"] == {"unsteered": 2}
