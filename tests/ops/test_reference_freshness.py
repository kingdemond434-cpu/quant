"""NOTHING IS RETIRED ON AN ABSENCE (LAWS 7) -- the behaviour, not the wording.

Every test here plants a reference and asserts what a DESTRUCTIVE PASS does with it, because the
law is about removals and not about a verdict string. The four shapes the incident taught:

  * an EMPTY reference stands the pass down and removes nothing,
  * a STALE reference does the same,
  * a FRESH reference still allows the removal (the law must not become a brake -- growth
    governance: a guard that also blocks the legitimate case has bought nothing),
  * an UNREADABLE reference is UNMEASURED and is never a licence to remove,

and the fifth that makes the first four operable: the stand-down is RECORDED where an operator
meets it without asking.

No test writes a tracked file: the stand-down log is redirected with the module's own env override
and every reference is planted under tmp_path.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.ops import reference_freshness as rf

CANON = "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json"


@pytest.fixture(autouse=True)
def _isolated_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    log = tmp_path / "standdowns.jsonl"
    monkeypatch.setenv("QUANT_REFERENCE_STANDDOWN_LOG", str(log))
    return log


def _plant(tmp_path: Path, rows: int, *, age_h: float = 0.0, name: str = "ref.json") -> Path:
    p = tmp_path / name
    stamp = (datetime.now(tz=UTC) - timedelta(hours=age_h)).isoformat(timespec="seconds")
    p.write_text(json.dumps({
        "n": rows, "swept_at": stamp,
        "survivors": {f"k{i}": {"sym": "XAUUSD"} for i in range(rows)},
    }), encoding="utf-8")
    return p


# --------------------------------------------------------------------------- a fake destructive
# pass, written exactly the way a real one is, so the tests exercise the contract and not a mock.

def _sweep(reference: Path, store: dict[str, dict], *, lease_s: float | None = None,
           min_rows: int = 1) -> dict:
    """Remove every row the reference does not back -- the certificate_truth shape, guarded."""
    state = rf.require_live_reference(
        reference, actor="test.sweep", action="remove rows the reference does not back",
        min_rows=min_rows, lease_s=lease_s)
    if not state.live:
        return rf.stand_down(state, actor="test.sweep", action="remove unbacked rows")
    try:
        backed = set(json.loads(reference.read_text(encoding="utf-8"))["survivors"])
    except (OSError, ValueError, KeyError):  # pragma: no cover - guarded above
        backed = set()
    removed = [k for k in list(store) if k not in backed]
    for k in removed:
        del store[k]
    return {"stood_down": False, "removed": len(removed)}


# --------------------------------------------------------------------------- the four shapes

def test_empty_reference_stands_the_pass_down_and_removes_nothing(tmp_path: Path) -> None:
    ref = _plant(tmp_path, 0)
    store = {f"row{i}": {} for i in range(837)}          # the incident's own row count
    out = _sweep(ref, store, lease_s=7200.0)
    assert out["stood_down"] is True
    assert out["removed"] == 0
    assert len(store) == 837, "an empty reference retired the store"
    assert out["verdict"] == rf.EMPTY
    assert "says nothing" in out["why"]


def test_stale_reference_stands_the_pass_down_and_removes_nothing(tmp_path: Path) -> None:
    # Non-empty, so ONLY the age can refuse it -- 46.7h, the measured age of the canon.
    ref = _plant(tmp_path, 7, age_h=46.7)
    store = {"row0": {}, "k0": {}}
    out = _sweep(ref, store, lease_s=7200.0)
    assert out["stood_down"] is True
    assert out["verdict"] == rf.STALE
    assert len(store) == 2
    assert out["age_s"] is not None and out["age_s"] > 7200.0


def test_fresh_reference_still_allows_the_removal(tmp_path: Path) -> None:
    ref = _plant(tmp_path, 3)
    store = {"k0": {}, "k1": {}, "k2": {}, "orphan": {}}
    out = _sweep(ref, store, lease_s=7200.0)
    assert out["stood_down"] is False
    assert out["removed"] == 1
    assert set(store) == {"k0", "k1", "k2"}, "the guard must not block a backed removal"


def test_unreadable_reference_is_unmeasured_and_never_a_licence(tmp_path: Path) -> None:
    ref = tmp_path / "ref.json"
    ref.write_text("{not json at all", encoding="utf-8")
    store = {"row0": {}, "row1": {}}
    out = _sweep(ref, store, lease_s=7200.0)
    assert out["stood_down"] is True
    assert out["verdict"] == rf.UNREADABLE
    assert len(store) == 2


def test_missing_reference_is_unmeasured_and_never_a_licence(tmp_path: Path) -> None:
    store = {"row0": {}}
    out = _sweep(tmp_path / "never_written.json", store, lease_s=7200.0)
    assert out["stood_down"] is True
    assert out["verdict"] == rf.MISSING
    assert len(store) == 1


def test_stump_floor_refuses_a_truncated_reference(tmp_path: Path) -> None:
    """FRESH AND NON-EMPTY IS STILL NOT ENOUGH when the desk has declared a floor: a 23-symbol
    registry is a collector outage wearing a young mtime."""
    ref = _plant(tmp_path, 23)
    store = {"row0": {}}
    out = _sweep(ref, store, lease_s=7200.0, min_rows=50)
    assert out["stood_down"] is True
    assert out["verdict"] == rf.EMPTY and out["rows"] == 23
    assert len(store) == 1


# --------------------------------------------------------------------------- the recording

def test_stand_down_is_recorded_where_an_operator_sees_it(tmp_path: Path,
                                                          _isolated_log: Path) -> None:
    ref = _plant(tmp_path, 0)
    _sweep(ref, {"row0": {}}, lease_s=7200.0)
    rows = rf.stand_downs()
    assert len(rows) == 1
    row = rows[0]
    assert row["actor"] == "test.sweep"
    assert row["removed"] == 0
    assert row["verdict"] == rf.EMPTY
    assert row["law"].startswith("LAWS 7")
    assert _isolated_log.exists(), "the operator-visible log was not written"


def test_recording_failure_never_turns_a_refusal_into_a_deletion(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Telemetry is best-effort BY DESIGN. An unwritable log must not propagate an exception into
    a pass whose only correct behaviour is to remove nothing."""
    monkeypatch.setenv("QUANT_REFERENCE_STANDDOWN_LOG",
                       str(tmp_path / "no_such_dir" / "x" / "log.jsonl"))
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError("read-only")))
    ref = _plant(tmp_path, 0)
    store = {"row0": {}}
    out = _sweep(ref, store, lease_s=7200.0)
    assert out["stood_down"] is True
    assert len(store) == 1


