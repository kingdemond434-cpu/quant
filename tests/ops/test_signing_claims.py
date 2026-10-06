"""NOTHING CALLS ITSELF "SIGNED" THAT IS NOT (2026-10-06 audit).

No desk commit is git-signed and `ops/signing/allowed_signers` is read by nothing. What the release
tooling really does is HASH-SEAL (the immutable judge manifest, `money_path_hash`) and HMAC-SEAL
(`RELEASE.json`, `libs/ops/release_signing.py`, with a box-local key). These pin the wording to
that, and pin the allowed_signers note to the truth in BOTH directions: while nothing verifies
commits the file says NOT WIRED and names what real signing needs; the day something runs
`git verify-commit` or reads the file, the note must go.

Data keys (`signature`, `signed`, `signed_by`, `UNSIGNED`) and the `--sign` flag are kept: they are
state the boxes read, and renaming them would break readers for a wording fix.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SIGNERS = ROOT / "ops" / "signing" / "allowed_signers"

#: The phrases that claimed a signature where only a hash seal or an HMAC exists.
FALSE_CLAIMS = ("signed manifest", "signed money-path", "signed judge", "signed ref",
                "SIGNED release", "SIGNED, SEALED", "signed target diff")

#: Release tooling and the files the audit named. scripts/check_immutable_evaluator.py is sealed:
#: its wording lands with patches/audit-governance/immutable_evaluator_sealed_wording.patch.
SCOPED = ("libs/ops/release.py", "libs/ops/release_signing.py", "libs/ops/capability_graph.py",
          "libs/ops/module_rent.py", "libs/research/immutable_rails.py",
          "scripts/check_immutable_rails.py", "scripts/check_target_seal.py",
          "ops/release_authority.py", "ops/organ_contract.py", "ops/run_release_authority.cmd",
          "desks/mt5/mt5desk/release_identity.py", "desks/mt5/scripts/Adopt-Release.ps1",
          "desks/mt5/scripts/Adopt-And-Seal.ps1", "docs/DESK_CYCLE_PROMPT.md",
          "docs/research/tier1_program.json")


@pytest.mark.parametrize("rel", SCOPED)
def test_no_false_signing_claim(rel: str) -> None:
    p = ROOT / rel
    if not p.is_file():
        pytest.skip(f"{rel} absent in this checkout")
    text = p.read_text("utf-8", errors="replace")
    bad = [c for c in FALSE_CLAIMS if c in text]
    assert not bad, f"{rel} claims a signature it does not have: {bad} (say hash-sealed / HMAC)"


def _wired() -> list[str]:
    files = subprocess.run(["git", "ls-files", "-z", "*.py", "*.sh", "*.ps1", "*.cmd"], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.split("\0")
    out = []
    for rel in filter(None, files):
        p = ROOT / rel
        if not p.is_file() or "tests" in Path(rel).parts:
            continue
        text = p.read_text("utf-8", errors="replace")
        if "allowed_signers" in text or "allowedSignersFile" in text or "verify-commit" in text:
            out.append(rel)
    return out


def test_the_allowed_signers_note_tells_the_truth() -> None:
    text = SIGNERS.read_text("utf-8")
    wired = _wired()
    says_unwired = text.startswith("# NOT WIRED")
    assert says_unwired == (not wired), (
        f"allowed_signers says NOT WIRED={says_unwired} but verification code is "
        f"{wired or 'absent'}: update the note to match")
    if says_unwired:
        for need in ("gpg.format ssh", "user.signingkey", "allowedSignersFile", "verify-commit",
                     "key on the box"):
            assert need in text, need
    keys = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    assert keys and all(" ssh-" in ln for ln in keys)        # still a valid allowed_signers file
