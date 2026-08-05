"""The cross-section collector must REFUSE a narrowed universe rather than write one.

A percentile is only as honest as its denominator. A truncated payload written to tape would bias
every residual taken against that row, permanently and invisibly -- so the thin-payload refusal and
the malformed-element accounting are the properties under test, not the happy path.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def collector():
    spec = importlib.util.spec_from_file_location(
        "collect_funding_cross_section", _ROOT / "scripts/collect_funding_cross_section.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _payload(n: int) -> list[dict]:
    return [{"symbol": f"S{i}USDT", "lastFundingRate": "0.0001",
             "nextFundingTime": 1_700_000_000_000 + i, "time": 1_699_999_999_000}
            for i in range(n)]


def test_snapshot_declares_its_clock_and_keeps_the_venue_stamp(collector) -> None:
    """L1.46: a timestamp whose clock is undeclared is an assumption in a measurement's clothes."""
    row = collector.snapshot(payload=_payload(300))
    assert row["c"] == "venue"
    assert row["tv"] == 1_699_999_999_000
    assert row["t"] >= row["tv"]              # our receipt cannot precede the venue's stamp
    assert row["venue"] == "binance_usdm"


def test_missing_venue_stamp_reads_recv_only_not_recv(collector) -> None:
    """A VENUE limitation must never read as a desk defect -- the two statuses stay distinct."""
    payload = [{"symbol": f"S{i}USDT", "lastFundingRate": "0.0001"} for i in range(300)]
    row = collector.snapshot(payload=payload)
    assert row["c"] == "recv_only"
    assert row["tv"] is None


def test_next_funding_time_is_retained(collector) -> None:
    """`nextFundingTime` arrives in a payload the desk already reads and had ZERO uses repo-wide."""
    row = collector.snapshot(payload=_payload(250))
    assert len(row["next_funding_ms"]) == 250
    assert row["next_funding_ms"]["S0USDT"] == 1_700_000_000_000


def test_every_discarded_element_is_counted(collector) -> None:
    """L2.4: a silent discard is a shrinking denominator that nothing can see."""
    payload = [
        *_payload(200),
        {"symbol": "BADRATE", "lastFundingRate": "not-a-number"},
        {"lastFundingRate": "0.0001"},                       # no symbol
        "not-a-dict",
        {"symbol": "BADNEXT", "lastFundingRate": "0.0001", "nextFundingTime": "soon"},
    ]
    row = collector.snapshot(payload=payload)
    assert row["malformed"]["rate"] == 1
    assert row["malformed"]["element"] == 2
    assert row["malformed"]["next_funding"] == 1
    assert row["n"] == 201                                   # 200 good + BADNEXT's rate parsed


def test_a_thin_payload_is_refused_not_written(collector, tmp_path, monkeypatch) -> None:
    """The refusal path (L1.41): a truncated response is a fault, not a small universe."""
    monkeypatch.setattr(collector, "OUT", tmp_path / "tape.jsonl")
    monkeypatch.setattr(collector, "snapshot", lambda: collector.snapshot.__wrapped__()
                        if False else {"t": 1, "tv": 1, "c": "venue", "venue": "binance_usdm",
                                       "kind": "funding_cross_section", "n": 5, "malformed": {},
                                       "rates": {"A": 0.1}, "next_funding_ms": {}})
    monkeypatch.setattr("sys.argv", ["collect_funding_cross_section.py"])
    assert collector.main() == 2
    assert not (tmp_path / "tape.jsonl").exists()


def test_min_symbols_floor_is_a_real_bar(collector) -> None:
    # 200 is well below Binance's ~855 but far above anything a partial response would return.
    assert collector.MIN_SYMBOLS >= 200
