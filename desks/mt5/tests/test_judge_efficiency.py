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
    assert (got["seen"], got["removed"], got["removed_bytes"]) == (6, 3, 3)
    assert sorted(got["removed_names"]) == ["k2.npz", "k3.npz", "k5.npz"]   # recorded, by name
    assert je.prune_cache(tmp_path / "absent", now=now) == {
        "seen": 0, "removed": 0, "removed_bytes": 0, "removed_names": []}


def test_prune_cache_is_a_declared_positive_destructive_path() -> None:
    from libs.ops import reference_freshness as rf
    row = next(p for p in rf.DESTRUCTIVE_PATHS if p.path_id == "judge_efficiency.prune_cache")
    assert (row.module, row.function, row.status) == (
        "desks/mt5/research/judge_efficiency.py", "prune_cache", "positive")


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


# ------------------------------------------------------------------ H3: never-judged exemption
def _backlog() -> list[dict]:
    """A large never-judged backlog in one low-yield family, re-judges in the others."""
    out = []
    for fam, n, n_new in (("discovered", 400, 300), ("carry", 40, 0), ("pca_residual", 60, 10)):
        for i in range(n):
            out.append({"sym": f"S{i % 7}", "family": fam, "params": {"i": i},
                        "_never_judged": i < n_new})
    return sorted(out, key=lambda sp: (not sp["_never_judged"], sp["sym"], sp["params"]["i"]))


def _is_nj(sp: dict) -> bool:
    return sp["_never_judged"] is True


def _trim(tmp_path, monkeypatch, before: list[dict]) -> list[dict]:
    g = _gauntlet()
    monkeypatch.setattr(g, "_family_yield", lambda root=None: {"carry": 0.05})
    monkeypatch.setattr(g, "REPORTS", tmp_path)
    keep, _ = g.allocate_by_yield(before)
    return keep


def test_the_exemption_keeps_never_judged_first_inside_the_same_budget(tmp_path,
                                                                        monkeypatch) -> None:
    before = _backlog()
    snapshot = json.dumps(before, sort_keys=True)
    keep = _trim(tmp_path, monkeypatch, before)
    budget = len(keep)
    waiting = [sp for sp in before if _is_nj(sp) and all(sp is not k for k in keep)]
    assert waiting, "the fixture must reproduce the cut: never-judged cells left outside"
    got, rec = je.exempt_never_judged(before, keep, _is_nj)
    # THE BUDGET: never above the trim's own cell count, exactly equal here.
    assert len(got) == budget == rec["budget_cells"] == rec["kept_cells"]
    assert len({id(sp) for sp in got}) == budget, "no cell kept twice"
    # NEVER-JUDGED BEFORE RE-JUDGES, in the helper's order and after H2's global reorder.
    for order in (got, je.reorder_keep(before, got)):
        flags = [_is_nj(sp) for sp in order]
        assert flags == sorted(flags, reverse=True)
    # THE CENSUS: the count reported is the count that moved, one re-judge out per cell in.
    n = rec[je.EXEMPT_KEY]
    nj_before, nj_after = sum(map(_is_nj, keep)), sum(map(_is_nj, got))
    assert n > 0 and n == nj_after - nj_before == rec["displaced_rejudges"]
    assert n == min(len(waiting), budget - nj_before)
    assert sum(rec["by_family"].values()) == n == sum(rec["displaced_by_family"].values())
    assert rec["never_judged_still_outside"] == len(waiting) - n
    assert sum(rec["kept_by_family"].values()) == budget
    # The admitted cells are the earliest waiting in the sweep's order; the displaced re-judges
    # are the ones the sweep ranks last.
    pos = {id(sp): i for i, sp in enumerate(before)}
    got_ids = {id(sp) for sp in got}
    assert [sp for sp in waiting if id(sp) in got_ids] == waiting[:n]
    kept_old = [pos[id(sp)] for sp in got if not _is_nj(sp)]
    gone_old = [pos[id(sp)] for sp in keep if not _is_nj(sp) and id(sp) not in got_ids]
    assert not kept_old or not gone_old or max(kept_old) < min(gone_old)
    # EVERY CELL IS CHARGED LIKE ANY OTHER: nothing about a spec changes, nothing is tagged.
    assert json.dumps(before, sort_keys=True) == snapshot


