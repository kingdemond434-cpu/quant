"""ADOPT-AND-SEAL REFRESHES THE PUBLISHED RELEASE IDENTITY AFTER THE SEAL.

`desks/mt5/data/release_identity.json` is what every adoption-lag reader trusts. Its regular
writer is the Fusion gateway pass, which exits at its pause check while the ruin rail holds it,
so on 2026-11-04 the box adopted c5ddf5f11 at 18:17Z and the next two publishes still named the
10-29 code at 147 h. The seal script now measures the identity itself, after the seal and the
authority bit and before the health gate. Parsed from the script so a reorder fails here, not on
the box.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "desks" / "mt5" / "scripts" / "Adopt-And-Seal.ps1"


def _code_lines() -> list[str]:
    src = SCRIPT.read_text("utf-8", errors="ignore")
    return [ln for ln in src.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


def _index(lines: list[str], needle: str) -> int:
    hits = [i for i, ln in enumerate(lines) if needle in ln]
    assert len(hits) == 1, f"expected exactly one code line containing {needle!r}, found {len(hits)}"
    return hits[0]


def test_identity_is_measured_after_the_seal_and_before_health() -> None:
    lines = _code_lines()
    seal = _index(lines, "release.seal(by='Adopt-And-Seal')")
    authority = _index(lines, 'research\\release_authority.py")')
    ident = _index(lines, 'mt5desk\\release_identity.py")')
    health = _index(lines, 'Invoke-AdoptGuard @("health", "--sealed", $head')
    assert seal < authority < ident < health, (seal, authority, ident, health)


def test_identity_call_writes_the_mirror_and_does_not_gate() -> None:
    line = _code_lines()[_index(_code_lines(), 'mt5desk\\release_identity.py")')]
    assert "--no-write" not in line, "the refresh must write data/release_identity.json"
    src = "\n".join(_code_lines())
    after = src.split('mt5desk\\release_identity.py")', 1)[1].split('Invoke-AdoptGuard @("health"', 1)[0]
    assert "Done " not in after and "exit " not in after and "Undo-Adoption" not in after, (
        "the identity exit code is logged, never obeyed: the health check is the gate")
