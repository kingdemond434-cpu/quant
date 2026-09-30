from __future__ import annotations

import sys
from pathlib import Path

RESEARCH = Path(__file__).resolve().parents[1] / "research"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import forward_calibration as fc  # noqa: E402


def test_forward_trade_counts_are_conserved_and_missing_is_not_zero(monkeypatch) -> None:
    rows = [
        {"key": "a", "status": "ACTIVE", "n": 3, "exp_r": 0.1, "days_active": 20},
        {"key": "b", "status": "ACTIVE", "n": 0, "exp_r": 0.0, "days_active": 20},
        {"key": "c", "status": "RETIRED", "n": 2, "exp_r": -0.1, "days_active": 20},
        {"key": "d", "status": "ACTIVE", "exp_r": 0.2, "days_active": 20},
        {"key": "e", "status": "ACTIVE", "n": 4, "exp_r": 0.1, "days_active": 20},
        {"key": "f", "status": "ACTIVE", "n": 5, "exp_r": 0.1, "days_active": 20},
        {"key": "g", "status": "ACTIVE", "n": 6, "exp_r": 0.1, "days_active": 20},
        {"key": "h", "status": "ACTIVE", "n": 7, "exp_r": 0.1, "days_active": 20},
    ]
    monkeypatch.setattr(fc, "_clocks", lambda: rows)
    monkeypatch.setattr(fc, "DRAWS", 2)
    doc = fc.build()
    assert doc["lane"]["n_with_trades"] == 6
    assert doc["lane"]["n_active_with_trades"] == 5
    assert doc["lane"]["n_zero_trade"] == 1
    assert doc["lane"]["forward_trades_reported"] == 27
    assert doc["trade_tracking"]["status"] == "UNMEASURED"
    assert doc["trade_tracking"]["clock_rows_missing_trade_count"] == ["d"]


def test_forward_tracking_is_complete_when_every_clock_has_an_n(monkeypatch) -> None:
    rows = [
        {"key": str(i), "status": "ACTIVE", "n": i, "exp_r": float(i) / 100,
         "days_active": 20}
        for i in range(1, 7)
    ]
    monkeypatch.setattr(fc, "_clocks", lambda: rows)
    monkeypatch.setattr(fc, "DRAWS", 2)
    doc = fc.build()
    assert doc["trade_tracking"]["status"] == "COMPLETE"
    assert doc["trade_tracking"]["n_missing"] == 0