def test_the_exemption_never_displaces_a_protected_cell_and_fails_closed(tmp_path,
                                                                          monkeypatch) -> None:
    before = _backlog()
    keep = _trim(tmp_path, monkeypatch, before)
    pos = {id(sp): i for i, sp in enumerate(before)}
    last_old = max((sp for sp in keep if not _is_nj(sp)), key=lambda sp: pos[id(sp)])
    got, rec = je.exempt_never_judged(before, keep, _is_nj, protect=lambda sp: sp is last_old)
    assert any(sp is last_old for sp in got) and rec["rejudges_protected"] == 1
    assert len(got) == len(keep)
    # An is_new that raises exempts nothing; a protect that raises displaces nothing.
    boom = lambda sp: (_ for _ in ()).throw(RuntimeError("x"))  # noqa: E731
    same, r1 = je.exempt_never_judged(before, keep, boom)
    assert r1[je.EXEMPT_KEY] == 0 and sorted(map(id, same)) == sorted(map(id, keep))
    same, r2 = je.exempt_never_judged(before, keep, _is_nj, protect=boom)
    assert r2[je.EXEMPT_KEY] == 0 and sorted(map(id, same)) == sorted(map(id, keep))
    # More waiting than re-judges: every re-judge goes, the budget still holds.
    tiny = [sp for sp in keep if _is_nj(sp)] + [sp for sp in keep if not _is_nj(sp)][:3]
    got, rec = je.exempt_never_judged(before, tiny, _is_nj)
    assert len(got) == len(tiny) and all(map(_is_nj, got)) and rec[je.EXEMPT_KEY] == 3
    assert je.exempt_never_judged([], [], _is_nj)[1][je.EXEMPT_KEY] == 0


def test_every_kept_cell_is_judged_and_charged_in_n_trials(tmp_path, monkeypatch) -> None:
    """The audit's first condition, end to end on the real `run_gauntlet`: an exempted cell is a
    column of the matrix like any other, and every verdict carries the same campaign charge."""
    from conftest import write_measured_dsr_inputs
    from libs.research import dsr_inputs

    monkeypatch.setattr(dsr_inputs, "REPORT", write_measured_dsr_inputs(tmp_path / "dsr"))
    monkeypatch.setattr("research.cost_to_edge.verdict",
                        lambda *a, **k: (False, "", {"measured": False, "why": "no terminal"}))
    cells = _cells()
    new = {"EURUSD", "USDJPY"}
    keep = [cells[1], cells[3]]                                      # the trim kept two re-judges
    got, rec = je.exempt_never_judged(cells, keep, lambda c: c["sym"] in new)
    assert rec[je.EXEMPT_KEY] == 2 and {c["sym"] for c in got} == new
    g = _gauntlet()
    out = g.run_gauntlet([dict(c) for c in got], "judge_efficiency_exempt", _META)
    assert out["n_cells"] == len(got) == len(keep)
    ids = {str(g.cell_id({"sym": c["sym"], "family": c["family"], "params": c["params"]}))
           for c in got}
    ruled = {str(v.get("cell")): v for v in out["verdicts"]}
    assert set(ruled) == ids, "every kept cell is ruled"
    for v in ruled.values():
        ds = (v.get("stages") or {}).get("deflated_sharpe") or {}
        assert ds.get("campaign_trials") == out["n_trials"] and out["n_trials"] > 0


