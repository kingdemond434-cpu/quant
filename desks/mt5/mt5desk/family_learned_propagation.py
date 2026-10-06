"""Trade an instrument on a LEARNED next-day forecast: graph propagation or attention.

    gnn_propagation:  pred_i,t = ridge( [x_i,t , (A x_t)_i , (A^2 x_t)_i] )
    attention_ts:     pred_i,t = ridge( [attention(x_i,t-L+1..t) , x_i,t] )
    side = sign(pred)            when |pred| / rms(pred over the trailing `norm` days) >= entry_z

Both models live in `libs/models/learned_propagation.py` (numpy only -- the trading box has no
torch and no sklearn) and are refitted WALK-FORWARD on the daily broker-date panel of every
instrument named in `peer_symbols`, so the prediction a signal acts on was made from closes the
desk already had. The panel is the hypothesis: a GNN cell on EURUSD trained against 23 peers is a
different claim from the same cell trained against 5, so the recipe carries the peer list and a
missing peer REFUSES the cell rather than silently shrinking the graph.

WHY THE FAMILY LOADS ITS OWN PEERS. The certifying door (`external_gauntlet.build_cell`) is
sealed and rebuilds multi-instrument inputs only for the families it names; this one is not among
them. Like `family_carry` reading its own recorded terms, the family therefore resolves
`peer_symbols` itself, from the same `data/universe/<SYM>_H1.parquet` store the gauntlet, the
forward engine and the miner all read. A caller that already holds the frames (the miner, a test)
passes them as `peers` and nothing is read from disk.

TIMING, stated once. Row t of the panel closes at the end of broker date t. The forecast for the
next close is acted on at the first bar of the next date whose stamp hour is >= `signal_hour`
(default 02:00 broker) and filled at the bar after, so neither the broker's rollover mark at hour
0 nor its reversion at hour 1 is ever a fill (`proposer_common.artifact_hours`). `hold_bars` is on
the cell's own chart and defaults to the rest of that trading day.

REFUSES: no `symbol`, no `peer_symbols`, a peer with no bars, or a panel too short for the first
walk-forward refit. Each returns [] -- the same contract as `family_lead_lag` without its driver.
`symbol` and `peer_symbols` are REQUIRED keyword-only arguments, like `calendar_month`'s source
evidence: a sweep that enumerates families at their defaults (`breadth_sweep`,
`orthogonal_sweep._unsuppliable`) therefore classifies these as needing their recipe instead of
minting default cells that could only ever fire nothing.
"""
from __future__ import annotations

import hashlib
import sys
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1

_DESK = Path(__file__).resolve().parents[1]
#: Where peer bars are read from, first hit wins. `data/universe` is the store every other door
#: reads; `universe/` is the older in-git snapshot, used only when the first has no file.
UNIVERSE_DIRS: tuple[Path, ...] = (_DESK / "data" / "universe", _DESK / "universe")

#: Predictions are cached per (model, config, panel fingerprint): the 24 cells of one panel share
#: ONE walk-forward, so the gauntlet judging all of them pays for it once per process.
_PRED_CACHE: OrderedDict[tuple[Any, ...], tuple[Any, np.ndarray]] = OrderedDict()
_PRED_CACHE_MAX = 16
_BAR_CACHE: OrderedDict[tuple[str, float], pd.DataFrame] = OrderedDict()
_BAR_CACHE_MAX = 64


