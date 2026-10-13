"""The breadth enforcer (principal 2026-10-13): saturated families at an exploration floor, the
unknown forced to the front, total mining never reduced, and a fence that fails on drift.

Every input is synthetic or redirected into `tmp_path`; nothing here reads or writes box state.
"""
from __future__ import annotations

import importlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT), str(_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_breadth_enforcer as fence  # noqa: E402

from research import breadth_enforcer as be  # noqa: E402
from research import judge_coverage as jc  # noqa: E402

SAT = ["cross_asset_residual", "carry"]


def _steer(**extra: Any) -> dict[str, Any]:
    certs = {"cross_asset_residual": 346, "carry": 155, "range_reversion": 7}
    judge = {"families": {
        "cross_asset_residual": {"mined": 9000, "judged_total": 5000, "unjudged": 900},
        "carry": {"mined": 5000, "judged_total": 3000, "unjudged": 500},
        "range_reversion": {"mined": 4000, "judged_total": 900, "unjudged": 400},
        "lead_lag": {"mined": 300, "judged_total": 400, "unjudged": 300},
        "newfam": {"mined": 50, "judged_total": 0, "unjudged": 50},
        "explored_fam": {"mined": 8000, "judged_total": 3000, "unjudged": 800}},
        "unmined_live_families": ["ghost_family"], **extra}
    return be.build_steer(certs, judge)


# ------------------------------------------------------------------------------ measurement
def test_saturated_set_is_measured_from_every_certificate_source(tmp_path: Path) -> None:
    sleeves = tmp_path / "sleeves.json"
    sleeves.write_text(json.dumps({"sleeves": [
        *({"family": "cross_asset_residual", "certificate": {"x": i}} for i in range(12)),
        {"family": "carry", "certificate": None},
        {"family": "carry", "certificate": {"x": 1}}]}))
    surv = tmp_path / "US.json"
    surv.write_text(json.dumps({"survivors": {
        **{f"external.EURUSD.carry.p={i}": {"shadow_spec": {}} for i in range(11)},
        "x": {"shadow_spec": {"family": "cross_asset_residual"}}}}))
    counts, meta = be.certificate_counts(sleeves, surv, tmp_path / "absent.json")
    assert counts == {"cross_asset_residual": 12, "carry": 11}       # MAX per family, not sum
    assert meta["basis_by_family"] == {"cross_asset_residual": "sleeves_registry",
                                       "carry": "universal_survivors"}
    assert meta["sources"]["survivors_canon"]["certificates"] == be.UNMEASURED
    st = be.build_steer(counts, {})
    assert st["saturated"] == ["cross_asset_residual", "carry"]


def test_classes_and_frontier_rank() -> None:
    st = _steer()
    assert st["status"] == "MEASURED" and st["saturated"] == SAT
    assert st["classes"]["newfam"] == be.UNKNOWN                  # no cert, never judged
    assert st["classes"]["ghost_family"] == be.UNKNOWN            # registered, never mined
    assert st["classes"]["lead_lag"] == be.UNDER_MINED            # judged, mined below median
    assert st["classes"]["explored_fam"] == be.EXPLORED
    assert st["classes"]["range_reversion"] == be.EXPLORED        # 7 certs < SAT_MIN_CERTS
    # UNKNOWN before UNDER_MINED; the never-mined ontology family first among the unknown.
    assert st["frontier"][:3] == ["ghost_family", "newfam", "lead_lag"]
    assert be.class_of("never_seen_anywhere", st) == be.UNKNOWN
    assert be.class_of("carry", None) == be.EXPLORED              # no steer: par


def test_no_certificate_source_is_unmeasured_never_saturated() -> None:
    st = be.build_steer({}, {"families": {"carry": {"mined": 10}}})
    assert st["status"] == be.UNMEASURED and st["saturated"] == []
    rows = [{"family": "carry"}] * 5
    assert be.apportion(rows, 3, st) == rows


# ------------------------------------------------------------------------------ apportion
def test_apportion_is_lossless_and_holds_saturated_to_the_floor() -> None:
    st = _steer()
    rows = ([{"family": "cross_asset_residual", "i": i} for i in range(500)]
            + [{"family": "explored_fam", "i": i} for i in range(300)]
            + [{"family": "newfam", "i": i} for i in range(100)])
    out = be.apportion(rows, 200, st)
    assert sorted(map(id, out)) == sorted(map(id, rows))           # same rows, all of them
    head = Counter(r["family"] for r in out[:200])
    assert head["cross_asset_residual"] == 20                       # ceil(10% x 200)
    assert head["newfam"] == 100                                    # the frontier first
    # Every prefix carries the floor: saturated cells are interleaved, not parked at the end.
    assert any(r["family"] == "cross_asset_residual" for r in out[:20])


def test_apportion_never_adds_saturated_cells_to_a_head_that_had_fewer() -> None:
    st = _steer()
    rows = ([{"family": "newfam"} for _ in range(195)] + [{"family": "carry"} for _ in range(5)]
            + [{"family": "carry"} for _ in range(500)] + [{"family": "lead_lag"}] * 100)
    head = Counter(r["family"] for r in be.apportion(rows, 200, st)[:200])
    assert head["carry"] == 5                                       # not raised to 20


def test_apportion_is_work_conserving_when_the_frontier_runs_dry() -> None:
    st = _steer()
    rows = ([{"family": "carry"} for _ in range(500)] + [{"family": "newfam"} for _ in range(30)])
    out = be.apportion(rows, 200, st)
    head = Counter(r["family"] for r in out[:200])
    assert head == {"newfam": 30, "carry": 170}                     # budget filled, never idle
    assert len(out) == len(rows)


# ------------------------------------------------------------------------------ judge hour
def _ranking(fams: list[str]) -> list[dict[str, Any]]:
    return [{"family": f, "rank": i + 1, "ev_per_cell": 1.0, "p": 0.01}
            for i, f in enumerate(fams)]


def test_judge_allocate_obeys_the_steer_and_never_reduces_the_hour() -> None:
    st = _steer()
    backlog = {"cross_asset_residual": 9000, "carry": 5000, "explored_fam": 800,
               "newfam": 50, "lead_lag": 300}
    ranking = _ranking(["cross_asset_residual", "carry", "explored_fam", "lead_lag", "newfam"])
    legacy = jc.allocate(backlog, 4000, ranking=ranking)
    steered = jc.allocate(backlog, 4000, ranking=ranking, steer=st)
    assert sum(steered.values()) == sum(legacy.values()) == 4000
    assert legacy["cross_asset_residual"] > 2000                    # the drift it replaces
    sat = steered["cross_asset_residual"] + steered["carry"]
    assert sat / 4000 <= be.SAT_EXPLORE_SHARE + 1e-9 + 1.0 - (800 + 50 + 300) / 4000
    assert steered["newfam"] == 50 and steered["lead_lag"] == 300 and steered["explored_fam"] == 800
    floor = max(1, int(4000 * jc.FLOOR_SHARE) // 5)
    assert min(steered.values()) >= min(floor, 50)                  # every floor untouched
    assert jc.allocate(backlog, 4000, ranking=ranking, steer=None) == legacy


def test_judge_allocate_holds_saturated_at_the_floor_when_others_can_fill() -> None:
    st = _steer()
    backlog = {"cross_asset_residual": 9000, "carry": 5000, "explored_fam": 9000, "newfam": 9000}
    ranking = _ranking(["cross_asset_residual", "carry", "explored_fam", "newfam"])
    q = jc.allocate(backlog, 4000, ranking=ranking, steer=st)
    assert sum(q.values()) == 4000
    # the exploration share on top of the two saturated families' own (untouched) floors
    floors = 2 * max(1, int(4000 * jc.FLOOR_SHARE) // 4)
    assert q["cross_asset_residual"] + q["carry"] <= max(floors, 4000 * be.SAT_EXPLORE_SHARE)
    b = be.judge_bounds(backlog, 4000, st, jc.FLOOR_SHARE)
    assert (q["cross_asset_residual"] + q["carry"]) / 4000 <= b["saturated_max"]
    walk = be.steer_walk(ranking, backlog, st)
    assert walk[0] == "newfam" and walk[-2:] == ["cross_asset_residual", "carry"]


# ------------------------------------------------------------------------------ the report
def _report(tmp_path: Path, *, shipped_sat: float, frontier: float, unknown: float,
            gauntlet_in_force: bool = False, legacy: int = 100, steered: int = 100,
            age_h: float = 0.0) -> Path:
    shares = {"status": "MEASURED", "n": 1000, "saturated_share": shipped_sat,
              "frontier_share": frontier, "unknown_share": unknown}
    doc = {
        "generated_utc": (datetime.now(UTC) - timedelta(hours=age_h)).isoformat(),
        "steer": {"status": "MEASURED", "saturated": SAT,
                  "params": {"share_tolerance": 0.05, "sat_explore_share": 0.10}},
        "judge": {"shipped": shares, "steer_in_force": True,
                  "bounds": {"saturated_max": 0.10, "frontier_min": 0.50, "unknown_min": 0.25},
                  "total_cells_legacy": legacy, "total_cells_steered": steered},
        "gauntlet": {"status": "MEASURED", "steer_in_force": gauntlet_in_force,
                     "built": {**shares, "saturated_share": 0.6},
                     "bounds": {"saturated_max": 0.10, "frontier_min": 0.0, "unknown_min": 0.0}},
        "verdicts": {**shares, "saturated_share": 0.55},
        "mint": {"status": "MEASURED", "producers": {
            "breadth_sweep": {"status": "MEASURED", "n": 10, "saturated_share": 0.05},
            "card_explosion": {"status": "MEASURED", "n": 10, "saturated_share": 0.9}}},
        "mint_enforced": ["breadth_sweep"],
    }
    p = tmp_path / "BREADTH_ENFORCER.json"
    p.write_text(json.dumps(doc))
    return p


def test_fence_passes_inside_the_bounds_and_warns_loudly_on_the_sealed_judge(
        tmp_path: Path) -> None:
    out = fence.judge(_report(tmp_path, shipped_sat=0.08, frontier=0.6, unknown=0.3))
    assert out["verdict"] == "OK", out
    assert any("SEALED" in w for w in out["warnings"])
    assert any("card_explosion" in w for w in out["warnings"])


@pytest.mark.parametrize("kw,needle", [
    ({"shipped_sat": 0.40, "frontier": 0.6, "unknown": 0.3}, "saturated share"),
    ({"shipped_sat": 0.08, "frontier": 0.20, "unknown": 0.3}, "frontier share"),
    ({"shipped_sat": 0.08, "frontier": 0.6, "unknown": 0.05}, "unknown share"),
    ({"shipped_sat": 0.08, "frontier": 0.6, "unknown": 0.3, "gauntlet_in_force": True},
     "gauntlet build split"),
    ({"shipped_sat": 0.08, "frontier": 0.6, "unknown": 0.3, "steered": 90}, "REDUCED"),
])
def test_fence_fails_on_a_drifted_fixture(tmp_path: Path, kw: dict, needle: str) -> None:
    out = fence.judge(_report(tmp_path, **kw))
    assert out["verdict"] == "FAIL" and any(needle in f for f in out["failures"]), out
    assert fence.main(["--report", str(tmp_path / "BREADTH_ENFORCER.json")]) == 1


def test_fence_is_portable_and_strict_on_the_box(tmp_path: Path) -> None:
    absent = tmp_path / "nope.json"
    assert fence.judge(absent)["verdict"] == "UNMEASURED"
    assert fence.main(["--report", str(absent)]) == 0
    assert fence.judge(absent, require_state=True)["verdict"] == "FAIL"
    stale = _report(tmp_path, shipped_sat=0.08, frontier=0.6, unknown=0.3, age_h=9.0)
    assert fence.judge(stale)["verdict"] == "OK"
    assert fence.judge(stale, require_state=True)["verdict"] == "FAIL"


def test_build_writes_the_report_on_fixtures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch
                                             ) -> None:
    (tmp_path / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"family": "carry", "certificate": {"i": i}} for i in range(15)]}))
    monkeypatch.setattr(be, "SLEEVES", tmp_path / "sleeves.json")
    monkeypatch.setattr(be, "SURVIVORS", tmp_path / "a.json")
    monkeypatch.setattr(be, "CANON", tmp_path / "b.json")
    monkeypatch.setattr(be, "PRODUCER_BREADTH", tmp_path / "c.json")
    monkeypatch.setattr(be, "RESEARCH_ALLOCATION", tmp_path / "d.json")
    monkeypatch.setattr(be, "BREADTH_SWEEP", tmp_path / "e.json")
    monkeypatch.setattr(be, "DOCKET", tmp_path / "f.json")
    (tmp_path / "jc.json").write_text(json.dumps({
        "at": "2026-10-13T00:00:00+00:00", "quota": {"carry": 300, "newfam": 100},
        "totals": {"capacity_measured": 400},
        "families": {"carry": {"mined": 9000, "unjudged": 9000, "judged_total": 900},
                     "newfam": {"mined": 9000, "unjudged": 9000, "judged_total": 0}},
        "value_ranking": _ranking(["carry", "newfam"])}))
    monkeypatch.setattr(be, "JUDGE_COVERAGE", tmp_path / "jc.json")
    monkeypatch.setattr(jc, "GATE_LEDGER", tmp_path / "ledger.jsonl")
    doc = be.build()
    assert doc["verdict"] == "MEASURED" and doc["steer"]["saturated"] == ["carry"]
    j = doc["judge"]
    assert j["shipped"]["saturated_share"] == 0.75
    assert j["steered_replay"]["saturated_share"] < j["legacy_replay"]["saturated_share"]
    assert j["total_cells_steered"] == j["total_cells_legacy"]
    assert any(ln.get("family") == "carry" for ln in doc["missed_growth_lines"])
    path = be.write(doc, tmp_path / "out.json")
    assert fence.judge(path)["verdict"] == "FAIL"                   # 0.75 saturated shipped
    monkeypatch.setattr(be, "OUT", path)
    assert be.load_steer()["saturated"] == ["carry"]


