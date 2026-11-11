"""The SYSTEM adopter heals the box merge gate's two admin-only jams (2026-11-11).

The gate died at its own clone refresh from 23:40Z 11-10 and both remedies needed an
administrator. These pin the narrow conditions under which the adopter now acts itself.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PS = (ROOT / "desks/mt5/scripts/Adopt-And-Seal.ps1").read_text(encoding="utf-8")


def _block(start: str, end: str) -> str:
    return PS[PS.index(start) : PS.index(end)]


HEAL = _block("0a2. THE MERGE GATE'S OWN CLONE", "0b. THE RELEASE GATE")
REFRESH = _block("3a. THE MERGE GATE'S INSTALLED COPY", "4. the gateway reads the seal")


def test_the_heal_runs_before_the_release_gate_so_a_held_pass_still_heals() -> None:
    assert PS.index("0a2. THE MERGE GATE'S OWN CLONE") < PS.index("$gateScript = Join-Path")


def test_the_clone_is_removed_only_on_three_clone_failures_with_the_mutex_free() -> None:
    assert "[int]$beat.rc -eq 1" in HEAL and "$fails.Count -eq 3" in HEAL
    assert "-match $cloneFail }).Count -eq 3" in HEAL
    assert "Global\\QuantBox-WorkflowGate" in HEAL and "WaitOne(0)" in HEAL
    assert "ReparsePoint" in HEAL
    # it removes the clone and nothing else
    removes = [ln for ln in HEAL.splitlines() if "Remove-Item" in ln]
    assert removes == [ln for ln in removes if "$gateRepo" in ln] and len(removes) == 1


def test_the_installed_gate_follows_only_the_seal_just_made() -> None:
    # audit MF1: the seal commit, with HEAD proven to still be it, never the symbolic HEAD
    assert 'rev-parse "${sealCommit}:$relPath"' in REFRESH
    assert "$headIs -ne $sealCommit" in REFRESH
    assert '"HEAD:$relPath"' not in REFRESH
    # audit MF2: only a release the gate approved, never OVERRIDE_TIP
    assert '$decision -notin @("ADOPT_TIP", "ADOPT_RELEASE")' in REFRESH
    assert "OVERRIDE_TIP" not in REFRESH.replace("never on OVERRIDE_TIP", "")
    # audit MF3: the written bytes hash to the seal's blob before the move
    checked = REFRESH.index("$got -ne $want")
    assert "hash-object --no-filters" in REFRESH
    assert checked < REFRESH.index("Move-Item -LiteralPath $tmpOut -Destination $dst")
    assert 'relPath = "ops/box/workflow_gate.ps1"' in REFRESH
    # only the PROTECTED gate script; the other bin scripts stay owner-installed
    code = [ln for ln in REFRESH.splitlines() if not ln.lstrip().startswith("#")]
    assert not any("unattended_boot" in ln or "sign_train" in ln for ln in code)
    assert PS.index("pure seal commit") < PS.index("3a. THE MERGE GATE'S INSTALLED COPY")


def test_the_heal_refuses_a_junction_anywhere_inside_the_clone() -> None:
    assert "-Recurse -ErrorAction SilentlyContinue" in HEAL
    assert "$links.Count -eq 0" in HEAL


def test_the_gate_script_it_copies_is_protected() -> None:
    gate = (ROOT / ".github/scripts/audit_gate.py").read_text(encoding="utf-8")
    start = gate.index("\nPROTECTED = (")
    prot = gate[start : gate.index("\n)", start)]
    assert '"ops/box/workflow_gate.ps1"' in prot
