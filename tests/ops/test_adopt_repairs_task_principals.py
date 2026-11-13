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
BLOCK = SRC.split("# ------------------------------------- 1c.", 1)[1].split("\n# ----", 1)[0]


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


def test_nothing_is_removed_unless_its_xml_was_kept_and_read_back() -> None:
    """The script runs with ErrorActionPreference Continue: without -ErrorAction Stop a failed
    export would fall through to the unregister (#801 audit MF1)."""
    assert '$ErrorActionPreference = "Continue"' in SRC  # why the explicit Stops matter
    export = BLOCK.split("Export-ScheduledTask", 1)[1].split("Unregister-ScheduledTask", 1)[0]
    assert export.count("-ErrorAction Stop") == 2  # the export and the write
    assert "(Get-Item -LiteralPath $xml).Length -gt 0" in export
    assert "left registered" in BLOCK


def test_the_contract_terms_log_reports_what_the_principal_is_not_what_was_wanted() -> None:
    """#801 audit MF2, SF4, SF5."""
    part = BLOCK.split('"MT5-ContractTerms" -ErrorAction Stop', 1)[1].split("$noon =", 1)[0]
    assert part.index("} catch {") < part.index("$now = Get-ScheduledTask")
    assert "is now $is" in part
    assert "-RunLevel $gw.Principal.RunLevel" in part and "-RunLevel Highest" not in BLOCK
    assert '$gwLogon -ne "Interactive"' in BLOCK


def test_a_failed_repair_never_stops_the_seal_and_starts_nothing() -> None:
    body = BLOCK.split("try {", 1)[1]
    assert "} catch {" in body
    assert not [ln for ln in body.splitlines() if ln.strip().startswith(("throw", "exit"))]
    assert "Start-ScheduledTask" not in body


def test_the_side_channel_miners_task_is_ensured_from_the_repo_root() -> None:
    want = '"Quant-SideChannelMiners"; Path = "scripts\\install_side_channel_miners_task.ps1"'
    assert want in SRC
    assert (ROOT / "scripts" / "install_side_channel_miners_task.ps1").exists()
