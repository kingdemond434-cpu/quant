"""0x800710E0 on a Running task is the task's own resident instance, not a refusal (2026-10-29).

MEASURED on the trading box: 36 tasks carried last result 0x800710E0, every one in state Running.
Under MultipleInstances=IgnoreNew that code means "an instance is already running": the task's
resident or long instance refused a relaunch. None were run-as or logon refusals. These pin the
reading: such a row is RESIDENT_RUNNING (never refused, never UNCONTRACTED), judged by the
freshest of its artifact and its log. Output older than the task's own ExecutionTimeLimit (for
example MT5-IndependenceIntake, PT20M, log 96 min old) is HUNG, named, and the headline is RED.
"""

from __future__ import annotations

import importlib.util
import os
import time
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ph = _load("process_health_resident_under_test", "ops/process_health.py")
tl = _load("task_limits_under_test", "ops/task_limits.py")
ns = _load("never_stale_resident_under_test", "ops/never_stale.py")

SIGNED = "-2147020576"   # 0x800710E0 as schtasks prints it

TASK_XML = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><URI>\\{name}</URI></RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <Repetition><Interval>PT1H</Interval></Repetition>
      <StartBoundary>2026-10-01T00:07:00</StartBoundary>
    </TimeTrigger>
  </Triggers>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    {limit}
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>cmd.exe</Command>
      <Arguments>/c "py.exe" "x.py" &gt;&gt; "{log}" 2&gt;&amp;1"</Arguments>
    </Exec>
  </Actions>
