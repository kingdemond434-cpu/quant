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


# ------------------------------------------------------- the ledger is a record (2026-11-11)
# immutable_evaluator BREACH on ledger_xau_m5_anti_momentum_ny.json: the clock re-simulated its
# whole history every pass and rewrote the file, so a sealed prefix stopped hashing.

def _row(opened: str, closed: str, r: float, phase: str = "forward") -> dict:
    return {"opened_at": opened, "closed_at": closed, "direction": 1, "depth": 1, "r": r,
            "risk_allocated_r": 1.0, "phase": phase}


def test_recorded_trades_stand_when_the_replay_disagrees() -> None:
    prior = [_row("2026-11-01T14:00:00+00:00", "2026-11-01T14:30:00+00:00", 0.5),
             _row("2026-11-02T14:00:00+00:00", "2026-11-02T14:30:00+00:00", -1.0)]
    replay = [_row("2026-11-01T14:00:00+00:00", "2026-11-01T14:30:00+00:00", 0.47),  # moved
              _row("2026-11-02T14:00:00+00:00", "2026-11-02T14:30:00+00:00", -1.0),
              _row("2026-11-03T14:00:00+00:00", "2026-11-03T14:30:00+00:00", 1.5),   # new, closed
              _row("2026-11-04T14:00:00+00:00", "2026-11-04T14:45:00+00:00", 0.2)]   # cut off
    merged, drift = scalp_shadow.append_only(prior, replay,
                                             pd.Timestamp("2026-11-04T14:45:00+00:00"))
    assert merged[:2] == prior
    assert [r["opened_at"] for r in merged[2:]] == ["2026-11-03T14:00:00+00:00"]
    assert drift["n_differ"] == 1 and drift["first_differ"].startswith("2026-11-01")
    assert drift["appended"] == 1 and drift["n_missing"] == 0


def test_a_recorded_trade_the_replay_lost_is_kept_and_counted() -> None:
    prior = [_row("2026-11-01T14:00:00+00:00", "2026-11-01T14:30:00+00:00", 0.5)]
    merged, drift = scalp_shadow.append_only(prior, [], pd.Timestamp("2026-11-05T00:00:00Z"))
    assert merged == prior and drift["n_missing"] == 1


def _run_fixture(tmp_path: Path, monkeypatch, replay: list[dict]) -> Path:
    data, shadow = tmp_path / "data", tmp_path / "shadow"
    data.mkdir()
    shadow.mkdir()
    index = pd.date_range("2026-11-01", periods=8, freq="1D", tz="UTC")
    pd.DataFrame({"open": np.ones(8), "high": np.ones(8), "low": np.ones(8),
                  "close": np.ones(8)}, index=index).to_parquet(data / "XAUUSD_M5.parquet")
    (data / "XAUUSD_scalp_source.json").write_text('{"promotion_authority": true}')
    state = shadow / "scalp_shadow_state.json"
    state.write_text(json.dumps({"sleeves": {"candidate": {
        "forward_start": "2026-08-23T00:00:00+00:00"}}}))
    choice = families.Choice("anti_donchian_breakout", "all", 1.0, 1.5, 9)
    monkeypatch.setattr(scalp_shadow, "DATA", data)
    monkeypatch.setattr(scalp_shadow, "SHADOW", shadow)
    monkeypatch.setattr(scalp_shadow, "STATE", state)
    monkeypatch.setattr(scalp_shadow, "CANDIDATES", {"candidate": ("M5", choice)})
    monkeypatch.setattr(scalp_shadow, "certified_recipes", lambda: {})
    monkeypatch.setattr(scalp_shadow, "_broker_offset_h", lambda: 0.0)
    monkeypatch.setattr(scalp_shadow, "_trading_lag_hours", lambda *_: 0.0)
    monkeypatch.setattr(scalp_shadow.families, "_base_signals", lambda df: {
        "anti_donchian_breakout": np.zeros(len(df), dtype=np.int8)})
    monkeypatch.setattr(scalp_shadow.families, "_session_mask",
                        lambda index, _s: np.ones(len(index), dtype=bool))
    monkeypatch.setattr(scalp_shadow.families, "_cfg", lambda *_: object())
    monkeypatch.setattr(scalp_shadow.core, "simulate", lambda *_a, **_k: [dict(r) for r in replay])
    return shadow / "ledger_candidate.json"


def test_the_clock_never_rewrites_a_written_trade(tmp_path: Path, monkeypatch) -> None:
    first = [{k: v for k, v in _row("2026-11-01T14:00:00+00:00",
                                    "2026-11-02T00:00:00+00:00", 0.5).items() if k != "phase"}]
    ledger = _run_fixture(tmp_path, monkeypatch, first)
    scalp_shadow.run(datetime(2026, 11, 8, 12, tzinfo=UTC))
    written = ledger.read_bytes()
    moved = [dict(first[0], r=0.31),
             {k: v for k, v in _row("2026-11-03T14:00:00+00:00",
                                    "2026-11-04T00:00:00+00:00", 1.5).items() if k != "phase"}]
    monkeypatch.setattr(scalp_shadow.core, "simulate", lambda *_a, **_k: [dict(r) for r in moved])
    row = scalp_shadow.run(datetime(2026, 11, 8, 13, tzinfo=UTC))["sleeves"]["candidate"]
    rows = json.loads(ledger.read_text())
    assert rows[0] == json.loads(written)[0] and rows[0]["r"] == 0.5
    assert len(rows) == 2 and rows[1]["r"] == 1.5
    assert row["n"] == 2 and row["replay_drift"]["n_differ"] == 1
    assert row["expectancy_r"] == 1.0


def test_an_unreadable_ledger_is_never_overwritten(tmp_path: Path, monkeypatch) -> None:
    ledger = _run_fixture(tmp_path, monkeypatch, [])
    ledger.write_text("{torn")
    row = scalp_shadow.run(datetime(2026, 11, 8, 12, tzinfo=UTC))["sleeves"]["candidate"]
    assert row["status"] == "LEDGER_UNREADABLE"
    assert ledger.read_text() == "{torn"
