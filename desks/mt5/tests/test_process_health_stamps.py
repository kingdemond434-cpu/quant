"""Freshness is read from the stamp INSIDE an artifact, never only from its mtime (2026-10-14).

The box's process_health.json read MT5-Gauntlet OK at a 2-minute artifact age while its registry
said `swept_at: 2026-09-16`, and MT5-FusionDeadman OK at 0.2 minutes over a 2026-09-12
`checked_at`. These pin the four behaviours that end that class:

1. a file rewritten seconds ago whose stamp is old is STALE, and says it was rewritten;
2. a JSON artifact with no readable stamp is UNMEASURED, never OK (a .log keeps mtime, labelled);
3. a scheduler that times out is UNMEASURED/UNKNOWN, never NOT INSTALLED;
4. a FAILING/STALE row produces an alert event through the existing alert ledger, and an unarmed
   pager is itself a red row.
"""
from __future__ import annotations

import importlib.util
import json
import os
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


oc = _load("_ph_stamps_organ_contract", "ops/organ_contract.py")
ph = _load("_ph_stamps_process_health", "ops/process_health.py")
ns = _load("_ph_stamps_never_stale", "ops/never_stale.py")


@pytest.fixture(autouse=True)
def _host_disk_is_not_the_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    """The board's rows are the subject here, not this machine's free space."""
    monkeypatch.setattr(ph, "DISK_FLOOR_GB", 0.0)
    # Nor is the repository's own sleeves.json: the deadman row has its own tests
    # (test_process_health_deadman_codes.py) and would otherwise colour every headline here.
    monkeypatch.setattr(ph, "deadman_invariant", lambda **_: None)
dh = _load("_ph_stamps_desk_health", "desks/mt5/scripts/check_desk_health.py")

NOW = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)


def _write(root: Path, rel: str, body: Any, *, mtime_age_min: float = 0.5) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body if isinstance(body, str) else json.dumps(body), "utf-8")
    t = (NOW - timedelta(minutes=mtime_age_min)).timestamp()
    os.utime(p, (t, t))
    return p


def _iso(minutes_ago: float) -> str:
    return (NOW - timedelta(minutes=minutes_ago)).isoformat()


# ------------------------------------------------------------------ 1. stale by stamp, mtime fresh

def test_rewritten_file_with_an_old_stamp_is_stale(tmp_path: Path) -> None:
    _write(tmp_path, "a/survivors.json", {"swept_at": "2026-09-16T15:07:26+00:00", "n": 3})
    r = oc.read_artifact_age("a/survivors.json", root=tmp_path, now=NOW)
    assert r["exists"] and r["age_basis"] == "stamp:swept_at"
    assert r["mtime_age_min"] == 0.5
    assert r["age_min"] > 27 * 24 * 60


def test_newest_top_level_stamp_wins(tmp_path: Path) -> None:
    _write(tmp_path, "x.json", {"at": _iso(9000), "updated_at": _iso(3)})
    r = oc.read_artifact_age("x.json", root=tmp_path, now=NOW)
    assert r["age_basis"] == "stamp:updated_at" and round(r["age_min"]) == 3


def test_declared_specs_read_the_field_the_organ_actually_advances(tmp_path: Path) -> None:
    _write(tmp_path, "cursor.json", {"EURUSD": "2026-09-23T20:55:42+00:00",
                                     "XAUUSD": "2026-09-20T00:00:00+00:00"})
    r = oc.read_artifact_age("cursor.json", "MT5-Gauntlet (rotation)", root=tmp_path, now=NOW)
    assert r["age_basis"] == "stamp:*" and r["stamp"] == "2026-09-23T20:55:42+00:00"

    _write(tmp_path, "gw.json", {"armed": True, "last_reconcile": _iso(2)})
    r = oc.read_artifact_age("gw.json", "MT5-Gateway", root=tmp_path, now=NOW)
    assert r["age_basis"] == "stamp:last_reconcile" and round(r["age_min"]) == 2

    _write(tmp_path, "u.json", {"A": {"updated_at": _iso(50)}, "B": {"updated_at": _iso(5)}})
    r = oc.read_artifact_age("u.json", "MT5-Universe", root=tmp_path, now=NOW)
    assert round(r["age_min"]) == 5


