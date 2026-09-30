"""PR #141 detected the box-state stall; these pin the five gaps that kept it from CURING one.

1. the freshness fence reads the state-flow meter on BOTH output paths (--json too), and it and
   the desk health check run on a clock (core-plan hourly legs before `publish_state`);
2. stall_watch.json's `alerts_armed` / `alerts_line` have readers (the fence, the desk health
   check and LIVE_SYSTEM_STATE's box section);
3. `box_state_age_hours` is always a key (null + a reason when unmeasured), and the fence's report
   is published: allowlisted, carried by $relPaths, declared NON_CODE on both sides of the seal;
4. MT5-StallWatch has an installer of its own, in the plumbing watchdog's trigger shape;
5. the gateway resident is ONE organ, `resident:gateway`, not two.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

NOT_ARMED = "ALERTS NOT ARMED: STALLED pages reach no one"
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git required")


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fence = _load("_quant_bsfa_freshness", "scripts/check_box_state_freshness.py")
health = _load("_quant_bsfa_desk_health", "desks/mt5/scripts/check_desk_health.py")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "Contabo MT5 Desk",
                        "GIT_COMMITTER_NAME": "Contabo MT5 Desk",
                        "GIT_AUTHOR_EMAIL": "b@example.com",
                        "GIT_COMMITTER_EMAIL": "b@example.com"})


def _repo(tmp_path: Path, *, stamp: datetime, flow: dict | None) -> Path:
    repo = tmp_path / "r"
    _git(tmp_path, "init", "-q", "-b", "live", str(repo))
    _git(repo, "config", "commit.gpgsign", "false")
    script = repo / "desks/mt5/scripts/sync_shadow_to_git.ps1"
    script.parent.mkdir(parents=True)
    script.write_text('$relPaths = @(\n    "desks/mt5/reports/shadow/shadow_health.json",\n'
                      '    "desks/mt5/reports/BOX_STATE_FLOW.json"\n)\n', "utf-8")
    h = repo / "desks/mt5/reports/shadow/shadow_health.json"
    h.parent.mkdir(parents=True)
    h.write_text(json.dumps({"updated_at": stamp.isoformat()}), "utf-8")
    if flow is not None:
        (repo / "desks/mt5/reports/BOX_STATE_FLOW.json").write_text(json.dumps(flow), "utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "state")
    return repo


# ------------------------------------------------------------------ 1. the meter, both paths

@needs_git
def test_the_meter_rides_the_document_so_json_mode_reads_it(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    flow = {"verdict": "STALLED", "why": "origin 30h old", "measured_at": now.isoformat(),
            "alerts": {"armed": 0, "kinds": [], "line": NOT_ARMED}}
    doc = fence.measure(_repo(tmp_path, stamp=now - timedelta(hours=1), flow=flow), ref="HEAD")
    assert doc["box_state_flow"]["verdict"] == "STALLED"
    assert doc["box_state_flow"]["alerts_line"] == NOT_ARMED
    assert doc["alerts_line"] == NOT_ARMED, "the line must be IN the document --json prints"


def test_json_mode_prints_one_document_carrying_the_line(tmp_path: Path, monkeypatch,
                                                         capsys) -> None:
    doc = {"verdict": "FRESH", "why": "ok", "alerts_line": NOT_ARMED,
           "box_state_age_hours": 1.0}
    monkeypatch.setattr(fence, "measure", lambda *a, **k: dict(doc))
    rc = fence.main(["--json", "--out", str(tmp_path / "BOX_STATE_FRESHNESS.json")])
    cap = capsys.readouterr()
    assert rc == 0
    assert json.loads(cap.out)["alerts_line"] == NOT_ARMED, "stdout must stay one JSON document"
    assert NOT_ARMED in cap.err, "and the line is still loud, on stderr"
    written = json.loads((tmp_path / "BOX_STATE_FRESHNESS.json").read_text("utf-8"))
    assert written["alerts_line"] == NOT_ARMED


def test_the_local_meter_outranks_a_stale_published_copy() -> None:
    doc = {"alerts": {"armed": 0, "line": NOT_ARMED},
           "box_state_flow_local": {"alerts_armed": 2, "alerts_line": None}}
    assert fence.alerts_line(doc) is None
    doc["box_state_flow_local"] = None
    assert fence.alerts_line(doc) == NOT_ARMED


def test_fence_and_desk_health_are_core_legs_before_publication() -> None:
    import hourly_cycle as hc

    from libs.research import layers
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    for leg in ("box_state_freshness", "desk_health"):
        assert leg in hc.CORE_LEGS
        assert f'_costed("{leg}"' in src
        assert src.index(f'_costed("{leg}"') < src.index('_costed("publish_state"'), (
            "the report must exist before the push that carries it")
        assert layers.LEG_LAYER[leg] == "meta"
    assert '"scripts/check_box_state_freshness.py"' in src
    assert '"scripts/check_desk_health.py", "--out"' in src


def test_desk_health_writes_its_findings(tmp_path: Path, monkeypatch) -> None:
    desk = tmp_path / "desk"
    (desk / "reports").mkdir(parents=True)
    (desk / "data").mkdir()
    monkeypatch.setattr(health, "DESK", desk)
    monkeypatch.setattr(health, "_run", lambda *a, **k: (124, "no scheduler here"))
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "DESK_HEALTH.json"
    assert health.main(["--out", str(out)]) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["schema"] == "desk_health/1"
    assert doc["verdict"] == "PROBLEM"
    assert doc["counts"]["PROBLEM"] > 0 and doc["findings"]
    sections = {f["section"] for f in doc["findings"]}
    assert any(s.startswith("DOES A STALL PAGE ANYONE") for s in sections)


# ------------------------------------------------------------------ 2. alerts_* have readers

def _stall(tmp_path: Path, doc: dict) -> Path:
    p = tmp_path / "desks/mt5/data/stall_watch.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    # PowerShell 5 writes a BOM; the readers must not choke on it.
    p.write_bytes(b"\xef\xbb\xbf" + json.dumps(doc).encode("utf-8"))
    return p


def test_the_fence_reads_stall_watch_alerts(tmp_path: Path) -> None:
    _stall(tmp_path, {"checked_at": "2026-09-30T10:00:00Z", "alerts_armed": 0,
                      "alerts_line": NOT_ARMED, "state_flow_watch": "FLOWING"})
    got = fence.stall_watch_alerts(tmp_path)
    assert got["status"] == "MEASURED" and got["alerts_line"] == NOT_ARMED
    assert fence.alerts_line({"stall_watch_alerts": got}) == NOT_ARMED


def test_absent_or_pre_watcher_stall_watch_is_unmeasured(tmp_path: Path) -> None:
    assert fence.stall_watch_alerts(tmp_path)["status"] == "UNMEASURED"
    _stall(tmp_path, {"checked_at": "2026-09-16T16:30:00Z", "actions": []})
    got = fence.stall_watch_alerts(tmp_path)
    assert got["status"] == "UNMEASURED" and got["alerts_armed"] is None


def test_desk_health_names_not_armed_from_stall_watch(tmp_path: Path, monkeypatch,
                                                      capsys) -> None:
    desk = tmp_path / "desks/mt5"
    _stall(tmp_path, {"alerts_armed": 0, "alerts_line": NOT_ARMED})
    monkeypatch.setattr(health, "DESK", desk)
    health.check_stall_watch_alerts()
    out = capsys.readouterr().out
    assert "[PROBLEM]" in out and NOT_ARMED in out


def test_live_system_state_box_section_reads_alerts() -> None:
    import live_system_state as lss
    now = datetime(2026, 9, 30, 12, tzinfo=UTC)
    box = lss._box_section({"checked_at": "2026-09-30T11:55:00Z", "alerts_armed": 0,
                            "alerts_line": NOT_ARMED, "state_flow_watch": "STALLED"}, {}, now)
    assert box["alerts"]["status"] == "NOT_ARMED" and box["alerts"]["line"] == NOT_ARMED
    armed = lss._box_section({"alerts_armed": 2, "alerts_line": None}, {}, now)
    assert armed["alerts"]["status"] == "ARMED"
    assert lss._box_section({"checked_at": "x"}, {}, now)["alerts"]["status"] == lss.UNMEASURED
    assert lss._box_section(None, {}, now)["alerts"]["status"] == lss.UNMEASURED


# ------------------------------------------------------------------ 3. D17 key + publication

@needs_git
def test_d17_key_is_present_and_null_with_a_reason_when_unmeasured(tmp_path: Path) -> None:
    repo = tmp_path / "empty"
    _git(tmp_path, "init", "-q", "-b", "live", str(repo))
    doc = fence.measure(repo, ref=None)
    assert doc["verdict"] == "UNMEASURED"
    assert "box_state_age_hours" in doc and doc["box_state_age_hours"] is None
    assert doc["box_state_age_reason"].startswith("UNMEASURED")


@needs_git
def test_d17_key_carries_the_age_when_measured(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    doc = fence.measure(_repo(tmp_path, stamp=now - timedelta(hours=2), flow=None), ref="HEAD")
    assert doc["verdict"] == "FRESH" and 1.9 < doc["box_state_age_hours"] < 2.2
    assert "box_state_age_reason" not in doc


@pytest.mark.parametrize("rel", ["desks/mt5/reports/BOX_STATE_FRESHNESS.json",
                                 "desks/mt5/reports/DESK_HEALTH.json"])
def test_the_reports_are_published_not_ignored(rel: str) -> None:
    from mt5desk import release_identity

    from libs.ops import release
    assert f"!{rel}" in (ROOT / ".gitignore").read_text("utf-8").splitlines()
    sync = (DESK / "scripts" / "sync_shadow_to_git.ps1").read_text("utf-8", errors="ignore")
    block = sync.split("$relPaths = @(", 1)[1].split("\n)", 1)[0]
    assert f'"{rel}"' in block
    assert rel in release.NON_CODE and rel in release_identity.NON_CODE
    assert fence.OUT_REL == "desks/mt5/reports/BOX_STATE_FRESHNESS.json"
    assert health.OUT == DESK / "reports" / "DESK_HEALTH.json"


@needs_git
def test_git_does_not_ignore_the_reports() -> None:
    r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q",
                        "desks/mt5/reports/BOX_STATE_FRESHNESS.json"], check=False)
    assert r.returncode == 1, "the freshness report is still gitignored"


# ------------------------------------------------------------------ 4. the StallWatch installer

INSTALLER = DESK / "scripts" / "install_stall_watch_task.ps1"


def test_stall_watch_has_its_own_installer_in_the_watchdog_shape() -> None:
    src = INSTALLER.read_text("utf-8")
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    assert "$TaskName = 'MT5-StallWatch'" in code
    assert "scripts\\stall_watch.ps1" in code
    # through powershell, never through the python interpreter
    assert "powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File" in code
    # daily trigger re-armed every midnight, repeating every ten minutes for one day
    assert "New-ScheduledTaskTrigger -Daily" in code
    assert "RepetitionInterval (New-TimeSpan -Minutes 10)" in code
    assert "RepetitionDuration (New-TimeSpan -Days 1)" in code
    assert "-MultipleInstances IgnoreNew" in code and "-StartWhenAvailable" in code
    # the principal: an existing registration's identity (S4U included) is kept, a fresh box
    # gets the table's SYSTEM / ServiceAccount, both at Highest
    assert "-LogonType $existing.Principal.LogonType -RunLevel Highest" in code
    assert '-UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest' in code
    assert code.index("$existing.Principal") < code.index("Unregister-ScheduledTask")
    assert "Start-ScheduledTask -TaskName $TaskName" in code


def test_the_manifest_names_the_installer() -> None:
    text = (DESK / "ops" / "box_tasks.manifest").read_text("utf-8")
    row = next(ln for ln in text.splitlines() if ln.startswith('TASK name="MT5-StallWatch"'))
    assert 'installer="desks/mt5/scripts/install_stall_watch_task.ps1"' in row
    assert re.search(r'trigger="every 10 minutes"', row)


# ------------------------------------------------------------------ 5. one gateway resident

def test_the_gateway_resident_is_one_organ() -> None:
    spec = importlib.util.spec_from_file_location("_quant_bsfa_components",
                                                  DESK / "ops" / "components.py")
    assert spec and spec.loader
    c = importlib.util.module_from_spec(spec)
    sys.modules["_quant_bsfa_components"] = c   # dataclasses resolve their module by name
    spec.loader.exec_module(c)
    manifest_ids = {s.component_id for s in c.manifest_task_specs()}
    assert "task:MT5-GatewayResident" not in manifest_ids
    explicit = {s.component_id: s for s in c.explicit_specs()}
    assert explicit["resident:gateway"].schedule == "MT5-GatewayResident"
    assert c.TASK_CANONICAL["MT5-GatewayResident"] == "resident:gateway"
    # every canonical id really is modelled elsewhere, so the skip never drops an organ
    ids = set(explicit) | {s.component_id for s in c.resident_specs()}
    assert set(c.TASK_CANONICAL.values()) <= ids


def test_the_allocator_edge_names_the_canonical_gateway() -> None:
    from libs.ops.control_plane import edges
    assert edges.edges_for(consumer="resident:gateway")[0].producer == "leg:pf_allocator"
    assert not edges.edges_for(consumer="task:MT5-GatewayResident")
