from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))

from libs.data.pit import is_stamped  # noqa: E402
from research.merge_hypotheses import stamp_fresh_intake  # noqa: E402


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
