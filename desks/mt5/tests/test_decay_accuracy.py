"""The decay detectors' scorecard (desk idea 249, brief U5).

Pinned: CUSUM recovers a planted mean shift sooner than the current rule; a stationary positive
series raises few false alarms and every one is costed; a missed event is counted; fewer than
five events is UNMEASURED; the replay is causal; and the organ writes only its own report.
"""
from __future__ import annotations

import json
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import decay_accuracy as A  # noqa: E402
from research import decay_monitor as D  # noqa: E402

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _pts(rs: list[float]) -> list[tuple[datetime, float]]:
    return [(T0 + timedelta(hours=6 * i), r) for i, r in enumerate(rs)]


def _series(name: str, rs: list[float]) -> dict[str, Any]:
    return {"name": name, "source": "test", "points": _pts(rs), "phases": ["forward"]}


CANON = {"survivors": {"x": {"cell": "EURUSD.carry.p=abc", "gates": {"expected_value": {"ev": 0.3}},
                             "shadow_spec": {"symbol": "EURUSD", "family": "carry",
                                             "selector": "asia"}}}}


def test_constants_are_imported_from_decay_monitor() -> None:
    assert A.IMPORT_NOTE.startswith("imported")
    assert (A.N_MIN_VERDICT, A.EARLY_FADE_N, A.EARLY_FADE_R, A.DD_HARD_R, A.TRAIL_MAX_TRADES,
            A.T_PROMOTE) == (D.N_MIN_VERDICT, D.EARLY_FADE_N, D.EARLY_FADE_R, D.DD_HARD_R,
                             D.TRAIL_MAX_TRADES, D.T_PROMOTE)


def test_cusum_recovers_a_planted_shift_sooner_than_current() -> None:
    rng = random.Random(7)  # noqa: S311
    # 40 healthy trades at the certified +0.3R, then the edge flips to -0.6R.
    good = [rng.gauss(0.3, 0.8) for _ in range(40)]
    bad = [rng.gauss(-0.6, 0.8) for _ in range(40)]
    rs = good + bad
    pts = _pts(rs)
    cus = A.cusum_alarms(rs, 0.3, 1.0)
    cur = A.current_states(pts)
    first_cus = next(j for j, v in enumerate(cus) if v and j >= 40)
    first_cur = next((j for j, v in enumerate(cur) if v and j >= 40), len(rs))
    assert first_cus < first_cur
    sc_cus = A.score(rs, cus, [j for j, v in enumerate(cus) if v])
    sc_cur = A.score(rs, cur, A._onsets(cur))
    assert sc_cus["n_events"] >= 1
    assert sc_cus["misses"] <= sc_cur["misses"]
    assert sorted(sc_cus["leads_r"])[0] < (sorted(sc_cur["leads_r"]) or [1e9])[0]


def test_stationary_positive_series_few_false_alarms_and_costed() -> None:
    rng = random.Random(11)  # noqa: S311
    rs = [rng.gauss(0.3, 1.0) for _ in range(400)]
    cus = A.cusum_alarms(rs, 0.3, 1.0)
    sc = A.score(rs, cus, [j for j, v in enumerate(cus) if v])
    assert sc["n_alarms"] <= 400 * 0.05
    if sc["false_alarms"]:
        assert sc["false_alarm_cost_r"] > 0
    # a hand-built false alarm: alarm at 0, then 20 +0.5R trades -> cost 0.5 * 10R = 5R
    rs2 = [0.5] * 25
    state = [False] * 25
    state[0] = True
    sc2 = A.score(rs2, state, [0])
    assert sc2["false_alarms"] == 1
    assert sc2["false_alarm_cost_r"] == 5.0


def test_missed_event_is_counted() -> None:
    rs = [0.5, 0.5, -1.0, -1.0, -1.0, -1.0, 0.5]
    never = [False] * len(rs)
    sc = A.score(rs, never, [])
    assert sc["n_events"] == 1 and sc["misses"] == 1 and sc["leads_r"] == []
    late = [False] * len(rs)
    late[5] = True                                   # at the trough: too late, still a miss
    assert A.score(rs, late, [5])["misses"] == 1
    early = [False] * len(rs)
    early[2] = True
    s3 = A.score(rs, early, [2])
    assert s3["misses"] == 0 and s3["leads_r"] == [1.0]


