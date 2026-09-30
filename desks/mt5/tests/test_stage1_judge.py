"""The two-stage judge's first stage: honest windows, honest multiplicity, every cell ruled, wired.

The property everything rests on is the boundary: stage 1 must never read a day the sealed
gauntlet's walk-forward TEST region or its lockbox could read, for ANY development length and ANY
lockbox cut the sealed code could produce. The rest pins that every backlog cell gets a logged
verdict (UNBUILDABLE never silent), that every evaluated cell is a charged trial, that a reject is
re-screenable and never deleted, and that the order consumers read keeps v4 re-mint first.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parent.parent
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mass_screen as MS  # noqa: E402
import stage1_judge as S  # noqa: E402
import stage1_record as REC  # noqa: E402
from research.gate_policy import LOCKBOX_FRAC, carve_lockbox, lockbox_cut  # noqa: E402


# ------------------------------------------------------------------------ the boundary
def test_wf_lower_bound_is_the_minimum_over_every_development_length() -> None:
    for lo in range(0, 400, 7):
        for hi in (lo, lo + 1, lo + 13, lo + 250):
            b = S.wf_start_lb(lo, hi)
            assert all(b <= MS.wf_start_rank(n) for n in range(lo, hi + 1))
            assert b in {MS.wf_start_rank(n) for n in range(lo, hi + 1)}


def _union(earliest: date, today: date, weekend: bool) -> list[pd.Timestamp]:
    idx = pd.date_range(earliest, today - timedelta(days=1), freq="D")
    return list(idx if weekend else idx[idx.weekday < 5])


@pytest.mark.parametrize("weekend", [False, True])
@pytest.mark.parametrize("years", [2, 5, 9, 16])
def test_lockbox_lower_bound_never_exceeds_the_sealed_cut(weekend: bool, years: int) -> None:
    today = date(2026, 9, 30)
    earliest = today - timedelta(days=365 * years)
    for start in (earliest, earliest + timedelta(days=200)):
        cal = _union(start, today, weekend)
        cut = lockbox_cut([pd.Series(0.0, index=cal)])
        assert cut is not None
        assert S.lockbox_cut_lb(earliest, today) <= cut.date()


def test_training_window_never_reaches_walk_forward_test_or_lockbox() -> None:
    """Random activity patterns (dense early, dense late, sparse), random sweep calendars: every
    training day precedes both the sealed WF test region of the dev series and the lockbox."""
    rng = np.random.default_rng(3)
    today = date(2026, 9, 30)
    earliest = date(2014, 1, 1)
    cut_lb = S.lockbox_cut_lb(earliest, today)
    for trial in range(150):
        first = earliest + timedelta(days=int(rng.integers(0, 3000)))
        cal = pd.date_range(first, today - timedelta(days=1), freq="B")
        w = np.linspace(1.0, float(rng.uniform(0.02, 8.0)), len(cal))
        p = np.clip(w / w.max() * rng.uniform(0.05, 0.9), 0, 1)
        days = cal[rng.random(len(cal)) < p]
        if len(days) < 60:
            continue
        end, _ = S.train_boundary(days.values.astype("datetime64[D]"), first, today, cut_lb,
                                  MS.TRAIN_FRAC)
        # any sweep: union from `earliest` (weekday dense) plus this cell
        union_start = earliest + timedelta(days=int(rng.integers(0, 1500)))
        union = sorted(set(_union(union_start, today, bool(trial % 2))) | set(days))
        cut = lockbox_cut([pd.Series(0.0, index=pd.DatetimeIndex(union))])
        assert end <= cut.date()
        ds = pd.Series(1.0, index=days)
        (dev,), _held = carve_lockbox([ds], cut)
        r = MS.wf_start_rank(len(dev))
        if r < len(dev):
            assert end <= dev.index[r].date(), (trial, end, dev.index[r])
        assert LOCKBOX_FRAC > 0


def test_mirrored_floors_match_the_sealed_gauntlet() -> None:
    src = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
    assert "len(_d) < 60" in src and S.MIN_DAYS_FULL == 60
    assert "test_size=max(20, len(arr) // 6)" in src and S.MIN_TRAIN_DAYS == MS.WF_MIN_TEST
    assert "_lock_cut = lockbox_cut(daily)" in src
    assert "daily, lock_daily = carve_lockbox(daily, _lock_cut)" in src


# ------------------------------------------------------------------------ verdicts
def test_bh_over_the_run_and_the_stress_decide_pass_and_reject() -> None:
    rows = [{"cid": f"c{i}", "verdict": "EVALUATED", "p": 0.5, "mean_r": 0.0,
             "mean_r_x3": -0.1} for i in range(40)]
    rows += [{"cid": "strong", "verdict": "EVALUATED", "p": 1e-9, "mean_r": 0.2,
              "mean_r_x3": 0.1},
             {"cid": "fragile", "verdict": "EVALUATED", "p": 1e-9, "mean_r": 0.2,
              "mean_r_x3": -0.01},
             {"cid": "thin", "verdict": REC.PASS, "basis": "UNSCREENABLE_TRAIN_WINDOW", "p": 1.0},
             {"cid": "short", "verdict": REC.REJECT, "reason": "R_UNDER_60_DAYS"},
             {"cid": "broken", "verdict": REC.UNBUILDABLE, "cause": "MODIFIER_REFUSED"}]
    fdr = S.finalise(rows)
    by = {r["cid"]: r for r in rows}
    assert fdr["m"] == 44                       # untestable counted, unbuildable not
    assert by["strong"]["verdict"] == REC.PASS and by["strong"]["basis"] == "BH_SURVIVOR"
    assert by["fragile"]["reason"] == "R_COST_STRESS_X3"
    assert by["c0"]["reason"] == "R_BH_NOT_SIGNIFICANT"
    assert by["broken"]["verdict"] == REC.UNBUILDABLE


@pytest.mark.parametrize("why,cause", [
    ("NOT_RUN_MODIFIER: conditioner='event': no conditioning series", "MODIFIER_REFUSED"),
    ("formula raised TypeError: family_formula() got an unexpected keyword argument "
     "'population'", "PARAM_SIGNATURE_MISMATCH"),
    ("unsupported family parameter(s): w; refusing", "PARAM_SIGNATURE_MISMATCH"),
    ("factor basket incomplete: no H1 bars for USDZAR", "FACTOR_BASKET_INCOMPLETE"),
    ("no M30 bars for XAUUSD", "NO_CHART_BARS"),
    ("no implementation of family 'x' in families", "NO_FAMILY_IMPLEMENTATION"),
    ("input load failed: KeyError: 'x'", "INPUT_LOAD_FAILED"),
    ("jump raised ValueError: bad", "FAMILY_RAISED"),
    (None, "BUILD_FAILED_UNNAMED")])
def test_unbuildable_causes_are_named_from_the_sealed_builders_words(why, cause) -> None:
    assert S.unbuildable_cause(why) == cause


# ------------------------------------------------------------------------ the fence
def _doc(proj, target, backlog):
    return {"stage1": {"projected_per_day_18c_50pct": proj, "target_per_day": target},
            "backlog": {"cells": backlog}}


def test_fence_fails_when_the_projection_misses_the_target_with_a_backlog() -> None:
    assert S.throughput_fence(_doc(60_000, 100_000, 1_400_000))["status"] == "FAIL"
    assert S.throughput_fence(_doc(160_000, 100_000, 1_400_000))["status"] == "PASS"
    assert S.throughput_fence(_doc(1, 100_000, 0))["status"] == "PASS"
    assert S.throughput_fence(_doc("UNMEASURED", 100_000, 5))["status"] == "UNMEASURED"


def test_target_ramps_from_100k_to_500k() -> None:
    t0 = datetime(2026, 9, 30, tzinfo=UTC)
    assert S.target_for(t0.isoformat(), t0) == 100_000
    assert S.target_for(t0.isoformat(), t0 + timedelta(days=7)) == 300_000
    assert S.target_for(t0.isoformat(), t0 + timedelta(days=40)) == 500_000


def test_the_published_stage1_projection_meets_the_target() -> None:
    """THE FENCE ON THE MEASURED RATE: fails whenever the latest JUDGING_TWO_STAGE.json projects
    stage 1 under its day's target while cells are waiting."""
    if not S.REPORT.exists():
        pytest.skip("stage 1 has not published on this host")
    doc = json.loads(S.REPORT.read_text("utf-8"))
    fence = S.throughput_fence(doc)
    assert fence["status"] != "FAIL", fence["why"]


