"""Regression coverage for sparse ETH/BTC alignment in the pre-registered study."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.run_ethbtc_rotation_study as S  # noqa: E402

PREREG = ROOT / "docs/research/ETHBTC_ROTATION_PREREGISTRATION.md"


def _frame(timestamps: list[str], closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"timestamp": pd.to_datetime(timestamps, utc=True), "close": closes}
    )


def _run_without_arms(eth: pd.DataFrame, btc: pd.DataFrame) -> dict:
    """Run main while making any attempted strategy evaluation a test failure."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        out = root / "data/ethbtc_rotation_study.json"
        prereg = root / "docs/research/ETHBTC_ROTATION_PREREGISTRATION.md"
        with (
            patch.object(S, "ROOT", root),
            patch.object(S, "OUT", out),
            patch.object(S, "PREREG", prereg),
            patch.object(S, "_load", side_effect=[eth, btc]),
            patch.object(
                S,
                "_rotate",
                side_effect=AssertionError("an unmeasurable return series reached the grid"),
            ),
            patch.object(sys, "argv", ["run_ethbtc_rotation_study.py"]),
        ):
            assert S.main() == 0
            return json.loads(out.read_text("utf-8"))


def _assert_unmeasured_without_manufactured_results(rep: dict) -> None:
    assert rep["verdict"] == "UNMEASURED"
    assert rep["observed_return_intervals"] == 0
    assert rep["arms"] == []
    assert rep["best_arm"] == {}
    assert rep["buy_and_hold_log_return"] == {}
    assert rep["nominal_trials"] == 72
    assert rep["shared_budget"] == 16_632
    assert rep["kill_criteria_fired"] == [
        "K8 SAMPLE FLOOR: 0 trades < 100 -> UNMEASURED, not 'no edge'"
    ]
    assert "NOTHING IS SYNTHESISED" in rep["note"]
    assert "no strategy or control arm evaluated" in rep["stage_reached"]


def test_current_bars_with_no_preregistered_oos_overlap_are_unmeasured() -> None:
    current = _frame(["2026-08-15T00:00:00Z"], [100.0])
    rep = _run_without_arms(current, current)
    _assert_unmeasured_without_manufactured_results(rep)
    assert rep["input_bars"] == {"ETHUSDT": 1, "BTCUSDT": 1}
    assert rep["raw_aligned_bars"] == 0
    assert rep["bars"] == 0


def test_one_aligned_oos_close_cannot_be_presented_as_a_backtest() -> None:
    eth = _frame(["2021-01-01T00:00:00Z"], [1_000.0])
    btc = _frame(["2021-01-01T00:00:00Z"], [30_000.0])
    rep = _run_without_arms(eth, btc)
    _assert_unmeasured_without_manufactured_results(rep)
    assert rep["raw_aligned_bars"] == 1
    assert rep["bars"] == 1


def test_nonpositive_and_nonfinite_aligned_closes_are_not_treated_as_prices() -> None:
    timestamps = ["2021-01-01T00:00:00Z", "2021-01-02T00:00:00Z"]
    eth = _frame(timestamps, [0.0, np.nan])
    btc = _frame(timestamps, [30_000.0, 31_000.0])
    rep = _run_without_arms(eth, btc)
    _assert_unmeasured_without_manufactured_results(rep)
    assert rep["raw_aligned_bars"] == 2
    assert rep["bars"] == 0


def test_preregistered_budget_and_sample_floor_are_unchanged() -> None:
    doc = PREREG.read_text("utf-8")
    assert S.nominal_trials() == 72
    assert S.SHARED_BUDGET == 16_632
    assert S.MIN_TRADES == 100
    for token in ("K6", "K7", "K8", "16,632", "72"):
        assert token in doc