# ------------------------------------------------------------------------------ consumers
def test_frontier_ceo_drops_saturated_stale_gaps_and_proposes_the_frontier(
        monkeypatch: pytest.MonkeyPatch) -> None:
    ceo = importlib.import_module("research.frontier_ceo")
    st = _steer()
    monkeypatch.setattr(be, "load_steer", lambda *a, **k: st)
    out = ceo._with_breadth_frontier([{"family": "cross_asset_residual", "needs": "price only"},
                                      {"family": "lead_lag", "needs": ""}])
    fams = [m["family"] for m in out]
    assert "cross_asset_residual" not in fams
    assert fams[0] == "lead_lag" and set(st["frontier"]) <= set(fams)
    monkeypatch.setattr(be, "load_steer", lambda *a, **k: None)
    stale = [{"family": "cross_asset_residual", "needs": ""}]
    assert ceo._with_breadth_frontier(stale) == stale


def test_seat_brief_names_saturated_and_frontier_only_when_fresh(tmp_path: Path) -> None:
    from libs.research import proposer_seat as ps
    p = tmp_path / "BE.json"
    st = _steer()
    p.write_text(json.dumps({"generated_utc": datetime.now(UTC).isoformat(), "steer": st}))
    lines = ps.breadth_steer_lines(p)
    assert "cross_asset_residual (346)" in lines[0] and "ghost_family" in lines[1]
    p.write_text(json.dumps({"generated_utc": (datetime.now(UTC) - timedelta(hours=9))
                             .isoformat(), "steer": st}))
    assert ps.breadth_steer_lines(p) == []
    assert ps.breadth_steer_lines(tmp_path / "absent.json") == []