def test_fewer_than_five_events_is_unmeasured(tmp_path: Path) -> None:
    rs = [0.3] * 10 + [-1.0] * 4 + [0.3] * 10
    doc = A.run(shadow=[_series("EURUSD_carry_asia", rs)], live=[], canon=CANON,
                drift_state={}, report_path=tmp_path / "r.json")
    assert doc["detectors"]["CURRENT"]["n_events"] < A.MIN_EVENTS
    assert doc["promotion"]["CUSUM"]["verdict"] == A.UNMEASURED
    assert doc["series"][0]["anchor"]["basis"].startswith("certified")
    assert doc["detectors"]["FEATURE_DRIFT"]["verdict"] == A.UNMEASURED


def test_promotion_verdict_rules() -> None:
    cur = {"n_events": 6, "misses": 2, "median_lead_r": 3.0, "false_alarm_cost_r": 4.0}
    good = {"n_events": 6, "misses": 1, "median_lead_r": 1.5, "false_alarm_cost_r": 3.0}
    assert A.promotion_verdict(cur, good)["verdict"] == "PROMOTABLE"
    costly = dict(good, false_alarm_cost_r=9.0)
    v = A.promotion_verdict(cur, costly)
    assert v["verdict"] == "NOT_PROMOTABLE" and "cost" in v["why"]


def test_replay_is_causal() -> None:
    rng = random.Random(3)  # noqa: S311
    rs = [rng.gauss(0.0, 1.0) for _ in range(120)]
    more = rs + [rng.gauss(-1.0, 1.0) for _ in range(60)]
    assert A.cusum_alarms(more, 0.3, 1.0)[:120] == A.cusum_alarms(rs, 0.3, 1.0)
    assert A.current_states(_pts(more))[:120] == A.current_states(_pts(rs))
    eps = [{"first_flag_at": (T0 + timedelta(hours=6 * 50)).isoformat(), "cleared_at": None}]
    a = A.drift_alarms(_pts(rs), eps)
    b = A.drift_alarms(_pts(more), eps)
    assert a is not None and b is not None and b[:120] == a
    # a self-anchor reads only its first 30 trades
    r1 = A.evaluate_series(_series("ZZZ_x", rs), [], None)
    r2 = A.evaluate_series(_series("ZZZ_x", more), [], None)
    assert r1["anchor"]["mu0"] == r2["anchor"]["mu0"] and r1["scored_from"] == A.SELF_ANCHOR_N


def test_organ_writes_only_its_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    desk = tmp_path / "desk"
    (desk / "data").mkdir(parents=True)
    (desk / "reports").mkdir()
    sleeves = desk / "data" / "sleeves.json"
    sleeves.write_text(json.dumps({"sleeves": [{"name": "eurusd_carry_asia_p_abc"}]}))
    ledger = desk / "data" / "live_ledger.jsonl"
    ledger.write_text("".join(json.dumps({"time": (T0 + timedelta(hours=i)).isoformat(),
                                          "sleeve": "eurusd_carry_asia_p_abc",
                                          "r_multiple": -1.0 if 10 <= i < 16 else 0.4,
                                          "risk_quote": 10.0}) + "\n" for i in range(40)))
    canon = desk / "data" / "canon.json"
    canon.write_text(json.dumps(CANON))
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "ledger_EURUSD_carry_asia.json").write_text(json.dumps(
        [{"exit_time": (T0 + timedelta(hours=i)).isoformat(), "r_multiple": 0.2}
         for i in range(5)]))
    report = desk / "reports" / "DECAY_ACCURACY.json"
    monkeypatch.setattr(A, "LEDGER", ledger)
    monkeypatch.setattr(A, "SLEEVES_FILE", sleeves)
    monkeypatch.setattr(A, "CANON", canon)
    monkeypatch.setattr(A, "DRIFT_STATE", desk / "data" / "feature_drift_state.json")
    monkeypatch.setattr(A, "SHADOW_LEDGER_DIRS", (shadow,))
    monkeypatch.setattr(A, "REPORT", report)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    doc = A.run(report_path=report)
    after = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert set(after) - set(before) == {report}
    assert all(after[p] == b for p, b in before.items())
    assert doc["inputs"]["live_series"] == 1 and doc["inputs"]["shadow_series"] == 1
    assert doc["series"][-1]["anchor"]["basis"] == "certified_exact"
    assert {x["rail"] for x in doc["missed_growth"]} == {f"decay_accuracy.{d}" for d in A.DETECTORS}
    assert json.loads(report.read_text())["generated_at"] == doc["generated_at"]
