"""install_drop.ps1 must keep loop.json's ACL (box 11-26 04:07Z: the loop's explicit read grant was
dropped by Move-Item of a fresh file, and every QuantForge-Loop pass died reading loop.json)."""
from __future__ import annotations

from pathlib import Path

SRC = (Path(__file__).resolve().parents[2] / "ops" / "box_git" / "install_drop.ps1").read_text(
    encoding="utf-8")


def test_explicit_grants_are_captured_before_and_regranted_after_the_write():
    get, move, put = (SRC.index("$explicit = @((Get-Acl -LiteralPath $cfgPath).Access"),
                      SRC.index("Move-Item -LiteralPath $tmp -Destination $cfgPath -Force"),
                      SRC.index("foreach ($r in $explicit)"))
    assert get < move < put


def test_gate_user_read_is_granted_and_verified_or_the_install_fails():
    assert '/grant "${GateUser}:(R)"' in SRC
    assert "cannot read ${cfgPath} after the write" in SRC