def test_the_docket_order_restatement_exempts_only_once_the_sealed_file_does() -> None:
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

    before = _backlog()
    plain = O.allocate(G, before)
    O_order, O_drop, O_stamp, O_ban = O.order, O.drop_redundant, O.stamp_new, O.drop_banned
    try:
        O.drop_banned = lambda s: (s, 0)                            # type: ignore[assignment]
        O.order = lambda _G, s: s                                   # type: ignore[assignment]
        O.drop_redundant = lambda _G, s: (s, 0)                     # type: ignore[assignment]
        O.stamp_new = lambda _G, s: sum(1 for x in s if x["_never_judged"])  # type: ignore
        keep_off, census_off = O.sealed_keep(G, before, novelty=False)
        G.JUDGE_NEVER_JUDGED_EXEMPT = True  # type: ignore[attr-defined]
        G.JUDGE_KEEP_REORDER = True  # type: ignore[attr-defined]
        keep, census = O.sealed_keep(G, before, novelty=False)
    finally:
        O.order, O.drop_redundant, O.stamp_new, O.drop_banned = O_order, O_drop, O_stamp, O_ban
    assert [id(x) for x in keep_off] == [id(x) for x in plain]
    assert census_off["exempted_never_judged"] == 0
    want, rec = je.exempt_never_judged(before, plain, _is_nj)
    assert keep == je.reorder_keep(before, want)
    assert len(keep) == len(plain)
    assert census["exempted_never_judged"] == rec[je.EXEMPT_KEY] > 0
    assert census["keep_never_judged"] == sum(map(_is_nj, plain)) + rec[je.EXEMPT_KEY]


def test_the_sealed_hunk_matches_the_restatement_and_publishes_the_count(tmp_path,
                                                                         monkeypatch) -> None:
    """Runs fully once the SEAL_CLEAR H3 patch is applied (the scratch-copy run); before that it
    pins that the sealed file is untouched and the restatement dormant."""
    import judge_docket_order as O

    g = _gauntlet()
    monkeypatch.setattr(g, "_family_yield", lambda root=None: {"carry": 0.05})
    monkeypatch.setattr(g, "REPORTS", tmp_path)
    monkeypatch.setattr(g, "_explore_unmeasured_axes", lambda specs, keep: ([], {}))
    monkeypatch.setattr(g, "_orthogonality_floor", lambda specs, keep: ([], {}))
    before = _backlog()
    plain, _ = g.allocate_by_yield(before)
    if not hasattr(g, "JUDGE_NEVER_JUDGED_EXEMPT"):
        assert O.allocate(g, before, is_new=_is_nj) == plain, "dormant until the seal lands"
        return
    keep, report = g.allocate_by_yield(before, is_new=_is_nj)
    assert len(keep) == len(plain), "inside the same budget"
    rec: dict = {}
    assert [id(x) for x in O.allocate(g, before, is_new=_is_nj, record=rec)] == \
        [id(x) for x in keep]
    doc = json.loads((tmp_path / "RESEARCH_ALLOCATION.json").read_text("utf-8"))
    assert doc["exempted_never_judged"] == rec[je.EXEMPT_KEY] > 0
    assert doc["built_this_sweep"] == len(keep)
    assert sum(r["exempted_never_judged"] for r in report.values()) == rec[je.EXEMPT_KEY]
    assert sum(r["built_this_sweep"] for r in report.values()) == len(keep)
    # Without is_new (every other caller) the sealed trim is exactly what it was.
    again, _ = g.allocate_by_yield(before)
    assert [id(x) for x in again] == [id(x) for x in plain]


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


def _reserved(monkeypatch, tmp_path, switch_text: str | None) -> list:
    monkeypatch.setattr(ec, "REPORT", tmp_path / "r.json")
    sw = tmp_path / "JUDGE_ELASTIC_CORES.json"
    if switch_text is not None:
        sw.write_text(switch_text, "utf-8")
    monkeypatch.setattr(ec, "SWITCH", sw)
    monkeypatch.setattr(ec.jp, "reserved_cores",
                        lambda n=None, path=None: {"enabled": True, "cpus": FLOOR, "why": "t"})
    touched: list[tuple[int, list[int]]] = []
    monkeypatch.setattr(ec, "_confine_checked",
                        lambda row, cpus: touched.append((row["pid"], cpus)) or {"applied": True})
    return touched