def test_jsonl_is_judged_by_its_last_line(tmp_path: Path) -> None:
    _write(tmp_path, "events.jsonl",
           "\n".join(json.dumps({"at": _iso(m), "kind": "LEG_DONE"}) for m in (400, 300)) + "\n")
    r = oc.read_artifact_age("events.jsonl", root=tmp_path, now=NOW)
    assert r["age_basis"] == "stamp:at" and round(r["age_min"]) == 300


def test_process_health_flags_stale_by_stamp_though_mtime_is_fresh(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = _write(tmp_path, "deadman.json", {"checked_at": "2026-09-12T12:05:02+00:00"})
    os.utime(p, None)   # rewritten just now, by the real clock build() reads
    monkeypatch.setattr(ph, "ROOT", tmp_path)
    monkeypatch.setattr(ph, "_contracts", lambda: {
        "MT5-FusionDeadman": ("deadman.json", 90, "dead-man watch")})
    monkeypatch.setattr(ph, "_tasks", lambda: ([{
        "TaskName": r"\MT5-FusionDeadman", "Scheduled Task State": "Ready",
        "Last Result": "0"}], "OK powershell"))
    doc = ph.build()
    row = next(r for r in doc["processes"] if r["name"] == "MT5-FusionDeadman")
    assert row["verdict"] == "STALE"
    assert row["age_basis"] == "stamp:checked_at"
    assert row["artifact_mtime_age_min"] is not None and row["artifact_mtime_age_min"] < 5
    assert "rewritten" in row["why"]
    assert doc["status"] == "ATTENTION"


# ------------------------------------------------------------------ 2. no stamp -> UNMEASURED

def test_stampless_json_is_unmeasured_not_ok(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, "state.json", {"armed": True, "lot": 0.06}, mtime_age_min=0.1)
    r = oc.read_artifact_age("state.json", root=tmp_path, now=NOW)
    assert r["exists"] and r["age_min"] is None and r["age_basis"] == "none"
    assert "UNMEASURED" in r["why"]

    monkeypatch.setattr(ph, "ROOT", tmp_path)
    monkeypatch.setattr(ph, "_contracts", lambda: {"MT5-Thing": ("state.json", 10, "x")})
    monkeypatch.setattr(ph, "_tasks", lambda: ([{
        "TaskName": r"\MT5-Thing", "Scheduled Task State": "Ready", "Last Result": "0"}],
        "OK powershell"))
    doc = ph.build()
    row = next(r for r in doc["processes"] if r["name"] == "MT5-Thing")
    assert row["verdict"] == "UNMEASURED" and row["age_basis"] == "none"
    assert doc["status"] == "ATTENTION"


def test_a_log_keeps_mtime_and_says_so(tmp_path: Path) -> None:
    _write(tmp_path, "x.log", "pass ok\n", mtime_age_min=7)
    r = oc.read_artifact_age("x.log", root=tmp_path, now=NOW)
    assert r["age_basis"] == "mtime" and round(r["age_min"]) == 7


def test_declared_stampless_artifact_uses_mtime(tmp_path: Path) -> None:
    _write(tmp_path, "s.json", {"a": 1}, mtime_age_min=4)
    r = oc.read_artifact_age("s.json", root=tmp_path, now=NOW, spec="mtime")
    assert r["age_basis"] == "mtime" and round(r["age_min"]) == 4


def test_every_contract_spec_is_a_known_form() -> None:
    for organ, spec in oc.STAMP_SPEC.items():
        assert organ in oc.CONTRACTS, organ
        assert spec == "mtime" or spec.startswith(("key:", "newest:*")), spec


# ------------------------------------------------------------------ never_stale does not loop

def _health(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, Any]]) -> None:
    h = tmp_path / "process_health.json"
    h.write_text(json.dumps({"at": datetime.now(UTC).isoformat(), "processes": rows}), "utf-8")
    monkeypatch.setattr(ns, "HEALTH", h)
    monkeypatch.setattr(ns, "STARTS", tmp_path / "starts.json")
    monkeypatch.setattr(ns, "_capital_faults", lambda: [])


