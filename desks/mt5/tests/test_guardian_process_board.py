"""The guardian acts on the process board (principal 2026-11-25 01:47Z: every broken component is
known and fixed box-natively). FAILING/STALE non-money tasks are re-run inside the existing
bounds and ended first when hung; alert-only verdicts and every money-path fault are PAGED and
never touched; a re-runnable task still faulted after 2 re-runs in 24h is paged."""
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

NOW = datetime(2026, 11, 25, 2, 0, tzinfo=UTC)


def _row(name, verdict, *, code=1, state="Enabled", age=None, limit=None):
    return {"name": name, "verdict": verdict, "why": f"{verdict} why", "state": state,
            "last_result_code": code, "artifact_age_min": age, "contract_max_age_min": limit}


def _board(root: Path, rows, *, at: datetime = NOW, uncontracted: int = 88) -> None:
    p = root / heal.BOARD_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"at": at.isoformat(), "counts": {"UNCONTRACTED": uncontracted},
                             "processes": rows}), encoding="utf-8")


def _run(root: Path, *, now: datetime = NOW, running: bool = False):
    calls: list[tuple[str, str]] = []
    doc = rheal.run(root=root, apply=True, out=root / "out.json",
                    ledger_path=root / "ledger.json", now=now,
                    run_task=lambda t: calls.append(("run", t)) or True,
                    task_running=lambda t: running,
                    end_task=lambda t: calls.append(("end", t)) or True)
    return doc, calls


def _board_calls(calls, name):
    return [c for c in calls if c[1] == name]


def test_failing_research_task_is_rerun(tmp_path):
    _board(tmp_path, [_row("MT5-DeepenUniverse", "FAILING")])
    _, calls = _run(tmp_path)
    assert _board_calls(calls, "MT5-DeepenUniverse") == [("run", "MT5-DeepenUniverse")]


def test_hung_stale_task_is_ended_then_run(tmp_path):
    _board(tmp_path, [_row("MT5-LocalConvert", "STALE", code=267009, age=616, limit=180)])
    _, calls = _run(tmp_path, running=True)
    assert _board_calls(calls, "MT5-LocalConvert") == [("end", "MT5-LocalConvert"),
                                                       ("run", "MT5-LocalConvert")]


def test_money_path_is_never_touched_and_stale_output_is_paged(tmp_path):
    _board(tmp_path, [_row("MT5-GatewayResident", "STALE", code=0, age=36085, limit=10),
                      _row("MT5-TerminalBoot", "STALE", code=2, age=3695, limit=180),
                      _row("MT5-AllocatorFast", "STALE", code=0, age=4820, limit=90),
                      _row("Quant-SignTrain", "FAILING"),
                      _row("E8-Executor", "FAILING")])
    doc, calls = _run(tmp_path, running=True)
    assert calls == []
    paged = {a["organ"]: a["detail"] for a in doc["moneypath_alerts"]}
    assert paged["moneypath board MT5-GatewayResident"].startswith("STALE_OUTPUT")
    assert {"moneypath board MT5-TerminalBoot", "moneypath board MT5-AllocatorFast",
            "moneypath board Quant-SignTrain", "moneypath board E8-Executor"} <= set(paged)


def test_alert_only_verdicts_page_and_never_run(tmp_path):
    _board(tmp_path, [_row("MT5-CertHygiene", "NOT_SCHEDULED", code=None, state="ABSENT"),
                      _row("MT5-FrontierAudit (causal discovery)", "NO_ARTIFACT",
                           code=None, state="COMPONENT")])
    doc, calls = _run(tmp_path)
    assert calls == []
    assert set(doc["moneypath_paged"]) >= {"board MT5-CertHygiene",
                                           "board MT5-FrontierAudit (causal discovery)"}


def test_disabled_and_ok_rows_are_left_alone(tmp_path):
    _board(tmp_path, [_row("MT5-SealIfClean", "DISABLED"), _row("MT5-Hourly", "OK", code=0)])
    doc, calls = _run(tmp_path)
    assert calls == [] and not [a for a in doc["moneypath_alerts"] if "board" in a["organ"]]


def test_still_faulted_after_two_reruns_is_paged(tmp_path):
    _board(tmp_path, [_row("MT5-DeepenUniverse", "FAILING")])
    doc1, _ = _run(tmp_path)
    assert "board MT5-DeepenUniverse" not in doc1["moneypath_paged"]
    later = NOW + timedelta(seconds=rheal.RERUN_MIN_GAP_S + 60)
    _board(tmp_path, [_row("MT5-DeepenUniverse", "FAILING")], at=later)
    doc2, calls = _run(tmp_path, now=later)
    assert _board_calls(calls, "MT5-DeepenUniverse") == [("run", "MT5-DeepenUniverse")]
    assert "board MT5-DeepenUniverse" in doc2["moneypath_paged"]