</Task>
"""


def _xml(name: str, log: str, limit: str | None = "PT20M") -> bytes:
    lim = "" if limit is None else f"<ExecutionTimeLimit>{limit}</ExecutionTimeLimit>"
    return TASK_XML.format(name=name, log=log, limit=lim).encode("utf-16")


@pytest.fixture
def box(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    (tmp_path / "Tasks").mkdir()
    (tmp_path / "desks" / "mt5" / "logs").mkdir(parents=True)
    monkeypatch.setattr(ph, "ROOT", tmp_path)
    monkeypatch.setattr(ph, "_contracts", lambda: {})
    monkeypatch.setattr(ph, "account_key_file", lambda: {"state": "present"})
    monkeypatch.setattr(ph, "account_key_backup", lambda: {"state": "ok"})
    real = tl.task_limits
    monkeypatch.setattr(ph, "_task_limits", lambda name: real(name, tmp_path / "Tasks"))
    return tmp_path


def _task(box: Path, name: str, *, log_age_min: float | None, limit: str | None = "PT20M",
          declared_log: bool = True) -> None:
    log = box / "logs-elsewhere" / f"{name}.log"
    (box / "Tasks" / name).write_bytes(_xml(name, str(log) if declared_log else "nul.txt",
                                            limit))
    if log_age_min is not None:
        target = log if declared_log else box / "desks" / "mt5" / "logs" / f"{name}.log"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x", "utf-8")
        t = time.time() - log_age_min * 60
        os.utime(target, (t, t))


def _build(monkeypatch: pytest.MonkeyPatch, *rows: dict[str, str]) -> dict[str, Any]:
    monkeypatch.setattr(ph, "_tasks", lambda: (list(rows), "OK schtasks"))
    return ph.build()


def _row(name: str, state: str = "Running", code: str = SIGNED) -> dict[str, str]:
    return {"TaskName": f"\\{name}", "Status": state, "Scheduled Task State": "Enabled",
            "Last Result": code, "Last Run Time": "29/10/2026 14:07:00"}


def _by(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {r["name"]: r for r in doc["processes"]}


# --- the task definition's own limits ----------------------------------------------------------

@pytest.mark.parametrize(("text", "minutes"), [
    ("PT20M", 20.0), ("PT1H30M", 90.0), ("P3D", 4320.0), ("PT72H", 4320.0), ("PT90S", 1.5),
    ("PT0S", None), ("", None), ("garbage", None), (None, None), ("P", None),
])
def test_iso_durations_read_in_minutes_and_pt0s_is_no_limit(text: str | None,
                                                            minutes: float | None) -> None:
    assert tl.duration_min(text) == minutes


def test_a_task_definition_yields_its_limit_cadence_policy_and_log() -> None:
    lim = tl.parse_limits(_xml("MT5-IndependenceIntake", r"C:\opt\quant\desks\mt5\logs\I.log"))
    assert lim["execution_time_limit"] == "PT20M" and lim["execution_time_limit_min"] == 20.0
    assert lim["interval_min"] == 60.0 and lim["multiple_instances"] == "IgnoreNew"
    assert lim["logs"] == [r"C:\opt\quant\desks\mt5\logs\I.log"]


def test_an_absent_limit_is_the_schedulers_72_hour_default_and_pt0s_is_none() -> None:
    assert tl.parse_limits(_xml("X", "a.log", None))["execution_time_limit_min"] == 4320.0
    assert tl.parse_limits(_xml("X", "a.log", "PT0S"))["execution_time_limit_min"] is None


def test_a_missing_definition_never_raises(tmp_path: Path) -> None:
    lim = tl.task_limits("\\Nope", tmp_path)
    assert lim["execution_time_limit_min"] is None and "unreadable" in lim["why"]


# --- the verdict -------------------------------------------------------------------------------

def test_running_past_its_own_execution_limit_is_hung_red_and_named(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    _task(box, "MT5-IndependenceIntake", log_age_min=96)
    doc = _build(monkeypatch, _row("MT5-IndependenceIntake"))
    row = _by(doc)["MT5-IndependenceIntake"]
    assert row["verdict"] == "HUNG"
    assert "MT5-IndependenceIntake" in row["why"] and "PT20M" in row["why"]
    assert "96 min" in row["why"]
    assert row["resident"]["execution_time_limit_min"] == 20.0
    assert 95 <= row["resident"]["freshest_output_age_min"] <= 97
    assert doc["status"] == "RED" and doc["hung"] == ["MT5-IndependenceIntake"]
    assert doc["n_needing_attention"] == 1


def test_a_resident_with_fresh_output_is_resident_running_never_uncontracted_or_refused(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    _task(box, "MT5-NewsDesk", log_age_min=5, limit="PT0S")
    doc = _build(monkeypatch, _row("MT5-NewsDesk"))
    row = _by(doc)["MT5-NewsDesk"]
    assert row["verdict"] == "RESIDENT_RUNNING"
    assert row["last_result"] == ph.RESIDENT_MEANING and "already running" in row["last_result"]
    assert "administrator refused" not in row["last_result"]
    assert row["last_result_code"] == 0x800710E0
    assert doc["status"] == "OK" and doc["n_needing_attention"] == 0 and doc["hung"] == []


def test_the_desk_log_convention_is_read_when_the_action_declares_no_log(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    _task(box, "MT5-Quiet", log_age_min=40, declared_log=False)   # desks/mt5/logs/MT5-Quiet.log
    row = _by(_build(monkeypatch, _row("MT5-Quiet")))["MT5-Quiet"]
    assert row["verdict"] == "HUNG"
    assert row["resident"]["freshest_output"].endswith(os.path.join("logs", "MT5-Quiet.log"))


def test_a_stale_contracted_artifact_beats_a_fresh_log(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    _task(box, "MT5-Gateway", log_age_min=1, limit="PT0S")
    art = box / "gw.json"
    art.write_text("{}", "utf-8")
    t = time.time() - 30 * 60
    os.utime(art, (t, t))
    monkeypatch.setattr(ph, "_contracts", lambda: {"MT5-Gateway": ("gw.json", 10, "broker")})
    row = _by(_build(monkeypatch, _row("MT5-Gateway")))["MT5-Gateway"]
    assert row["verdict"] == "STALE" and "10 min contract" in row["why"]


def test_a_daemon_with_no_limit_is_judged_against_its_cadence(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    _task(box, "MT5-Daemon", log_age_min=200, limit="PT0S")   # PT1H cadence, 2x = 120 min
    row = _by(_build(monkeypatch, _row("MT5-Daemon")))["MT5-Daemon"]
    assert row["verdict"] == "STALE" and "60 min cadence" in row["why"]


def test_zero_observable_output_is_resident_unmeasured_a_fault_never_green(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    # rule 13 (coordinator ruling on #510): no artifact contract and no log is a FAULT
    _task(box, "MT5-Silent", log_age_min=None)
    doc = _build(monkeypatch, _row("MT5-Silent"))
    row = _by(doc)["MT5-Silent"]
    assert row["verdict"] == "RESIDENT_UNMEASURED"
    assert row["resident"]["freshest_output"] is None
    assert row["cure"] == ph.RESIDENT_UNMEASURED_CURE
    assert row["cure"].startswith("declare a log or contract an artifact")
    assert "cure: declare a log or contract an artifact" in row["why"]
    assert doc["n_needing_attention"] == 1
    assert doc["status"] == "ATTENTION"          # AMBER: never OK, and not RED like HUNG
    assert doc["hung"] == []


def test_one_silent_resident_among_healthy_ones_still_keeps_the_headline_off_ok(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    _task(box, "MT5-Silent", log_age_min=None)
    _task(box, "MT5-NewsDesk", log_age_min=3, limit="PT0S")
    doc = _build(monkeypatch, _row("MT5-Silent"), _row("MT5-NewsDesk"))
    assert doc["counts"] == {"RESIDENT_UNMEASURED": 1, "RESIDENT_RUNNING": 1}
    assert doc["status"] == "ATTENTION" and doc["n_needing_attention"] == 1


def test_the_task_folder_is_process_healths_tasks_dir_when_it_defines_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    # reconciled with #491: one folder, named TASKS_DIR in both modules
    assert isinstance(tl.TASKS_DIR, Path) and tl.TASKS_DIR.parts[-2:] == ("System32", "Tasks")
    (tmp_path / "MT5-X").write_bytes(_xml("MT5-X", "a.log", "PT7M"))
    monkeypatch.setattr(ph, "TASKS_DIR", tmp_path, raising=False)
    assert ph._task_limits("\\MT5-X")["execution_time_limit_min"] == 7.0


def test_the_same_code_on_a_task_that_is_not_running_is_still_failing(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    _task(box, "MT5-Stopped", log_age_min=1)
    row = _by(_build(monkeypatch, _row("MT5-Stopped", state="Ready")))["MT5-Stopped"]
    assert row["verdict"] == "FAILING" and row["resident"] is None


def test_never_stale_skips_resident_running_and_escalates_hung_and_silent_with_cures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = {"processes": [
        {"name": "MT5-NewsDesk", "verdict": "RESIDENT_RUNNING", "last_result_code": 0x800710E0},
        {"name": "MT5-Silent", "verdict": "RESIDENT_UNMEASURED", "last_result_code": 0x800710E0,
         "cure": ph.RESIDENT_UNMEASURED_CURE},
        {"name": "MT5-IndependenceIntake", "verdict": "HUNG", "why": "HUNG: ...",
         "last_result_code": 0x800710E0},
    ]}
    monkeypatch.setattr(ns, "_age_min", lambda p: 5.0)
    monkeypatch.setattr(ns, "_read", lambda p: doc)
    monkeypatch.setattr(ns, "_capital_faults", lambda: [])
    out = ns.run(apply=False)
    by = {e["task"]: e for e in out["escalated"]}
    assert set(by) == {"MT5-Silent", "MT5-IndependenceIntake"}
    assert by["MT5-IndependenceIntake"]["diagnosis"] == ns.HUNG_DIAGNOSIS
    assert by["MT5-Silent"]["diagnosis"] == ph.RESIDENT_UNMEASURED_CURE
    assert out["status"] == "NEEDS_HUMAN"
    assert out["acted"] == []


# --- Auditor HOLD on #510 (35ed8f4ec): the regressions ----------------------------------------

def _art(box: Path, rel: str, age_min: float) -> None:
    art = box / rel
    art.write_text("{}", "utf-8")
    t = time.time() - age_min * 60
    os.utime(art, (t, t))


def test_an_unreadable_task_definition_is_resident_unmeasured_with_its_cure_never_green(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    # MF1: garbage XML, no contract, 5-day-old desk log -> was RESIDENT_RUNNING
    (box / "Tasks" / "MT5-Garbled").write_bytes(b"<Task><not-closed>")
    log = box / "desks" / "mt5" / "logs" / "MT5-Garbled.log"
    log.write_text("x", "utf-8")
    t = time.time() - 5 * 1440 * 60
    os.utime(log, (t, t))
    doc = _build(monkeypatch, _row("MT5-Garbled"))
    row = _by(doc)["MT5-Garbled"]
    assert row["verdict"] == "RESIDENT_UNMEASURED"
    assert "task definition unreadable" in row["why"]
    assert row["cure"] == ph.RESIDENT_LIMITS_CURE
    assert "cure: " + ph.RESIDENT_LIMITS_CURE in row["why"]
    assert doc["status"] == "ATTENTION" and doc["n_needing_attention"] == 1


def test_a_wedged_instance_appending_to_its_log_is_hung_on_its_contracted_artifact(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    # MF2: PT20M limit, contracted artifact 300 min old, log 1 min old -> was RESIDENT_RUNNING
    _task(box, "MT5-Wedged", log_age_min=1, limit="PT20M")
    _art(box, "wedged.json", 300)
    monkeypatch.setattr(ph, "_contracts", lambda: {"MT5-Wedged": ("wedged.json", 600, "x")})
    doc = _build(monkeypatch, _row("MT5-Wedged"))
    row = _by(doc)["MT5-Wedged"]
    assert row["verdict"] == "HUNG" and "wedged.json" in row["why"]
    assert row["resident"]["judged_output"] == "wedged.json"
    assert doc["status"] == "RED" and doc["hung"] == ["MT5-Wedged"]


def test_no_limit_no_contract_and_no_cadence_is_resident_unmeasured_not_green(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    # Should: PT0S + no contract + no repetition interval -> nothing bounds the output's age
    xml = _xml("MT5-Unbounded", str(box / "u.log"), "PT0S").decode("utf-16")
    xml = xml.replace("<Repetition><Interval>PT1H</Interval></Repetition>", "")
    (box / "Tasks" / "MT5-Unbounded").write_bytes(xml.encode("utf-16"))
    (box / "u.log").write_text("x", "utf-8")
    doc = _build(monkeypatch, _row("MT5-Unbounded"))
    row = _by(doc)["MT5-Unbounded"]
    assert row["verdict"] == "RESIDENT_UNMEASURED"
    assert row["cure"] == ph.RESIDENT_UNBOUNDED_CURE and doc["status"] == "ATTENTION"


@pytest.mark.parametrize("enc", ["utf-8", "utf-16"])
def test_a_definition_carrying_a_doctype_is_refused_before_parsing(
    tmp_path: Path, enc: str,
) -> None:
    # Should: XXE / billion-laughs -- a DOCTYPE never reaches ET.fromstring
    bomb = ('<?xml version="1.0"?><!DOCTYPE t [<!ENTITY a "aaaaaaaaaa">'
            '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]><Task>&b;</Task>')
    with pytest.raises(ValueError, match="DOCTYPE"):
        tl.parse_limits(bomb.encode(enc))
    (tmp_path / "MT5-Bomb").write_bytes(bomb.encode(enc))
    lim = tl.task_limits("\\MT5-Bomb", tmp_path)
    assert lim["execution_time_limit_min"] is None and "unreadable" in lim["why"]


# --- Auditor HOLD on #510 v2 (43b98b484) -------------------------------------------------------

def test_an_end_of_run_artifact_mid_run_inside_its_limit_is_not_hung(
    monkeypatch: pytest.MonkeyPatch, box: Path,
) -> None:
    # MF probe: limit 90, interval 60, contract 180, artifact 125 min old (written at the END of
    # the last run), current run 70 min in -> was HUNG while the contract still holds
    _task(box, "MT5-EndWriter", log_age_min=1, limit="PT90M")
    _art(box, "end.json", 125)
    monkeypatch.setattr(ph, "_contracts", lambda: {"MT5-EndWriter": ("end.json", 180, "x")})
    doc = _build(monkeypatch, _row("MT5-EndWriter"))
    row = _by(doc)["MT5-EndWriter"]
    assert row["verdict"] == "RESIDENT_RUNNING", row["why"]
    assert doc["status"] == "OK" and doc["hung"] == []
    # past limit + interval (150 min) it IS hung, contract or not
    _art(box, "end.json", 160)
    monkeypatch.setattr(ph, "_contracts", lambda: {"MT5-EndWriter": ("end.json", 600, "x")})
    assert _by(_build(monkeypatch, _row("MT5-EndWriter")))["MT5-EndWriter"]["verdict"] == "HUNG"


def test_an_unknown_xml_encoding_never_raises(tmp_path: Path) -> None:
    # SF1: LookupError from ET on encoding="x-bogus" broke NEVER RAISES
    (tmp_path / "MT5-Bogus").write_bytes(b'<?xml version="1.0" encoding="x-bogus"?><Task/>')
    lim = tl.task_limits("\\MT5-Bogus", tmp_path)
    assert lim["execution_time_limit_min"] is None and "unreadable" in lim["why"]


@pytest.mark.parametrize("raw", ["4320", "P1W"])
def test_an_unparseable_execution_limit_is_a_why_and_reads_unmeasured(
    monkeypatch: pytest.MonkeyPatch, box: Path, raw: str,
) -> None:
    # SF2: a non-empty unparseable limit was silently PT0S, so HUNG could never fire
    lim = tl.parse_limits(_xml("X", "a.log", raw))
    assert lim["execution_time_limit_min"] is None and raw in lim["why"]
    _task(box, "MT5-OddLimit", log_age_min=1, limit=raw)
    _art(box, "odd.json", 5)
    monkeypatch.setattr(ph, "_contracts", lambda: {"MT5-OddLimit": ("odd.json", 60, "x")})
    doc = _build(monkeypatch, _row("MT5-OddLimit"))
    row = _by(doc)["MT5-OddLimit"]
    assert row["verdict"] == "RESIDENT_UNMEASURED" and raw in row["why"]
    assert row["cure"] == ph.RESIDENT_LIMITS_CURE and doc["status"] == "ATTENTION"