def test_never_stale_never_starts_an_unmeasured_row(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    _health(tmp_path, monkeypatch, [{"name": "MT5-Thing", "verdict": "UNMEASURED",
                                     "why": "no stamp"}])
    started: list[str] = []
    monkeypatch.setattr(ns, "_start", lambda t: (started.append(t), (True, "ok"))[1])
    doc = ns.run(apply=True)
    assert started == [] and doc["status"] == "UNMEASURED"
    assert doc["unmeasured"][0]["task"] == "MT5-Thing"


def test_rewritten_but_not_advancing_is_escalated_not_restarted(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _health(tmp_path, monkeypatch, [{
        "name": "MT5-FusionDeadman", "verdict": "STALE", "why": "old stamp",
        "age_basis": "stamp:checked_at", "artifact_mtime_age_min": 0.2,
        "contract_max_age_min": 90, "last_result_code": 0}])
    started: list[str] = []
    monkeypatch.setattr(ns, "_start", lambda t: (started.append(t), (True, "ok"))[1])
    doc = ns.run(apply=True)
    assert started == []
    assert doc["escalated"][0]["diagnosis"].startswith("REWRITTEN BUT NOT ADVANCING")


def test_a_start_that_did_not_cure_is_not_repeated(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    row = {"name": "MT5-Thing", "verdict": "STALE", "why": "old", "age_basis": "mtime",
           "artifact_mtime_age_min": 500, "contract_max_age_min": 90}
    _health(tmp_path, monkeypatch, [row])
    started: list[str] = []
    monkeypatch.setattr(ns, "_start", lambda t: (started.append(t), (True, "ok"))[1])
    assert ns.run(apply=True)["acted"][0]["action"] == "started"
    doc = ns.run(apply=True)
    assert started == ["MT5-Thing"]
    assert "DID NOT CURE" in doc["escalated"][0]["diagnosis"]


# ------------------------------------------------------------------ 3. scheduler timeout

def test_scheduler_timeout_is_unknown_not_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dh, "TASKS", (("MT5-Gateway", "the money path"),))
    monkeypatch.setattr(dh, "_run", lambda args, timeout=30: (
        124, "TimeoutExpired: Command '['schtasks']' timed out after 30 seconds"))
    dh._FINDINGS.clear()
    dh.check_tasks()
    [f] = dh._FINDINGS
    assert f["level"] == "UNKNOWN" and "NOT INSTALLED" not in f["message"]
    assert "UNMEASURED" in f["message"]


def test_a_task_the_scheduler_says_is_absent_is_still_not_installed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dh, "TASKS", (("MT5-Gateway", "the money path"),))
    monkeypatch.setattr(dh, "_run", lambda args, timeout=30: (
        1, "ERROR: The system cannot find the file specified.\n"))
    dh._FINDINGS.clear()
    dh.check_tasks()
    [f] = dh._FINDINGS
    assert f["level"] == "PROBLEM" and "NOT INSTALLED" in f["message"]


def test_process_health_unreadable_scheduler_is_never_not_scheduled(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ph, "_tasks", lambda: (
        [], "UNMEASURED: powershell TimeoutExpired; schtasks TimeoutExpired"))
    monkeypatch.setattr(ph, "_contracts", lambda: {"MT5-Gateway": ("g.json", 10, "x")})
    doc = ph.build()
    assert doc["counts"].get("NOT_SCHEDULED", 0) == 0
    assert next(r for r in doc["processes"]
                if r["name"] == "MT5-Gateway")["verdict"] == "SCHEDULER_UNMEASURED"


def test_desk_health_artifact_age_reads_the_stamp(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    desk = tmp_path / "desk"
    _write(desk, "reports/UNIVERSAL_SURVIVORS.json",
           {"swept_at": "2026-09-16T15:07:26+00:00"}, mtime_age_min=0.0)
    monkeypatch.setattr(dh, "DESK", desk)
    monkeypatch.setattr(dh, "ARTIFACTS",
                        (("reports/UNIVERSAL_SURVIVORS.json", "the gauntlet's canon", 6.0),))
    dh._FINDINGS.clear()
    dh.check_artifacts()
    [f] = dh._FINDINGS
    assert f["level"] == "PROBLEM" and "stamp:swept_at" in f["message"]


# ------------------------------------------------------------------ 4. alerts

def _doc(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"at": NOW.isoformat(), "processes": rows, "alerts": {"armed": 0, "line": "UNARMED"}}


def test_failing_and_stale_rows_page_once_then_dedupe(tmp_path: Path) -> None:
    sent: list[tuple[str, str]] = []

    def sender(title: str, body: str) -> dict[str, Any]:
        sent.append((title, body))
        return {"armed": 1, "delivered": 1}

    state = tmp_path / "alert.json"
    doc = _doc([{"name": "MT5-Gauntlet", "verdict": "STALE", "why": "old stamp"},
                {"name": "MT5-LawGate", "verdict": "FAILING", "why": "exit 1"},
                {"name": "MT5-Ok", "verdict": "OK", "why": ""}])
    out = ph.page_attention(doc, state_path=state, sender=sender, now=NOW)
    assert out["sent"] and len(sent) == 1
    assert "MT5-Gauntlet" in sent[0][1] and "MT5-LawGate" in sent[0][1]
    assert "MT5-Ok" not in sent[0][1]
    again = ph.page_attention(doc, state_path=state, sender=sender, now=NOW)
    assert not again["sent"] and len(sent) == 1
    later = ph.page_attention(doc, state_path=state, sender=sender,
                              now=NOW + timedelta(hours=7))
    assert later["sent"] and len(sent) == 2
    clear = ph.page_attention(_doc([]), state_path=state, sender=sender,
                              now=NOW + timedelta(hours=8))
    assert clear["sent"] and "clear" in sent[-1][0]


def test_unarmed_page_lands_in_the_delivery_ledger(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT))
    from libs.ops import alert_channels
    ledger = tmp_path / "alert_delivery.jsonl"

    def sender(title: str, body: str) -> dict[str, Any]:
        return alert_channels.send_all(title, body, config=tmp_path / "absent.json",
                                       ledger=ledger)

    out = ph.page_attention(_doc([{"name": "MT5-X", "verdict": "STALE", "why": "w"}]),
                            state_path=tmp_path / "s.json", sender=sender, now=NOW)
    assert out["sent"] and out["armed"] == 0
    row = json.loads(ledger.read_text("utf-8").splitlines()[-1])
    assert row["channel"] == "none" and row["detail"].startswith("NOT-ARMED")


def test_unarmed_pager_is_a_red_row_with_the_owner_action(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ph, "_tasks", lambda: ([], "OK powershell"))
    monkeypatch.setattr(ph, "_contracts", lambda: {})
    monkeypatch.setattr(ph, "_alerts_armed", lambda root=None: {
        "armed": 0, "kinds": [], "line": "ALERTS NOT ARMED"})
    doc = ph.build()
    row = next(r for r in doc["processes"] if r["name"] == "ALERT CHANNELS")
    assert row["verdict"] == "ALERTS_UNARMED" and "alert_channels.json" in row["why"]
    assert doc["status"] == "ATTENTION" and doc["processes"][0] is row

    monkeypatch.setattr(ph, "_alerts_armed", lambda root=None: {
        "armed": 1, "kinds": ["telegram"], "line": None})
    doc = ph.build()
    assert not any(r["name"] == "ALERT CHANNELS" for r in doc["processes"])
    assert doc["status"] == "OK"


def test_disk_under_the_floor_is_a_red_row_that_lists_and_never_deletes(tmp_path, monkeypatch):
    import shutil
    from collections import namedtuple

    (tmp_path / "logs").mkdir()
    big = tmp_path / "logs" / "old.log"
    big.write_bytes(b"x" * 2048)
    du = namedtuple("du", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda _p: du(100 * 1024 ** 3, 95 * 1024 ** 3,
                                                           5 * 1024 ** 3))
    d = ph.disk_state(tmp_path, floor_gb=10.0)
    assert d["verdict"] == "DISK_LOW" and d["free_gb"] == 5.0
    assert d["reclaimable"][0]["path"].endswith("old.log") and big.exists()
    assert "DISK_LOW" in ph.ATTENTION
    monkeypatch.setattr(shutil, "disk_usage", lambda _p: du(100 * 1024 ** 3, 50 * 1024 ** 3,
                                                           50 * 1024 ** 3))
    assert ph.disk_state(tmp_path, floor_gb=10.0)["verdict"] == "OK"
    assert "DISK_LOW" in ns.VERDICT_DIAGNOSIS
