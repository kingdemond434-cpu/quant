"""The companion-law matrix must disclose, not hide, the master crosswalk debt."""

from __future__ import annotations

import json

from scripts import build_enforcement_matrix as matrix
from scripts import controller_checkpoint


def test_master_authority_and_crosswalk_scope_are_explicit() -> None:
    built = matrix.build()
    authority = built["authority"]
    sealed = json.loads((matrix._ROOT / "data/constitution_core.lock").read_text("utf-8"))["master"]
    assert authority["master_path"] == "docs/MASTER_QUANT_CONSTITUTION.md"
    assert authority["master_sections"] == 218
    assert authority["master_sha256"] == sealed["sha256"]
    crosswalk = authority["master_to_code_crosswalk"]
    assert crosswalk == {
        "status": "UNMEASURED",
        "covered_sections": None,
        "total_sections": 218,
        "owed": True,
        "scope_note": crosswalk["scope_note"],
    }
    assert "companion laws" in crosswalk["scope_note"]


def test_checkpoint_records_the_canonical_master_seal() -> None:
    sealed = json.loads((matrix._ROOT / "data/constitution_core.lock").read_text("utf-8"))["master"]
    summary = controller_checkpoint._git_summary()
    assert summary["master_constitution"] == sealed["path"]
    assert summary["master_constitution_sha256"] == sealed["sha256"]