def test_the_off_switch_gives_borrowed_cores_back_to_the_floor(tmp_path, monkeypatch) -> None:
    """AUDIT HOLD defect 1: OFF (enabled=false, or a malformed switch, which also reads OFF) with
    the reservation in force confines every judge pid -- and only judge pids -- to the reserved
    cores; a dry run still touches nothing."""
    rows = [{"pid": 1, "cls": "judge"}, {"pid": 2, "cls": "miner"}, {"pid": 3, "cls": "live"},
            {"pid": 5, "cls": "judge"}]
    reading = {"n_cpus": 18, "percpu_busy": [0.0] * 18, "judge_cores": 12.0, "live_cores": 0.0,
               "other_cores": 0.0, "free_mb": 60 * GB, "total_mb": 96 * GB, "unreadable": 0,
               "rows": rows}
    for text in (json.dumps({"enabled": False}), "{not json",
                 json.dumps({"research_cap_share": 0.9})):
        touched = _reserved(monkeypatch, tmp_path, text)
        doc = ec.run_pass(reading=reading)
        assert doc["mode"] == "off" and doc["workers_now"] == 6 and doc["borrowed"] == 0
        assert touched == [(1, FLOOR), (5, FLOOR)], text
        assert doc["applied"]["judge_pids"] == 2 and not doc["shed_not_applied"]
        touched.clear()
        ec.run_pass(reading=reading, apply=False)
        assert touched == []


def test_a_failed_measurement_still_sheds_every_judge_pid_to_the_floor(tmp_path,
                                                                        monkeypatch) -> None:
    """AUDIT HOLD defect 2: measure() failed (rows=[]), so the pass re-enumerates the judge pids
    by a cheap census and confines them to the floor; if the census fails too, the report says
    UNMEASURED with shed_not_applied -- never a silent 'fine'."""
    touched = _reserved(monkeypatch, tmp_path, None)
    calls: list[float] = []

    def snap(s=0.0):
        calls.append(s)
        return [{"pid": 7, "ppid": 0, "name": "python.exe",
                 "cmdline": ["python", "external_gauntlet.py"], "nice": 0x20, "cpu_cores": None,
                 "create_time": 1.0},
                {"pid": 8, "ppid": 0, "name": "terminal64.exe", "cmdline": ["terminal64.exe"],
                 "nice": 0x8000, "cpu_cores": None, "create_time": 1.0}]

    monkeypatch.setattr(ec.jp, "snapshot", snap)
    failed = {"n_cpus": 18, "percpu_busy": None, "judge_cores": None, "live_cores": None,
              "other_cores": None, "free_mb": None, "total_mb": None, "unreadable": 0,
              "rows": [], "error": "RuntimeError: boom"}
    doc = ec.run_pass(reading=failed)
    assert calls == [0.0], "a cheap census, no CPU sample"
    assert touched == [(7, FLOOR)]
    assert doc["shed"] and doc["workers_now"] == 6 and doc["status"] == "UNMEASURED"
    assert not doc["shed_not_applied"] and "UNMEASURED" in doc["reason"]

    touched.clear()
    monkeypatch.setattr(ec.jp, "snapshot",
                        lambda s=0.0: (_ for _ in ()).throw(RuntimeError("census down")))
    doc = ec.run_pass(reading=failed)
    assert touched == []
    assert doc["status"] == "UNMEASURED" and doc["shed_not_applied"] is True
    assert "census down" in doc["census_error"]
    on_disk = json.loads((tmp_path / "r.json").read_text("utf-8"))
    assert on_disk["shed_not_applied"] is True and on_disk["status"] == "UNMEASURED"

    # The real measure() failing feeds the same path: a raising snapshot, end to end.
    import types

    fake = types.SimpleNamespace(
        cpu_count=lambda: 18,
        virtual_memory=lambda: types.SimpleNamespace(available=60 * 2**30, total=96 * 2**30),
        cpu_percent=lambda *a, **k: [10.0] * 18)
    monkeypatch.setitem(sys.modules, "psutil", fake)
    m = ec.measure(0.0)
    assert m["rows"] == [] and "census down" in m["error"]
    assert ec.run_pass(reading=m)["shed_not_applied"] is True


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
