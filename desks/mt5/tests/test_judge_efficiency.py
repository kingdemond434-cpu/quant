"""The judge-efficiency fixes keep every verdict identical, and the elastic cores obey the owner.

Owner, 2026-11-25: fix per-verdict efficiency first; keep the 6 reserved judge cores as a floor
and borrow idle cores up to the 75% research cap; live always wins. Every fix must keep verdicts
identical -- the same cells give the same verdicts before and after.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research"), str(DESK / "scripts"),
           str(DESK / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judge_efficiency as je  # noqa: E402
from scripts import judge_elastic_cores as ec  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "_gaunt_eff", DESK / "scripts" / "external_gauntlet.py")


def _gauntlet():
    assert _SPEC and _SPEC.loader
    g = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(g)
    return g


# ------------------------------------------------------------------ H1: the prune, same files
def _sealed_prune(cache_dir: Path, now: float) -> None:
    """The sealed loop, verbatim but for the clock."""
    try:
        for _f in cache_dir.glob("*.npz"):
            if now - _f.stat().st_mtime > 3 * 86400:
                _f.unlink(missing_ok=True)
    except OSError:
        pass


def _cache(tmp: Path, name: str, now: float) -> Path:
    d = tmp / name
    d.mkdir()
    for i, age_d in enumerate((0.1, 2.9, 3.1, 10.0, 1.0, 4.0)):
        f = d / f"k{i}.npz"
        f.write_bytes(b"x")
        os.utime(f, (now - age_d * 86400, now - age_d * 86400))
    (d / "k_old.json").write_bytes(b"x")
    os.utime(d / "k_old.json", (now - 30 * 86400, now - 30 * 86400))
    return d


def test_the_scandir_prune_deletes_exactly_the_files_the_sealed_prune_deletes(tmp_path) -> None:
    now = time.time()
    a, b = _cache(tmp_path, "a", now), _cache(tmp_path, "b", now)
    _sealed_prune(a, now)
    got = je.prune_cache(b, now=now)
    assert sorted(p.name for p in a.iterdir()) == sorted(p.name for p in b.iterdir())
    assert got == {"seen": 6, "removed": 3}
    assert je.prune_cache(tmp_path / "absent", now=now) == {"seen": 0, "removed": 0}


# ------------------------------------------------------------------ H2: the order, same cells
def _specs() -> list[dict]:
    out = []
    for fam, n in (("discovered", 40), ("carry", 12), ("pca_residual", 30)):
        for i in range(n):
            out.append({"sym": f"S{i % 5}", "family": fam, "params": {"i": i},
                        "_never_judged": i % 4 == 0})
    # The sweep's sort: never-judged first, then the rest -- interleaved across families.
    return sorted(out, key=lambda sp: (not sp["_never_judged"], sp["sym"], sp["params"]["i"]))


def test_reorder_is_a_permutation_that_restores_new_first_across_families(tmp_path,
                                                                         monkeypatch) -> None:
    g = _gauntlet()
    monkeypatch.setattr(g, "_family_yield", lambda root=None: {"carry": 0.05})
    monkeypatch.setattr(g, "REPORTS", tmp_path)
    before = _specs()
    keep, _ = g.allocate_by_yield(before)
    fixed = je.reorder_keep(before, keep)
    assert sorted(map(id, fixed)) == sorted(map(id, keep)), "same objects, nothing added/dropped"
    flags = [sp["_never_judged"] for sp in fixed]
    assert flags == sorted(flags, reverse=True), "every never-judged cell precedes every re-judge"
    pos = {id(sp): i for i, sp in enumerate(before)}
    assert [pos[id(sp)] for sp in fixed] == sorted(pos[id(sp)] for sp in fixed)
    # The defect it repairs: the family-block order puts a re-judge ahead of a never-judged cell.
    blk = [sp["_never_judged"] for sp in keep]
    assert blk != sorted(blk, reverse=True)


def test_reorder_keeps_an_unknown_spec_in_place_after_the_known_ones() -> None:
    a, b, c = {"k": 1}, {"k": 2}, {"k": 3}
    assert je.reorder_keep([a, b], [c, b, a]) == [a, b, c]
    assert je.reorder_keep([], [c, a]) == [c, a]


def test_the_docket_order_restatement_reorders_only_once_the_sealed_file_does() -> None:
    import judge_docket_order as O

    class G:
        YIELD_ALLOCATION_STRENGTH, YIELD_MAX_SHARE, YIELD_MIN_SHARE = 0.7, 0.45, 0.15

        @staticmethod
        def _family_yield():
            return {"carry": 0.05}

        @staticmethod
        def _explore_unmeasured_axes(specs, keep):
            return [], {}

        @staticmethod
        def _orthogonality_floor(specs, keep):
            return [], {}

    before = _specs()
    plain = O.allocate(G, before)
    G.JUDGE_KEEP_REORDER = True  # type: ignore[attr-defined]
    O_order, O_drop, O_stamp, O_ban = O.order, O.drop_redundant, O.stamp_new, O.drop_banned
    try:
        O.drop_banned = lambda s: (s, 0)                            # type: ignore[assignment]
        O.order = lambda _G, s: s                                   # type: ignore[assignment]
        O.drop_redundant = lambda _G, s: (s, 0)                     # type: ignore[assignment]
        O.stamp_new = lambda _G, s: sum(1 for x in s if x["_never_judged"])  # type: ignore
        keep, census = O.sealed_keep(G, before, novelty=False)
        del G.JUDGE_KEEP_REORDER  # type: ignore[attr-defined]
        keep_off, _ = O.sealed_keep(G, before, novelty=False)
    finally:
        O.order, O.drop_redundant, O.stamp_new, O.drop_banned = O_order, O_drop, O_stamp, O_ban
    assert [id(x) for x in keep_off] == [id(x) for x in plain]
    assert keep == je.reorder_keep(before, plain)
    assert census["keep_never_judged"] == sum(1 for x in plain if x["_never_judged"])


# ------------------------------------------------------------------ VERDICTS ARE IDENTICAL
_META = {s: {"median_spread_pts": 10.0, "tick_size": 1e-5, "tick_value": 0.9,
             "contract_size": 1e5, "swap_long": -3.0, "swap_short": 1.0}
         for s in ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD")}


def _cells() -> list[dict]:
    days, d = [], date(2020, 1, 6)
    while len(days) < 700:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    out = []
    for k, (sym, fam, mu) in enumerate((("EURUSD", "carry", 0.15), ("GBPUSD", "carry", 0.0),
                                        ("USDJPY", "pca_residual", 0.1),
                                        ("AUDUSD", "discovered", 0.05))):
        rng = np.random.default_rng(k + 1)
        ds = pd.Series(rng.normal(mu, 1.0, len(days)), index=days, dtype=float)
        out.append({"sym": sym, "family": fam, "params": {"seed": k},
                    "_cached_ds": ds, "_cached_ds3": ds - 0.01})
    return out


def _verdicts(g, cells: list[dict]) -> dict[str, dict]:
    out = g.run_gauntlet([dict(c) for c in cells], "judge_efficiency_identity", _META)
    rows = {}
    for v in out["verdicts"]:
        v = {k: val for k, val in v.items() if k not in ("at", "judged_at", "swept_at")}
        rows[str(v.get("cell"))] = json.loads(json.dumps(v, sort_keys=True, default=str))
    return rows


def test_the_same_cells_give_the_same_verdicts_in_either_order(tmp_path, monkeypatch) -> None:
    """THE IDENTITY THE REORDER RESTS ON: the sealed judge's verdict for a cell depends on the SET
    of cells it rules, never on their order. Run the real `run_gauntlet` on one set in the
    family-block order and in the restored order: every verdict is byte-identical."""
    from conftest import write_measured_dsr_inputs
    from libs.research import dsr_inputs

    monkeypatch.setattr(dsr_inputs, "REPORT", write_measured_dsr_inputs(tmp_path / "dsr"))
    monkeypatch.setattr("research.cost_to_edge.verdict",
                        lambda *a, **k: (False, "", {"measured": False, "why": "no terminal"}))
    g = _gauntlet()
    cells = _cells()
    a = _verdicts(g, cells)
    b = _verdicts(g, list(reversed(cells)))
    c = _verdicts(g, [cells[2], cells[0], cells[3], cells[1]])
    assert set(a) == {str(v) for v in a} and len(a) == len(cells)
    assert a == b == c


# ------------------------------------------------------------------ ELASTIC CORES
FLOOR = [8, 9, 10, 11, 12, 13]
GB = 1024.0


def _plan(**kw):
    args = {"n_cpus": 18, "floor_cpus": FLOOR, "percpu_busy": [0.1] * 18, "judge_cores": 5.0,
            "live_cores": 0.2, "other_cores": 3.0, "free_mb": 60 * GB, "total_mb": 96 * GB}
    args.update(kw)
    return ec.plan(**args)


def test_floor_is_six_and_ceiling_is_the_75pct_research_cap() -> None:
    p = _plan()
    assert p["floor"] == 6 and p["ceiling"] == 13
    assert p["workers_now"] == 13 and set(FLOOR) <= set(p["cpus"]) and not p["shed"]


def test_borrowing_takes_only_what_others_and_live_leave_idle() -> None:
    # 18 - live reserve 2 - ceil(others 8.5) = 7 spare -> 7 cores, the idlest non-floor ones.
    busy = [0.9] * 18
    busy[2] = 0.0
    p = _plan(other_cores=8.5, percpu_busy=busy)
    assert p["workers_now"] == 7 and p["borrowed"] == 1 and 2 in p["cpus"]
    # Others busy enough that nothing is spare: the floor holds, it is never cut.
    assert _plan(other_cores=17.0)["workers_now"] == 6


def test_live_load_memory_pressure_unreadable_or_unmeasured_shed_to_the_floor_at_once() -> None:
    for kw in ({"live_cores": 1.0}, {"free_mb": 8 * GB}, {"unreadable": 1},
               {"percpu_busy": None}, {"free_mb": None}, {"live_cores": None}):
        p = _plan(previous=13, **kw)
        assert p["workers_now"] == 6 and p["shed"] and p["cpus"] == FLOOR, kw
    # Memory reserve is a share of the MEASURED total, never a hard-coded box figure.
    assert _plan(free_mb=12 * GB)["shed"] is True            # 15% of 96 GB = 14.4 GB
    assert _plan(free_mb=12 * GB, total_mb=32 * GB)["shed"] is False


def test_growth_is_stepped_but_shedding_is_not() -> None:
    assert _plan(previous=6)["workers_now"] == 6 + ec.BORROW_STEP
    assert _plan(previous=12, other_cores=8.5)["workers_now"] == 7


def test_the_switch_can_lower_the_cap_or_turn_it_off_never_raise_it(tmp_path) -> None:
    p = tmp_path / "JUDGE_ELASTIC_CORES.json"
    assert ec.switch(p)["enabled"] and ec.switch(p)["cap_share"] == 0.75
    p.write_text(json.dumps({"research_cap_share": 0.9}), "utf-8")
    assert not ec.switch(p)["enabled"]
    p.write_text(json.dumps({"research_cap_share": 0.5}), "utf-8")
    assert ec.switch(p)["cap_share"] == 0.5
    p.write_text(json.dumps({"enabled": False}), "utf-8")
    assert not ec.switch(p)["enabled"]
    p.write_text("{not json", "utf-8")
    assert not ec.switch(p)["enabled"]


def test_a_pass_confines_only_judge_pids_and_publishes_the_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ec, "REPORT", tmp_path / "JUDGE_ELASTIC_CORES.json")
    monkeypatch.setattr(ec, "SWITCH", tmp_path / "absent.json")
    monkeypatch.setattr(ec.jp, "reserved_cores",
                        lambda n=None, path=None: {"enabled": True, "cpus": FLOOR, "why": "t"})
    touched: list[tuple[int, list[int]]] = []
    monkeypatch.setattr(ec, "_confine_checked",
                        lambda row, cpus: touched.append((row["pid"], cpus)) or {"applied": True})
    rows = [{"pid": 1, "cls": "judge"}, {"pid": 2, "cls": "miner"}, {"pid": 3, "cls": "live"},
            {"pid": 4, "cls": "judge_warm"}, {"pid": 5, "cls": "judge"}]
    reading = {"n_cpus": 18, "percpu_busy": [0.1] * 18, "judge_cores": 5.0, "live_cores": 0.1,
               "other_cores": 3.0, "free_mb": 60 * GB, "total_mb": 96 * GB, "unreadable": 0,
               "rows": rows}
    doc = ec.run_pass(reading=reading)
    assert [t[0] for t in touched] == [1, 5]
    on_disk = json.loads((tmp_path / "JUDGE_ELASTIC_CORES.json").read_text("utf-8"))
    for k in ("workers_now", "floor", "ceiling", "reason"):
        assert on_disk[k] == doc[k]
    assert on_disk["floor"] == 6 and on_disk["ceiling"] == 13
    # Dry run measures and reports, touches nothing.
    touched.clear()
    ec.run_pass(reading=reading, apply=False)
    assert touched == []


def test_off_or_no_reservation_leaves_affinity_untouched(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ec, "REPORT", tmp_path / "r.json")
    monkeypatch.setattr(ec, "SWITCH", tmp_path / "absent.json")
    monkeypatch.setattr(ec.jp, "reserved_cores",
                        lambda n=None, path=None: {"enabled": False, "cpus": [], "why": "off"})
    monkeypatch.setattr(ec, "_confine_checked",
                        lambda row, cpus: (_ for _ in ()).throw(AssertionError("touched")))
    doc = ec.run_pass(reading={"n_cpus": 18, "rows": [{"pid": 1, "cls": "judge"}]})
    assert doc["mode"] == "off"


def test_measure_uses_psutil_and_never_raises(monkeypatch) -> None:
    import types

    fake = types.SimpleNamespace(
        cpu_count=lambda: 18,
        virtual_memory=lambda: types.SimpleNamespace(available=60 * 2**30, total=96 * 2**30),
        cpu_percent=lambda *a, **k: [10.0] * 18)
    monkeypatch.setitem(sys.modules, "psutil", fake)
    monkeypatch.setattr(ec.jp, "snapshot", lambda s=0.0: [
        {"pid": 1, "ppid": 0, "name": "python.exe", "cmdline": ["python", "external_gauntlet.py"],
         "nice": 0x20, "cpu_cores": 4.0, "create_time": 1.0},
        {"pid": 2, "ppid": 0, "name": "terminal64.exe", "cmdline": ["terminal64.exe"],
         "nice": 0x8000, "cpu_cores": 0.3, "create_time": 1.0},
        {"pid": 3, "ppid": 0, "name": "python.exe", "cmdline": ["python", "miner.py"],
         "nice": 0x4000, "cpu_cores": 2.5, "create_time": 1.0}])
    m = ec.measure(0.0)
    assert (m["n_cpus"], m["judge_cores"], m["live_cores"], m["other_cores"]) == (18, 4.0, 0.3, 2.5)
    assert m["total_mb"] == 96 * 1024.0 and m["unreadable"] == 0
    monkeypatch.setitem(sys.modules, "psutil", types.SimpleNamespace())
    assert ec.measure(0.0)["percpu_busy"] is None


# ------------------------------------------------------------------ THE LADDER
def test_the_ladder_ratchets_up_on_the_measured_rate_and_never_falls() -> None:
    s = je.ladder_step(None, 6734.0)
    assert (s["floor_now"], s["next_floor"], s["raised_this_pass"]) == (100_000, 200_000, False)
    s = je.ladder_step(s, 100_000.0)
    assert (s["floor_now"], s["next_floor"], s["raised_this_pass"]) == (200_000, 300_000, True)
    s = je.ladder_step(s, 10.0)
    assert s["floor_now"] == 200_000, "a lower rate never lowers a floor"
    s = je.ladder_step(je.ladder_step(s, 250_000.0), 300_000.0)
    assert (s["floor_now"], s["next_floor"]) == (400_000, 500_000)
    assert je.ladder_step({"floor_now": 5}, None)["floor_now"] == 100_000
    assert je.ladder_step({"floor_now": "x"}, None)["gap_per_day"] == je.UNMEASURED


def test_publish_reads_the_judges_own_reports_and_writes_the_ladder(tmp_path) -> None:
    doc = je.publish(ladder_path=tmp_path / "ladder.json", out=tmp_path / "eff.json",
                     now=datetime(2026, 11, 25, tzinfo=UTC))
    lad = doc["ladder"]
    for k in ("floor_now", "next_floor", "measured_rate_24h", "per_core"):
        assert k in lad
    assert lad["floor_now"] >= 100_000
    on_disk = json.loads((tmp_path / "ladder.json").read_text("utf-8"))
    assert on_disk["floor_now"] == lad["floor_now"]
    assert json.loads((tmp_path / "eff.json").read_text("utf-8"))["ladder"] == lad


def test_absent_reports_are_unmeasured_never_zero(tmp_path) -> None:
    m = je.measure(tmp_path)
    assert m["first_verdicts_24h"] is None and m["judged_cells_per_day"] is None
    assert m["cache_hit_rate"] == je.UNMEASURED
    doc = je.publish(reports=tmp_path, write=False)
    assert doc["ladder"]["measured_rate_24h"] == je.UNMEASURED
