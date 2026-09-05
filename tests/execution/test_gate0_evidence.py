"""L1.61 FABRICATED-SIDE repair (R0536/R0537): the two Gate-0 organs read ONE source.

Every test here fails against the pre-repair code, where `run_live_guard` built
`principal_signoff` from `data/stage_state.json['principal_signoff']` (a key no code writes) and
`symbol_count` only from the `data/ramp_state.json` evidence spread (a file that has never
existed). Both criteria therefore published False permanently while the Gate-0 board -- calling
the SAME `s1_entry_met` -- measured both True from the real artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.execution import gate0_evidence

_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def box(tmp_path: Path) -> Path:
    """A box whose artifacts say exactly what the real one says: signed, top=4, no ramp file."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data/gate0_signoff.json").write_text(
        json.dumps({"decision": "go", "at": "2026-07-30T00:00:00+00:00"}), "utf-8")
    (tmp_path / "data/cashcarry_config.json").write_text(json.dumps({"top": 4}), "utf-8")
    # The phantom source, present and WITHOUT the key -- exactly the live artifact.
    (tmp_path / "data/stage_state.json").write_text(json.dumps({"stage": "S0"}), "utf-8")
    return tmp_path


class TestSharedReader:
    def test_signoff_is_the_file_not_a_flag(self, box: Path) -> None:
        assert gate0_evidence.principal_signoff(box) is True
        (box / "data/gate0_signoff.json").unlink()
        assert gate0_evidence.principal_signoff(box) is False

    def test_corrupt_signoff_still_reads_as_consent(self, box: Path) -> None:
        """The principal's act was CREATING the file; a parse error must not revoke consent."""
        (box / "data/gate0_signoff.json").write_text("{not json", "utf-8")
        assert gate0_evidence.principal_signoff(box) is True

    def test_symbol_count_reads_the_executor_knob(self, box: Path) -> None:
        assert gate0_evidence.symbol_count(box) == 4

    def test_unreadable_config_is_none_never_zero(self, box: Path) -> None:
        """None is UNMEASURED; 0 would be a verdict nobody measured (L1.28a)."""
        (box / "data/cashcarry_config.json").write_text("{not json", "utf-8")
        assert gate0_evidence.symbol_count(box) is None
        (box / "data/cashcarry_config.json").unlink()
        assert gate0_evidence.symbol_count(box) is None

    def test_non_dict_config_is_none(self, box: Path) -> None:
        (box / "data/cashcarry_config.json").write_text("[1, 2, 3]", "utf-8")
        assert gate0_evidence.symbol_count(box) is None



# ---------------------------------------------------------------------------------------------
# RETIRED 2026-09-05 -- TestGuardEvidenceNoLongerFabricated and the two guard-reading tests of
# TestOneReaderNotTwo.
#
# They loaded `scripts/run_live_guard.py` by path. That script was DELETED in 1657d5f7 and its
# schedule was retired in ops/crontab.manifest with the reason written beside the row: it was an
# ops/execution organ bound to the retired crypto executor and its Gate-0 staging ladder, and the
# MT5 gateway carries its own cost, quality and guard path under desks/mt5/. The deletion was
# correct; these tests were the last thing still pointing at it, and they had been failing on
# FileNotFoundError ever since -- which is not a verdict on anything, it is a test for code that
# the desk decided on purpose not to have.
#
# WHAT SURVIVES, AND WHY IT IS THE HALF WORTH KEEPING. `TestSharedReader` above tests
# `libs/execution/gate0_evidence`, which is alive and is the ONE reader both organs were meant to
# share -- the property that mattered (two organs, one evidence reader, no fabricated criteria)
# is asserted there against code that exists. `test_registry_no_longer_calls_these_two_sides
# _fabricated` is kept below for the same reason.
#
# THE REGISTRY ENTRY WENT WITH THEM. `libs/ops/claim_registry` still declared
# `Publisher("run_live_guard", "data/live_guard.json", ...)` for a script that no longer exists,
# so the desk was carrying a publisher claim nothing could satisfy -- one of the 166 dead wires
# `scripts/check_read_without_writer.py` counts. A claim whose claimant was deleted is not a
# pending task; it is a false statement about the desk.
# ---------------------------------------------------------------------------------------------


class TestOneReaderNotTwo:
    def test_registry_no_longer_calls_these_two_sides_fabricated(self) -> None:
        """The registry is read FROM the producer's code; a stale flag accuses a measurement."""
        from libs.ops.claim_registry import _S1_CRITERIA
        flags = {c[0]: c[4] for c in _S1_CRITERIA}
        assert flags["principal_signoff"] is False
        assert flags["symbol_count_4_5"] is False
