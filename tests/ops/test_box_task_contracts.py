"""EVERY BOX TASK HAS A FRESHNESS CONTRACT, AND A DESK TASK WITHOUT ONE READS RED.

process_health measured 77 desk tasks UNCONTRACTED on the trading box on 2026-11-03 -- among them
MT5-AdoptRelease (the only road code takes onto the box) and MT5-IntelShip (whose upstream went
silent for 14 h while the task exited 0 every hour). UNCONTRACTED was not a fault, so neither
stall reached the published health report. These tests pin the class fix:

  * every TASK line of desks/mt5/ops/box_tasks.manifest has a contract (curated, the box-task
    table, or derived for the 24/7 residents) or a named NOT_CONTRACTABLE reason;
  * NOT_CONTRACTABLE only shrinks;
  * an uncontracted DESK task makes the board ATTENTION; a foreign task is FOREIGN, never a fault;
  * the adoption block compares RELEASE.json with LIVE's code head and is never OK by default;
  * MT5-IntelShip's age is the shipped commit's, so a silent upstream reads STALE.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "desks" / "mt5" / "ops" / "box_tasks.manifest"
if str(ROOT / "ops") not in sys.path:
    sys.path.insert(0, str(ROOT / "ops"))

import organ_contract as oc  # noqa: E402

_spec = importlib.util.spec_from_file_location("process_health_box_contracts",
                                               ROOT / "ops" / "process_health.py")
assert _spec and _spec.loader
ph = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ph)

#: The ratchet: NOT_CONTRACTABLE may only get shorter.
NOT_CONTRACTABLE_MAX = 5


def _manifest_tasks() -> set[str]:
    text = MANIFEST.read_text(encoding="utf-8")
    return {m.group(1) for m in re.finditer(r'^TASK\s+name="([^"]+)"', text, re.M)}


def test_every_manifest_task_has_a_freshness_contract() -> None:
    contracts = oc.all_contracts()
    missing = sorted(t for t in _manifest_tasks()
                     if t not in contracts and t not in oc.NOT_CONTRACTABLE)
    assert not missing, (
        "these box tasks have no artifact contract, so they could stop and nothing would "
        f"notice: {missing}. Add each to ops/organ_contract.py BOX_TASK_CONTRACTS with the file "
        "its own script writes (or, only if it truly writes nothing, NOT_CONTRACTABLE with why)")


def test_the_not_contractable_list_only_shrinks_and_never_overlaps() -> None:
    assert len(oc.NOT_CONTRACTABLE) <= NOT_CONTRACTABLE_MAX
    assert all(why.strip() for why in oc.NOT_CONTRACTABLE.values())
    assert not set(oc.NOT_CONTRACTABLE) & set(oc.all_contracts())
    assert set(oc.NOT_CONTRACTABLE) <= _manifest_tasks(), "an exemption for no task is stale"


def test_the_two_tasks_that_stalled_silently_are_contracted() -> None:
    c = oc.all_contracts()
    assert c["MT5-AdoptRelease"][0] == "desks/mt5/reports/ADOPTION_HEARTBEAT.json"
    assert c["MT5-IntelShip"][0] == "desks/mt5/reports/INTEL_SHIP.json"
    assert oc.INTERNAL_STAMPS["desks/mt5/reports/INTEL_SHIP.json"] == "ship_head_at"
    script = (ROOT / "desks/mt5/scripts/intel_ship_adopt.ps1").read_text(encoding="utf-8")
    assert "INTEL_SHIP.json" in script and "ship_head_at" in script


def test_every_resident_is_derived_from_the_component_registry() -> None:
    sys.path.insert(0, str(ROOT))
    from desks.mt5.ops import components

    derived = oc.resident_contracts()
    for spec in components.resident_specs():
        assert spec.schedule in derived, spec.schedule
        _rel, max_age, _what = derived[spec.schedule]
        assert max_age * 60 >= int(spec.max_silence_s or 0)


def test_every_contract_age_is_positive() -> None:
    for name, (rel, max_age, what) in oc.all_contracts().items():
        assert rel and max_age > 0 and what, name


def test_a_silent_upstream_reads_stale_while_the_file_is_fresh(tmp_path: Path) -> None:
    rel = "desks/mt5/reports/INTEL_SHIP.json"
    p = tmp_path / rel
    p.parent.mkdir(parents=True)
    old = (datetime.now(UTC) - timedelta(hours=14)).isoformat()
    # PowerShell 5 writes a BOM; the stamp must still be read.
    p.write_text("\ufeff" + json.dumps({"ship_head_at": old}), encoding="utf-8")
    age = oc.artifact_age_min(rel, root=tmp_path)
    assert age is not None and age > oc.all_contracts()["MT5-IntelShip"][1]


# ------------------------------------------------------------------ process_health judging
BRIEF = (
    '"TaskName","Next Run Time","Status"\r\n'
    '"\\MT5-Orphan","20/10/2026 19:00:00","Ready"\r\n'
    '"\\GoogleUpdaterTask","20/10/2026 19:00:00","Ready"\r\n'
)
VERBOSE = (
    '"HostName","TaskName","Next Run Time","Status","Logon Mode","Last Run Time","Last Result",'
    '"Author","Task To Run","Scheduled Task State"\r\n'
    '"BOX","\\MT5-Orphan","20/10/2026 19:00:00","Ready","Interactive only",'
    '"20/10/2026 18:00:00","0","quant","py","Enabled"\r\n'
    '"BOX","\\GoogleUpdaterTask","20/10/2026 19:00:00","Ready","Interactive only",'
    '"20/10/2026 18:00:00","0","x","exe","Enabled"\r\n'
)


def _fake_schtasks(monkeypatch: pytest.MonkeyPatch) -> None:
    def run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        assert cmd[0] == "schtasks"
        return subprocess.CompletedProcess(cmd, 0, VERBOSE if "/v" in cmd else BRIEF, "")

    monkeypatch.setattr(ph.subprocess, "run", run)


def test_an_uncontracted_desk_task_is_red_and_a_foreign_one_is_not(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fake_schtasks(monkeypatch)
    monkeypatch.setattr(ph, "ROOT", tmp_path)
    monkeypatch.setattr(ph, "_contracts", dict)
    monkeypatch.setattr(ph, "account_key_file", lambda: {"state": "present"})
    monkeypatch.setattr(ph, "account_key_backup", lambda: {"state": "present"})
    doc = ph.build()
    by = {r["name"]: r for r in doc["processes"]}
    assert by["MT5-Orphan"]["verdict"] == "UNCONTRACTED"
    assert by["GoogleUpdaterTask"]["verdict"] == "FOREIGN"
    assert doc["status"] == "ATTENTION"
    assert doc["n_needing_attention"] == 1


def _release(root: Path, at: datetime) -> None:
    p = root / "desks" / "mt5" / "data" / "RELEASE.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"generated_utc": at.isoformat(), "live_sha": "a" * 40}), "utf-8")


NOW = datetime(2026, 11, 3, 17, 0, tzinfo=UTC)


def test_adoption_lag_beyond_the_bound_is_stale(tmp_path: Path) -> None:
    _release(tmp_path, NOW - timedelta(days=5))
    head = (NOW - timedelta(hours=1)).isoformat()
    doc = ph.adoption_age(NOW, root=tmp_path, git=lambda a: f"{'b' * 40} {head}\n")
    assert doc["verdict"] == "STALE" and doc["lag_h"] > ph.ADOPTION_MAX_LAG_H
    assert doc["release_age_h"] == pytest.approx(120.0)


def test_a_release_newer_than_lives_code_is_ok(tmp_path: Path) -> None:
    _release(tmp_path, NOW - timedelta(hours=2))
    head = (NOW - timedelta(hours=3)).isoformat()
    doc = ph.adoption_age(NOW, root=tmp_path, git=lambda a: f"{'b' * 40} {head}\n")
    assert doc["verdict"] == "OK" and doc["lag_h"] == 0.0


@pytest.mark.parametrize("release, git_out", [(False, "x 2026-11-03T16:00:00+00:00"),
                                              (True, "")])
def test_an_unread_side_is_unmeasured_never_ok(tmp_path: Path, release: bool,
                                               git_out: str) -> None:
    if release:
        _release(tmp_path, NOW - timedelta(hours=1))
    doc = ph.adoption_age(NOW, root=tmp_path, git=lambda a: git_out)
    assert doc["verdict"] == "UNMEASURED" and doc["lag_h"] is None


def test_a_stale_adoption_turns_the_board_to_attention(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fake_schtasks(monkeypatch)
    monkeypatch.setattr(ph, "ROOT", tmp_path)
    monkeypatch.setattr(ph, "_contracts", lambda: {"MT5-Orphan": ("fresh.json", 120, "x")})
    (tmp_path / "fresh.json").write_text("{}", "utf-8")
    monkeypatch.setattr(ph, "account_key_file", lambda: {"state": "present"})
    monkeypatch.setattr(ph, "account_key_backup", lambda: {"state": "present"})
    monkeypatch.setattr(ph, "adoption_age", lambda now, root=None: {"verdict": "STALE"})
    doc = ph.build()
    assert doc["adoption"]["verdict"] == "STALE"
    assert doc["status"] == "ATTENTION"
