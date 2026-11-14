"""Seal carriers never merge (2026-11-14: #1193 and #1081 reached LIVE on a CLEAR of the carrier
head). The gate refuses a PR that adds or changes a carrier file, whatever its verdict; removing
carrier files still merges."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "audit_gate_carriers", ROOT / ".github/scripts/audit_gate.py"
)
assert _spec is not None and _spec.loader is not None
ag = importlib.util.module_from_spec(_spec)
sys.modules["audit_gate_carriers"] = ag
_spec.loader.exec_module(ag)

CARRIER = "desks/mt5/data/seal_carriers/888eab63df1976d21b0ab4bc9be161e3c1294a89.bundle"


def _tier(*files: dict[str, Any]) -> tuple[str, str]:
    return ag.tier(list(files), len(files), lambda n: False)


def test_adding_or_changing_a_carrier_file_is_refused() -> None:
    for status in ("added", "modified", "renamed", "copied", ""):
        level, why = _tier({"filename": CARRIER, "status": status})
        assert level == "REFUSED", status
        assert "seal carrier" in why
    level, _ = _tier({"filename": "libs/x.py", "status": "modified"},
                     {"filename": CARRIER.upper(), "status": "added"})  # fmt: skip
    assert level == "REFUSED"  # case-blind, as on the box's NTFS checkout


def test_removing_carrier_files_still_merges() -> None:
    level, _ = _tier({"filename": CARRIER, "status": "removed"})
    assert level != "REFUSED"


def test_the_carrier_branch_prefix_is_pinned() -> None:
    assert ag.SEAL_CARRIER_BRANCH == "claude/seal-carrier-"
    assert ag.SEAL_CARRIERS == ("desks/mt5/data/seal_carriers/*",)


def test_a_carrier_branch_is_never_merged_even_with_a_clear(tmp_path: Path) -> None:
    import pytest

    pytest.importorskip("cryptography")
    spec = importlib.util.spec_from_file_location(
        "authority_sandbox_sc", ROOT / "ops/release/authority/sandbox.py"
    )
    assert spec is not None and spec.loader is not None
    sb_mod = importlib.util.module_from_spec(spec)
    sys.modules["authority_sandbox_sc"] = sb_mod
    spec.loader.exec_module(sb_mod)
    sb = sb_mod.Sandbox(tmp_path)
    sb.ag.REGISTRY_HOLD_H = 24.0
    assert sb.authority()[0] == "CLEAR"
    sb.gh.pr["head"]["ref"] = "claude/seal-carrier-888eab63"
    sb.gate()
    sb.clock.advance(hours=25)
    sb.gate()
    assert sb.gh.merges() == []