def test_strict_mode_raises_with_the_state_attached(tmp_path: Path) -> None:
    ref = _plant(tmp_path, 0)
    with pytest.raises(rf.ReferenceNotLive) as exc:
        rf.require_live_reference(ref, actor="t", action="a", lease_s=7200.0, strict=True)
    assert exc.value.state.verdict == rf.EMPTY
    assert exc.value.state.live is False


# --------------------------------------------------------------------------- lease resolution

def test_lease_comes_from_the_registry_max_silence_when_declared(tmp_path: Path) -> None:
    registry = tmp_path / "COMPONENT_REGISTRY.json"
    ref = _plant(tmp_path, 4)
    registry.write_text(json.dumps({"freshness": [
        {"component_id": "leg:some_writer", "cadence_s": 3600, "max_silence_s": 9999,
         "outputs": [str(ref)]}]}), encoding="utf-8")
    lease, source, writer = rf.lease_for(ref, registry=registry)
    assert lease == 9999.0
    assert source == "registry:max_silence_s"
    assert writer == "leg:some_writer"


def test_lease_is_derived_from_cadence_and_the_derivation_is_recorded(tmp_path: Path) -> None:
    registry = tmp_path / "COMPONENT_REGISTRY.json"
    ref = _plant(tmp_path, 4)
    registry.write_text(json.dumps({"freshness": [
        {"component_id": "leg:hourly_writer", "cadence_s": 3600, "max_silence_s": None,
         "outputs": [str(ref)]}]}), encoding="utf-8")
    lease, source, writer = rf.lease_for(ref, registry=registry)
    assert lease == 7200.0, "two cadences is the desk's standing hourly rule"
    assert source.startswith("derived:cadence_s(3600s)"), source
    assert writer == "leg:hourly_writer"


