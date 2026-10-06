"""THE STRATEGY RUNNER MUST PRICE FILLS THE WAY THE DESK WOULD ACTUALLY GET THEM.

Two things are pinned here that a green backtest would never reveal on its own.

The FILL PRICE. The strategy signals on a close and the engine executes at the next open, so P&L
has to be struck at that open. Pricing it at the signal close books a price nobody could have got
and silently deletes gap risk from every trade. It is invisible on a synthetic frame where
open[i] == close[i-1] -- which is exactly how the first fixture was built, and why the correction
produced byte-identical output and proved nothing. The test below puts real gaps in.

The SELF-AUDIT. This strategy was built in response to a gold EA advertised at 5-10%/week, using a
module written to doubt that EA. Exempting our own trades from that same audit is the double
standard this desk keeps convicting other organs of, so the runner audits itself every run.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.run_ict_strategy as R  # noqa: E402

from libs.ict.strategy import ICTParams, schedule  # noqa: E402


def _bars(n: int = 4000, seed: int = 11, gaps: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 30000 * np.exp(np.cumsum(rng.normal(0, 0.0035, n)))
    if gaps:
        # A real tape gaps between bars. Without this, open[i] == close[i-1] and the entire
        # next-open fill path is untested by construction.
        open_ = np.concatenate(([30000.0], close[:-1] * (1 + rng.normal(0, 0.001, n - 1))))
    else:
        open_ = np.concatenate(([30000.0], close[:-1]))
    w = np.abs(rng.normal(0, 0.0035, n)) * close
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC"),
        "open": open_, "high": np.maximum(open_, close) + w,
        "low": np.minimum(open_, close) - w, "close": close, "volume": 1.0})


def _run(tmp: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / "scripts/run_ict_strategy.py"), *args],
                          capture_output=True, text=True, cwd=ROOT, timeout=600, check=False)


# ---------------------------------------------------------------------- pricing

def test_entry_is_priced_at_the_next_open_not_the_signal_close(tmp_path: Path) -> None:
    """THE TEST THAT THE FIRST FIXTURE COULD NOT MAKE. With genuine gaps between bars, pricing the
    fill at the signal close gives a measurably different -- and flattering -- answer."""
    df = _bars(gaps=True)
    _, taken = schedule(df, ICTParams())
    if len(taken) < 5:
        import pytest
        pytest.skip("too few setups in this sample")
    pnl_correct, _ = R.trade_pnl(df, taken, 0.0)

    # Recompute the way the earlier draft did: entry at the signal bar's CLOSE.
    open_, high, low, close = (df["open"].to_numpy(), df["high"].to_numpy(),
                               df["low"].to_numpy(), df["close"].to_numpy())
    naive = []
    for s in taken:
        if s.entry_i + 1 >= len(df):
            continue
        exit_px = float(close[-1])
        for j in range(s.entry_i + 1, len(df)):
            if s.direction > 0 and low[j] <= s.stop:
                exit_px = s.stop
                break
            if s.direction > 0 and high[j] >= s.target:
                exit_px = s.target
                break
            if s.direction < 0 and high[j] >= s.stop:
                exit_px = s.stop
                break
            if s.direction < 0 and low[j] <= s.target:
                exit_px = s.target
                break
        naive.append(s.direction * (exit_px - s.entry_price) / s.entry_price)
    assert not np.allclose(pnl_correct, np.asarray(naive)), (
        "the two pricings must differ on a gapping tape -- if they do not, the fixture has no "
        "gaps and this test is proving nothing")
    assert open_[taken[0].entry_i + 1] != close[taken[0].entry_i]


def test_a_signal_on_the_final_bar_is_never_counted() -> None:
    """It could not have been filled. Counting it books a trade that never existed."""
    df = _bars(n=600)
    _, taken = schedule(df, ICTParams())
    pnl, _sizes = R.trade_pnl(df, taken, 0.0)
    assert pnl.size == len([s for s in taken if s.entry_i + 1 < len(df)])


def test_costs_reduce_the_result(tmp_path: Path) -> None:
    """Gross of costs is a number about the detector; net of costs is a number about the desk."""
    df = _bars()
    _, taken = schedule(df, ICTParams())
    free, _ = R.trade_pnl(df, taken, 0.0)
    charged, _ = R.trade_pnl(df, taken, 0.00075)
    assert charged.sum() < free.sum()


# --------------------------------------------------------------------- end to end

def test_runner_reports_and_audits_itself(tmp_path: Path) -> None:
    p = tmp_path / "bars.csv"
    _bars().to_csv(p, index=False)
    r = _run(tmp_path, "--bars", str(p))
    assert r.returncode == 0, r.stderr
    assert "SELF-AUDIT" in r.stdout
    rep = json.loads((ROOT / "data/ict_strategy.json").read_text("utf-8"))
    assert rep["self_audit"]["verdict"] in {"NO-RISK-LOADING-FOUND", "SUSPECT", "UNDECIDABLE"}, (
        "fixed-fractional sizing must never audit as RISK-LOADED -- if it does, the sizing rule "
        "changed and the strategy became the thing it was built to be an answer to")


def test_a_random_walk_does_not_pay_after_costs(tmp_path: Path) -> None:
    """THE CONTROL. Noise plus fees must lose. A pattern strategy that prints money here is
    measuring its own arithmetic."""
    p = tmp_path / "bars.csv"
    _bars().to_csv(p, index=False)
    assert _run(tmp_path, "--bars", str(p)).returncode == 0
    rep = json.loads((ROOT / "data/ict_strategy.json").read_text("utf-8"))
    if rep.get("trades", 0) >= 10:
        assert rep["net_return_multiple"] < 1.05, (
            f"random walk returned x{rep['net_return_multiple']:.3f} net of costs")


def test_missing_bars_are_reported_not_synthesised(tmp_path: Path) -> None:
    r = _run(tmp_path, "--bars", str(tmp_path / "nope.csv"))
    assert r.returncode == 0
    assert "NO BARS" in r.stdout
    rep = json.loads((ROOT / "data/ict_strategy.json").read_text("utf-8"))
    assert "NOT synthesised" in rep["note"]


def test_too_few_trades_refuses_to_report_a_return(tmp_path: Path) -> None:
    """An observation count is not a sample size, and a return computed on two trades is a number
    with no content that will nonetheless get quoted."""
    p = tmp_path / "bars.csv"
    _bars(n=300).to_csv(p, index=False)
    assert _run(tmp_path, "--bars", str(p)).returncode == 0
    rep = json.loads((ROOT / "data/ict_strategy.json").read_text("utf-8"))
    if rep.get("trades", 0) < 2:
        assert rep["state"] == "TOO FEW TRADES"
        assert "net_return_multiple" not in rep
