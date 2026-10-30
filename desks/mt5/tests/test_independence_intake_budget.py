"""THE BUDGET IS THE WHOLE RUN'S, AND THE GRID IS THE WHOLE REGISTRY'S (2026-10-29).

`MT5-IndependenceIntake` sat in `Running` for 100+ minutes on a 600 s budget because only the
filler looked at the clock, and the filler aimed at 291 cells and created none because the grid
was built from the first 400,000 registry rows. These pin both repairs by behaviour.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.ops.run_budget import RunBudget  # noqa: E402
from research import independence_intake as ii  # noqa: E402

_COLS = ("family TEXT, symbol TEXT, horizon TEXT, content_hash TEXT, mechanism TEXT, "
         "params_json TEXT, origin TEXT, generator TEXT, producer TEXT, discovery_id TEXT, "
         "region TEXT")


def _ago(seconds: float, now: datetime | None = None) -> str:
    t = (now or datetime.now(tz=UTC)) - timedelta(seconds=seconds)
    return t.isoformat(timespec="seconds")


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _db(tmp_path: Path, rows: list[tuple[Any, ...]]) -> Path:
    path = tmp_path / "registry.sqlite"
    con = sqlite3.connect(path)
    con.execute(f"create table research_candidates(seq INTEGER PRIMARY KEY AUTOINCREMENT, {_COLS})")
    _add(path, rows, con)
    con.close()
    return path


def _add(path: Path, rows: list[tuple[Any, ...]], con: sqlite3.Connection | None = None) -> None:
    c = con or sqlite3.connect(path)
    c.executemany("insert into research_candidates(family, symbol, horizon, content_hash, "
                  "mechanism, params_json, origin, generator, producer, discovery_id, region) "
                  "values(?,?,?,?,?,?,?,?,?,?,?)", rows)
    c.commit()
    if con is None:
        c.close()


def _row(fam: str, sym: str, hor: str, h: str, *, mech: str = "m", params: str = '{"b": 1}',
         origin: str = "miner", gen: str = "gen") -> tuple[Any, ...]:
    return (fam, sym, hor, h, mech, params, origin, gen, "prod", None, None)


def test_the_census_sees_every_row_the_bounded_read_missed(tmp_path: Path,
                                                          monkeypatch: Any) -> None:
    """THE 291-AIMED-0-CREATED ROOT CAUSE. `_rows` reads `LIMIT MAX_ROWS` with no order; every
    cell past that row -- every transplant this organ ever minted, on a 740k-row registry -- was
    invisible to the grid, so the filler re-aimed at ground it had already filled."""
    rows = [_row("carry", "eurusd", "sub_4h", "h1"), _row("carry", "eurusd", "sub_4h", "h2"),
            _row("carry", "xauusd", "sub_4h", "h3", origin=ii.SOURCE)]
    db = _db(tmp_path, rows)
    monkeypatch.setattr(ii, "MAX_ROWS", 2)
    bounded, _ = ii._rows(db)
    assert {f"{f}|{s}|{h}" for f, s, h, _, _ in bounded} == {"carry|eurusd|sub_4h"}
    cen = ii.census(db, path=tmp_path / "census.json")
    assert cen["complete"] and cen["rows"] == 3
    assert cen["cells"] == {"carry|eurusd|sub_4h", "carry|xauusd|sub_4h"}
    monkeypatch.setattr(ii, "_axes", lambda: (["eurusd", "xauusd"], ["carry"], ["sub_4h"], {}))
    grid = ii.grid_occupancy([], mintable={"carry"}, occupied=cen["cells"])
    assert grid["reachable_empty_cells"] == 0, "the transplanted cell must read occupied"


def test_the_census_reads_only_what_is_new_and_nothing_when_nothing_is(tmp_path: Path) -> None:
    db = _db(tmp_path, [_row("carry", "eurusd", "sub_4h", f"h{i}") for i in range(5)])
    path = tmp_path / "census.json"
    first = ii.census(db, path=path)
    assert first["seq_read_this_pass"] == 5 and not first["reused"]
    again = ii.census(db, path=path)
    assert again["reused"] and again["seq_read_this_pass"] == 0 and again["rows"] == 5
    _add(db, [_row("trend", "xauusd", "multi_day", "h9")])
    third = ii.census(db, path=path)
    assert third["seq_read_this_pass"] == 1 and third["rows"] == 6
    assert "trend|xauusd|multi_day" in third["cells"]
    assert third["content_hashes"] == 6


def test_a_census_stopped_by_the_deadline_resumes_from_its_cursor(tmp_path: Path,
                                                                   monkeypatch: Any) -> None:
    monkeypatch.setattr(ii, "CENSUS_CHUNK", 2)
    db = _db(tmp_path, [_row("carry", f"s{i}", "sub_4h", f"h{i}") for i in range(7)])
    path = tmp_path / "census.json"
    clock = _Clock()
    rb = RunBudget(10.0, clock=clock)
    clock.t = 11.0                                       # the run's clock is already spent
    cut = ii.census(db, rb, path=path)
    assert cut["available"] and not cut["complete"] and cut["interrupted"]
    assert cut["cursor"] == 0
    whole = ii.census(db, path=path)
    assert whole["complete"] and whole["rows"] == 7 and len(whole["cells"]) == 7


def test_a_replaced_registry_rebuilds_the_census(tmp_path: Path) -> None:
    db = _db(tmp_path, [_row("carry", "eurusd", "sub_4h", f"h{i}") for i in range(4)])
    path = tmp_path / "census.json"
    ii.census(db, path=path)
    db.unlink()
    _db(tmp_path, [_row("trend", "xauusd", "sub_4h", "z")])
    cen = ii.census(db, path=path)
    assert cen["rebuilt"] and cen["rows"] == 1 and cen["cells"] == {"trend|xauusd|sub_4h"}


def test_the_census_donors_are_the_grouped_querys_donors(tmp_path: Path) -> None:
    """Two implementations of one rule are two rules unless a test holds them together."""
    rows = [_row("carry", "eurusd", "sub_4h", "a", params='{"b": 1}'),
            _row("carry", "gbpusd", "sub_4h", "b", params='{"b": 2}'),
            _row("carry", "xauusd", "sub_4h", "c", params='{"b": 3}', origin=ii.SOURCE),
            _row("trend", "eurusd", "multi_day", "d", params="{}"),
            _row("trend", "eurusd", "multi_day", "e", params='{"w": 5}', gen=ii.SOURCE),
            _row("mr", "usdjpy", "sub_4h", "f", params='{"z": 1}', mech="MR rule")]
    db = _db(tmp_path, rows)
    grouped = ii._donors(db)
    folded = ii.census_donors(ii.census(db, path=tmp_path / "census.json"))
    assert folded == grouped
    assert folded["carry"]["params"] == {"b": 2}         # the latest that is not this organ's
    assert "trend" not in folded


def test_the_census_ladder_and_gain_match_the_row_forms(tmp_path: Path) -> None:
    rows = [_row("carry", "eurusd", "sub_4h", "a", mech="x (mutation: step_band_up)"),
            _row("carry", "eurusd", "sub_4h", "b", mech="x (mutation: step_band_up)"),
            _row("carry", "xauusd", "sub_4h", "c", mech="x (mutation: condition_on_state)"),
            _row("trend", "eurusd", "multi_day", "d", mech="plain")]
    db = _db(tmp_path, rows)
    cen = ii.census(db, path=tmp_path / "census.json")
    full, _ = ii._rows(db)
    lad, ref = ii.census_ladder(cen), ii.dedup_ladder(full)
    for key in ("raw_cells", "content_hashes", "grid_cells", "mechanisms"):
        assert lad[key] == ref[key], key
    gain = ii.gain_from_sets(cen["gain_emitted"], cen["gain_cells"])
    assert gain == ii.orthogonality_gain(full)


def test_run_budget_skips_every_stage_after_the_deadline() -> None:
    clock = _Clock()
    rb = RunBudget(5.0, clock=clock)
    with rb.stage("a") as go:
        assert go
        clock.t = 6.0
    with rb.stage("b") as go:
        assert not go
    assert rb.skipped == ["b"] and rb.stages[0]["overran_deadline"]


def _isolate(tmp_path: Path, monkeypatch: Any) -> None:
    for name, fname in (("OUT", "INDEPENDENCE_INTAKE.json"), ("MIX", "mix.json"),
                        ("OCCUPANCY_RATCHET", "ratchet.json"), ("YIELD", "yield.json"),
                        ("COVERAGE", "coverage.json"), ("CENSUS", "census.json")):
        monkeypatch.setattr(ii, name, tmp_path / fname)
    monkeypatch.setattr(ii, "_axes", lambda: (["eurusd", "xauusd"], ["carry"], ["sub_4h"], {}))


def test_a_run_past_its_deadline_publishes_what_it_has_marked_partial(
        tmp_path: Path, monkeypatch: Any) -> None:
    """THE WHOLE RUN IS ON ONE CLOCK. A census that eats the budget leaves every later stage
    skipped and recorded, the fill is never run on an incomplete census, and the last measured
    grid is carried forward stamped stale so `empty_pairs` still has targets."""
    _isolate(tmp_path, monkeypatch)
    prev_grid = {"available": True, "targets": [{"family": "carry", "symbol": "xauusd"}]}
    ii.OUT.write_text(json.dumps({"generated_utc": _ago(900), "grid": prev_grid}),
                      encoding="utf-8")
    db = _db(tmp_path, [_row("carry", "eurusd", "sub_4h", "a")])
    clock = _Clock()
    rb = RunBudget(10.0, clock=clock)
    real = ii.census

    def _slow(*a: Any, **kw: Any) -> dict[str, Any]:
        out = real(*a, **kw)
        clock.t = 50.0                                   # the census overran the whole budget
        return out

    monkeypatch.setattr(ii, "census", _slow)
    monkeypatch.setattr(ii, "fill_empty_cells",
                        lambda *a, **kw: pytest.fail("the fill must not run past the deadline"))
    doc = ii.run(10.0, db=db, rb=rb)
    assert doc["partial"] and doc["verdict"] == "PARTIAL"
    skipped = set(doc["run_budget"]["skipped_stages"])
    assert {"grid", "fill", "headline", "intake", "ratchet"} <= skipped
    assert doc["grid"]["stale"] and doc["grid"]["targets"] == prev_grid["targets"]
    assert "grid" in doc["carried_blocks"]
    assert doc["fill"]["available"] is False
    ii.OUT.write_text(json.dumps(doc, default=str), encoding="utf-8")
    assert ii.empty_pairs(ii.OUT) == {"carry|xauusd"}


def test_an_incomplete_census_never_feeds_the_grid_or_the_fill(tmp_path: Path,
                                                               monkeypatch: Any) -> None:
    _isolate(tmp_path, monkeypatch)
    db = _db(tmp_path, [_row("carry", "eurusd", "sub_4h", "a")])
    monkeypatch.setattr(ii, "census", lambda *a, **kw: {
        "available": True, "complete": False, "cursor": 0, "max_seq": 1, "rows": 0,
        "cells": set(), "interrupted": "deadline"})
    monkeypatch.setattr(ii, "fill_empty_cells",
                        lambda *a, **kw: pytest.fail("an incomplete census must not be filled"))
    doc = ii.run(600.0, db=db)
    assert doc["partial"] and doc["grid"]["available"] is False
    assert any("census incomplete" in r for r in doc["partial_reasons"])


def test_the_filler_sees_every_target_the_artifact_slices(tmp_path: Path,
                                                          monkeypatch: Any) -> None:
    """THE REPORT IS TRUNCATED, THE WORK IS NOT -- and the filler is handed the census's donors,
    so the whole candidate table is never grouped a second time inside one run."""
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(ii, "MAX_TARGETS", 1)
    db = _db(tmp_path, [_row("carry", "gbpusd", "sub_4h", "a")])
    seen: dict[str, Any] = {}

    def _fill(grid: dict[str, Any], **kw: Any) -> dict[str, Any]:
        seen["targets"] = len(grid["targets"])
        seen["donors"] = kw.get("donors")
        seen["budget_s"] = kw.get("budget_s")
        return {"available": True, "occupied_cells_after": 1}

    monkeypatch.setattr(ii, "fill_empty_cells", _fill)
    monkeypatch.setattr(ii, "_donors", lambda db=None: pytest.fail("donors re-grouped"))
    doc = ii.run(600.0, db=db)
    assert seen["targets"] == 2 and len(doc["grid"]["targets"]) == 1
    assert set(seen["donors"]) == {"carry"}
    assert 0 < seen["budget_s"] < 600.0
    assert not doc["partial"] and doc["verdict"] in ("MEASURED", ii.UNMEASURED)


def test_main_declares_its_deadline_to_the_job_broker(tmp_path: Path, monkeypatch: Any) -> None:
    from research import job_lock
    monkeypatch.setattr(job_lock, "LOCK_ROOT", tmp_path / ".job_locks")
    ii.declare_to_broker(600.0, 120.0)
    doc = json.loads((tmp_path / ".job_locks" / f"{ii.JOB_NAME}.peaks.json").read_text("utf-8"))
    assert doc["declared"]["deadline_s"] == 720.0 and doc["declared"]["cpu"] == 1


def test_the_watchdog_fires_inside_the_tasks_own_limit() -> None:
    """MT5-IndependenceIntake: --budget-s 600 under a 20-minute ExecutionTimeLimit. The organ's
    own stop (budget + grace) must land before the scheduler's, or the scheduler is the stop."""
    src = (_DESK / "scripts" / "install_independence_intake_task.ps1").read_text("utf-8")
    assert "--budget-s 600" in src and "-Minutes 20" in src
    grace = max(ii.WATCHDOG_MIN_GRACE_S, ii.WATCHDOG_GRACE_SHARE * 600)
    assert 600 + grace < 20 * 60