def test_a_reference_with_no_lease_and_no_cadence_can_never_authorise_a_removal(
        tmp_path: Path) -> None:
    registry = tmp_path / "COMPONENT_REGISTRY.json"
    registry.write_text(json.dumps({"freshness": []}), encoding="utf-8")
    ref = _plant(tmp_path, 9)
    state = rf.assess_reference(ref, registry=registry)
    assert state.live is False
    assert state.verdict == rf.UNREADABLE
    assert state.lease_source == rf.UNMEASURED
    assert "never been decided" in state.why


def test_every_declared_lease_records_its_writer_and_its_derivation() -> None:
    """A derived lease is a finding, not a default: each row must name who writes the store and
    show the arithmetic, or it is a magic number in a table's clothes."""
    assert rf.DERIVED_LEASES, "the derived-lease table may not be empty"
    for path, (lease, organ, derivation, floor) in rf.DERIVED_LEASES.items():
        assert lease > 0, path
        assert organ and organ != rf.UNMEASURED, f"{path} names no writing organ"
        assert any(ch.isdigit() for ch in derivation), f"{path} shows no arithmetic"
        assert floor >= 1, path


# --------------------------------------------------------------------------- row counting

def test_row_count_never_trusts_a_self_declared_n(tmp_path: Path) -> None:
    """A truncated write is exactly the case where `n` and the container disagree."""
    p = tmp_path / "lying.json"
    p.write_text(json.dumps({"n": 837, "survivors": {}}), encoding="utf-8")
    rows, how = rf.count_rows(p)
    assert rows == 0, f"trusted the declared n ({how})"
    assert rf.assess_reference(p, lease_s=7200.0).verdict == rf.EMPTY


def test_row_count_reads_jsonl_and_sqlite(tmp_path: Path) -> None:
    jl = tmp_path / "ledger.jsonl"
    jl.write_text('{"a":1}\n\n{"a":2}\n', encoding="utf-8")
    assert rf.count_rows(jl)[0] == 2

    db = tmp_path / "store.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE claims (id TEXT)")
    con.executemany("INSERT INTO claims VALUES (?)", [("a",), ("b",), ("c",)])
    con.commit()
    con.close()
    assert rf.count_rows(db, rows_key="claims")[0] == 3


def test_content_stamp_outranks_mtime(tmp_path: Path) -> None:
    """A deploy, a formatter or a puller's revert rewrites a file and makes an mtime lie FRESH --
    the dangerous direction. The document's own stamp must win."""
    ref = _plant(tmp_path, 5, age_h=48.0)
    os.utime(ref, (time.time(), time.time()))           # a young mtime over an old document
    state = rf.assess_reference(ref, lease_s=7200.0)
    assert state.verdict == rf.STALE, "the young mtime was believed over the document's stamp"


# --------------------------------------------------------------------------- in-memory references

def test_an_empty_computed_reference_stands_a_sweep_down() -> None:
    state = rf.assess_rows("payloads", [], min_rows=1)
    assert state.live is False and state.verdict == rf.EMPTY


def test_an_unmeasured_computed_reference_is_unreadable_not_empty() -> None:
    state = rf.assess_rows("payloads", [], measured=False)
    assert state.verdict == rf.UNREADABLE
    assert "UNMEASURED" in state.why


def test_a_live_computed_reference_passes_through() -> None:
    assert rf.assess_rows("payloads", [1, 2, 3]).live is True


# --------------------------------------------------------------------------- the real call sites

