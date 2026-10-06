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
from typing import Any

import pytest

from libs.execution import gate0_evidence, staging

_ROOT = Path(__file__).resolve().parents[2]


#: THE TWO ORGANS THIS FILE ORIGINALLY PINNED ARE RETIRED. `scripts/run_live_guard.py` (the
#: executor-side evaluator) and `scripts/check_gate0_ready.py` (the launch-day board) were deleted
#: with the cash-carry desk under the MT5 universe mandate (ops/crontab.manifest "RETIRED
#: 2026-09-05"). What survives is the shared reader and the gate it feeds, so the guard-side tests
#: below now build the evidence FROM THE SHARED READER -- the only construction a revived organ
#: may use -- and the one-reader tests pin that no surviving code re-reads the phantom key.
_RETIRED = ("scripts/run_live_guard.py", "scripts/check_gate0_ready.py")


def _evidence(root: Path) -> dict[str, Any]:
    """The S1 evidence as the shared reader supplies it, on an unarmed box.

    An unreadable symbol count OMITS the key rather than publishing a fabricated 0 -- the rule
    `run_live_guard._promo_evidence` followed -- so the gate's own default does the refusing.
    """
    ev: dict[str, Any] = {"principal_signoff": gate0_evidence.principal_signoff(root),
                          "keys_present": False, "connector_verified": False,
                          "capital_fraction": 0.1}
    n = gate0_evidence.symbol_count(root)
    if n is not None:
        ev["symbol_count"] = n
    return ev


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


class TestGuardEvidenceNoLongerFabricated:
    def test_signoff_is_seen_without_the_phantom_key(self, box: Path) -> None:
        """THE ROW ITSELF (R0536): stage_state.json has no such key and never will. The reader
        must see consent from the signoff FILE, and a stray key in stage_state must not override
        it in either direction."""
        assert "principal_signoff" not in json.loads(
            (box / "data/stage_state.json").read_text())
        assert _evidence(box)["principal_signoff"] is True
        (box / "data/stage_state.json").write_text(
            json.dumps({"stage": "S0", "principal_signoff": False}), "utf-8")
        assert _evidence(box)["principal_signoff"] is True

    def test_symbol_count_survives_an_absent_ramp_file(self, box: Path) -> None:
        """THE ROW ITSELF (R0537): ramp_state.json has never existed on this box."""
        assert not (box / "data/ramp_state.json").exists()
        assert _evidence(box)["symbol_count"] == 4

    def test_unreadable_config_omits_the_key_rather_than_publishing_zero(
            self, box: Path) -> None:
        (box / "data/cashcarry_config.json").write_text("{not json", "utf-8")
        ev = _evidence(box)
        assert "symbol_count" not in ev              # never a fabricated 0
        assert staging.s1_entry_met(ev)[0] is False  # the gate's own default refuses
        assert "symbol_count_4_5=False" in staging.s1_entry_met(ev)[1]

    def test_the_two_criteria_agree_with_the_board(self, box: Path) -> None:
        """L1.61: both organs fed one gate, so their readings had to be the same reading. Both
        organs are retired; the reader they shared is what the gate reads now."""
        for rel in _RETIRED:
            assert not (_ROOT / rel).exists(), f"{rel} is back -- pin it to the shared reader"
        ev = _evidence(box)
        assert ev["principal_signoff"] is gate0_evidence.principal_signoff(box)
        assert ev["symbol_count"] == gate0_evidence.symbol_count(box)

    def test_repair_opens_no_gate_on_an_unarmed_box(self, box: Path) -> None:
        """THE LOAD-BEARING ONE. Two criteria go True; the gate stays SHUT on genuine grounds."""
        met, why = staging.s1_entry_met(_evidence(box))
        assert met is False
        assert "keys_present=False" in why
        assert "principal_signoff=True" in why and "symbol_count_4_5=True" in why


class TestOneReaderNotTwo:
    def test_both_organs_import_the_shared_reader(self) -> None:
        """A second encoding of one human act is how these two boards drifted for 20 days. Both
        organs are retired; the reader must still be the ONLY place Gate-0 consent is decoded."""
        for rel in _RETIRED:
            assert not (_ROOT / rel).exists(), (
                f"{rel} is back -- it must use the shared Gate-0 reader (gate0_evidence)")
        readers = sorted(
            p.relative_to(_ROOT).as_posix() for d in ("scripts", "libs", "desks")
            for p in (_ROOT / d).rglob("*.py")
            if "__pycache__" not in p.parts and "gate0_signoff.json" in p.read_text(
                "utf-8", errors="ignore"))
        # claim_registry only NAMES the file in the criterion's description string.
        assert readers == ["libs/execution/gate0_evidence.py", "libs/ops/claim_registry.py"], (
            readers)

    def test_the_phantom_key_is_gone_from_the_guard(self) -> None:
        """Regression pin: the exact defect was a read of a key nothing writes. The guard is gone;
        nothing that survives may bring the read back."""
        offenders = sorted(
            str(p.relative_to(_ROOT)) for d in ("scripts", "libs", "desks")
            for p in (_ROOT / d).rglob("*.py")
            if "__pycache__" not in p.parts
            and 'stage_state.json", {})\n' in (t := p.read_text("utf-8", errors="ignore"))
            and '.get("principal_signoff")' in t)
        assert offenders == []

    def test_registry_no_longer_calls_these_two_sides_fabricated(self) -> None:
        """The registry is read FROM the producer's code; a stale flag accuses a measurement."""
        from libs.ops.claim_registry import _S1_CRITERIA
        flags = {c[0]: c[4] for c in _S1_CRITERIA}
        assert flags["principal_signoff"] is False
        assert flags["symbol_count_4_5"] is False
