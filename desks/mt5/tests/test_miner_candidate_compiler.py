from __future__ import annotations

import numpy as np
import pandas as pd

from research import miner_candidate_compiler as compiler
from research import orthogonal_sweep
from mt5desk.families_orthogonal import family_calendar_month


UNIVERSE = {"EURUSD", "GBPUSD", "USDJPY", "EURGBP", "XAUUSD", "AUDNZD"}


def test_currency_evidence_expands_only_through_live_registry() -> None:
    assert compiler.resolve_symbols({"currency": "GBP"}, UNIVERSE) == [
        "EURGBP", "GBPUSD"
    ]


def test_structured_miners_compile_to_source_faithful_candidates() -> None:
    event, event_status = compiler.compile_row(
        "forexfactory",
        {"type": "calendar_event", "currency": "USD", "title": "CPI"},
        UNIVERSE,
    )
    cot, cot_status = compiler.compile_row(
        "cot", {"type": "positioning", "symbol": "AUDNZD"}, UNIVERSE,
    )
    seasonal, seasonal_status = compiler.compile_row(
        "seasonality", {"month": 8, "direction": "down", "symbols": ["XAUUSD"]},
        UNIVERSE,
    )

    assert event_status == "STRUCTURED_EVENT"
    assert {row["family"] for row in event} == {"event_reaction"}
    assert {row["symbol"] for row in event} == {"EURUSD", "GBPUSD", "USDJPY"}
    assert cot_status == "STRUCTURED_COT"
    assert cot[0]["family"] == "cot_positioning"
    assert seasonal_status == "STRUCTURED_CALENDAR"
    assert seasonal[0]["params"] == {"active_month": 8, "side_bias": -1}


def test_vague_miner_claim_routes_to_deepening_not_a_guessed_family() -> None:
    rows, disposition = compiler.compile_row(
        "youtube", {"symbols": ["XAUUSD"], "patterns": ["scalping"]}, UNIVERSE,
    )
    assert rows == []
    assert disposition == "NEEDS_EXACT_RULE_EXTRACTION"


def test_calendar_month_family_uses_the_mined_month_and_direction() -> None:
    idx = pd.date_range("2024-01-01", "2025-12-31 23:00", freq="h", tz="UTC")
    close = 100 + np.arange(len(idx)) * 0.001
    frame = pd.DataFrame({
        "open": close,
        "high": close + 0.1,
        "low": close - 0.1,
        "close": close,
    }, index=idx)

    signals = family_calendar_month(frame, active_month=8, side_bias=-1)

    assert len(signals) >= 50
    assert all(signal.time.month == 8 and signal.side == -1 for signal in signals)


def test_cot_candidate_reader_uses_owned_history_weekly(tmp_path, monkeypatch) -> None:
    desk = tmp_path / "desks" / "mt5"
    (tmp_path / "data").mkdir()
    idx = pd.date_range("2020-01-01", periods=900, freq="d", tz="UTC")
    pd.DataFrame({"XAUUSD": np.sin(np.arange(len(idx)) / 40)}, index=idx).to_parquet(
        tmp_path / "data" / "cot_zcache.parquet"
    )
    monkeypatch.setattr(orthogonal_sweep, "BASE", desk)
    orthogonal_sweep._cot_frame.cache_clear()

    cot = orthogonal_sweep._cot_frame("XAUUSD")

    assert list(cot) == ["net"]
    assert 120 <= len(cot) <= 140
    assert cot.index.dayofweek.nunique() == 1
