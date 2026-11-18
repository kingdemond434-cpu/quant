"""TDA fragility state: landscape norms are right on a known diagram, the H0 fallback matches
Rips semantics, and no row reads a later bar (row 119 of the 2026-11-18 build check)."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import state_conditioner as sc  # noqa: E402
import tda_state as T  # noqa: E402

from libs.research.adapters import ripser as adapter  # noqa: E402

SYMS = ("EURUSD", "USDJPY", "GBPUSD", "XAUUSD")


def test_landscape_of_one_bar_is_its_tent() -> None:
    l1, l2 = T.landscape_norms(np.asarray([[0.0, 2.0]]), grid=2001)
    assert abs(l1 - 1.0) < 1e-3                       # triangle: base 2, height 1
    assert abs(l2 - np.sqrt(2.0 / 3.0)) < 1e-3
    assert T.landscape_norms(np.zeros((0, 2))) == (0.0, 0.0)
    assert T.landscape_norms(np.asarray([[0.0, np.inf]])) == (0.0, 0.0)


def test_h0_without_ripser_is_the_spanning_tree(monkeypatch) -> None:
    monkeypatch.setattr(adapter.A, "library", lambda name: None)
    dg, engine = adapter.diagrams(np.asarray([[0.0], [1.0], [3.0]]), maxdim=1)
    assert engine == "scipy_mst_h0"
    finite = sorted(float(d) for d in dg[0][:, 1] if np.isfinite(d))
    assert finite == [1.0, 2.0] and np.isinf(dg[0][:, 1]).sum() == 1
    assert dg[1].shape == (0, 2)                       # H1 absent, never approximated


def _write_bars(root: Path, n: int, seed: int, shock_at: int | None = None) -> pd.DatetimeIndex:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-06-01", periods=n, freq="h", tz="UTC")
    root.mkdir(parents=True, exist_ok=True)
    for k, s in enumerate(SYMS):
        r = rng.normal(0, 1e-3 * (k + 1), n)
        if shock_at is not None:     # its own generator, so the clean prefix is identical
            r[shock_at:] += np.random.default_rng(k).normal(0, 0.05, n - shock_at)
        pd.DataFrame({"close": 100 * np.exp(np.cumsum(r))}, index=idx).to_parquet(
            root / f"{s}_H1.parquet")
    return idx


def test_no_row_reads_a_later_bar(tmp_path: Path) -> None:
    n, cut = 800, 700
    _write_bars(tmp_path / "a", n, seed=5)
    _write_bars(tmp_path / "b", n, seed=5, shock_at=cut)    # identical up to cut, wild after
    sa = T.scaled_returns(T.load_returns(SYMS, tmp_path / "a"))
    sb = T.scaled_returns(T.load_returns(SYMS, tmp_path / "b"))
    pos = list(range(len(sa) - 300, len(sa)))
    ra, rb = T.rows_for(sa, pos), T.rows_for(sb, pos)
    last_clean = sa.index.get_loc(sa.index[sa.index < pd.Timestamp("2026-06-01", tz="UTC")
                                           + pd.Timedelta(hours=cut)][-1])
    k = last_clean - pos[0]
    assert k > 50
    for a, b in zip(ra[:k], rb[:k], strict=True):
        assert a == b
    assert ra[k + 5]["h0_l1"] != rb[k + 5]["h0_l1"]
    # stamped at the TRUE UTC close of the broker-labelled bar
    bar = datetime.fromisoformat(ra[0]["broker_bar"])
    assert datetime.fromisoformat(ra[0]["available_time"]) == sc.broker_to_utc(
        bar + timedelta(hours=1))


def test_a_pass_publishes_and_is_incremental(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(T, "MIN_ROWS_TO_MINT", 10 ** 9)       # this test never donates
    monkeypatch.setattr(T, "BASKET", SYMS)
    idx = _write_bars(tmp_path / "bars", 700, seed=9)
    now = sc.broker_to_utc(idx[-1].tz_localize(None).to_pydatetime() + timedelta(minutes=30))
    rep = tmp_path / "TDA_STATE.json"
    kw: dict[str, Any] = {"bars": tmp_path / "bars", "series_root": tmp_path / "series",
                          "state_path": tmp_path / "s.json", "report": rep, "budget_s": 60}
    doc = T.run(now=now, **kw)
    assert doc["verdict"] == "MEASURED" and doc["new_rows"] > 0
    # the newest bar is still open at `now`: never computed
    assert doc["latest"]["broker_bar"] == idx[-2].tz_localize(None).isoformat()
    assert json.loads(rep.read_text())["engine"] in {"ripser", "scipy_mst_h0"}
    series = pd.read_csv(tmp_path / "series" / f"{T.SID}.csv")
    assert {"available_time", "event_time", "fragility_z", "h0_l1"} <= set(series)
    assert (pd.to_datetime(series["available_time"]) <= pd.Timestamp(now)).all()
    again = T.run(now=now, **kw)
    assert again["new_rows"] == 0 and again["rows"] == doc["rows"]
    later = T.run(now=now + timedelta(hours=1), **kw)
    assert later["new_rows"] == 1


def test_fewer_than_four_symbols_is_unmeasured(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(T, "BASKET", SYMS[:3])
    _write_bars(tmp_path / "bars", 400, seed=1)
    doc = T.run(bars=tmp_path / "bars", series_root=tmp_path / "s", state_path=tmp_path / "x",
                report=None, now=datetime(2026, 7, 1, tzinfo=UTC))
    assert doc["verdict"] == "UNMEASURED"