def test_screen_conversion_removes_nothing_when_the_conversion_yields_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE WORST CASE FOUND: `convert_all` skips every source it cannot read, so one upstream
    outage used to unlink every converted screen on disk."""
    from libs.research import screen_conversion as sc

    out_dir = tmp_path / sc._AXIS_DIR
    out_dir.mkdir(parents=True)
    stale = out_dir / f"{sc.CONVERTED_PREFIX}axis_one.json"
    stale.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(sc, "convert_all",
                        lambda base: {"payloads": [], "skipped": [], "n_artifacts": 0,
                                      "n_cells": 0})
    result = sc.write_converted(tmp_path)
    assert stale.exists(), "an empty conversion deleted the whole canonical axis directory"
    assert result["removed_stale"] == []
    assert result["stood_down"]["removed"] == 0


def test_screen_conversion_still_sweeps_against_a_live_conversion(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.research import screen_conversion as sc

    out_dir = tmp_path / sc._AXIS_DIR
    out_dir.mkdir(parents=True)
    (out_dir / f"{sc.CONVERTED_PREFIX}gone.json").write_text("{}", encoding="utf-8")
    payload = {"axis": f"{sc.CONVERTED_PREFIX}live", "trials": []}
    monkeypatch.setattr(sc, "convert_all",
                        lambda base: {"payloads": [payload], "skipped": [], "n_artifacts": 1,
                                      "n_cells": 0})
    result = sc.write_converted(tmp_path)
    assert result["removed_stale"] == [f"{sc.CONVERTED_PREFIX}gone.json"]
    assert "stood_down" not in result


def _worker_registry(tmp_path: Path):  # type: ignore[no-untyped-def]
    from libs.ops import workers as w
    from libs.store.connection import Database

    db = Database(tmp_path / "workers.sqlite")
    with db.transaction() as conn:
        conn.execute("""CREATE TABLE workers (
            worker_id TEXT PRIMARY KEY, pid INTEGER, host TEXT, status TEXT,
            current_campaign TEXT, started_at TEXT, last_seen TEXT, campaigns_done INTEGER)""")
    return w.WorkerRegistry(db)


def test_workers_prune_stands_down_when_no_heartbeat_is_live(tmp_path: Path) -> None:
    """A dead stamper, a clock skew or a restore makes every row look stale at once."""
    reg = _worker_registry(tmp_path)
    reg.register("w1", pid=1, host="h")
    reg.register("w2", pid=2, host="h")
    # stale_seconds=0 makes every row stale at once -- the clock-skew / dead-stamper shape.
    assert reg.prune(stale_seconds=0) == 0, "pruned the whole fleet on a dead heartbeat"
    assert len(reg.all()) == 2
    rows = rf.stand_downs()
    assert rows and rows[-1]["actor"] == "workers.WorkerRegistry.prune"
    # The escape hatch exists and must be asked for BY NAME.
    assert reg.prune(stale_seconds=0, require_live_heartbeat=False) == 2


def test_workers_prune_still_removes_dead_rows_when_the_stamper_is_alive(tmp_path: Path) -> None:
    reg = _worker_registry(tmp_path)
    reg.register("alive", pid=1, host="h")
    with reg.db.transaction() as conn:                      # one row stamped long ago
        conn.execute("INSERT INTO workers (worker_id, pid, host, status, started_at, last_seen,"
                     " campaigns_done) VALUES ('old', 2, 'h', 'idle', ?, ?, 0)",
                     ("2000-01-01T00:00:00+00:00", "2000-01-01T00:00:00+00:00"))
    assert reg.prune(stale_seconds=3600) == 1, "a live stamper must still let the dead be pruned"
    assert {r["worker_id"] for r in reg.all()} == {"alive"}


def test_proctree_kills_nothing_when_the_process_table_is_unmeasured() -> None:
    from libs.ops import proctree

    killed: list[int] = []
    out = proctree.reap_orphaned_workers(apply=True, table=[], killer=killed.append)
    assert killed == [], "an empty process table manufactured orphans and killed them"
    assert out["measured"] is False
    assert out["stood_down"]["removed"] == 0


# --------------------------------------------------------------------------- the inventory

def test_every_declared_destructive_path_carries_a_reference_and_a_known_status() -> None:
    assert rf.DESTRUCTIVE_PATHS
    allowed = {"guarded", "positive", "sealed", "unguarded"}
    seen: set[str] = set()
    for spec in rf.DESTRUCTIVE_PATHS:
        assert spec.status in allowed, f"{spec.path_id}: {spec.status}"
        assert spec.reference, f"{spec.path_id} names no reference"
        assert spec.removes, f"{spec.path_id} does not say what it removes"
        assert spec.path_id not in seen, f"duplicate path_id {spec.path_id}"
        seen.add(spec.path_id)
        if spec.status in {"unguarded", "sealed"}:
            assert spec.note, f"{spec.path_id} is {spec.status} with no reason recorded"


def test_the_unguarded_ratchet_only_falls() -> None:
    """The ceiling is a promise that the backlog shrinks. Pinned so raising it is a deliberate
    edit to this test and not a quiet number change."""
    import scripts.check_no_retirement_on_absence as fence

    assert fence.UNGUARDED_CEILING <= 2
    assert len(rf.unguarded()) <= fence.UNGUARDED_CEILING


def test_the_fence_passes_on_this_tree(tmp_path: Path) -> None:
    import scripts.check_no_retirement_on_absence as fence

    doc = fence.audit()
    assert doc["ok"], doc["problems"]
    assert doc["counts"]["guarded"] >= 5
    assert doc["surface_fingerprint"]
    # Every sealed finding is surfaced for the principal rather than silently edited.
    assert any(r["sealed_file"] for r in doc["declared"])


def test_the_fence_fails_when_a_guarded_path_stops_calling_the_guard(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """An import is not a guard: the proof is the AST call, so removing it must fail the fence."""
    import scripts.check_no_retirement_on_absence as fence

    monkeypatch.setattr(fence.rf, "guard_call_names", lambda: ("a_name_no_module_calls",))
    doc = fence.audit()
    assert not doc["ok"]
    assert any("an import is not a guard" in p for p in doc["problems"])


def test_a_stale_inventory_that_still_describes_this_tree_is_reported_not_failed() -> None:
    import scripts.check_no_retirement_on_absence as fence

    old = (datetime.now(tz=UTC) - timedelta(hours=72)).isoformat(timespec="seconds")
    verdict = fence._inventory_staleness({"generated_at": old, "surface_fingerprint": "abc"},
                                         "abc")
    assert verdict["verdict"] == rf.STALE
    assert verdict["fatal"] is False


def test_a_stale_inventory_whose_surface_moved_is_fatal() -> None:
    import scripts.check_no_retirement_on_absence as fence

    old = (datetime.now(tz=UTC) - timedelta(hours=72)).isoformat(timespec="seconds")
    verdict = fence._inventory_staleness({"generated_at": old, "surface_fingerprint": "abc"},
                                         "def")
    assert verdict["verdict"] == rf.STALE
    assert verdict["fatal"] is True
    assert "no longer exists" in verdict["why"]


def test_a_missing_inventory_is_unmeasured_never_a_failure() -> None:
    import scripts.check_no_retirement_on_absence as fence

    verdict = fence._inventory_staleness({}, "abc")
    assert verdict["verdict"] == rf.UNMEASURED
    assert verdict["fatal"] is False


def test_the_fence_is_registered_in_the_law_gate() -> None:
    src = (Path(rf.ROOT) / "scripts" / "run_law_gate.py").read_text(encoding="utf-8")
    assert '("check_no_retirement_on_absence.py", ())' in src


def test_the_canon_incident_row_names_the_guard_call_its_owner_must_add() -> None:
    """The one UNGUARDED path must hand its owner the exact call, not a description of one."""
    row = rf.by_id("certificate_truth.apply")
    assert row is not None
    assert row.status == "unguarded"
    assert "require_live_reference(" in row.note
    assert CANON in row.reference
