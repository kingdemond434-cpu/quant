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
    """Only zuck's own file is copied, and only when every guard of the ROOT ruling holds."""
    body = _body("Invoke-PinRelocation")
    assert "Copy-Item -LiteralPath $OwnerPin -Destination $RegistryPin" in body
    assert "pin_root.py" not in body and "--write" not in HEAL      # no digest of our own
    copy = body.index("Copy-Item")
    for g in ["Test-RunnerIsAdmin", "$owner -eq $live", "Test-AdminOnlyWrite $OwnerPin",
              "merge-base --is-ancestor $commit", "-not $live"]:
        assert g in body and body.index(g) < copy, g
    assert "$g.digest_is_live -and $g.admin_only_write -and $g.commit_in_live" in body


def test_the_pin_guards_follow_the_ruling() -> None:
    body = _body("Invoke-PinRelocation")
    assert "Get-LiveRootDigest" in _body("Invoke-BoxSelfHeal")      # (d) read from LIVE at run time
    assert "5a8778c7" not in HEAL                                     # never a remembered value
    assert "$row.equal = ($row.destination_sha256 -eq $src)" in body  # (e) byte copy, verified
    assert "Rename-Item -LiteralPath $RegistryPin" in body            # (f) a stale pin is kept
    assert "Remove-Item -LiteralPath $OwnerPin" not in body and "Move-Item" not in body  # (g)
    assert "Rename-Item -LiteralPath $kept" in body  # a mismatch restores the old pin
    assert body.count("Write-HealLedger $row") >= 4                    # (h) every outcome recorded
    assert "UNMEASURED" in body                                       # (j)


def test_only_admins_or_system_may_have_written_the_owner_pin() -> None:
    body = _body("Test-AdminOnlyWrite")
    assert '"S-1-5-32-544", "S-1-5-18"' in HEAL and "return $false" in body


def test_the_gate_clone_is_renamed_not_deleted_and_never_loops() -> None:
    body = _body("Invoke-GateCloneReset")
    jam = body.index("sparse-checkout failed")
    assert "LastWriteTimeUtc -ge" in body                       # a checkout since: leave it
    assert jam < body.index("Rename-Item -LiteralPath $clone")
    assert "Remove-Item -LiteralPath $clone" not in body         # a rename, never a delete
    assert "AddHours(-24)" in body and "PAGE" in body            # one reset per 24 h, then page
    assert 'StartsWith($clone + "\\"' in body                  # the log is outside the clone
    prune = body.index("gate-repo.failed-*")
    assert "AddDays(-7)" in body[prune:prune + 400] and "$good" in body[prune:prune + 400]


def test_bin_copies_refresh_only_from_the_pinned_tree() -> None:
    body = _body("Invoke-BinRefresh")
    assert "$pin -ne $treeDigest" in body and body.index("$pin -ne") < body.index("Copy-Item")
    assert "-not $treeDigest" in body
    assert "before_sha256" in body and "after_sha256" in body


def test_no_step_can_stop_the_seal() -> None:
    body = _body("Invoke-BoxSelfHeal")
    assert body.count("catch") >= 2
    import re

    # dot-sourced into the adopter: an exit statement here would end the adopter itself
    assert not re.search(r"(^|[;{}]\s*)exit\b", HEAL, flags=re.M | re.I)


def test_a_throw_after_the_rename_puts_the_old_pin_back() -> None:
    body = _body("Invoke-PinRelocation")
    assert body.index("$kept = $null") < body.index("try {")          # hoisted: the catch can see it
    tail = body[body.index("a throw after the rename"):]                 # the outer catch
    restore = tail.index("Rename-Item -LiteralPath $kept")
    assert "$row.restored = $kept" in tail
    assert tail.index("Remove-Item -LiteralPath $RegistryPin") < restore
    # $kept is set only AFTER the rename succeeded, so a failed rename restores nothing
    renamed = body.index('NewName ("ROOT_PIN.json.superseded-"')
    assert renamed < body.index('$kept = "$RegistryPin.superseded-')


def test_bin_copies_only_files_equal_to_head() -> None:
    body = _body("Invoke-BinRefresh")
    check = body.index("diff --quiet HEAD --")
    assert check < body.index("Copy-Item") and "$skipped += $name; continue" in body


def test_a_failed_ledger_append_is_said_not_swallowed() -> None:
    body = _body("Write-HealLedger")
    assert "LEDGER APPEND FAILED" in body and "return $false" in body and "catch { }" not in body
