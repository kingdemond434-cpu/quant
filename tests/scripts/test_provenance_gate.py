"""Triage item #82 -- the measurement gate's sixth family: where the numbers came from.

Families 1-5 interrogate the data. None of them can see the property that invalidates a dataset
WITHOUT LEAVING A TRACE IN IT. That is the whole reason this family exists, and the first two
tests here prove the gap is real rather than assumed: a self-reported volume series and a
survivorship-selected universe are constructed to be flawless by every distributional test, and
family 6 is the only thing that rejects them.

The remaining tests pin the two design decisions that make the register worth having:
CONTRADICTED must be a FAIL (a wrong provenance claim is trusted where an absent one invites a
check), and UNDECLARED must be a WARN (blocking every dataset on day one converts a control into
an outage, and outages are how controls get switched off).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _gate():
    spec = importlib.util.spec_from_file_location("mg", ROOT / "scripts/measurement_gate.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mg = _gate()
REGISTER = mg.load_provenance()


def _rows(n: int = 60, **extra) -> list[dict]:
    """A series that is deliberately PERFECT for families 1-5: regular hourly stamps, no nulls,
    no frozen runs, real variance. Any rejection therefore comes from family 6 alone."""
    return [{"ts": 1_780_000_000 + i * 3600, "value": 100.0 + (i % 17) * 0.5, **extra}
            for i in range(n)]


def test_register_parses_and_is_populated() -> None:
    assert REGISTER, "docs/research/data_provenance.json must exist and carry datasets"
    for name, rec in REGISTER.items():
        assert rec.get("source"), f"{name} declares no source"
        assert rec["collection_method"] in mg._COLLECTION, name
        assert rec["manipulation_risk"] in mg._RISK_LEVELS, name
        assert rec["survivorship"] in mg._SURVIVORSHIP, name


def test_self_reported_volume_is_rejected_by_family_6_alone() -> None:
    """THE GAP, DEMONSTRATED. Perfect by families 1-5; invalid because of who produced it."""
    rows = _rows()
    assert mg.check_timestamps(rows, "TIME_SERIES")[0] == [], "family 1 sees nothing wrong"
    assert mg.check_correctness(rows, "TIME_SERIES")[0] == [], "family 2 sees nothing wrong"
    assert mg.check_features(rows)[0] == [], "family 3 sees nothing wrong"

    fails, _, meta = mg.check_provenance(Path("data/exchange_volume.jsonl"), rows, REGISTER)
    assert meta["manipulation_risk"] == "HIGH"
    assert any("MANIPULATION RISK HIGH" in f for f in fails), (
        "a series whose counterparty chooses the number must be blocked, not warned")


def test_survivorship_contamination_blocks() -> None:
    reg = {"universe.jsonl": {"source": "desk", "collection_method": "DERIVED",
                              "manipulation_risk": "LOW", "survivorship": "CONTAMINATED"}}
    fails, _, _ = mg.check_provenance(Path("data/universe.jsonl"), _rows(), reg)
    assert any("SURVIVORSHIP CONTAMINATED" in f for f in fails)


def test_contradicted_provenance_is_a_fail_not_a_warning() -> None:
    """The register must be falsifiable AGAINST THE DATA, or it is a wish list.

    A declaration nothing can contradict is worth nothing: it would be satisfied just as well by
    writing 'bybit' next to a file scraped from anywhere.
    """
    fails, _, meta = mg.check_provenance(
        Path("data/moat_depth.jsonl"), _rows(venue="binance"), REGISTER)
    assert any("PROVENANCE CONTRADICTED" in f for f in fails)
    assert meta["observed_sources"] == ["binance"]


def test_corroborated_provenance_passes_clean() -> None:
    fails, warns, _ = mg.check_provenance(
        Path("data/moat_depth.jsonl"), _rows(venue="bybit"), REGISTER)
    assert fails == [] and warns == []


def test_undeclared_warns_but_never_blocks() -> None:
    """Undeclared is unknown, not invalid. Blocking it on day one is how the gate gets disabled."""
    fails, warns, meta = mg.check_provenance(Path("data/brand_new.jsonl"), _rows(), REGISTER)
    assert fails == [], "an undeclared dataset must not be blocked -- it must be COUNTED"
    assert len(warns) == 1 and "UNDECLARED PROVENANCE" in warns[0]
    assert meta == {"declared": False}


def test_ungraded_risk_is_not_low_risk() -> None:
    """The silent-default trap: a missing grade must not read as the safe grade."""
    reg = {"x.jsonl": {"source": "s", "collection_method": "PUBLIC_API",
                       "manipulation_risk": "", "survivorship": ""}}
    fails, warns, _ = mg.check_provenance(Path("data/x.jsonl"), _rows(), reg)
    assert fails == []
    assert any("manipulation_risk" in w for w in warns)
    assert any("survivorship" in w for w in warns)


def test_undeclared_count_is_reported_for_ratcheting() -> None:
    """A list nobody sums is a list that never shrinks."""
    src = (ROOT / "scripts/measurement_gate.py").read_text("utf-8")
    assert '"provenance_undeclared"' in src
    assert '"n": len(undeclared)' in src


@pytest.mark.parametrize("name", ["moat_depth.jsonl", "moat_trades.jsonl", "funding_history.jsonl"])
def test_high_value_sources_are_declared(name: str) -> None:
    """The desk's own information-advantage ranking puts the moat first; it must be graded."""
    assert name in REGISTER


def test_funding_survivorship_is_honestly_unknown() -> None:
    """UNKNOWN is a legitimate grade and must not be laundered into CLEAN.

    The funding endpoint returns history for LISTED symbols, so delisted perps are absent by
    construction. Nobody has measured that hole, and writing CLEAN to silence a warning is the
    exact failure this register exists to prevent.
    """
    assert REGISTER["funding_history.jsonl"]["survivorship"] == "UNKNOWN"


def test_register_is_tracked_outside_gitignored_data() -> None:
    """data/ is gitignored; a provenance record that dies with the working directory is not one."""
    assert mg.PROVENANCE.relative_to(ROOT).as_posix().startswith("docs/")
    json.loads(mg.PROVENANCE.read_text("utf-8"))
