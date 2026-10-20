"""The Fusion deadman invariant, and task result codes that are not what they look like.

Measured on the box's published state 2026-10-14: desks/mt5/data/fusion_deadman_state.json read
`checked_at: 2026-09-12T12:05:02+00:00`, `mode: DRY-RUN` while three sleeves were LIVE, and
process_health read MT5-FusionDeadman OK. MT5-Gauntlet read OK on 0x800710E0 (a trigger refused
while an instance ran), 267009 ("running") was folded into OK, and MT5-Shadow's exit 3 -- a
census the cycle reports on purpose -- read FAILING.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _load(name: str, rel: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ph = _load("_ph_deadman_process_health", "ops/process_health.py")
ns = _load("_ph_deadman_never_stale", "ops/never_stale.py")
NOW = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ph, "DISK_FLOOR_GB", 0.0)
    monkeypatch.setattr(ph, "_alerts_armed", lambda root=None: {
        "armed": 1, "kinds": ["hc"], "line": None})


def _files(tmp_path: Path, *, live: int = 3, state: Any = None,
           sleeves: str | None = None) -> tuple[Path, Path]:
    sl = tmp_path / "sleeves.json"
    sl.write_text(sleeves if sleeves is not None else json.dumps({"sleeves": (
        [{"name": f"s{i}", "status": "LIVE"} for i in range(live)]
        + [{"name": "r", "status": "RETIRED"}, {"name": "b", "status": "STANDBY"}])}), "utf-8")
    st = tmp_path / "fusion_deadman_state.json"
    if state is not None:
        st.write_text(state if isinstance(state, str) else json.dumps(state), "utf-8")
    return st, sl


def _state(minutes_ago: float, mode: str = "LIVE") -> dict[str, Any]:
    # The writer's own shape: proposals/fusion_deadman.py main() sets `mode` and `checked_at`.
    return {"checked_at": (NOW - timedelta(minutes=minutes_ago)).isoformat(timespec="seconds"),
            "mode": mode, "readings": {"equity": 484.83, "peak_equity": 784.38}}


def _dm(tmp_path: Path, **kw: Any) -> dict[str, Any]:
    st, sl = _files(tmp_path, **kw)
    row = ph.deadman_invariant(state_path=st, sleeves_path=sl, now=NOW)
    assert row is not None
    return row


# ------------------------------------------------------------------ 1. the deadman invariant

def test_the_published_shape_is_red(tmp_path: Path) -> None:
    """checked_at 2026-09-12 and DRY-RUN while LIVE sleeves exist: both faults are named."""
    row = _dm(tmp_path, state={"checked_at": "2026-09-12T12:05:02+00:00", "mode": "DRY-RUN"})
    assert row["verdict"] == "DEADMAN_UNARMED"
    assert "'DRY-RUN', not 'LIVE'" in row["why"] and "min old" in row["why"]
    assert "--live" in row["why"] and "LAWS" in row["why"]
    assert row["age_basis"] == "stamp:checked_at"


def test_fresh_but_dry_run_is_red(tmp_path: Path) -> None:
    row = _dm(tmp_path, state=_state(2, "DRY-RUN"))
    assert row["verdict"] == "DEADMAN_UNARMED" and "min old" not in row["why"]


def test_armed_but_stale_is_red(tmp_path: Path) -> None:
    row = _dm(tmp_path, state=_state(16, "LIVE"))
    assert row["verdict"] == "DEADMAN_UNARMED" and "not 'LIVE'" not in row["why"]


def test_armed_and_fresh_is_ok(tmp_path: Path) -> None:
    assert _dm(tmp_path, state=_state(4, "LIVE"))["verdict"] == "OK"


@pytest.mark.parametrize("body", [None, "{not json", "[]", json.dumps({"mode": "LIVE"})])
def test_unreadable_or_unstamped_state_with_live_sleeves_is_red_never_ok(
        tmp_path: Path, body: str | None) -> None:
    assert _dm(tmp_path, state=body)["verdict"] == "DEADMAN_UNARMED"


def test_no_live_sleeve_means_the_invariant_does_not_bind(tmp_path: Path) -> None:
    row = _dm(tmp_path, live=0, state=None)
    assert row["verdict"] == "OK" and row["live_sleeves"] == []


def test_unreadable_sleeves_is_unmeasured_not_ok(tmp_path: Path) -> None:
    assert _dm(tmp_path, sleeves="{broken", state=_state(1))["verdict"] == "UNMEASURED"


def test_the_red_row_tops_the_board_counts_and_is_escalated_never_started(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    st, sl = _files(tmp_path, state=_state(30 * 24 * 60, "DRY-RUN"))
    monkeypatch.setattr(ph, "DEADMAN_STATE", st)
    monkeypatch.setattr(ph, "SLEEVES", sl)
    monkeypatch.setattr(ph, "_tasks", lambda: ([], "OK powershell"))
    monkeypatch.setattr(ph, "_contracts", lambda: {})
    doc = ph.build()
    assert doc["status"] == "ATTENTION" and doc["processes"][0]["verdict"] == "DEADMAN_UNARMED"
    assert "DEADMAN_UNARMED" in ph.ATTENTION
    sent: list[str] = []
    page = ph.page_attention(doc, state_path=tmp_path / "pg.json",
                             sender=lambda t, b: (sent.append(b), {"armed": 1, "delivered": 1})[1])
    assert page["sent"] and "DEADMAN_UNARMED" in sent[0]

    started = _never_stale(tmp_path, monkeypatch, doc["processes"])
    assert started == []
    esc = ns.run(apply=True)["escalated"]
    assert esc[0]["verdict"] == "DEADMAN_UNARMED"
    assert esc[0]["diagnosis"] == ns.VERDICT_DIAGNOSIS["DEADMAN_UNARMED"]


def _never_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                 rows: list[dict[str, Any]]) -> list[str]:
    h = tmp_path / "process_health.json"
    h.write_text(json.dumps({"at": datetime.now(UTC).isoformat(), "processes": rows}), "utf-8")
    monkeypatch.setattr(ns, "HEALTH", h)
    monkeypatch.setattr(ns, "STARTS", tmp_path / "starts.json")
    monkeypatch.setattr(ns, "_capital_faults", lambda: [])
    started: list[str] = []
    monkeypatch.setattr(ns, "_start", lambda t: (started.append(t), (True, "ok"))[1])
    ns.run(apply=True)
    return started


# ------------------------------------------------------------------ 2. result codes

def _reading(age: float | None):
    def r(organ: str, artifact: str) -> dict[str, Any]:
        return {"exists": True, "age_min": age, "age_basis": "stamp:at" if age is not None
                else "none", "stamp": None, "mtime_age_min": 1.0, "why": "no stamp"}
    return r


def _one(monkeypatch: pytest.MonkeyPatch, name: str, code: str, *, state: str = "Ready",
         contract: tuple[str, int, str] | None = ("a.json", 60, "x"),
         age: float | None = 5.0) -> dict[str, Any]:
    monkeypatch.setattr(ph, "_tasks", lambda: ([{
        "TaskName": "\\" + name, "Scheduled Task State": state, "Last Result": code}],
        "OK powershell"))
    monkeypatch.setattr(ph, "_contracts", lambda: {name: contract} if contract else {})
    monkeypatch.setattr(ph, "deadman_invariant", lambda **_: None)
    monkeypatch.setattr(ph, "_reading", _reading(age))
    return next(r for r in ph.build()["processes"] if r["name"] == name)


def test_overlap_with_a_fresh_stamp_is_ok_with_a_note(monkeypatch: pytest.MonkeyPatch) -> None:
    row = _one(monkeypatch, "MT5-Gauntlet", "2147946720", age=5.0)
    assert row["verdict"] == "OK" and "overlap" in row["why"]


def test_overlap_signed_form_reads_the_same(monkeypatch: pytest.MonkeyPatch) -> None:
    row = _one(monkeypatch, "MT5-Gauntlet", "-2147020576", age=5.0)
    assert row["verdict"] == "OK" and row["last_result_code"] == 2147946720


def test_overlap_with_a_stale_stamp_is_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _one(monkeypatch, "MT5-Gauntlet", "2147946720", age=999.0)["verdict"] == "STALE"


def test_overlap_without_a_stamp_is_never_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _one(monkeypatch, "MT5-Gauntlet", "2147946720", age=None)["verdict"] == "UNMEASURED"
    row = _one(monkeypatch, "MT5-Thing", "2147946720", contract=None)
    assert row["verdict"] == "OVERLAP" and "OVERLAP" in ph.ATTENTION


def test_already_running_refusal_is_the_same_overlap(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _one(monkeypatch, "MT5-Thing", "2147750687", contract=None)["verdict"] == "OVERLAP"


def test_267009_reads_running(monkeypatch: pytest.MonkeyPatch) -> None:
    row = _one(monkeypatch, "MT5-CacheWarm", "267009", state="Running", age=5.0)
    assert row["verdict"] == "RUNNING" and "RUNNING" not in ph.ATTENTION


def test_shadow_exit_3_and_2_are_findings_not_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    for code, word in (("3", "ENROLMENT_GAP"), ("2", "EVIDENCE_BLOCKED")):
        row = _one(monkeypatch, "MT5-Shadow", code, age=5.0)
        assert row["verdict"] == "FINDING" and word in row["why"]
    assert _one(monkeypatch, "MT5-Shadow", "1", age=5.0)["verdict"] == "FAILING"
    assert _one(monkeypatch, "MT5-Other", "3", age=5.0)["verdict"] == "FAILING"


def test_267014_stays_failing(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _one(monkeypatch, "E8-Spreads", "267014", age=5.0)["verdict"] == "FAILING"


# ------------------------------------------------------------------ 3. never_stale on those shapes

def test_running_and_overlap_are_never_started(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {"name": "MT5-A", "verdict": "RUNNING", "last_result_code": 267009},
        {"name": "MT5-B", "verdict": "STALE", "state": "Running", "last_result_code": 267009,
         "age_basis": "mtime", "artifact_mtime_age_min": 900, "contract_max_age_min": 60},
        {"name": "MT5-C", "verdict": "OVERLAP", "last_result_code": 2147946720},
        {"name": "MT5-FusionDeadman", "verdict": "STALE", "last_result_code": 0,
         "age_basis": "mtime", "artifact_mtime_age_min": 900, "contract_max_age_min": 90},
    ]
    assert _never_stale(tmp_path, monkeypatch, rows) == []
    esc = {e["task"]: e for e in ns.run(apply=True)["escalated"]}
    assert "MT5-A" not in esc
    assert esc["MT5-B"]["diagnosis"].startswith("RUNNING BUT NOT ADVANCING")
    assert esc["MT5-C"]["diagnosis"] == ns.DIAGNOSIS[2147946720]
    assert "NEVER_START" in esc["MT5-FusionDeadman"]["diagnosis"]


@pytest.mark.parametrize("task,code", [
    ("MT5-Shadow", 3), ("MT5-Shadow", 2), ("MT5-DeepenUniverse", 1), ("MT5-ContractTerms", 1),
    ("MT5-DashboardFence", 1), ("MT5-PushBacklog", 1), ("E8-Spreads", 1)])
def test_each_box_failure_carries_its_own_diagnosis(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch,
                                                    task: str, code: int) -> None:
    verdict = "FINDING" if task == "MT5-Shadow" else "FAILING"
    assert _never_stale(tmp_path, monkeypatch, [
        {"name": task, "verdict": verdict, "last_result_code": code}]) == []
    esc = ns.run(apply=True)["escalated"]
    assert esc[0]["diagnosis"] == ns.TASK_DIAGNOSIS[(task, code)]


@pytest.mark.parametrize("code", [2147946720, 2147750687, 267009, 267014])
def test_scheduler_codes_have_a_generic_diagnosis(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch,
                                                  code: int) -> None:
    _never_stale(tmp_path, monkeypatch, [
        {"name": "MT5-Any", "verdict": "FAILING", "last_result_code": code}])
    assert ns.run(apply=True)["escalated"][0]["diagnosis"] == ns.DIAGNOSIS[code]


def test_exit_3_is_no_longer_claimed_for_every_organ() -> None:
    assert 3 not in ns.DIAGNOSIS and ("MT5-Shadow", 3) in ns.TASK_DIAGNOSIS


def test_the_e8_sampler_pass_fits_its_task_limit() -> None:
    """install_e8_tasks.ps1 gives E8-Spreads the default -LimitMinutes 50; the pass must end
    before it, or every pass is killed (0x41306) and reads FAILING."""
    src = (ROOT / "desks" / "mt5" / "prop" / "e8_spread_sampler.py").read_text("utf-8")
    inst = (ROOT / "desks" / "mt5" / "scripts" / "install_e8_tasks.ps1").read_text("utf-8")
    assert "[int] $LimitMinutes = 50" in inst
    assert "RUN_BUDGET_S = 45 * 60" in src and "HOURS*3600" not in src
    # re-audit: bounded raw, atomic write, a slow venue cannot overrun, and the installer's
    # trigger is the manifest's hourly one, not at-startup
    assert "MAX_RAW_PER_SYMBOL" in src and "_write_atomic(OUT" in src
    assert "replace_resilient(tmp, path)" in src
    assert "MAX_RAW_PER_SYMBOL" in src and "last_pass_s" in src
    i = inst.index('Set-E8Task -Name "E8-Spreads"')
    assert "-RepetitionInterval (New-TimeSpan -Hours 1)" in inst[i:i + 400]
    assert "-AtStartup" not in inst[i:i + 400]


# ------------------------------------------------------------------ 3. re-audit of 4854d7289

@pytest.mark.parametrize("minutes_ahead", [180, 30 * 24 * 60])
def test_a_future_checked_at_is_never_armed(tmp_path: Path, minutes_ahead: float) -> None:
    row = _dm(tmp_path, state=_state(-minutes_ahead, "LIVE"))
    assert row["verdict"] == "DEADMAN_UNARMED" and "FUTURE" in row["why"]


def test_ordinary_clock_skew_still_reads_armed(tmp_path: Path) -> None:
    assert _dm(tmp_path, state=_state(-2, "LIVE"))["verdict"] == "OK"


@pytest.mark.parametrize("sleeves", [json.dumps({"sleeves": {"a": {"status": "LIVE"}}}),
                                     json.dumps({"rows": [{"name": "a", "status": "LIVE"}]}),
                                     json.dumps({"sleeves": None}), "7"])
def test_a_sleeves_file_of_another_shape_is_unmeasured_not_no_risk(
        tmp_path: Path, sleeves: str) -> None:
    assert _dm(tmp_path, sleeves=sleeves, state=_state(1))["verdict"] == "UNMEASURED"


def test_a_page_that_reached_no_one_is_not_deduplicated(tmp_path: Path) -> None:
    doc = {"at": NOW.isoformat(), "processes": [
        {"name": "FUSION DEADMAN ARMED", "verdict": "DEADMAN_UNARMED", "why": "x"}]}
    pg = tmp_path / "pg.json"

    def boom(t: str, b: str) -> dict[str, Any]:
        raise OSError("network")
    for sender in (boom, lambda t, b: {"armed": 1, "delivered": 0}):
        out = ph.page_attention(doc, state_path=pg, sender=sender, now=NOW)
        assert out["sent"] and "state_kept" in out and not pg.exists()
    out = ph.page_attention(doc, state_path=pg, sender=lambda t, b: {"armed": 1, "delivered": 1},
                            now=NOW)
    assert pg.exists() and "state_kept" not in out
    again = ph.page_attention(doc, state_path=pg, sender=lambda t, b: {"delivered": 1}, now=NOW)
    assert again == {"sent": False, "reason": "deduplicated"}


def test_an_unmeasured_deadman_row_is_escalated_with_the_deadman_remedy(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"name": "FUSION DEADMAN ARMED", "verdict": "UNMEASURED", "why": "sleeves unreadable"}]
    assert _never_stale(tmp_path, monkeypatch, rows) == []
    esc = ns.run(apply=True)["escalated"]
    assert esc[0]["diagnosis"] == ns.VERDICT_DIAGNOSIS["DEADMAN_UNARMED"]
    assert esc[0]["needs_human"] is True


def test_a_far_future_stamp_reads_unmeasured_in_the_organ_contract(tmp_path: Path) -> None:
    oc = _load("_ph_deadman_organ_contract", "ops/organ_contract.py")
    p = tmp_path / "a.json"
    for ahead, measured in ((timedelta(hours=3), False), (timedelta(minutes=2), True)):
        p.write_text(json.dumps({"generated_at": (NOW + ahead).isoformat()}), "utf-8")
        got = oc.read_artifact_age("a.json", root=tmp_path, now=NOW, spec="key:generated_at")
        assert (got.get("age_min") is not None) is measured, (ahead, got)


def test_a_padded_live_status_still_binds_the_invariant(tmp_path: Path) -> None:
    body = json.dumps({"sleeves": [{"name": "a", "status": " live "}]})
    assert _dm(tmp_path, sleeves=body, state=None)["verdict"] == "DEADMAN_UNARMED"


def test_a_future_board_stamp_is_unmeasured(monkeypatch: pytest.MonkeyPatch) -> None:
    ahead = (datetime.now(UTC) + timedelta(hours=3)).isoformat()
    assert ns._health_age_min({"at": ahead}) is None
    assert ns._health_age_min({"at": datetime.now(UTC).isoformat()}) is not None
