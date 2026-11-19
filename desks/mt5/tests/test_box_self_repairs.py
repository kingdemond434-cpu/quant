"""THE THREE BOX SELF-REPAIRS (principal 2026-11-19: "add them").

1. Every account trades every market day: a miss is a CRITICAL defect carrying its diagnosis.
2. A stalled judge or tape recorder is cured by re-running the task that owns it, within bounds.
3. A box behind the shipped branch re-runs the one adopter, within bounds, never a writer of ours.

Motivated by 2026-11-19: the box ran 11-10 code, FTMO refused 356/357 strategies for days, and
certification sat stalled for 27h with the pager naming it and nothing curing it.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import desk_self_heal as heal  # noqa: E402
import run_desk_self_heal as rheal  # noqa: E402
from desks.mt5.research import accounts_traded as at  # noqa: E402
from desks.mt5.research import plumbing_watchdog as pw  # noqa: E402

#: A Monday: the last completed market day is Friday 2026-11-13, never the weekend.
MONDAY = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
FRIDAY = "2026-11-13T15:00:00+00:00"


def _journal(desk: Path, rel: str, rows: list[dict]) -> None:
    p = desk / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _desk(tmp_path: Path) -> Path:
    d = tmp_path / "desks" / "mt5"
    d.mkdir(parents=True)
    return d


# ------------------------------------------------------------------ 1. accounts traded
def test_a_monday_pass_judges_friday_never_the_weekend() -> None:
    assert at.last_market_day(MONDAY).isoformat() == "2026-11-13"
    assert at.last_market_day(datetime(2026, 11, 18, 1, tzinfo=UTC)).isoformat() == "2026-11-17"


def test_each_lane_counts_only_rows_that_reached_the_venue(tmp_path: Path) -> None:
    d = _desk(tmp_path)
    _journal(d, "data/decision_ledger.jsonl", [{"time": FRIDAY, "taken": True},
                                               {"time": FRIDAY, "taken": False,
                                                "reason": "no_signal"}])
    _journal(d, "data/e8_intents.jsonl", [{"at": FRIDAY, "status": "SENT"}])
    _journal(d, "data/ftmo_exec_intents.jsonl",
             [{"at": FRIDAY, "status": "NOT_LISTED"}] * 356 + [{"at": FRIDAY,
                                                                "status": "WOULD_SEND"}])
    m = at.measure(d, MONDAY)
    a = m["accounts"]
    assert (a["fusion"]["placed"], a["e8"]["placed"], a["ftmo"]["placed"]) == (1, 1, 0)
    assert a["ftmo"]["top_refusals"][0] == {"why": "NOT_LISTED", "n": 356}


def test_a_day_with_no_placement_on_the_box_is_a_critical_defect_with_its_cause(
        tmp_path: Path) -> None:
    """The 2026-11-19 shape, end to end: old code, every FTMO strategy refused, nothing sent."""
    d = _desk(tmp_path)
    _journal(d, "data/decision_ledger.jsonl", [{"time": FRIDAY, "taken": True}])
    _journal(d, "data/e8_intents.jsonl", [{"at": FRIDAY, "status": "SENT"}])
    _journal(d, "data/ftmo_exec_intents.jsonl", [{"at": FRIDAY, "status": "NOT_LISTED"}] * 3)
    rows, facts = pw.check_accounts_traded(tmp_path, MONDAY, on_box=True,
                                           adoption={"commits_behind": 412, "head": "b78e2ec03"})
    assert facts["applicable"] is True
    assert [r["organ"] for r in rows] == ["account:ftmo"]
    r = rows[0]
    assert r["severity"] == "CRITICAL" and r["repair"]
    assert "NOT_LISTED x3" in r["evidence"]
    assert "412 commit(s) behind" in r["evidence"]


def test_a_lane_that_wrote_nothing_is_named_as_not_running(tmp_path: Path) -> None:
    d = _desk(tmp_path)
    _journal(d, "data/decision_ledger.jsonl", [{"time": FRIDAY, "taken": True}])
    _journal(d, "data/ftmo_exec_intents.jsonl", [{"at": FRIDAY, "status": "SENT"}])
    rows, _ = pw.check_accounts_traded(tmp_path, MONDAY, on_box=True)
    assert [r["organ"] for r in rows] == ["account:e8"]
    assert "never ran here" in rows[0]["evidence"]


def test_off_the_trading_box_the_published_copy_is_never_judged(tmp_path: Path) -> None:
    _desk(tmp_path)
    rows, facts = pw.check_accounts_traded(tmp_path, MONDAY, on_box=False)
    assert rows == [] and facts["applicable"] is False


def test_the_traded_check_is_read_only() -> None:
    src = Path(at.__file__).read_text(encoding="utf-8")
    for bad in ("subprocess", "schtasks", "write_text", "os.replace", "create_order", "ARMED"):
        assert bad not in src, bad


# ------------------------------------------------------------------ 3. code drift
def _lag_row() -> dict:
    return pw.defect("adoption_lag", pw.ADOPT_TASK, "HEAD is 9 commits behind", "adopt",
                     severity="CRITICAL")


def test_a_box_behind_the_branch_runs_the_one_adopter_and_is_bounded(tmp_path: Path,
                                                                      monkeypatch) -> None:
    seen: list = []

    def runner(argv, timeout_s, cwd):
        seen.append(list(argv))
        return {"rc": 0, "tail": ""}
    monkeypatch.setattr(pw, "ADOPTION_STATE", tmp_path / "ADOPTION_STATE.json")
    state = tmp_path / "readopt_state.json"
    rec = pw.repair_code_drift([_lag_row()], apply=True, now=MONDAY, runner=runner,
                               state_path=state, root=tmp_path)
    assert seen == [["schtasks", "/Run", "/TN", "MT5-AdoptRelease"]]
    assert rec and rec["name"] == "readopt"
    again = pw.repair_code_drift([_lag_row()], apply=True, now=MONDAY + timedelta(minutes=15),
                                 runner=runner, state_path=state, root=tmp_path)
    assert again and again["result"] == "BOUNDED" and len(seen) == 1


def test_the_daily_cap_holds_even_past_the_gap() -> None:
    runs = [(MONDAY - timedelta(hours=3 * i)).isoformat() for i in range(1, 7)]
    ok, why = pw.readopt_due({"runs": runs}, MONDAY)
    assert not ok and "cap" in why
    assert pw.readopt_due({"runs": []}, MONDAY) == (True, "due")


def test_no_drift_no_repair_and_a_retired_box_is_never_touched(tmp_path: Path) -> None:
    assert pw.repair_code_drift([], apply=True, now=MONDAY, root=tmp_path) is None
    (tmp_path / "desks/mt5/data").mkdir(parents=True)
    (tmp_path / "desks/mt5/data/BOX_RETIRED").write_text("retired")
    rec = pw.repair_code_drift([_lag_row()], apply=True, now=MONDAY, root=tmp_path,
                               state_path=tmp_path / "s.json")
    assert rec == {"name": "readopt", "result": "SKIPPED", "why": "data/BOX_RETIRED present"}


# ------------------------------------------------------------------ 2. stalls
def _judge_stall(root: Path, **incidents) -> None:
    p = root / "desks/mt5/reports"
    p.mkdir(parents=True, exist_ok=True)
    (p / "JUDGE_STALL.json").write_text(json.dumps({"incidents": {
        k: {"open": v, "why": f"{k} why"} for k, v in incidents.items()}}), encoding="utf-8")


def test_a_dead_judge_is_cured_by_re_running_the_gauntlet_task(tmp_path: Path) -> None:
    _judge_stall(tmp_path, resident_dead=True, cores_idle=False)
    f = heal.check_judge_stall(tmp_path, datetime.now(UTC))
    assert not f.ok and f.fixable
    ran: list[str] = []
    rem, _ = heal.plan([f], run_task=lambda t: ran.append(t) or True)
    for r in rem:
        r.apply()
    assert ran == ["MT5-Gauntlet"]


def test_a_measurement_fault_is_escalated_not_guessed_at(tmp_path: Path) -> None:
    _judge_stall(tmp_path, host_unreadable=True)
    f = heal.check_judge_stall(tmp_path, datetime.now(UTC))
    assert not f.ok and not f.fixable


def test_a_stopped_tape_recorder_is_re_run_but_a_down_terminal_is_not(tmp_path: Path) -> None:
    p = tmp_path / "desks/mt5/reports"
    p.mkdir(parents=True)
    doc = {"status": "RED", "n_red": 2,
           "cause": "the terminal link is up and the recorder reports no pause: it is not "
                    "running or not advancing"}
    (p / "TAPE_FRESHNESS.json").write_text(json.dumps(doc), encoding="utf-8")
    f = heal.check_tape(tmp_path, datetime.now(UTC))
    assert not f.ok and f.fixable
    doc["cause"] = "the terminal link is down"
    (p / "TAPE_FRESHNESS.json").write_text(json.dumps(doc), encoding="utf-8")
    assert not heal.check_tape(tmp_path, datetime.now(UTC)).fixable


def test_re_runs_are_bounded_per_task(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(heal, "_is_producing_host", lambda root, rel: True)
    _judge_stall(tmp_path, sweep_dead=True)
    ran: list[str] = []
    now = datetime.now(UTC)
    kw = {"root": tmp_path, "apply": True, "out": tmp_path / "out.json",
          "ledger_path": tmp_path / "ledger.json", "run_task": lambda t: ran.append(t) or True}
    rheal.run(now=now, **kw)
    assert ran.count("MT5-Gauntlet") == 1, "cadence and judge stall share one run"
    doc = rheal.run(now=now + timedelta(minutes=30), **kw)
    assert ran.count("MT5-Gauntlet") == 1
    assert any(b["task"] == "MT5-Gauntlet" for b in doc["bounded"])
    rheal.run(now=now + timedelta(hours=3), **kw)
    assert ran.count("MT5-Gauntlet") == 2
