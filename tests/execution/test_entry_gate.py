"""Locks the R0057 entry-gate semantics (2026-07-31, _MIN_FUNDING deletion).

The absolute per-8h funding floor was deleted because the per-symbol cost gate
(p90 fail-closed default) plus the structural-bleed denylist carry all of its
protection, while the floor's only measured remaining effect was vetoing the
net-positive majors (245/245 candidates rejected). These tests pin BOTH
directions: measured-cheap books clear at baseline funding, and the fail-closed
default / denylist still refuse everything the floor used to be credited with.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import scripts.run_cashcarry_executor as ex


@pytest.fixture()
def _gate_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cost = tmp_path / "cost_model.json"
    cost.write_text(json.dumps({
        "symbols": {"BTCUSDT": {"pair": {"500": {"pair_roundtrip_bps": 2.0}}}}
    }), "utf-8")
    forensics = tmp_path / "trade_forensics.json"
    forensics.write_text(json.dumps({
        "worst_symbols": [{"symbol": "NOMUSDT", "n": 5, "bps": -149.0}]
    }), "utf-8")
    monkeypatch.setattr(ex, "_COST_MODEL", cost)
    monkeypatch.setattr(ex, "_FORENSICS", forensics)


def test_measured_cheap_major_clears_at_baseline_funding(_gate_files: None) -> None:
    # Binance baseline 0.0001/8h over a 24h min hold = 3.0 bps capture > 2.0 bps measured
    # round-trip. Net-positive, and the exact case the deleted floor was vetoing.
    assert ex._entry_gate("BTCUSDT", 0.0001, min_hold_h=24.0) is True


def test_measured_cheap_major_still_blocked_below_its_own_cost(_gate_files: None) -> None:
    # No free pass for being a major: 0.00005/8h -> 1.5 bps capture < 2.0 bps round-trip.
    assert ex._entry_gate("BTCUSDT", 0.00005, min_hold_h=24.0) is False


def test_unmeasured_symbol_fails_closed_at_baseline_funding(_gate_files: None) -> None:
    # Absent from the cost model => p90 default 39.5 bps; 3.0 bps capture never clears it.
    # This is the disaster class (gap #43, -92.7 bps bucket) the floor was built for.
    assert ex._entry_gate("THINUSDT", 0.0001, min_hold_h=24.0) is False


def test_bleed_denylist_blocks_regardless_of_funding(_gate_files: None) -> None:
    # Proven structural loser stays blocked even at 15x baseline funding.
    assert ex._entry_gate("NOMUSDT", 0.0015, min_hold_h=24.0) is False
