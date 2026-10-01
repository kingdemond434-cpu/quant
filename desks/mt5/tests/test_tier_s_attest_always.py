"""A full `tier_s` pass attests before its organs and names a failed attestation (2026-09-30).

`box_evidence.attest()` ran only after the last organ, so a pass killed at the leg cap left no
data/tier_s/box_evidence.json for the box's sync to carry, and a failed attestation was added to
`errors` after the summary had been written -- recorded nowhere.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import tier_s as ts  # noqa: E402

from libs.tiers import box_evidence  # noqa: E402


def test_a_failed_attestation_is_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise OSError("disk full")

    monkeypatch.setattr(box_evidence, "attest", boom)
    errors: dict[str, str] = {}
    assert ts._attest(errors) is False
    assert errors["box_evidence"] == "OSError: disk full"


def test_a_later_success_clears_the_early_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(box_evidence, "attest", lambda: {})
    errors = {"box_evidence": "OSError: disk full"}
    assert ts._attest(errors) is True
    assert "box_evidence" not in errors


def test_a_full_pass_attests_before_its_first_organ() -> None:
    src = (DESK / "research" / "tier_s.py").read_text("utf-8")
    body = src[src.index("def main("):]
    first_attest = body.index("_attest(errors)")
    first_organ = body.index("for name, fn in plan:")
    assert first_attest < first_organ, "a pass killed mid-organ would leave no attestation"
    assert body.count("_attest(errors)") >= 2, "the end-of-pass attestation was dropped"
