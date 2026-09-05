"""COT positioning must actually reach the search leg, not merely be owned by the desk.

`edge_search.resolve_inputs` looked for `cot.json`, `cot_tff.json` and `cot_disagg.json` under
the desk's data directory. Nothing in this repository has ever written any of those three: the
only mentions anywhere are that loop and the identical one in `orthogonal_sweep._cot_frame`. So
every resolve fell through all three names, hit `continue`, and produced no `cot_net` -- for the
whole life of the leg, and silently, because a missing optional input looks exactly like an
input that is genuinely unavailable.

The data was never missing. `data/cot_zcache.parquet` holds 26 years of point-in-time CFTC
history across 11 assets, refreshed on a timer and shipped to the desk box by the external
pipeline. `orthogonal_sweep` was given this read after the same defect was found there; its
comment records that a COT miner "could produce a real candidate that always rebuilt with
cot=None". The search leg never got the fix.

Pinned here: the z-cache is read and keyed by SYMBOL, a repeated daily value never counts as an
independent weekly report, too short a history is refused rather than used, and a symbol the
cache does not cover costs nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

edge_search = pytest.importorskip("research.edge_search",
                                  reason="the search leg ships with the research package")


def _zcache(root: Path, symbols: dict[str, int], days: int = 900) -> Path:
    """A forward-filled DAILY cache, which is the shape the real one has."""
    idx = pd.date_range("2022-01-03", periods=days, freq="D", tz="UTC")
    frame = pd.DataFrame({s: [float(base + i) for i in range(days)]
                          for s, base in symbols.items()}, index=idx)
    p = root / "data" / "cot_zcache.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(p)
    return p


def _resolve(monkeypatch, tmp_path: Path, symbol: str) -> dict:
    """`BASE.parent.parent / "data"` is the repo root, so BASE is <tmp>/desks/mt5."""
    base = tmp_path / "desks" / "mt5"
    base.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(edge_search, "BASE", base)
    monkeypatch.setattr(edge_search, "_RESOLVE_CACHE", type(edge_search._RESOLVE_CACHE)())
    index = pd.date_range("2023-06-01", periods=40, freq="D", tz="UTC")
    return edge_search.resolve_inputs(symbol, index, [symbol])


def test_the_search_leg_reads_cot_for_the_symbol_it_is_resolving(monkeypatch, tmp_path) -> None:
    _zcache(tmp_path, {"XAUUSD": 1000, "EURUSD": 5000})
    got = _resolve(monkeypatch, tmp_path, "XAUUSD")
    assert "cot_net" in got, "the desk owns 26 years of COT and the search leg saw none of it"
    series = got["cot_net"]
    assert len(series) >= 52
    # keyed by SYMBOL: gold's column, not whichever column happened to sort first
    assert float(series.iloc[0]) >= 1000.0 and float(series.iloc[0]) < 5000.0


def test_a_forward_filled_daily_value_is_not_an_independent_weekly_report(
        monkeypatch, tmp_path) -> None:
    """COT is published weekly. Resampling is what stops 900 daily rows reading as 900 reports,
    which would make every significance test on it wrong in the direction that admits noise."""
    _zcache(tmp_path, {"XAUUSD": 1000}, days=700)
    series = _resolve(monkeypatch, tmp_path, "XAUUSD")["cot_net"]
    assert len(series) < 700 / 6, f"{len(series)} observations from 700 daily rows is not weekly"
    assert (series.index.to_series().diff().dropna().dt.days == 7).all()


def test_too_little_history_is_refused_rather_than_used(monkeypatch, tmp_path) -> None:
    """Under a year of reports is not a positioning series, and half a signal is worse than
    none: it passes the presence check and then conditions capital on nothing."""
    _zcache(tmp_path, {"XAUUSD": 1000}, days=120)
    assert "cot_net" not in _resolve(monkeypatch, tmp_path, "XAUUSD")


def test_a_symbol_the_cache_does_not_cover_costs_nothing(monkeypatch, tmp_path) -> None:
    """Eleven assets are covered and the desk trades far more. An uncovered symbol must resolve
    every OTHER input normally rather than raising."""
    _zcache(tmp_path, {"XAUUSD": 1000})
    got = _resolve(monkeypatch, tmp_path, "GBPNOK")
    assert "cot_net" not in got
    assert isinstance(got, dict)


def test_no_cache_at_all_is_survivable(monkeypatch, tmp_path) -> None:
    """The VPS gitignores the lake, so a fresh checkout has no cache. That is not an error."""
    got = _resolve(monkeypatch, tmp_path, "XAUUSD")
    assert "cot_net" not in got


def test_the_unwritten_json_names_are_still_only_a_fallback() -> None:
    """A REGRESSION GUARD ON THE DIAGNOSIS. If someone later starts writing these files the
    fallback should serve them, but the z-cache must stay the primary read -- restoring the old
    order would restore the blindness, because the files still do not exist.
    """
    src = (_DESK / "research" / "edge_search.py").read_text("utf-8")
    z, j = src.index("cot_zcache.parquet"), src.index('"cot_tff.json"')
    assert z < j, "the z-cache read must come BEFORE the json fallback, or COT is lost again"