def test_a_second_pass_never_re_aims_at_cells_the_first_pass_filled(tmp_path: Path,
                                                                    monkeypatch: Any) -> None:
    """END TO END ON THE REAL REGISTRY DOOR, with the old 400k bound shrunk to one row. Before
    the census the second pass re-aimed at every cell the first had filled and created nothing;
    now it aims at none of them."""
    import libs.moat.registry as reg
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(reg, "_PATH", tmp_path / "alpha_registry.sqlite")
    monkeypatch.setattr(reg, "BACKUP", tmp_path / "no_backup")
    monkeypatch.setattr(ii, "REGISTRY", tmp_path / "alpha_registry.sqlite")
    monkeypatch.setattr(ii, "MAX_ROWS", 1)
    monkeypatch.setattr(ii, "_symbol_case", lambda: {"eurusd": "EURUSD", "xauusd": "XAUUSD"})
    monkeypatch.setattr(ii, "_axes", lambda: (["eurusd", "xauusd"], ["carry"],
                                              ["sub_4h", "multi_day"], {}))
    con = reg.connect()
    try:
        reg.enqueue_candidate(family="carry", symbol="EURUSD", params={"band": 0.2},
                              origin="miner", horizon="sub_4h", conn=con, mechanism="carry")
    finally:
        con.close()
    first = ii.run(120.0)
    assert first["fill"]["cells_created_in_empty_cells"] == 3
    second = ii.run(120.0)
    assert second["grid"]["reachable_empty_cells"] == 0
    assert second["fill"].get("already_present", 0) == 0
    assert second["census"]["seq_read_this_pass"] == 3        # only the three new rows read