def test_every_consumer_is_wired_and_the_leg_and_fence_are_scheduled() -> None:
    src = {n: (_DESK / "research" / f"{n}.py").read_text("utf-8")
           for n in ("breadth_sweep", "judge_coverage", "frontier_ceo", "hourly_cycle")}
    assert "apportion(out, MAX_NEW_PER_RUN)" in src["breadth_sweep"]
    assert "allocate(backlog, capacity, ranking=ranking, steer=steer)" in src["judge_coverage"]
    assert "_with_breadth_frontier" in src["frontier_ceo"]
    assert '_costed("breadth_enforcer"' in src["hourly_cycle"]
    assert src["hourly_cycle"].index('_costed("breadth_enforcer"') < src["hourly_cycle"].index(
        '_costed("frontier_ceo"')
    assert "breadth_steer_lines" in (_ROOT / "libs" / "ops" / "deepseek_cycle.py").read_text()
    assert "_breadth_brief" in (_ROOT / "scripts" / "kimi_hunter.py").read_text()
    hc = importlib.import_module("research.hourly_cycle")
    from libs.research.layers import LEG_LAYER
    assert "breadth_enforcer" in hc.CORE_LEGS
    assert hc.department_of("breadth_enforcer") == "meta" and LEG_LAYER["breadth_enforcer"]
    assert hc.LEG_BUDGET_SEC["breadth_enforcer"] >= 120
    lg = importlib.import_module("run_law_gate")
    assert ("check_breadth_enforcer.py", ()) in lg._LAW_FENCES
    assert ("check_breadth_enforcer.py", ("--require-state",)) in lg._STATE_FENCES
