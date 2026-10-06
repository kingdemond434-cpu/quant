"""Legacy receipts cannot manufacture pre-backfill point-in-time availability."""
from datetime import UTC, datetime, timedelta

from research.merge_hypotheses import _identity, recover_banked_provenance

from libs.data.pit import is_stamped, stamp, usable_at


def test_legacy_receipt_preserves_rule_and_does_not_borrow_first_seen():
    now = datetime(2026, 10, 3, tzinfo=UTC)
    old = {"symbol": "USDJPY", "family": "session_range_breakout",
           "params": {"rr": 2.5, "wait_bars": 12}, "first_seen": "2020-01-01"}
    new = recover_banked_provenance(old, now=now)
    assert is_stamped(new)
    assert new["source_version"] == "backfill"
    assert new["available_time"] == now.isoformat()
    assert new["first_seen"] == old["first_seen"]
    assert _identity(new) == _identity(old)
    assert usable_at(new, now - timedelta(seconds=1)) is False
    assert usable_at(new, now) is True
    assert "available_time" not in old


def test_complete_original_stamp_is_untouched_and_recovery_is_idempotent():
    now = datetime(2026, 10, 3, tzinfo=UTC)
    old = stamp({"symbol": "USDJPY", "family": "carry", "params": {}},
                "original", source_version="real-producer", now=now)
    assert recover_banked_provenance(old, now=now) is old
    legacy = {"symbol": "USDJPY", "family": "carry", "params": {}}
    once = recover_banked_provenance(legacy, now=now)
    assert recover_banked_provenance(once, now=now) is once


def test_partial_stamp_preserves_recorded_availability_and_fills_invalid_receipt():
    now = datetime(2026, 10, 3, tzinfo=UTC)
    old = {"symbol": "USDJPY", "family": "carry", "params": {},
           "available_time": "2026-10-01T00:00:00+00:00", "source_version": None,
           "ingested_time": "", "payload_hash": None}
    new = recover_banked_provenance(old, now=now)
    assert is_stamped(new)
    assert new["available_time"] == old["available_time"]
    assert new["ingested_time"] == now.isoformat()
    assert new["source_version"] == "backfill"
