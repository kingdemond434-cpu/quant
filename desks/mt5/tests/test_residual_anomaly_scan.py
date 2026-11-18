"""The residual anomaly scan (build check row 20): its residual never sees the future, a family's
position explains only the bars after its signal, and what it donates is what the candidate
compiler already compiles -- once.

Every bar is synthetic and every path is redirected into `tmp_path`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import residual_anomaly_scan as ras  # noqa: E402

#: Hypothesis-lane symbols in the broker registry: four USD pairs, one cross, two metals.
SYMS = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "XAUUSD", "XAGUSD")
N_BARS = 2_000


def _bars(rets: np.ndarray, start: float, index: pd.DatetimeIndex) -> pd.DataFrame:
    close = start * np.exp(np.cumsum(rets))
    rng = np.random.default_rng(int(abs(rets[:5].sum()) * 1e9) % 2**32)
    wig = np.abs(rng.normal(0, 0.0004, len(close))) * close
    opn = np.concatenate([[close[0]], close[:-1]])
    return pd.DataFrame({"open": opn, "high": np.maximum(opn, close) + wig,
                         "low": np.minimum(opn, close) - wig, "close": close,
                         "tick_volume": rng.integers(100, 1000, len(close)),
                         "spread": np.full(len(close), 10), "real_volume": 0}, index=index)


def _returns(seed: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    out = {s: rng.normal(0, 0.001, N_BARS) for s in SYMS}
    # A metals co-movement no factor names (two members: the class factor is dropped).
    common = rng.normal(0, 0.002, N_BARS)
    out["XAUUSD"] = out["XAUUSD"] + common
    out["XAGUSD"] = out["XAGUSD"] + common
    # A shared-USD-leg co-movement, which is known structure.
    usd = rng.normal(0, 0.0015, N_BARS)
    out["EURUSD"] = out["EURUSD"] + usd
    out["GBPUSD"] = out["GBPUSD"] + usd
    # AUDUSD's own residual reverts at lag 1.
    e = rng.normal(0, 0.001, N_BARS)
    out["AUDUSD"] = e - 0.45 * np.concatenate([[0.0], e[:-1]])
    return out


def _write(universe: Path, rets: dict[str, np.ndarray]) -> None:
    universe.mkdir(parents=True, exist_ok=True)
    idx = pd.date_range("2026-01-05", periods=N_BARS, freq="h", tz="UTC")
    for i, (s, r) in enumerate(rets.items()):
        _bars(r, 1.0 + i, idx).to_parquet(universe / f"{s}_H1.parquet")


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(ras, "REPORT", tmp_path / "reports" / "UNEXPLAINED_RESIDUALS.json")
    monkeypatch.setattr(ras, "DONATIONS", tmp_path / "data" / "intelligence" / "residual_scan")
    monkeypatch.setattr(ras, "SEEN", tmp_path / "data" / "residual_scan_seen.json")
    _write(tmp_path / "universe", _returns(7))
    return tmp_path


def test_the_residual_never_sees_a_later_bar(tmp_path: Path) -> None:
    """Rewrite every symbol's bars after CUT; no residual before CUT may move."""
    base = _returns(11)
    _write(tmp_path / "a", base)
    cut = 1_400
    rng = np.random.default_rng(99)
    altered = {s: np.concatenate([r[:cut], rng.normal(0, 0.004, N_BARS - cut)])
               for s, r in base.items()}
    _write(tmp_path / "b", altered)
    fams, _ = ras.regressor_families()
    za, _ = ras.scan(SYMS, budget_s=600, universe_dir=tmp_path / "a", families=fams)
    zb, _ = ras.scan(SYMS, budget_s=600, universe_dir=tmp_path / "b", families=fams)
    assert set(za) == set(SYMS)
    for s in SYMS:
        a, b = za[s].to_numpy()[:cut], zb[s].to_numpy()[:cut]
        assert np.isfinite(a).sum() > 600, s
        np.testing.assert_allclose(a, b, rtol=0, atol=1e-12, equal_nan=True, err_msg=s)
        # and the future really was different, so the check had something to catch
        assert not np.allclose(za[s].to_numpy()[cut + 5:], zb[s].to_numpy()[cut + 5:],
                               equal_nan=True)


def test_a_signal_holds_only_the_bars_after_it() -> None:
    idx = pd.date_range("2026-01-05", periods=10, freq="h", tz="UTC")
    df = pd.DataFrame({"close": np.ones(10)}, index=idx)

    class Sig:
        def __init__(self, i: int, side: int, ttl: int) -> None:
            self.time, self.side, self.ttl_bars = idx[i], side, ttl

    e = ras.family_exposure(df, lambda _df: [Sig(2, 1, 3), Sig(8, -1, 5)])
    assert e.tolist() == [0, 0, 0, 1, 1, 1, 0, 0, 0, -1]


def test_patterns_are_donated_in_the_compilers_shapes_once(desk: Path) -> None:
    import miner_candidate_compiler as mcc
    report, rows, seen = ras.build(600, universe_dir=desk / "universe", symbols=list(SYMS))
    assert report["symbols_measured"] == len(SYMS)
    assert report["trials"] > 0 and report["sizing_reads"].startswith("none")

    hyp = [r for r in rows if r["kind"] == "hypothesis"]
    assert any(r["symbols"] == ["AUDUSD"] and r["family"] == "mean_reversion_rsi" for r in hyp)
    pair = [r for r in rows if r["kind"] == "anomaly"]
    assert {(r["symbol"], r["against"]) for r in pair} == {("XAGUSD", "XAUUSD")} or \
        {(r["symbol"], r["against"]) for r in pair} == {("XAUUSD", "XAGUSD")}
    # The shared-USD-leg pair is measured, reported, and never donated.
    usd = [e for e in report["eligible_patterns"] if e["pattern"] == "comovement"
           and {e["symbol"], e["against"]} == {"EURUSD", "GBPUSD"}]
    assert usd and usd[0]["disposition"].startswith("REPORTED: shared currency leg")

    universe = set(SYMS)
    for r in hyp:
        _, disp = mcc.compile_row(f"{ras.SEAT}", r, universe)
        assert disp == "STRUCTURED_HYPOTHESIS", r
    for r in pair:
        cands, disp = mcc.compile_row(f"{ras.SEAT}", r, universe)
        assert disp == "STRUCTURED_CROSS_ASSET_RESIDUAL" and cands, r

    ras.write(report, rows, seen)
    files = list((desk / "data" / "intelligence" / "residual_scan").glob("discoveries_*.json"))
    assert len(files) == 1
    assert json.loads(files[0].read_text("utf-8"))["discoveries"] == rows
    assert json.loads((desk / "reports" / "UNEXPLAINED_RESIDUALS.json").read_text("utf-8"))[
        "cells_donated"] == len(rows)

    again, rows2, _ = ras.build(600, universe_dir=desk / "universe", symbols=list(SYMS))
    assert rows2 == []
    assert any(e["disposition"].startswith("SEEN") for e in again["eligible_patterns"])


def test_a_short_series_is_unmeasured_not_clean(tmp_path: Path) -> None:
    uni = tmp_path / "u"
    _write(uni, _returns(3))
    idx = pd.date_range("2026-01-05", periods=300, freq="h", tz="UTC")
    _bars(np.zeros(300) + 1e-4, 1.0, idx).to_parquet(uni / "EURUSD_H1.parquet")
    _zs, notes = ras.scan(SYMS, budget_s=600, universe_dir=uni, families={})
    assert notes["EURUSD"]["state"].startswith("UNMEASURED")
