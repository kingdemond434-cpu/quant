"""The DatasetContract: every missing field named, legality a hard gate, vintages immutable.

The property that matters most is the one a plausible implementation would get wrong quietly:
a BLOCKED contract with an enormous expected value must be exactly as inadmissible as one worth
nothing, because the gate has no value input at all. The rest pins the RESEARCH-11 field list,
the vintage semantics (a revision supersedes, never overwrites) and the replay question.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import data_contract as DC  # noqa: E402

AT = "2026-09-22T00:00:00+00:00"


def complete(**over: object) -> DC.DatasetContract:
    base: dict[str, object] = {
        "dataset_id": "fred:DGS10", "source": "FRED", "owner": "St. Louis Fed",
        "acquisition_method": "research/fetch_fred.py", "public_or_licensed": "OPEN_DATA",
        "licence_version": "FRED terms of use 2024", "permitted_uses": ("research", "backtest"),
        "redistribution_rights": "none", "personal_data_status": "NONE",
        "mnpi_review_status": "NOT_APPLICABLE", "jurisdiction": "US",
        "point_in_time_timestamp": AT, "revision_policy": "REVISED_IN_PLACE",
        "retention_policy": "INDEFINITE", "compliance_owner": "principal",
        "provenance_state": "CLEAR", "schema": {"available_time": "iso8601", "value": "float"},
        "timestamp_semantics": "both",
    }
    base.update(over)
    return DC.DatasetContract(**base)  # type: ignore[arg-type]


# ------------------------------------------------------------------------- completeness
def test_the_field_list_is_exactly_research_11s() -> None:
    assert DC.CONTRACT_FIELDS == (
        "source", "owner", "acquisition_method", "public_or_licensed", "licence_version",
        "permitted_uses", "redistribution_rights", "personal_data_status", "mnpi_review_status",
        "jurisdiction", "point_in_time_timestamp", "revision_policy", "retention_policy",
        "compliance_owner")


def test_validate_names_every_missing_field() -> None:
    empty = DC.DatasetContract(dataset_id="x")
    assert empty.missing() == DC.CONTRACT_FIELDS
    problems = empty.validate()
    for name in DC.CONTRACT_FIELDS:
        assert any(p.startswith(f"{name}:") for p in problems), name
    two = complete(owner=DC.UNMEASURED, jurisdiction="")
    assert two.missing() == ("owner", "jurisdiction")
    assert not two.complete and complete().complete


def test_a_value_outside_the_vocabulary_is_named_too() -> None:
    problems = complete(revision_policy="whenever").validate()
    assert any(p.startswith("revision_policy:") and "whenever" in p for p in problems)


# ----------------------------------------------------------------- the legality hard gate
def test_blocked_provenance_is_inadmissible_regardless_of_value() -> None:
    blocked = complete(provenance_state="BLOCKED")
    assert not blocked.admissible()
    for value in (0.0, 1.0, 1e9):
        verdict = DC.gate(blocked, value)
        assert not verdict.admitted
        assert verdict.expected_value == value            # carried, never consulted
        assert any("BLOCKED" in r for r in verdict.reasons)
    assert DC.gate(complete(), 0.0).admitted             # and a clean one at zero value is fine


def test_unresolved_mnpi_review_shuts_the_gate() -> None:
    for state in ("PENDING", "FLAGGED", DC.UNMEASURED):
        assert not complete(mnpi_review_status=state).admissible(), state
    assert complete(mnpi_review_status="REVIEWED_CLEAR").admissible()


def test_refused_labels_quarantine_and_incomplete_contracts_are_inadmissible() -> None:
    assert not complete(public_or_licensed="CONFIDENTIAL_MNPI").admissible()
    assert not complete(provenance_state="QUARANTINED").admissible()
    assert not complete(provenance_state=DC.UNMEASURED).admissible()
    assert not complete(owner=DC.UNMEASURED).admissible()
    assert not complete(personal_data_status="PERSONAL").admissible()
    assert DC.provenance_from_verdict(refused=True, quarantine=False) == "BLOCKED"
    assert DC.provenance_from_verdict(refused=False, quarantine=True) == "QUARANTINED"
    assert DC.provenance_from_verdict(refused=False, quarantine=False) == "CLEAR"


def test_machine_extraction_needs_explicit_permission_and_the_lease_is_measured() -> None:
    c = complete(permitted_uses=("research", "machine_extract"))
    assert c.may("research") and not c.may("machine_extract")      # None is not permission
    assert complete(permitted_uses=("machine_extract",), machine_use_allowed=True).may(
        "machine_extract")
    assert not complete(permitted_uses=("machine_extract",), machine_use_allowed=False).may(
        "machine_extract")
    assert c.fresh(AT) is None                                       # no lease: UNMEASURED
    leased = complete(freshness_lease_s=3600.0, last_available="2026-09-22T00:30:00+00:00")
    assert leased.fresh("2026-09-22T01:00:00+00:00") is True
    assert leased.fresh("2026-09-22T02:00:00+00:00") is False
    assert DC.contract_state_of(None) == DC.CONTRACT_MISSING
    assert DC.contract_state_of(complete()) == "CONTRACTED"
    assert DC.contract_state_of(complete(owner=DC.UNMEASURED)) == "CONTRACT_INCOMPLETE"


# -------------------------------------------------------------- vintages and lineage
ROWS_1 = [{"available_time": f"2026-09-{d:02d}T00:00:00+00:00", "value": float(d)}
          for d in range(1, 11)]
ROWS_2 = [*ROWS_1[:-1], {"available_time": ROWS_1[-1]["available_time"], "value": 99.0}]


def test_snapshot_is_immutable_and_a_revision_supersedes_it() -> None:
    first = DC.snapshot(complete(), ROWS_1, at=AT, code_version="abc123")
    assert first.vintage.supersedes is None and first.vintage.n_rows == 10
    assert first.contract.first_available == ROWS_1[0]["available_time"]
    assert first.contract.last_available == ROWS_1[-1]["available_time"]
    assert DC.verify(first.lineage, ROWS_1) and not DC.verify(first.lineage, ROWS_2)
    again = DC.revise(first, ROWS_1, at="2026-09-23T00:00:00+00:00", code_version="abc123")
    assert again is first                                             # unchanged content
    second = DC.revise(first, ROWS_2, at="2026-09-23T00:00:00+00:00", code_version="def456")
    assert second.vintage.supersedes == first.vintage.vintage_id
    assert second.vintage.vintage_id != first.vintage.vintage_id
    assert first.vintage.snapshot_hash == DC.hash_rows(ROWS_1)[0]     # the old vintage stands
    assert second.lineage.parents == (first.lineage.lineage_id,)
    chain = DC.lineage_chain([first.lineage, second.lineage], second.lineage.lineage_id)
    assert [r.vintage_id for r in chain] == [second.vintage.vintage_id, first.vintage.vintage_id]
    assert DC.replay_key(second.lineage).startswith("fred:DGS10@")
    assert "def456" in DC.replay_key(second.lineage)


def test_json_round_trip_keeps_every_field_and_the_vintage() -> None:
    snap = DC.snapshot(complete(machine_use_allowed=True, freshness_lease_s=60.0), ROWS_1,
                       at=AT, code_version="abc123")
    doc = snap.contract.to_json()
    back = DC.DatasetContract.from_json(doc)
    assert back == snap.contract
    assert back.vintage is not None and back.vintage == snap.vintage
    assert doc["contract_hash"] == snap.contract.content_hash()
    lineage = DC.LineageRecord.from_json(snap.lineage.to_json())
    assert lineage == snap.lineage and lineage.lineage_id == snap.lineage.lineage_id


def test_hash_rows_is_order_sensitive_and_deterministic() -> None:
    assert DC.hash_rows(ROWS_1) == DC.hash_rows(list(ROWS_1))
    assert DC.hash_rows(ROWS_1)[0] != DC.hash_rows(list(reversed(ROWS_1)))[0]
    with pytest.raises(TypeError):
        DC.hash_rows(None)  # type: ignore[arg-type]
