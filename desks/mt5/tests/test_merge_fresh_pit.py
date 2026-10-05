from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))

from research.merge_hypotheses import (  # noqa: E402
    _identity,
    admit_registry_row,
    stamp_fresh_intake,
)

from libs.data.pit import is_stamped  # noqa: E402


def test_fresh_intake_is_available_at_merge_not_old_found_time() -> None:
    now = datetime(2026, 9, 30, 15, 0, tzinfo=UTC)
    row = {"symbol": "XAUUSD", "family": "opening_range", "params": {},
           "found_at": "2024-01-01T00:00:00+00:00"}

    stamped = stamp_fresh_intake(row, "miner_candidates.json", now)

    assert is_stamped(stamped)
    assert stamped["available_time"] == "2026-09-30T15:00:00+00:00"
    assert stamped["ingested_time"] == "2026-09-30T15:00:00+00:00"
    assert stamped["intake_stamp"]["source_artifact"] == "miner_candidates.json"


def test_complete_producer_stamp_is_not_rewritten() -> None:
    row = {"available_time": "2026-09-29T00:00:00+00:00",
           "ingested_time": "2026-09-29T00:01:00+00:00",
           "source_version": "v1", "payload_hash": "hash"}

    assert stamp_fresh_intake(
        row, "miner_candidates.json", datetime(2026, 9, 30, tzinfo=UTC)
    ) is row


def test_registry_reemission_recovers_exact_unstamped_identity() -> None:
    old = {"symbol": "USDJPY", "family": "carry", "params": {"side": 1},
           "first_seen": "2026-09-01", "unverified_evidence": "old"}
    emitted = stamp_fresh_intake(
        {"symbol": "USDJPY", "family": "carry", "params": {"side": 1},
         "candidate_id": "recorded-registry-id"}, "alpha_registry",
        datetime(2026, 10, 3, tzinfo=UTC))
    merged = {_identity(old): old}
    assert admit_registry_row(merged, emitted) == "recovered"
    recovered = merged[_identity(old)]
    assert recovered["payload_hash"] == emitted["payload_hash"]
    assert recovered["available_time"] == emitted["available_time"]
    assert recovered["first_seen"] == old["first_seen"]
    assert "unverified_evidence" not in recovered
    assert "available_time" not in old


def test_registry_does_not_replace_valid_producer_or_stamp_unknown_payload() -> None:
    raw = {"symbol": "USDJPY", "family": "carry", "params": {"side": 1}}
    valid = stamp_fresh_intake(raw, "producer", datetime(2026, 10, 3, tzinfo=UTC))
    merged = {_identity(raw): valid}
    assert admit_registry_row(merged, raw) == "kept"
    assert merged[_identity(raw)] is valid
    assert admit_registry_row({}, raw) == "refused"
    other = {**raw, "params": {"side": -1}}
    assert admit_registry_row(merged, other) == "refused"
    assert len(merged) == 1