# ---- audit HOLD, 2026-10-29 -------------------------------------------------------------------


def _partial_doc() -> dict[str, Any]:
    return {"verdict": "PARTIAL", "partial": True, "partial_reasons": ["deadline"]}


def test_a_run_stopped_on_its_own_deadline_exits_a_named_failure(tmp_path: Path,
                                                                 monkeypatch: Any) -> None:
    """MUST-FIX 1: the artifact said PARTIAL while main returned 0, so LastTaskResult and the
    hourly ledger recorded success for a run that never finished. It exits EXIT_PARTIAL, and the
    cycle's ledger names it."""
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(ii, "declare_to_broker", lambda *a: None)
    monkeypatch.setattr(ii, "_record_peak", lambda: None)
    import libs.ops.events as events
    monkeypatch.setattr(events, "emit", lambda *a, **kw: None)     # never the live event log
    monkeypatch.delenv("QUANT_LEG_BUDGET_S", raising=False)
    monkeypatch.setattr(ii, "run", lambda **kw: _partial_doc())
    assert ii.main(["--once", "--budget-s", "5"]) == ii.EXIT_PARTIAL
    assert ii.EXIT_PARTIAL not in (0, 1, 2, 124)
    assert json.loads(ii.OUT.read_text("utf-8"))["verdict"] == "PARTIAL"
    monkeypatch.setattr(ii, "run", lambda **kw: {"verdict": "MEASURED", "partial": False})
    assert ii.main(["--once", "--budget-s", "5"]) == 0

    from research import hourly_cycle as hc
    assert hc._exit_outcome("independence_intake", ii.EXIT_PARTIAL) == "exit_code=3:PARTIAL"
    assert ii.EXIT_PARTIAL not in hc.VERDICT_EXITS.get("independence_intake", ())
    from libs.ops.run_budget import EXIT_OVERRUN
    assert hc._exit_outcome("independence_intake", EXIT_OVERRUN).endswith(":OVERRAN")


