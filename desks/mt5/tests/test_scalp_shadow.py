from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from desks.mt5.research import scalp_shadow as shadow


def test_only_chronologically_stable_candidates_enter_shadow() -> None:
    assert set(shadow.CANDIDATES) == {
        "xau_m5_anti_breakout_overlap", "xau_m5_anti_momentum_ny",
        "xau_m15_anti_breakout", "xau_m15_anti_momentum",
    }
    assert all(choice.family.startswith("anti_") for _, choice in shadow.CANDIDATES.values())


@pytest.mark.parametrize(
    ("authority", "expected"), [(False, "PROXY_SHADOW"), (True, "PROMOTION_CANDIDATE")],
)
def test_proxy_feed_can_never_authorize_capital(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, authority: bool, expected: str,
) -> None:
    data = tmp_path / "data"
    reports = tmp_path / "shadow"
    data.mkdir()
    idx = pd.date_range(shadow.SHADOW_START, periods=100, freq="15min")
    frame = pd.DataFrame({
        "open": np.full(100, 100.0), "high": np.full(100, 101.0),
        "low": np.full(100, 99.0), "close": np.full(100, 100.0),
        "spread": np.full(100, 10), "tick_volume": np.full(100, 100),
    }, index=idx)
    for tf in ("M5", "M15"):
        frame.to_parquet(data / f"XAUUSD_{tf}.parquet")
    records = [{"r": 0.10}] * 60
    monkeypatch.setattr(shadow, "DATA", data)
    monkeypatch.setattr(shadow, "SHADOW", reports)
    monkeypatch.setattr(shadow, "STATE", reports / "state.json")
    monkeypatch.setattr(shadow, "_source", lambda: {"promotion_authority": authority})
    monkeypatch.setattr(shadow.core, "simulate", lambda *a, **k: records)
    state = shadow.run(datetime(2026, 8, 23, tzinfo=UTC))
    assert all(row["status"] == expected for row in state["sleeves"].values())
    assert all(row["n"] == 60 for row in state["sleeves"].values())


def test_missing_universal_certificate_no_longer_blocks_shadow_entry(
    tmp_path: Path, monkeypatch,
) -> None:
    """Shadow entry is not the live-capital gate (principal decision 2026-08-23): every declared
    candidate gets a real shadow attempt regardless of certificate status, so it can build a
    genuine track record. Live capital is unaffected -- promoter.py independently re-checks
    authorized_specs() at the moment of actual promotion (see test_promotion_lifecycle.py's
    test_candidate_without_original_ten_gate_certificate_is_blocked, which still enforces this)."""
    monkeypatch.setattr(shadow, "DESK", tmp_path)
    monkeypatch.setattr(shadow, "SHADOW", tmp_path / "reports")
    monkeypatch.setattr(shadow, "STATE", tmp_path / "reports" / "state.json")
    state = shadow.run(datetime(2026, 8, 23, tzinfo=UTC))
    assert state["configured_sleeves"] == len(shadow.CANDIDATES)
    assert state["gate_blocked_sleeves"] == 0
    assert not any(row.get("status") == "BLOCKED_UNIVERSAL_GATES"
                   for row in state["sleeves"].values())