# ------------------------------------------------------------------------ the record, the order
def test_tiers_keep_named_priorities_first_and_rejects_last(tmp_path: Path) -> None:
    db = tmp_path / "r.sqlite"
    con = REC.connect(db)
    for cid, v, basis in (("a", REC.PASS, "BH_SURVIVOR"),
                          ("b", REC.PASS, "UNSCREENABLE_TRAIN_WINDOW"),
                          ("c", REC.REJECT, None), ("d", REC.UNBUILDABLE, None),
                          ("e", REC.REJECT, None)):
        con.execute("INSERT INTO cells(cid, verdict, basis, ruled_at) VALUES(?,?,?,?)",
                    (cid, v, basis, "2026-09-30T00:00:00+00:00"))
    con.commit()
    con.close()
    pri = tmp_path / "priority_remint.json"
    pri.write_text(json.dumps({"attestation": "x", "cells": ["e"]}))
    t = REC.tiers(["a", "b", "c", "d", "e", "z"], db, REC.priority_cells([pri]))
    assert t == {"a": 1, "b": 2, "c": 4, "d": 4, "e": 0, "z": 3}
    assert REC.tiers(["a"], tmp_path / "absent.sqlite", set()) == {"a": 3}


def test_warmer_orders_the_backlog_by_stage1_tier_as_a_permutation() -> None:
    import warm_gauntlet_cache as W
    specs = [{"sym": s, "_never_judged": nj} for s, nj in
             (("rej", True), ("old", False), ("pass", True), ("unruled", True), ("pri", True))]
    tier = {"rej": 4, "old": 1, "pass": 1, "unruled": 3, "pri": 0}
    out = W.backlog_first(specs, {id(sp): tier[sp["sym"]] for sp in specs})
    assert [sp["sym"] for sp in out] == ["pri", "pass", "unruled", "rej", "old"]
    assert W.backlog_first(specs, None) == sorted(
        specs, key=lambda sp: 0 if sp["_never_judged"] else 1)


