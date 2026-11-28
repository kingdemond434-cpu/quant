"""THE 87 BOX TASKS THAT COULD STOP UNSEEN, AND THE GATEWAY THAT READ BROKEN WHILE PAUSED.

process_health.json of 2026-11-17 20:00Z listed 87 scheduled tasks as UNCONTRACTED: nothing
judged what they produce, so any of them could stop and no board would turn red. This pins the
rows added for them, and the two corrections made beside them:

  * MT5-CertHygiene was a contract for a task that does not exist (manifest: UNDECLARED); the
    organ runs FIRST inside ops/run_frontier_audit.cmd, so it is that task's component now.
  * MT5-GatewayResident read STALE for 18 days while the Fusion ruin rail held
    data/GATEWAY_PAUSED; it now reads PAUSED, names only the marker and its age (the marker's
    text carries account figures and process_health.json is published), and is never restarted.
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"_t_{name}", ROOT / "ops" / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


oc = _load("organ_contract")
ph = _load("process_health")

#: The tasks this change contracts (each was UNCONTRACTED on the box).
NEWLY_CONTRACTED = (
    "MT5-AuditLane", "MT5-BoxHeartbeat", "MT5-ClockFixer", "MT5-ContractTerms", "MT5-ConvertSwarm",
    "MT5-CostState", "MT5-CycleMidnight", "MT5-CycleNoon", "MT5-DeepSeek", "MT5-Deepening",
    *(f"MT5-Dept-{d}" for d in ("Data", "Execution", "Forward", "Intel", "Japan", "Macro",
                                "Mathlab", "Meta", "Regions", "Rest", "Validate")),
    *(f"MT5-Forest-{f}" for f in ("Africa", "Asean", "China", "Europe", "Korea", "Latam", "Mena",
                                  "NorthAmerica", "Oceania", "RussiaCis", "SouthAsia")),
    "MT5-E8WindowGuard", "MT5-FTMO-Executor", "MT5-FTMO-VenueReader", "MT5-FusionDeadmanDryRun",
    "MT5-FusionDeadmanLive", "MT5-GateAttest", "MT5-HourlyCore", "MT5-LawGate",
    "MT5-Moat-Exploit", "MT5-Moat-Explore", "MT5-Moat-Resurrect", "MT5-NoLog",
    "MT5-OffsiteBackup", "MT5-PlumbingWatchdog", "MT5-ReapGitWriters", "MT5-RebootDrill",
    "MT5-RegimeMonitor", "MT5-ResearchSupervisor", "MT5-ShadowSync", "MT5-SshGuard",
    "Quant-SideChannelMiners", "Quant-VideoCells",
)


def test_every_new_task_has_a_contract() -> None:
    missing = [t for t in NEWLY_CONTRACTED if t not in oc.CONTRACTS]
    assert not missing, f"still UNCONTRACTED: {missing}"


def test_every_contract_artifact_is_repo_relative() -> None:
    """process_health.json is published, and an absolute box path on a public branch is the
    host's layout; a contract joins its artifact onto the repository root anyway."""
    bad = {k: v[0] for k, v in oc.CONTRACTS.items()
           if re.match(r"^(?:[A-Za-z]:|/|\\\\)", v[0]) or ".." in v[0].split("/")}
    assert not bad, bad


def test_every_age_is_a_positive_minute_count_and_every_stamp_names_a_contract() -> None:
    assert all(isinstance(v[1], int) and v[1] > 0 for v in oc.CONTRACTS.values())
    artifacts = {v[0] for v in oc.CONTRACTS.values()}
    assert set(oc.INTERNAL_STAMPS) <= artifacts, set(oc.INTERNAL_STAMPS) - artifacts


def test_the_ftmo_allocator_is_not_contracted_here() -> None:
    assert "MT5-FTMO-Allocator" not in oc.CONTRACTS


def test_cert_hygiene_is_the_frontier_audit_component_that_runs_it() -> None:
    assert "MT5-CertHygiene" not in oc.CONTRACTS
    art = oc.CONTRACTS["MT5-FrontierAudit (certificate hygiene)"][0]
    assert art == "desks/mt5/reports/CERTIFICATE_HYGIENE.json"
    cmd = (ROOT / "ops" / "run_frontier_audit.cmd").read_text("utf-8", errors="ignore")
    assert "certificate_hygiene.py" in cmd


def test_paused_by_names_the_marker_and_its_age_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "desks" / "mt5" / "data" / "GATEWAY_PAUSED"
    marker.parent.mkdir(parents=True)
    marker.write_text("EQUITY FLOOR 266.01 < 315.00 account 51234567", "utf-8")
    old = time.time() - 5 * 3600
    os.utime(marker, (old, old))
    monkeypatch.setattr(ph, "ROOT", tmp_path)
    why = ph.paused_by("MT5-GatewayResident")
    assert why and "GATEWAY_PAUSED" in why and "5h" in why
    for leak in ("266", "315", "51234567", "EQUITY"):
        assert leak not in why
    assert ph.paused_by("MT5-AllocatorFast") is None
    marker.unlink()
    assert ph.paused_by("MT5-GatewayResident") is None


def test_paused_is_never_restarted_and_not_a_repair_item() -> None:
    ns = (ROOT / "ops" / "never_stale.py").read_text("utf-8")
    restartable = re.search(r"RESTARTABLE = \{([^}]*)\}", ns)
    assert restartable and "PAUSED" not in restartable.group(1)
    src = (ROOT / "ops" / "process_health.py").read_text("utf-8")
    bad_block = src[src.index("bad = [r for r in rows"):][:300]
    assert "PAUSED" not in bad_block
