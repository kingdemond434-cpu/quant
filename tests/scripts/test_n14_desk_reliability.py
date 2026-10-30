"""N14 (2026-10-13): the desk's reliability readings say what is true, and say it off the box.

1. DESK_HEALTH read a RUNNING task's refused trigger (0x800710E0, printed signed by schtasks) as a
   failed run, and a healthy MT5-GatewayResident loop as "the gateway pass is NOT running".
2. TIER1_SCORECARD counted eleven silent scheduled failures out of process_health.json, which
   never left the box, so nobody could say which eleven. It is published now.
3. Two root-level-looking state files described a desk that no longer exists: MT5_DESK_STATE.json
   (the 2026-08 Vantage gold desk, with its account login) and research_state.json (crypto-era
   OI/LS/cash-and-carry priorities). The first is retired; the second is derived from the MT5
   desk's own sleeves and scorecard.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load(name: str, rel: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


health = _load("check_desk_health_n14", "desks/mt5/scripts/check_desk_health.py")
cycle = _load("research_cycle_n14", "scripts/research_cycle.py")


def _schtasks(status: str, result: str) -> str:
    return (f"TaskName:                             \\MT5-Hourly\n"
            f"Status:                               {status}\n"
            f"Last Run Time:                        10/12/2026 9:00:01 AM\n"
            f"Last Result:                          {result}\n"
            f"Scheduled Task State:                 Enabled\n")


def _tasks(monkeypatch: pytest.MonkeyPatch, status: str, result: str) -> list[dict[str, str]]:
    monkeypatch.setattr(health, "TASKS", (("MT5-Hourly", "the hourly chain"),))
    monkeypatch.setattr(health, "_run", lambda args, timeout=30: (0, _schtasks(status, result)))
    health._FINDINGS.clear()
    health.check_tasks()
    return list(health._FINDINGS)


@pytest.mark.parametrize("result", ["-2147020576", "2147946720", "0x800710E0"])
def test_a_running_task_whose_next_trigger_was_refused_is_not_a_failure(
        monkeypatch: pytest.MonkeyPatch, result: str) -> None:
    [f] = _tasks(monkeypatch, "Running", result)
    assert f["level"] == "OK", f


@pytest.mark.parametrize("result", ["-2147020576", "2147946720"])
def test_a_refused_trigger_with_nothing_running_is_a_named_problem(
        monkeypatch: pytest.MonkeyPatch, result: str) -> None:
    [f] = _tasks(monkeypatch, "Ready", result)
    assert f["level"] == "PROBLEM"
    assert "REFUSED" in f["message"] and "Interactive" in f["message"] and "IgnoreNew" in f[
        "message"]


@pytest.mark.parametrize(("result", "level"), [("0", "OK"), ("267009", "OK"), ("267011", "OK"),
                                               ("1", "PROBLEM"), ("garbage", "PROBLEM")])
def test_plain_results_keep_their_meaning(monkeypatch: pytest.MonkeyPatch, result: str,
                                          level: str) -> None:
    [f] = _tasks(monkeypatch, "Ready", result)
    assert f["level"] == level


def test_the_resident_gateway_loop_counts_as_the_gateway_pass(
        monkeypatch: pytest.MonkeyPatch) -> None:
    blob = "terminal64.exe\npython.exe C:\\opt\\quant\\desks\\mt5\\research\\gateway_resident.py"
    monkeypatch.setattr(health, "_process_blob", lambda: (0, blob))
    health._FINDINGS.clear()
    health.check_processes()
    by = {f["message"].split(" is ")[0]: f["level"] for f in health._FINDINGS}
    assert by["the gateway pass"] == "OK"
    assert by["the MT5 terminal itself"] == "OK"


def test_process_health_is_published_off_the_box() -> None:
    from mt5desk import release_identity

    from libs.ops import release
    rel = "desks/mt5/reports/process_health.json"
    assert f"!{rel}" in (ROOT / ".gitignore").read_text("utf-8").splitlines()
    sync = (DESK / "scripts" / "sync_shadow_to_git.ps1").read_text("utf-8", errors="ignore")
    block = sync.split("$relPaths = @(", 1)[1].split("\n)", 1)[0]
    assert f'"{rel}"' in block
    assert rel in release.NON_CODE and rel in release_identity.NON_CODE


def test_mt5_desk_state_is_retired_and_points_at_live_authorities() -> None:
    doc = json.loads((DESK / "docs" / "MT5_DESK_STATE.json").read_text("utf-8"))
    assert doc["status"] == "RETIRED"
    text = json.dumps(doc).lower()
    for gone in ("login", "deployed_sleeves", "sizing_model", "\"account\""):
        assert gone not in text, gone
    sync = (DESK / "scripts" / "sync_shadow_to_git.ps1").read_text("utf-8", errors="ignore")
    for rel in doc["read_instead"].values():
        path = rel.split()[0]
        assert (ROOT / path).exists() or f'"{path}"' in sync, rel


_CRYPTO = ("binance", "hyperliquid", "bybit", "okx", "cash_and_carry", "cash-and-carry",
           "oi_divergence", "ls_contrarian", "liquidation_reversal", "funding")


def test_research_state_names_no_crypto_era_priority() -> None:
    text = (ROOT / "research_state.json").read_text("utf-8").lower()
    for word in _CRYPTO:
        assert word not in text, word


def test_research_state_is_derived_from_the_mt5_desk(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    sleeves = tmp_path / "sleeves.json"
    sleeves.write_text(json.dumps({"sleeves": [
        {"name": "a", "status": "LIVE", "admission": {"delta_elogw_per_day": -0.001}},
        {"name": "b", "status": "LIVE", "admission": {"delta_elogw_per_day": 0.002}},
        {"name": "c", "status": "RETIRED"}]}), "utf-8")
    card = tmp_path / "card.json"
    card.write_text(json.dumps({"rows": [
        {"dimension": "near", "current": 90.0, "first_target": 100.0, "unit": "pct",
         "verdict": "BELOW", "lower_is_better": False},
        {"dimension": "far", "current": 11.0, "first_target": 0.0, "unit": "organs",
         "verdict": "BELOW", "lower_is_better": True},
        {"dimension": "fine", "current": 8.0, "first_target": 5.0, "verdict": "ABOVE"},
        {"dimension": "dark", "verdict": "UNMEASURED"}]}), "utf-8")
    monkeypatch.setattr(cycle, "_SLEEVES", sleeves)
    monkeypatch.setattr(cycle, "_SCORECARD", card)
    monkeypatch.chdir(tmp_path)
    doc = cycle._research_state({"open": [], "completed": []}, {})
    assert doc["deployed"]["sleeves"] == ["a", "b"] and doc["deployed"]["n_live"] == 2
    assert [b["bottleneck"] for b in doc["bottleneck_rankings"]] == ["far", "near"]
    assert doc["binding_constraint"].startswith("far:")
    assert doc["unmeasured_dimensions"] == ["dark"]
    assert [r["sleeve"] for r in doc["retirement_candidates"]] == ["a"]
    for word in _CRYPTO:
        assert word not in json.dumps(doc).lower(), word


def test_research_state_without_a_scorecard_says_unmeasured(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cycle, "_SLEEVES", tmp_path / "absent.json")
    monkeypatch.setattr(cycle, "_SCORECARD", tmp_path / "absent2.json")
    monkeypatch.chdir(tmp_path)
    doc = cycle._research_state({"open": [], "completed": []}, {})
    assert doc["binding_constraint"].startswith("UNMEASURED")
    assert doc["deployed"]["n_live"] == 0