def test_a_block_carried_twice_keeps_the_time_it_was_measured() -> None:
    """MUST-FIX 2: every partial pass restamped the carried block with the previous artifact's
    time, so after N partial runs a block days old read one pass old."""
    now = datetime.now(tz=UTC)
    measured = _ago(3600, now)
    grid = {"available": True, "targets": [{"family": "carry", "symbol": "xauusd"}]}
    first: dict[str, Any] = {}
    assert ii._carry(first, {"generated_utc": measured, "grid": grid}, now=now) == ["grid"]
    assert first["grid"]["carried_from_generated_utc"] == measured
    # The next partial pass carries the block the first one carried, from a newer artifact.
    second: dict[str, Any] = {}
    prev = {"generated_utc": _ago(900, now), "grid": first["grid"]}
    assert ii._carry(second, prev, now=now) == ["grid"]
    assert second["grid"]["carried_from_generated_utc"] == measured
    assert second["grid"]["carried_age_s"] == pytest.approx(3600, abs=1)


def test_a_carried_block_past_the_age_cap_reads_unmeasured() -> None:
    now = datetime.now(tz=UTC)
    measured = _ago(ii.CARRY_MAX_AGE_S + 60, now)
    old = {"available": True, "stale": True, "carried_from_generated_utc": measured,
           "targets": [{"family": "carry", "symbol": "xauusd"}]}
    blocks: dict[str, Any] = {}
    carried = ii._carry(blocks, {"generated_utc": _ago(900, now), "grid": old}, now=now)
    assert carried == []
    assert blocks["grid"]["available"] is False
    assert blocks["grid"]["why"].startswith(ii.UNMEASURED)
    assert blocks["grid"]["last_measured_utc"] == measured
    assert "targets" not in blocks["grid"]