# ------------------------------------------------------------------------ end to end, real bars
def _real_rows(n: int) -> list[dict]:
    import external_gauntlet as G
    doc = json.loads((DESK / "data" / "hypotheses" / "external_survivors.json").read_text())
    want = ("session_range_breakout", "adx_channel_hybrid", "mean_reversion_rsi")
    out, broken = [], []
    for r in doc:
        p = r.get("params") or {}
        if r.get("symbol") in ("EURUSD", "GBPUSD", "USDJPY") and "timeframe" not in p:
            if r.get("family") in want and len(out) < n:
                out.append(r)
            elif r.get("family") == "formula" and not broken:
                broken.append(r)                    # PARAM_SIGNATURE_MISMATCH in the sealed build
    assert G.UNI.exists()
    return out + broken


def test_every_backlog_cell_is_ruled_charged_recorded_and_rescreenable(tmp_path: Path) -> None:
    rows = _real_rows(10)
    docket = tmp_path / "docket.json"
    docket.write_text(json.dumps(rows))
    out = tmp_path / "out"
    db = out / "rec.sqlite"
    doc = S.run(budget_s=240, workers=1, cap=100, docket=docket,
                seen_path=tmp_path / "none.json", out_dir=out, db=db)
    ruled = doc["run"]["ruled"]
    assert ruled == len({(r["symbol"], r["family"], json.dumps(r["params"], sort_keys=True))
                         for r in rows})
    con = sqlite3.connect(db)
    verdicts = dict(con.execute("SELECT verdict, COUNT(*) FROM cells GROUP BY verdict"))
    assert sum(verdicts.values()) == ruled
    assert verdicts.get(REC.UNBUILDABLE, 0) >= 1              # the formula row, never silent
    assert doc["unbuildable_by_cause_this_run"]
    assert con.execute("SELECT COUNT(*) FROM rulings").fetchone()[0] == ruled
    trials = [json.loads(ln) for ln in (out / S.TRIALS.name).read_text().splitlines()]
    screened = sum(t["cells_screened"] for t in trials)
    assert screened == ruled - verdicts.get(REC.UNBUILDABLE, 0)
    assert all(t["fdr_q"] == S.FDR_Q for t in trials)
    assert (out / S.PRIORITY.name).exists()
    assert doc["fence"]["status"] in ("PASS", "FAIL", "UNMEASURED")
    # a second run rules nothing new: every cell is stage-1 ruled and not due
    doc2 = S.run(budget_s=120, workers=1, cap=100, docket=docket,
                 seen_path=tmp_path / "none.json", out_dir=out, db=db)
    assert doc2["run"]["ruled"] == 0
    # a family code change re-opens its cells; nothing was ever deleted
    con.execute("UPDATE cells SET family_ver='old' WHERE family='session_range_breakout'")
    con.commit()
    n_srb = con.execute("SELECT COUNT(*) FROM cells WHERE family='session_range_breakout'"
                        ).fetchone()[0]
    doc3 = S.run(budget_s=240, workers=1, cap=100, docket=docket,
                 seen_path=tmp_path / "none.json", out_dir=out, db=db)
    assert doc3["run"]["ruled"] == n_srb
    assert con.execute("SELECT COUNT(*) FROM cells").fetchone()[0] == ruled
    assert con.execute("SELECT MAX(times_ruled) FROM cells").fetchone()[0] == 2
    con.close()


