"""THE ROTATION UNDER A KILLING SCHEDULER, OVER THE REAL CORE ROSTER (Auditor HOLD, 2026-10-29).

Unit tests of `plan_pass` prove the plan is right on paper. The defect the Auditor measured was
the gap between paper and the pass: `main()` runs legs in FILE ORDER and `MT5-HourlyCore` kills the
pass where it stands, so a leg the plan admitted but placed past the kill line never runs. This
file runs the plan the way the box does -- the real 152-leg core roster read from
`hourly_cycle.py`, file order, a 3,300 s kill, a 2,640 s budget, 72 hourly passes, 3 seeds,
synthetic costs, the real `read_attendance` / `record` / `load_record` round trip -- and pins:

  MF1  on the MEASURED box (the always-run set alone 3,749 s, past the kill) every money-critical
       leg runs on every pass. Before: 8 of them (the tail ones) missed 72/72.
  MF2  with 30 STUCK legs (300 s cap, 1,150 s need) no pass is killed and no money-critical pass
       is missed: `plan_pass` charges the raised cap and bounds the raised seconds per pass.
  MF3  mining (discovery-department) legs run AT LEAST as often as under the LIVE policy in every
       scenario: never throttle mining.

The LIVE policy is the pre-ageing `plan_pass`/`should_run` (base branch), reproduced in
`_LivePolicy` so the comparison is pinned without the old module.
"""
from __future__ import annotations

import inspect
import json
import random
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from libs.ops import leg_rotation as LR

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"

KILL_S = 3300.0
BUDGET_S = 2640.0
PASSES = 72
SEEDS = (1, 2, 3)
T0 = datetime(2026, 10, 29, tzinfo=UTC)
N_STUCK = 30
STUCK_BASE_S = 300.0
STUCK_NEED_S = 1150.0

#: The always-run set as MEASURED on the box 2026-10-29 (3,749 s: tier_s at its 1,500 s
#: LEG_TIMEOUT, smoke_release at 120 s) and a HEALTHY box where it fits (1,439 s).
ALWAYS_MEASURED = {"smoke_release": 120.0, "health": 60.0, "replication_civilization": 900.0,
                   "tier_s_door": 300.0, "record_tape": 300.0, "heal_clocks": 200.0,
                   "judging_throughput": 150.0, "promoter": 150.0, "tier_s": 1500.0,
                   "forward_reconcile": 9.0, "bars_state": 60.0}
ALWAYS_HEALTHY = {"smoke_release": 60.0, "health": 30.0, "replication_civilization": 300.0,
                  "tier_s_door": 60.0, "record_tape": 120.0, "heal_clocks": 60.0,
                  "judging_throughput": 120.0, "promoter": 60.0, "tier_s": 600.0,
                  "forward_reconcile": 9.0, "bars_state": 20.0}
SCENARIOS = ("healthy", "measured", "stuck")