def test_stale_board_is_not_acted_on(tmp_path):
    _board(tmp_path, [_row("MT5-DeepenUniverse", "FAILING")],
           at=NOW - timedelta(hours=heal.BOARD_STALE_H + 1))
    doc, calls = _run(tmp_path)
    assert _board_calls(calls, "MT5-DeepenUniverse") == []
    assert _board_calls(calls, heal.BOARD_TASK) == [("run", heal.BOARD_TASK)]
    assert doc["board"]["measured"] is False


def test_census_carries_the_uncontracted_count(tmp_path):
    _board(tmp_path, [], uncontracted=88)
    doc, _ = _run(tmp_path)
    assert doc["board"]["uncontracted"] == 88 and doc["board"]["measured"] is True


def test_never_list_covers_the_operators_money_tasks():
    for t in ("MT5-GatewayResident", "MT5-Gateway", "E8-Executor", "MT5-FTMO-Executor",
              "MT5-FusionDeadmanLive", "MT5-AccountState", "MT5-ClockFixer",
              "MT5-E8WindowGuard", "MT5-TerminalBoot", "MT5-TickRecorder", "MemecoinBot",
              "MT5-LivePriority", "Quant-SignTrain", "Quant-WorkflowGate",
              "MT5-ReleaseAuthority", "MT5-AdoptRelease", "Claude-Bridge-Watchdog"):
        assert not heal.board_rerunnable(t), t
    for t in ("MT5-DeepenUniverse", "MT5-LocalConvert", "MT5-MergeDocket", "MT5-LawGate"):
        assert heal.board_rerunnable(t), t


def _write(root: Path, rel: str, doc) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")


def _inv(doc, key):
    return next(i for i in doc["invariants"] if i["invariant"] == key)


def test_paused_gateway_is_not_stale_output(tmp_path):
    _board(tmp_path, [_row("MT5-GatewayResident", "STALE", code=0, age=36085, limit=10)])
    (tmp_path / heal.GATEWAY_PAUSED).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / heal.GATEWAY_PAUSED).write_text("fusion 0", encoding="utf-8")
    doc, calls = _run(tmp_path)
    assert calls == [] and _inv(doc, "I3")["holds"] is True
    assert not [a for a in doc["moneypath_alerts"] if "GatewayResident" in a["organ"]]


def test_invariants_i3_i4_i5_are_checked_and_paged(tmp_path, monkeypatch):
    monkeypatch.setattr(heal, "_is_producing_host", lambda root, rel: True)   # the box
    _board(tmp_path, [_row("MT5-AllocatorFast", "STALE", code=0, age=4820, limit=90)])
    _write(tmp_path, heal.RELEASE_FILE, {"ok": False, "measured": True, "age_h": 344.2,
                                         "running_sha": "b78e2ec03fda", "reason": "REFUSED"})
    doc, _ = _run(tmp_path)
    assert _inv(doc, "I3")["holds"] is False and "MT5-AllocatorFast" in _inv(doc, "I3")["detail"]
    assert _inv(doc, "I4")["holds"] is False and "344.2h" in _inv(doc, "I4")["detail"]
    assert _inv(doc, "I5")["holds"] is False          # no ALERT_ROUTING.json: nothing proves it
    assert {"invariant I3", "invariant I4", "invariant I5"} <= set(doc["moneypath_paged"])
    assert _inv(doc, "I1")["holds"] is True and "UNMEASURED" in _inv(doc, "I1")["detail"]


def test_invariants_hold_when_the_box_matches_the_design(tmp_path):
    _board(tmp_path, [_row("MT5-Hourly", "OK", code=0)])
    _write(tmp_path, heal.RELEASE_FILE, {"ok": True, "measured": True, "age_h": 2.0,
                                         "running_sha": "a" * 40})
    _write(tmp_path, heal.ROUTING_FILE, {"all_routed": True, "alerts_24h": 3, "routed_24h": 3})
    _write(tmp_path, heal.INVARIANT_FILES["I2"], {"holds": False, "why": "159 candidates, 0 live"})
    doc, _ = _run(tmp_path)
    assert all(_inv(doc, k)["holds"] for k in ("I3", "I4", "I5"))
    assert _inv(doc, "I2")["holds"] is False and "invariant I2" in doc["moneypath_paged"]