def test_sealed_judged_cells_are_not_backlog(tmp_path: Path) -> None:
    import external_gauntlet as G
    rows = _real_rows(3)[:3]
    docket = tmp_path / "docket.json"
    docket.write_text(json.dumps(rows))
    cid = G.cell_id({"sym": rows[0]["symbol"], "family": rows[0]["family"],
                     "params": rows[0]["params"]})
    seen = tmp_path / "seen.json"
    seen.write_text(json.dumps({cid: "2026-09-29T00:00:00+00:00"}, indent=0))
    hashes, _hit, status = S.stream_seen(seen)
    assert status == "MEASURED" and S.h64(cid) in hashes
    con = REC.connect(tmp_path / "r.sqlite")
    meta = json.loads((G.UNI / "universe.json").read_text())
    chosen, census = S.select_backlog(G, meta, con, cap=10, now=datetime.now(tz=UTC),
                                      docket=docket, seen=hashes)
    assert census["sealed_judged"] == 1 and cid not in {c["cid"] for c in chosen}
    con.close()


def test_the_vectorised_path_agrees_with_the_engine_path() -> None:
    import external_gauntlet as G
    from mass_screen import TRAIN_FRAC
    today = datetime.now(tz=UTC).date()
    S._init_worker(S.lockbox_cut_lb(date(2010, 7, 2), today).isoformat(), TRAIN_FRAC)
    params = {"feat": "", "op": "gt", "thr": 0.0, "direction": 1, "hold": 4, "stop_atr": 2.5,
              "cond_feat": "", "hour": 8, "weekday": -1, "leader": "", "atr_n": 20, "gv": 1}
    spec = {"cid": "x", "sym": "EURUSD", "family": "mass_screen_clock", "params": params,
            "tf": "H1"}
    v = S.evaluate_vector(spec)
    e = S.evaluate_engine(spec)
    assert v is not None and v["path"] == "vector" and e["path"] == "engine"
    assert v["n_days_full"] == e["n_days_full"]
    assert abs(v["n_days_train"] - e["n_days_train"]) <= 1
    assert abs(v["mean_r"] - e["mean_r"]) < 0.05
    assert G is not None


# ------------------------------------------------------------------------ wiring
def test_the_leg_is_wired_with_a_budget_a_layer_and_a_consumer() -> None:
    import hourly_cycle as HC

    from libs.research import experiment_ledger as EL
    from libs.research import layers
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"stage1_judge", "research/stage1_judge.py", "--once", "--budget-s", "600"' in src
    assert HC.LEG_BUDGET_SEC["stage1_judge"] > 600
    assert HC.department_of("stage1_judge") == "validate"
    assert src.index('_costed("merge_docket"') < src.index('_costed("stage1_judge"') \
        < src.index('_costed("judging_throughput"') < src.index('_costed("external_gauntlet"')
    assert layers.LEG_LAYER.get("stage1_judge") == "prediction"
    assert EL.STAGE1_TRIALS.name == S.TRIALS.name
    jt = (DESK / "research" / "judging_throughput.py").read_text("utf-8")
    assert 'payload["two_stage"] = _two_stage()' in jt
    wg = (DESK / "scripts" / "warm_gauntlet_cache.py").read_text("utf-8")
    assert "backlog_first(keep, stage1_ranks(G, keep))" in wg


def test_stage1_trials_join_the_lifetime_ledger(tmp_path: Path) -> None:
    from libs.research import experiment_ledger as EL
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in (
        {"family": "carry", "cells_screened": 7},
        {"family": "carry", "cells_screened": 5, "dry_run": True},
        {"family": "jump", "cells_screened": 2})))
    assert EL._stage1_counts(p) == (9, {"carry": 7, "jump": 2})
