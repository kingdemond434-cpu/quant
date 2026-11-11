"""The SYSTEM adopter heals the box's three stuck steps (Governance, 2026-11-11).

No PowerShell runs in this container, so the guards are pinned as text. Each one is the reason a
step is safe to take with nobody in an elevated window.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HEAL = (ROOT / "ops" / "box" / "box_selfheal.ps1").read_text(encoding="utf-8")
ADOPT = (ROOT / "desks" / "mt5" / "scripts" / "Adopt-And-Seal.ps1").read_text(encoding="utf-8")


def _body(fn: str) -> str:
    start = HEAL.index(f"function {fn}")
    end = HEAL.find("\nfunction ", start + 1)
    return HEAL[start:end if end > 0 else None]


def test_the_adopter_runs_the_selfheal_before_it_seals() -> None:
    call = ADOPT.index("Invoke-BoxSelfHeal")
    assert call < ADOPT.index("# ------------------------------------------------------ 2. seal")
    assert "ops\\box\\box_selfheal.ps1" in ADOPT


def test_the_pin_is_moved_never_computed() -> None:
    """Only zuck's own file is copied, and only when every guard holds."""
    body = _body("Invoke-PinRelocation")
    assert "Copy-Item -LiteralPath $OwnerPin -Destination $RegistryPin" in body
    assert "pin_root.py" not in body and "--write" not in HEAL      # no digest of our own
    guards = ["$owner -ne $treeDigest", "Test-AdminOnlyWrite $OwnerPin",
              "merge-base --is-ancestor $commit HEAD"]
    copy = body.index("Copy-Item")
    for g in guards:
        assert g in body and body.index(g) < copy, g


def test_only_admins_or_system_may_have_written_the_owner_pin() -> None:
    body = _body("Test-AdminOnlyWrite")
    assert '"S-1-5-32-544", "S-1-5-18"' in HEAL and "return $false" in body


def test_the_gate_clone_is_reset_only_on_the_sparse_checkout_jam() -> None:
    body = _body("Invoke-GateCloneReset")
    assert "sparse-checkout failed" in body
    assert "LastWriteTimeUtc -ge" in body                      # a checkout since: leave it
    assert body.index("sparse-checkout failed") < body.index("Remove-Item")


def test_bin_copies_refresh_only_from_the_pinned_tree() -> None:
    body = _body("Invoke-BinRefresh")
    assert "$pin -ne $treeDigest" in body and body.index("$pin -ne") < body.index("Copy-Item")


def test_no_step_can_stop_the_seal() -> None:
    body = _body("Invoke-BoxSelfHeal")
    assert body.count("catch") >= 2
    import re

    # dot-sourced into the adopter: an exit statement here would end the adopter itself
    assert not re.search(r"(^|[;{}]\s*)exit\b", HEAL, flags=re.M | re.I)