def test_budget_s_must_be_positive(monkeypatch: Any) -> None:
    monkeypatch.setattr(ii, "run", lambda **kw: pytest.fail("a refused budget must not run"))
    for bad in ("0", "-5", "nan"):
        with pytest.raises(SystemExit) as exc:
            ii.main(["--once", "--budget-s", bad])
        assert exc.value.code == 2


def test_under_the_leg_cap_the_watchdog_stops_inside_the_kill() -> None:
    """The hourly leg runs --budget-s 240 under a 300 s cap: 240 + 48 s of grace left 12 s for
    the partial publish and exit. The budget is cut so budget + grace sits LEG_CAP_MARGIN_S in."""
    for cap in (300.0, 120.0, 1000.0):
        b = ii.effective_budget_s(240.0, {"QUANT_LEG_BUDGET_S": str(cap)})
        assert b <= 240.0
        assert b + ii._grace_s(b) <= cap - ii.LEG_CAP_MARGIN_S + 1e-9
    assert ii.effective_budget_s(240.0, {"QUANT_LEG_BUDGET_S": "1000"}) == 240.0
    assert ii.effective_budget_s(600.0, {}) == 600.0               # MT5-IndependenceIntake
    from research import hourly_cycle as hc
    cap = float(hc.LEG_BUDGET_SEC["independence_intake"])           # the leg's base cap
    b = ii.effective_budget_s(240.0, {"QUANT_LEG_BUDGET_S": str(cap)})
    assert b + ii._grace_s(b) + ii.LEG_CAP_MARGIN_S <= cap
