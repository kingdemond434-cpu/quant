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


def _canon_row(symbol: str) -> dict:
    return {"shadow_spec": {"symbol": symbol, "timeframe": "m5",
                            "family": "anti_donchian_breakout", "session": "all",
                            "stop_atr": 1.0, "target_atr": 1.5, "max_hold": 9}}


def test_certified_recipes_admit_gold_only(monkeypatch) -> None:
    """#110 audit MF2b: the promoter writes scalp sleeves as XAUUSD, so a recipe on another
    symbol must not reach it through this lane."""
    monkeypatch.setattr(scalp_shadow, "_admission_canon", lambda _d: ({}, None))
    monkeypatch.setattr(scalp_shadow, "_scalp_certificates", lambda _u: {
        "scalp.gold_recipe": _canon_row("XAUUSD"), "scalp.fx_recipe": _canon_row("EURUSD")})
    monkeypatch.setattr(scalp_shadow, "CANDIDATES", {})
    got = scalp_shadow.certified_recipes()
    assert set(got) == {"scalp.gold_recipe"}
    assert got["scalp.gold_recipe"][:2] == ("XAUUSD", "M5")


def test_a_canon_recipe_without_a_prior_clock_starts_now_not_at_shadow_start(
    tmp_path: Path, monkeypatch,
) -> None:
    """#110 audit MF2: a canon recipe was selected on bars up to its certificate; stamping it
    with SHADOW_START would count that window as forward on the next pass."""
    data, shadow = tmp_path / "data", tmp_path / "shadow"
    data.mkdir()
    shadow.mkdir()
    index = pd.date_range("2026-10-01", periods=4, freq="5min", tz="UTC")
    pd.DataFrame({"open": np.ones(4), "high": np.ones(4), "low": np.ones(4),
                  "close": np.ones(4)}, index=index).to_parquet(data / "XAUUSD_M5.parquet")
    (data / "XAUUSD_scalp_source.json").write_text('{"promotion_authority": true}')
    state = shadow / "scalp_shadow_state.json"
    choice = families.Choice("anti_donchian_breakout", "all", 1.0, 1.5, 9)
    monkeypatch.setattr(scalp_shadow, "DATA", data)
    monkeypatch.setattr(scalp_shadow, "SHADOW", shadow)
    monkeypatch.setattr(scalp_shadow, "STATE", state)
    monkeypatch.setattr(scalp_shadow, "CANDIDATES", {})
    monkeypatch.setattr(scalp_shadow, "certified_recipes",
                        lambda: {"scalp.recipe": ("XAUUSD", "M5", choice)})
    monkeypatch.setattr(scalp_shadow, "_broker_offset_h", lambda: 0.0)
    monkeypatch.setattr(scalp_shadow, "_trading_lag_hours", lambda *_: 0.0)
    monkeypatch.setattr(scalp_shadow.families, "_base_signals", lambda df: {
        "anti_donchian_breakout": np.zeros(len(df), dtype=np.int8)})
    monkeypatch.setattr(scalp_shadow.families, "_session_mask",
                        lambda index, _s: np.ones(len(index), dtype=bool))
    monkeypatch.setattr(scalp_shadow.families, "_cfg", lambda *_: object())
    monkeypatch.setattr(scalp_shadow.core, "simulate", lambda *_args, **_kwargs: [
        {"entry_time": "2026-10-01T00:05:00+00:00", "r": 0.4}])
    now = datetime(2026, 10, 30, 12, tzinfo=UTC)
    row = scalp_shadow.run(now)["sleeves"]["scalp.recipe"]
    assert row["forward_start"] == now.isoformat(timespec="seconds")
    assert row["n"] == 0
