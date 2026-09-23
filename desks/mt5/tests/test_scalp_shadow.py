from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from desks.mt5.research import scalp_family_expansion as families
from desks.mt5.research import scalp_shadow


def test_shadow_replay_preserves_frozen_clock_and_records_first_trade(
    tmp_path: Path, monkeypatch,
) -> None:
    data, shadow = tmp_path / "data", tmp_path / "shadow"
    data.mkdir()
    shadow.mkdir()
    index = pd.date_range("2026-08-24", periods=4, freq="5min", tz="UTC")
    pd.DataFrame({"open": np.ones(4), "high": np.ones(4), "low": np.ones(4),
                  "close": np.ones(4)}, index=index).to_parquet(data / "XAUUSD_M5.parquet")
    (data / "XAUUSD_scalp_source.json").write_text('{"promotion_authority": true}')
    old_start = "2026-08-23T00:00:00+00:00"
    state = shadow / "scalp_shadow_state.json"
    state.write_text(json.dumps({"sleeves": {"candidate": {"forward_start": old_start}}}))

    choice = families.Choice("anti_donchian_breakout", "all", 1.0, 1.5, 9)
    monkeypatch.setattr(scalp_shadow, "DATA", data)
    monkeypatch.setattr(scalp_shadow, "SHADOW", shadow)
    monkeypatch.setattr(scalp_shadow, "STATE", state)
    monkeypatch.setattr(scalp_shadow, "CANDIDATES", {"candidate": ("M5", choice)})
    monkeypatch.setattr(scalp_shadow, "_broker_offset_h", lambda: 0.0)
    monkeypatch.setattr(scalp_shadow, "_trading_lag_hours", lambda *_: 0.0)
    monkeypatch.setattr(scalp_shadow.families, "_base_signals", lambda df: {
        "anti_donchian_breakout": np.zeros(len(df), dtype=np.int8)})
    monkeypatch.setattr(scalp_shadow.families, "_session_mask", lambda index, _s: np.ones(len(index), dtype=bool))
    monkeypatch.setattr(scalp_shadow.families, "_cfg", lambda *_: object())
    monkeypatch.setattr(scalp_shadow.core, "simulate", lambda *_args, **_kwargs: [
        {"entry_time": "2026-08-24T00:05:00+00:00", "r": 0.4}])

    result = scalp_shadow.run(datetime(2026, 8, 24, 1, tzinfo=UTC))

    row = result["sleeves"]["candidate"]
    assert row["forward_start"] == old_start
    assert row["first_trade_at"] == "2026-08-24T00:05:00+00:00"