def core_roster() -> tuple[list[str], list[str], set[str]]:
    """(core roster in file order, its mining legs, its liftable legs) from the real cycle."""
    for p in (str(ROOT), str(DESK), str(DESK / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import hourly_cycle as hc
    full = LR.legs_in_order(LR.CYCLE)
    roster = [leg for leg in full if hc.in_plan(leg, "core")]
    mining = [leg for leg in roster if hc.department_of(leg) == "discovery"]
    lift = getattr(LR, "liftable_legs", None)
    liftable = set(lift(LR.CYCLE)) if lift is not None else set()
    return roster, mining, liftable


@dataclass
class Box:
    need: dict[str, float]
    cap: dict[str, float]
    stuck: set[str] = field(default_factory=set)


def synth(roster: list[str], mining: list[str], scenario: str, seed: int) -> Box:
    rng = random.Random(seed)
    always = ALWAYS_MEASURED if scenario == "measured" else ALWAYS_HEALTHY
    need: dict[str, float] = {}
    cap: dict[str, float] = dict.fromkeys(roster, float("inf"))
    others = [leg for leg in roster if leg not in LR.ALWAYS_RUN and leg not in LR.MONEY_CRITICAL
              and leg not in mining]
    cheap = set(rng.sample(others, 30))
    for leg in roster:
        if leg in always:
            need[leg] = always[leg]
        elif leg in LR.ALWAYS_RUN:
            need[leg] = 30.0
        elif leg in LR.MONEY_CRITICAL:
            need[leg] = rng.uniform(2.0, 12.0)
        elif leg in mining:
            need[leg] = rng.uniform(40.0, 180.0)
        elif leg in cheap:
            need[leg] = rng.uniform(0.5, 14.0)
        else:
            need[leg] = min(400.0, max(5.0, rng.lognormvariate(3.7, 0.8)))
    if scenario == "measured":
        need["tier_s"], cap["tier_s"] = 1e9, 1500.0          # LEG_TIMEOUT every pass
    stuck: set[str] = set()
    if scenario == "stuck":
        stuck = set(rng.sample([leg for leg in others if leg not in cheap], N_STUCK))
        for leg in stuck:
            need[leg], cap[leg] = STUCK_NEED_S, STUCK_BASE_S
    return Box(need=need, cap=cap, stuck=stuck)


class _LiveDecision:
    """The base branch's Decision: membership plus the overrun yield, nothing else."""

    def __init__(self, budget_s: float, deferred: set[str]) -> None:
        self.budget_s = budget_s
        self.deferred = deferred

    def runs(self, leg: str) -> bool:
        return leg not in self.deferred

    def should_run(self, leg: str, att: LR.Attendance, elapsed_s: float) -> tuple[bool, str]:
        if leg in self.deferred:
            return False, "deferred"
        if leg in LR.ALWAYS_RUN:
            return True, ""
        if elapsed_s > self.budget_s and att.runs.get(leg, 0) > 0:
            return False, "overrun"
        return True, ""


class _LivePolicy:
    """The LIVE `plan_pass` (base branch): always-run first, then oldest-first while it fits."""

    @staticmethod
    def plan(roster: list[str], att: LR.Attendance, now: datetime) -> _LiveDecision:
        order = {leg: i for i, leg in enumerate(roster)}

        def rank(n: str) -> tuple[int, float, int]:
            tier = 0 if n in LR.ALWAYS_RUN else (1 if att.runs.get(n, 0) <= 0 else 2)
            age = att.age_s(n, now)
            return (tier, -age if age != float("inf") else float("-inf"), order[n])
        spent, deferred = 0.0, set()
        for leg in sorted(roster, key=rank):
            cost = att.cost_s(leg)
            if leg in LR.ALWAYS_RUN or spent + cost <= BUDGET_S:
                spent += cost
            else:
                deferred.add(leg)
        return _LiveDecision(BUDGET_S, deferred)


def _call(fn: Any, *args: Any, **kw: Any) -> Any:
    params = inspect.signature(fn).parameters
    return fn(*args, **{k: v for k, v in kw.items() if k in params})


def _row(leg: str, at: datetime, wall: float, outcome: str, out: str | None) -> str:
    return json.dumps({"at": at.isoformat(), "run": leg, "kind": "hourly_cycle",
                       "outcome": outcome, "wall_s": round(wall, 3), "output_hash": out})


def simulate(lr: ModuleType | None, scenario: str, seed: int, tmp: Path, *,
             passes: int = PASSES) -> dict[str, Any]:
    """Run `passes` hourly passes; `lr=None` runs the LIVE policy."""
    mod = lr or LR
    roster, mining, liftable = core_roster()
    box = synth(roster, mining, scenario, seed)
    tmp.mkdir(parents=True, exist_ok=True)
    ledger, rec = tmp / "compute_ledger.jsonl", tmp / "LEG_ROTATION.json"
    for p in (ledger, rec):
        p.unlink(missing_ok=True)
    hist = []
    for leg in roster:
        if leg in box.stuck:
            hist += [_row(leg, T0 - timedelta(hours=48 - i), STUCK_BASE_S, "TIMEOUT", None)
                     for i in range(3)]
        else:
            n, c = box.need[leg], box.cap[leg]
            hist.append(_row(leg, T0 - timedelta(hours=48), min(n, c),
                             "TIMEOUT" if n > c else "ok", f"{leg}-h"))
    ledger.write_text("\n".join(hist) + "\n", encoding="utf-8")
    rng = random.Random(seed * 7919 + 1)
    runs = dict.fromkeys(roster, 0)
    finished = dict.fromkeys(roster, 0)
    killed = 0
    money = [leg for leg in roster if leg in LR.MONEY_CRITICAL]
    for k in range(passes):
        start = T0 + timedelta(seconds=3600.0 * k)
        prior = mod.load_record(rec)
        att = mod.read_attendance(ledger, prior=mod.Attendance.from_json(prior.get("attendance")))
        if lr is None:
            dec: Any = _LivePolicy.plan(roster, att, start)
            lifted: list[str] = []
        else:
            dec = _call(mod.plan_pass, roster, att, plan="core", budget_s=BUDGET_S, now=start,
                        full_roster=roster, prior=prior, kill_s=KILL_S, liftable=liftable,
                        mining=set(mining))
            _call(mod.record, dec, att, [], path=rec, started=start, now=start, complete=False,
                  residents={})
            lifted = list(getattr(dec, "lifted", []) or [])
        order = lifted + [leg for leg in roster if leg not in set(lifted)]
        t, ran, rows, was_killed = 0.0, [], [], False
        for leg in order:
            if not dec.runs(leg) or not dec.should_run(leg, att, t)[0]:
                continue
            cap = box.cap[leg]
            if leg in box.stuck and lr is not None:
                if hasattr(dec, "cap_for"):
                    cap = dec.cap_for(leg, att, cap)[0]
                elif hasattr(mod, "measured_cap"):
                    cap = mod.measured_cap(leg, att, cap, dec.budget_s)[0]
            need = box.need[leg] * (1.0 if leg in box.stuck else rng.uniform(0.85, 1.15))
            wall, timed_out = min(need, cap), need > cap
            if t + wall > KILL_S:
                was_killed = True
                break
            t += wall
            ran.append(leg)
            finished[leg] += not timed_out
            out = None if (timed_out and leg in box.stuck) else f"{leg}-{k}"
            rows.append(_row(leg, start + timedelta(seconds=t), wall,
                             "TIMEOUT" if timed_out else "ok", out))
        if rows:
            with ledger.open("a", encoding="utf-8") as fh:
                fh.write("\n".join(rows) + "\n")
        killed += was_killed
        for leg in ran:
            runs[leg] += 1
        if lr is not None and not was_killed:
            _call(mod.record, dec, att, ran, path=rec, started=start,
                  now=start + timedelta(seconds=t), residents={})
        elif lr is None:
            rec.write_text(json.dumps({"attendance": att.to_json()}), encoding="utf-8")
    return {"scenario": scenario, "seed": seed, "killed_passes": killed,
            "money_missed": sum(passes - runs[leg] for leg in money),
            "money_dark": sorted(leg for leg in money if runs[leg] == 0),
            "mining_runs": sum(runs[leg] for leg in mining),
            "dark": sorted(leg for leg in roster if runs[leg] == 0),
            "n_roster": len(roster), "runs": runs, "finished": finished,
            "stuck_finished": sum(finished[leg] for leg in box.stuck)}


@pytest.fixture(autouse=True)
def _no_live_resident_queue(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(LR, "RESIDENT_LOCKS", tmp_path / "_resident_locks")


def test_the_sim_runs_the_real_core_roster() -> None:
    roster, mining, liftable = core_roster()
    assert len(roster) == 152
    assert mining, "the core roster has discovery-department (mining) legs"
    money = [leg for leg in roster if leg in LR.MONEY_CRITICAL]
    assert set(money) <= liftable, "every money-critical core leg can be run ahead of file order"


@pytest.mark.parametrize("seed", SEEDS)
def test_mf1_measured_box_every_money_leg_runs_every_pass(seed: int, tmp_path: Path) -> None:
    """MF1: always-run 3,749 s is past the 3,300 s kill. At 344ab14 the 8 tail money-critical legs
    (kelly_survival, prop_challenge_allocator, release_identity, edge_reliability, fill_markout,
    productivity_census, box_state_freshness, desk_health) missed 72/72 passes (576 misses); LIVE
    missed all 12 core money legs (864). Now they run first and miss none."""
    live = simulate(None, "measured", seed, tmp_path / "live")
    new = simulate(LR, "measured", seed, tmp_path / "new")
    assert live["money_missed"] == 12 * PASSES, "the reproduction must reproduce"
    assert new["money_missed"] == 0, new["money_dark"]
    assert new["money_dark"] == []
    assert "desk_health" not in new["dark"]
    # What file order still cannot reach is the always-run tail past the kill, and the one leg
    # whose call closes over main() locals -- every one of them dark under LIVE as well.
    assert set(new["dark"]) <= set(live["dark"])
    assert set(new["dark"]) <= {"tier_s", "forward_reconcile", "bars_state", "frontier_report"}


@pytest.mark.parametrize("seed", SEEDS)
def test_mf2_stuck_legs_do_not_kill_passes_or_starve_money(seed: int, tmp_path: Path) -> None:
    """MF2: 30 stuck legs (300 s cap, need 1,150 s). At 344ab14 the uncharged, unbounded raise
    killed 59-62 of 72 passes and missed 290-303 money-critical passes (Auditor: 17/72 and 74-85
    on his costs). The raise is now charged and bounded per pass: no pass killed, no money pass
    missed -- and the stuck legs still FINISH (LIVE: never, at 300 s forever)."""
    live = simulate(None, "stuck", seed, tmp_path / "live")
    new = simulate(LR, "stuck", seed, tmp_path / "new")
    assert live["stuck_finished"] == 0
    assert new["killed_passes"] == 0
    assert new["money_missed"] == 0
    # 26-33 finishes over the 3 seeds (344ab14: 14-16, while killing most passes).
    assert new["stuck_finished"] >= 20


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("seed", SEEDS)
def test_mf3_mining_legs_never_run_less_than_live(scenario: str, seed: int,
                                                  tmp_path: Path) -> None:
    """MF3: never throttle mining. At 344ab14 mining runs fell 0-4% (healthy) and 24-27% (stuck)
    below LIVE; now they are at least LIVE's in every scenario, with no new killed pass and no
    leg left dark that LIVE reached."""
    live = simulate(None, scenario, seed, tmp_path / "live")
    new = simulate(LR, scenario, seed, tmp_path / "new")
    assert new["mining_runs"] >= live["mining_runs"], (scenario, seed, new["mining_runs"],
                                                       live["mining_runs"])
    assert new["money_missed"] <= live["money_missed"]
    assert new["killed_passes"] <= live["killed_passes"]
    assert set(new["dark"]) <= set(live["dark"])
