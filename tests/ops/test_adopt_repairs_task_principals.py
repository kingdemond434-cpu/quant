"""ADOPT-AND-SEAL REPAIRS THREE BROKEN TASK REGISTRATIONS ITSELF (2026-11-10).

MT5-ContractTerms (session 0, cannot reach the terminal), MT5-CycleNoon (a SYSTEM one-shot that
never ran) and MT5-DeepenUniverse (its action file deleted on 09-30) each waited on an
administrator typing a line. The adoption pass runs as SYSTEM, so it does it. These pins keep the
repairs narrow: each fires only on the exact broken shape, the account is read from MT5-Gateway
and never named, and a failure never stops the seal.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / "desks" / "mt5" / "scripts" / "Adopt-And-Seal.ps1").read_text("utf-8")
BLOCK = SRC.split("# ------------------------------------- 1c.", 1)[1].split(
    "# only when data/secrets/release_signing.key exists", 1
)[0]


def test_the_repairs_run_after_the_ensure_list_and_before_the_seal() -> None:
    assert SRC.index("1b. TASKS THE ADOPTED TREE DECLARES") < SRC.index("1c. TASKS REGISTERED SO")
    assert SRC.index("1c. TASKS REGISTERED SO") < SRC.index("function Ensure-Signed")


def test_the_account_is_read_from_the_gateway_task_and_never_named() -> None:
    assert 'Get-ScheduledTask -TaskName "MT5-Gateway"' in BLOCK
    assert "Administrator" not in BLOCK.split("try {", 1)[1]
    assert "nothing repaired" in BLOCK  # a SYSTEM or missing gateway principal repairs nothing


def test_each_repair_fires_only_on_its_broken_shape() -> None:
    assert '-ne "Interactive"' in BLOCK  # ContractTerms: only when not already interactive
    assert "(& $isSystem $noon.Principal.UserId)" in BLOCK  # CycleNoon: only while SYSTEM
    assert "-Lane noon -RunAs $gwUser -NoStart" in BLOCK  # and never the parked midnight lane
    assert "-not (Test-Path $gone)" in BLOCK and "run_deepen_universe" in BLOCK
    assert BLOCK.index("Export-ScheduledTask") < BLOCK.index("Unregister-ScheduledTask")


def test_a_failed_repair_never_stops_the_seal_and_starts_nothing() -> None:
    body = BLOCK.split("try {", 1)[1]
    assert "} catch {" in body and "throw" not in body and "exit " not in body
    assert "Start-ScheduledTask" not in body


def test_the_side_channel_miners_task_is_ensured_from_the_repo_root() -> None:
    want = '"Quant-SideChannelMiners"; Path = "scripts\\install_side_channel_miners_task.ps1"'
    assert want in SRC
    assert (ROOT / "scripts" / "install_side_channel_miners_task.ps1").exists()
