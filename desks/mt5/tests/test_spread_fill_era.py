"""The spread column's leading fill era is undefined to a formula, and nothing after it is
(box read 2026-11-10, input_column_fill_boundary over 102 M30/H1 files).

Pinned: one constant, yearly constants and several constants are all one era; the era ends at
the first stretch of quotes longer than five trading days, so a held run years later (EURSGD,
XAUUSD 2024-26) never moves it and is published as SUSPECT_CONSTANT_RUN, unmasked; a column held
from first bar to last is left as it is; tick_volume is never touched."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK / "scripts"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import alpha_grammar as ag  # noqa: E402

R = 120                         # H1: five trading days


def _frame(spread: np.ndarray, start: str = "2018-01-01") -> pd.DataFrame:
    n = spread.size
    idx = pd.date_range(start, periods=n, freq="1h", tz="UTC")
    rng = np.random.default_rng(3)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 1e-3, n)))
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close, "tick_volume": np.full(n, 7.0),
                         "spread": spread.astype(float)}, index=idx)


def _quotes(n: int, seed: int = 1) -> np.ndarray:
    return np.random.default_rng(seed).integers(5, 40, n).astype(float)


def test_one_constant_era_is_masked_and_the_quotes_after_it_are_kept() -> None:
    spread = np.concatenate([np.full(900, 50.0), _quotes(2000)])
    assert ag.fill_run_bars(_frame(spread).index) == R
    assert ag.leading_fill_end(spread, R) == 900
    frames = ag.terminal_frames(_frame(spread), raw=_frame(spread))
    assert frames["spread"].iloc[:900].isna().all()
    assert frames["spread"].iloc[900:].notna().all()
    assert (frames["activity"] == 7.0).all()                     # tick_volume untouched


def test_yearly_and_several_constants_with_short_blips_are_one_era() -> None:
    era = np.concatenate([np.full(300, 130.0), np.full(260, 120.0), _quotes(30, 2),
                          np.full(1155, 100.0), np.full(400, 200.0), np.full(500, 130.0)])
    spread = np.concatenate([era, _quotes(3000)])
    assert ag.leading_fill_end(spread, R) == era.size


def test_a_held_run_years_later_never_moves_the_era_and_is_published_unmasked() -> None:
    late = np.full(326, 2.0)
    spread = np.concatenate([np.full(900, 50.0), _quotes(20000), late, _quotes(500, 4)])
    raw = _frame(spread)
    assert ag.leading_fill_end(spread, R) == 900
    rep = ag.input_fill_report(raw)
    assert rep["fill_end_index"] == 900 and rep["fill_end_time"] == str(raw.index[900])
    (run,) = rep["suspect_constant_runs"]
    assert run["kind"] == "SUSPECT_CONSTANT_RUN" and run["bars"] == 326 and run["value"] == 2.0
    assert run["start"] == str(raw.index[20900]) and run["end"] == str(raw.index[21225])
    masked = ag.mask_leading_fill(raw["spread"])
    assert masked.iloc[20900:21226].eq(2.0).all()              # judged neither way


def test_quotes_first_and_a_column_held_throughout_are_left_as_they_are() -> None:
    quotes_first = np.concatenate([_quotes(500), np.full(900, 50.0), _quotes(500, 5)])
    assert ag.leading_fill_end(quotes_first, R) == 0
    held = np.full(1000, 10.0)
    assert ag.leading_fill_end(held, R) == 1000
    assert ag.mask_leading_fill(_frame(held)["spread"]).eq(10.0).all()
    assert ag.input_fill_report(_frame(held))["whole_column_held"] is True


def test_the_census_counts_what_the_rule_holds_and_releases(tmp_path: Path) -> None:
    import input_fill_census as C
    surv = {
        "a": {"shadow_spec": {"family": "formula", "symbol": "AUDSGD",
                              "params": {"expr": ["zscore", "spread", 24]}}},
        "b": {"shadow_spec": {"family": "formula", "symbol": "EURUSD",
                              "params": {"expr": "neg(corr(open, activity, 12))"}}},
        "c": {"shadow_spec": {"family": "formula", "symbol": "EURUSD",
                              "params": {"expr": ["delta", "close", 2]}}},
        "d": {"shadow_spec": {"family": "carry", "symbol": "EURUSD", "params": {}}},
    }
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json").write_text(
        json.dumps({"survivors": surv}), encoding="utf-8")
    reads = C.formula_reads(tmp_path)
    assert reads["formula_certificates"] == 3 and reads["reading_spread"] == 1
    assert reads["reading_activity_or_flow_only_released"] == 1
    assert reads["spread_symbols"] == {"AUDSGD": 1}
    assert C.publish(tmp_path, max_age_h=6.0, now=0.0) == "WRITTEN"
    doc = json.loads((tmp_path / "reports" / "INPUT_FILL_CENSUS.json").read_text("utf-8"))
    assert doc["files"] == 0 and doc["n_suspect_constant_runs"] == 0
    st = (tmp_path / "reports" / "INPUT_FILL_CENSUS.json").stat().st_mtime
    assert C.publish(tmp_path, max_age_h=6.0, now=st + 60) == "FRESH"
