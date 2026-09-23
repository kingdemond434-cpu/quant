"""The moat miner finds a planted tick-level effect and refuses noise and tautologies.

The tape is the desk's only proprietary dataset and it produced no candidates at all until now,
so the first question about this miner is not "does it run" but "does it propose things that are
there and decline things that are not". Both halves matter and the second one more: a proposer
that emits on noise turns the desk's scarcest resource -- gauntlet compute -- into a random
number generator, and the conversion funnel is already the binding constraint.

The third test is the one that would have been easiest to get wrong. Conditioning a bar's return
on that same bar's tick statistics is a tautology: a violent bar has a wide spread and a high
tick count BECAUSE it moved. It would manufacture a huge, entirely fake effect, and it would look
like success.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

DESK = pathlib.Path(__file__).resolve().parents[1]


def _module(tmp_path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(
        "moat_miner_under_test", DESK / "research" / "moat_miner.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    m.BASE = tmp_path
    m.TICKS = tmp_path / "data" / "tape" / "ticks"
    m.UNIVERSE = tmp_path / "data" / "universe"
    m.OUT = tmp_path / "data" / "hypotheses" / "moat_candidates.json"
    m.TICKS.mkdir(parents=True)
    m.UNIVERSE.mkdir(parents=True)
    return m


def _write_tape(m, symbol: str, hours: int, spread_by_hour, rng) -> pd.DatetimeIndex:
    """One tick file per day, 60 ticks an hour, with a controllable per-hour spread."""
    start = pd.Timestamp("2026-06-01", tz="UTC")
    idx = pd.date_range(start, periods=hours, freq="h")
    rows = []
    for i, ts in enumerate(idx):
        sp = float(spread_by_hour[i])
        mids = 100.0 + np.cumsum(rng.normal(0, 0.01, 60))
        t = pd.date_range(ts, periods=60, freq="min")
        rows.append(pd.DataFrame({"ts": t, "bid": mids - sp / 2, "ask": mids + sp / 2}))
    frame = pd.concat(rows, ignore_index=True)
    d = m.TICKS / symbol
    d.mkdir(parents=True, exist_ok=True)
    for day, chunk in frame.groupby(frame["ts"].dt.date):
        chunk.to_parquet(d / f"{day.isoformat()}.parquet", index=False)
    return idx


def _write_bars(m, symbol: str, idx, closes) -> None:
    pd.DataFrame({"time": idx, "close": closes}).to_parquet(
        m.UNIVERSE / f"{symbol}_H1.parquet", index=False)


def test_it_finds_a_planted_spread_regime_effect(tmp_path) -> None:
    """Wide spread this hour -> the NEXT hour drifts up. A real, if crude, microstructure claim."""
    rng = np.random.default_rng(7)
    n = 1400
    m = _module(tmp_path)
    # Spread alternates between two regimes in long blocks so terciles separate cleanly.
    wide = rng.random(n) < 0.4
    spread = np.where(wide, 0.40, 0.05) + rng.normal(0, 0.004, n)
    idx = _write_tape(m, "TESTFX", n, spread, rng)
    # The NEXT bar's return is positive after a wide-spread bar. Built by construction so the
    # effect is in the data rather than in the test's hope.
    nxt = np.zeros(n)
    nxt[1:] = np.where(wide[:-1], 0.0025, -0.0025) + rng.normal(0, 0.002, n - 1)
    closes = 100.0 * np.exp(np.cumsum(nxt))
    _write_bars(m, "TESTFX", idx, closes)

    rows = m.scan_symbol("TESTFX")

    spread_rows = [r for r in rows if r["params"]["conditioning"] == "spread_z"]
    assert spread_rows, f"the planted spread effect was not proposed; got {rows}"
    r = spread_rows[0]
    assert r["family"] == "liquidity_regime"
    assert r["params"]["side"] == "LONG", r
    assert r["symbol"] == "TESTFX" and r["mechanism_status"] == "NAMED"
    assert r["source"] == "moat_miner:spread_z"
    # In and out of sample must agree in sign -- that is the whole admission rule.
    assert r["exp_r"] * r["oos_separation_sd"] > 0, r


def test_it_declines_pure_noise(tmp_path) -> None:
    """A proposer that emits on noise spends the desk's scarcest resource on nothing."""
    rng = np.random.default_rng(11)
    n = 1400
    m = _module(tmp_path)
    spread = 0.2 + rng.normal(0, 0.05, n)
    idx = _write_tape(m, "NOISE", n, spread, rng)
    closes = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    _write_bars(m, "NOISE", idx, closes)

    rows = m.scan_symbol("NOISE")

    assert rows == [], f"noise produced {len(rows)} candidate(s): {rows}"


def test_the_return_is_the_next_bar_never_this_one(tmp_path) -> None:
    """THE TAUTOLOGY GUARD. A bar's own tick stats cannot be used to 'predict' its own return.

    Built so the SAME bar's return is perfectly explained by the spread and the next bar's is
    pure noise. A miner reading the current bar's return would find an enormous effect here; one
    reading the next bar's finds nothing, which is the correct answer.
    """
    rng = np.random.default_rng(23)
    n = 1400
    m = _module(tmp_path)
    wide = rng.random(n) < 0.4
    spread = np.where(wide, 0.40, 0.05) + rng.normal(0, 0.004, n)
    idx = _write_tape(m, "TAUT", n, spread, rng)
    # This bar's return is +0.5% whenever THIS bar's spread is wide; the next bar is noise.
    same_bar = np.where(wide, 0.005, -0.005)
    closes = 100.0 * np.exp(np.cumsum(same_bar))
    _write_bars(m, "TAUT", idx, closes)

    fwd = m._forward_returns("TAUT", idx)
    assert fwd is not None
    # The forward series is the NEXT bar's return: it must be the shifted one, not the aligned one.
    px = pd.Series(closes, index=idx)
    expected = px.pct_change().shift(-1).reindex(fwd.index).dropna()
    assert np.allclose(fwd.values, expected.loc[fwd.index].values), (
        "_forward_returns is not returning the NEXT bar's return")


def test_a_symbol_with_no_bars_is_skipped_not_guessed(tmp_path) -> None:
    rng = np.random.default_rng(3)
    m = _module(tmp_path)
    _write_tape(m, "NOBARS", 600, 0.2 + rng.normal(0, 0.05, 600), rng)
    assert m.scan_symbol("NOBARS") == []


def test_a_short_tape_proposes_nothing(tmp_path) -> None:
    """Below MIN_BARS a tercile split is a handful of points wearing a percentile."""
    rng = np.random.default_rng(5)
    m = _module(tmp_path)
    idx = _write_tape(m, "SHORT", 100, 0.2 + rng.normal(0, 0.05, 100), rng)
    _write_bars(m, "SHORT", idx, 100.0 * np.exp(np.cumsum(rng.normal(0, 0.002, 100))))
    assert m.scan_symbol("SHORT") == []


def test_the_output_is_wired_into_the_merge() -> None:
    """A producer nobody reads is this desk's most repeated defect. Assert the consumer knows."""
    src = (DESK / "research" / "merge_hypotheses.py").read_text("utf-8")
    assert '("moat_candidates.json", "hypotheses")' in src, (
        "moat_candidates.json is not in merge_hypotheses.SOURCES -- the miner would run every "
        "hour and its rows would reach no docket")
    hourly = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert "moat_miner" in hourly, "the moat miner is on no schedule"
    assert hourly.index("moat_miner") < hourly.index('_costed("mine"'), (
        "the moat miner must run BEFORE the compile leg that consumes its rows")