def _lp() -> Any:
    root = str(_DESK.parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from libs.models import learned_propagation
    return learned_propagation


def load_peer(sym: str) -> pd.DataFrame | None:
    """H1 bars for `sym` from the desk's universe store, UTC-indexed; None when absent."""
    for base in UNIVERSE_DIRS:
        p = base / f"{sym}_H1.parquet"
        if not p.exists():
            continue
        key = (str(p), p.stat().st_mtime)
        hit = _BAR_CACHE.get(key)
        if hit is not None:
            _BAR_CACHE.move_to_end(key)
            return hit
        try:
            df = pd.read_parquet(p)
        except (OSError, ValueError, ImportError):
            return None
        if df.empty or "close" not in df.columns:
            return None
        df.index = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
        df = df[~df.index.isna()]
        _BAR_CACHE[key] = df
        while len(_BAR_CACHE) > _BAR_CACHE_MAX:
            _BAR_CACHE.popitem(last=False)
        return df
    return None


def _fingerprint(df: pd.DataFrame) -> tuple[Any, ...]:
    h = hashlib.blake2b(np.ascontiguousarray(df["close"].to_numpy(dtype=float)).tobytes(),
                        digest_size=16)
    h.update(np.ascontiguousarray(df.index.asi8).tobytes())
    return (len(df), h.hexdigest())


def panel_predictions(df: pd.DataFrame, symbol: str, peer_symbols: Sequence[str],
                      peers: Mapping[str, pd.DataFrame] | None, model: str,
                      config: Mapping[str, Any]) -> tuple[Any, np.ndarray] | None:
    """(Panel, walk-forward predictions) with `df` standing in for `symbol`, or None."""
    lp = _lp()
    names = sorted({str(s) for s in peer_symbols} | {str(symbol)})
    frames: dict[str, pd.DataFrame] = {}
    for s in names:
        if s == symbol:
            frames[s] = df
            continue
        f = (peers or {}).get(s)
        if f is None:
            f = load_peer(s)
        if f is None or "close" not in f.columns:
            return None                       # a partial panel is a different model: refuse
        frames[s] = f
    key = (model, tuple(sorted((str(k), str(v)) for k, v in config.items())),
           tuple((s, _fingerprint(frames[s])) for s in names))
    hit = _PRED_CACHE.get(key)
    if hit is not None:
        _PRED_CACHE.move_to_end(key)
        return hit
    panel = lp.daily_panel(frames)
    if len(panel.dates) <= lp.MIN_TRAIN + 20 or symbol not in panel.symbols:
        return None
    preds = lp.predictions(lp.design(panel), model, config)
    _PRED_CACHE[key] = (panel, preds)
    while len(_PRED_CACHE) > _PRED_CACHE_MAX:
        _PRED_CACHE.popitem(last=False)
    return panel, preds


def forecast_strength(pred: np.ndarray, norm: int) -> np.ndarray:
    """pred / trailing RMS of pred over the last `norm` rows (rows <= t only); NaN before."""
    p = np.where(np.isfinite(pred), pred, np.nan)
    sq = pd.Series(p * p).rolling(int(norm), min_periods=max(20, int(norm) // 2)).mean()
    rms = np.sqrt(sq.to_numpy(dtype=float))
    with np.errstate(invalid="ignore", divide="ignore"):
        out: np.ndarray = np.where(rms > 0, p / rms, np.nan)
    return out


def _learned_signals(df: pd.DataFrame, *, model: str, config: dict[str, Any], symbol: str,
                     peer_symbols: Sequence[str], peers: Mapping[str, pd.DataFrame] | None,
                     entry_z: float, norm: int, hold_bars: int, signal_hour: int, atr_n: int,
                     stop_atr: float, rr: float, tag: str) -> list[Signal]:
    if not symbol or not peer_symbols or "close" not in df.columns:
        return []
    d = _h1(df)
    if len(d) < 300:
        return []
    got = panel_predictions(d, symbol, peer_symbols, peers, model, config)
    if got is None:
        return []
    panel, preds = got
    j = panel.symbols.index(symbol)
    strength = forecast_strength(preds[:, j], norm)
    printed = np.isfinite(panel.ret[:, j])

    # The first bar of each of this instrument's trading dates at/after `signal_hour` (else the
    # date's first bar, which is the whole day on D1), keyed by date.
    day = d.index.normalize()
    hours = d.index.hour
    first_ok: dict[pd.Timestamp, int] = {}
    first_any: dict[pd.Timestamp, int] = {}
    for i, (dt, h) in enumerate(zip(day, hours, strict=True)):
        first_any.setdefault(dt, i)
        if h >= int(signal_hour):
            first_ok.setdefault(dt, i)
    own_dates = sorted(first_any)
    date_pos = {dt: k for k, dt in enumerate(own_dates)}

    atr = _atr(d, atr_n).to_numpy(dtype=float)
    close = d["close"].to_numpy(dtype=float)
    out: list[Signal] = []
    last = -10 ** 9
    for t, dt in enumerate(panel.dates):
        z = strength[t]
        if not printed[t] or not np.isfinite(z) or abs(z) < float(entry_z):
            continue
        k = date_pos.get(dt)
        if k is None or k + 1 >= len(own_dates):
            continue
        nxt = own_dates[k + 1]
        i = first_ok.get(nxt, first_any[nxt])
        if i - last < int(hold_bars) or i + 1 >= len(d):
            continue
        a = atr[i]
        side = int(np.sign(z))
        if side == 0 or not np.isfinite(a) or a <= 0:
            continue
        px = close[i]
        out.append(Signal(time=d.index[i], side=side, stop=px - side * stop_atr * a,
                          target=px + side * stop_atr * a * rr, ttl_bars=int(hold_bars),
                          tag=tag, trigger=None, wait_bars=1))
        last = i
    return out


def family_gnn_propagation(
    df: pd.DataFrame,
    *,
    symbol: str,
    peer_symbols: Sequence[str],
    peers: Mapping[str, pd.DataFrame] | None = None,
    adjacency: str = "lead_lag",
    layers: int = 1,
    entry_z: float = 1.0,
    norm: int = 120,
    hold_bars: int = 20,
    signal_hour: int = 2,
    atr_n: int = 20,
    stop_atr: float = 8.0,
    rr: float = 1.5,
) -> list[Signal]:
    """Cross-asset information diffusion: the graph says which markets move first for this one."""
    if adjacency not in ("lead_lag", "corr") or int(layers) not in (1, 2):
        return []
    return _learned_signals(
        df, model="gnn", config={"adjacency": adjacency, "layers": int(layers)}, symbol=symbol,
        peer_symbols=peer_symbols, peers=peers, entry_z=entry_z, norm=norm, hold_bars=hold_bars,
        signal_hour=signal_hour, atr_n=atr_n, stop_atr=stop_atr, rr=rr,
        tag=f"gnn_propagation:{adjacency}:{int(layers)}")


def family_attention_ts(
    df: pd.DataFrame,
    *,
    symbol: str,
    peer_symbols: Sequence[str],
    peers: Mapping[str, pd.DataFrame] | None = None,
    heads: int = 1,
    lookback: int = 20,
    entry_z: float = 1.0,
    norm: int = 120,
    hold_bars: int = 20,
    signal_hour: int = 2,
    atr_n: int = 20,
    stop_atr: float = 8.0,
    rr: float = 1.5,
) -> list[Signal]:
    """State-dependent continuation/reversal learned by attention over the recent path."""
    if int(heads) not in (1, 2) or int(lookback) < 2:
        return []
    return _learned_signals(
        df, model="attention", config={"heads": int(heads), "lookback": int(lookback)},
        symbol=symbol, peer_symbols=peer_symbols, peers=peers, entry_z=entry_z, norm=norm,
        hold_bars=hold_bars, signal_hour=signal_hour, atr_n=atr_n, stop_atr=stop_atr, rr=rr,
        tag=f"attention_ts:h{int(heads)}:L{int(lookback)}")
