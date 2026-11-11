"""Trade an instrument when a macro fair-value reading moves hard: three bases, one family.

    basis "net_liquidity"      reading = z( weekly change of WALCL - WTREGEN - 1000 * RRPONTSYD )
    basis "rate_differential"  reading = <PAIR>.carry_differential(d) - its value `lookback_days`
                                         earlier (percentage points, BIS policy rates)
    basis "terms_of_trade"     reading = z( log(pair) - rolling OLS fit on log(commodity basket) )
    event   = the first reading on the named side (`move` "up": >= +min_abs, "down": <= -min_abs)
              after a reading that was not
    signal  = `direction`, on the first bar that opens after the market could know the reading

MECHANISM. Each basis is a fair value the instrument's holders reprice toward with a lag.
NET LIQUIDITY: the Fed balance sheet less the Treasury's cash at the Fed (TGA) less the overnight
reverse-repo facility is the dollar reserve the private system can deploy; a large weekly
injection or drain reprices duration-sensitive and dollar-denominated risk (gold, US indices, the
dollar crosses) over the days after the H.4.1 is read. RATE DIFFERENTIAL: a widening of one
currency's policy-rate advantage moves carry holders and rate-expectation holders into it, so the
pair drifts toward the currency whose advantage widened. TERMS OF TRADE: a commodity currency's
fair value is the price of what its economy exports (AUD and NZD on copper, gold and oil; CAD on
oil); a residual far from that fit is a dislocation the commodity-linked flow closes. Each claim
is falsifiable per cell: it fails when its events carry no forward return net of cost.

THE INPUTS ARE THE DESK'S OWN AXES AND BARS, READ WITH THE DESK'S OWN READER. FRED series come
from `data/axes/fred.json` and BIS policy-rate differentials from `data/axes/bis.json`, both
through `research.shadow_institutional.read_axis_points` (no second parser). Terms-of-trade peers
are the desk's own MT5 bars, resolved by the family itself through
`family_inputs.bars_named` (the mechanism `lead_lag` and the learned panel families use), on the
cell's own chart; a caller that already holds them passes `peers` and nothing is read from disk.

THE EVENT CLOCK IS THE PRINT'S KNOWABLE DAY, AND A DAY IS NOT AN INSTANT.
  - FRED: WALCL and WTREGEN are Wednesday levels published Thursday 16:30 ET (20:30/21:30 UTC);
    RRPONTSYD is a daily print. A point is keyed on its `knowable_at` when the axis stamps one,
    otherwise on its observation date + 1 day (`FRED_PUBLICATION_LAG_D`). The three series are
    joined as of each WALCL knowable day (WTREGEN and RRP at the latest knowable day at or before
    it). RRPONTSYD is in billions, WALCL and WTREGEN in millions: RRP is scaled by 1000.
  - BIS: each row is keyed on its `knowable_at` day (the policy rate in force that day).
  - Either way a knowable DAY carries no hour, and the H.4.1 posts in the US afternoon, so a
    reading is taken as knowable from 00:00 UTC of the FOLLOWING day.
THE BAR CLOCK. The bar index is broker time, measured at UTC+2 in winter and UTC+3 in summer; the
entry bar must be labelled at or after that UTC instant plus `BROKER_MAX_OFFSET_H` (3h), which is
on or after the knowable instant in BOTH seasons -- at most one hour late in winter, never early.
Terms of trade is on the bar clock throughout: bar t's residual uses bar t's CLOSE and a fit made
only on bars strictly before t, and it is acted on at bar t+1, the first bar opened after that
close existed.

THE Z-SCORES READ ONLY THE PAST. The net-liquidity change at print k is scored against the mean
and deviation of the `window` changes BEFORE k; the terms-of-trade residual at bar t is scored
against the residuals of the `window` bars it was fitted on (all before t).

THE INPUT IS NAMED ON THE RECIPE (`basis`, and `symbol` for the two per-pair bases) and loaded
HERE, so the sweep, the sealed gauntlet's `build_cell` and the forward clock rebuild the same
signals from the same identity.

AN ABSENT INPUT IS A NAMED REFUSAL, NOT A CELL THAT NEVER FIRES (L1.28a): a FRED series missing
from the axis (`fred_net_liquidity_absent`), a pair the BIS axis does not carry
(`bis_rate_differential_absent`), or a terms-of-trade peer with no bars or a pair with no basket
(`tot_basket_absent`) raises `MacroFairValueUnavailable`. It is also a TypeError on purpose -- the
sealed builder catches only TypeError on its first family call and names the failure on its
retry, so the refusal goes through the builder's own door, exactly as `CbToneUnavailable` does.

REFUSES (returns []) on an empty or unknown basis, move or direction, a negative threshold, or
too few bars.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal
from mt5desk.family_event_reaction import family_event_reaction

DESK = Path(__file__).resolve().parents[1]
AXES = DESK / "data" / "axes"
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

BASES = ("net_liquidity", "rate_differential", "terms_of_trade")
MOVES = ("up", "down")
DIRECTIONS = {"long": 1, "short": -1}

#: FRED: (axis series id, multiplier to millions of USD). Net liquidity = WALCL - WTREGEN - RRP.
NET_LIQUIDITY_SERIES: tuple[tuple[str, float], ...] = (("WALCL", 1.0), ("WTREGEN", 1.0),
                                                       ("RRPONTSYD", 1000.0))
#: Days from a FRED observation to its publication when the axis stamps no `knowable_at`
#: (WALCL/WTREGEN: Wednesday level, Thursday release).
FRED_PUBLICATION_LAG_D = 1
#: The traded pair -> its export basket. USDCAD is quoted the other way round; the OLS fit takes
#: the inverted sign itself (regressing log USDCAD on log oil is regressing -log CADUSD on it, so
#: the coefficient and the residual are exactly the CAD reading negated).
TOT_BASKETS: dict[str, tuple[str, ...]] = {
    "AUDUSD": ("XCUUSD", "XAUUSD", "XTIUSD"),
    "NZDUSD": ("XCUUSD", "XAUUSD", "XTIUSD"),
    "USDCAD": ("XTIUSD",),
}
#: The largest measured broker-time offset from UTC (summer). Adding it to a UTC instant gives a
#: bar label that is on or after that instant in both seasons.
BROKER_MAX_OFFSET_H = 3
_EVENT_SYMBOL = "MACRO_FAIR_VALUE"

ABSENT_FRED = "fred_net_liquidity_absent"
ABSENT_BIS = "bis_rate_differential_absent"
ABSENT_TOT = "tot_basket_absent"


class MacroFairValueUnavailable(LookupError, TypeError):
    """The recipe names a fair-value input this host does not hold."""


def _reader() -> Any:
    try:
        from research.shadow_institutional import read_axis_points
    except ImportError:                                   # pragma: no cover -- desk on sys.path
        from shadow_institutional import read_axis_points  # type: ignore[no-redef]
    return read_axis_points


def _mtime(name: str) -> int:
    try:
        return (Path(AXES) / f"{name}.json").stat().st_mtime_ns
    except OSError:
        return -1


@lru_cache(maxsize=64)
def _points(axes: str, name: str, series: str, mtime_ns: int) -> tuple[tuple[str, float], ...]:
    return tuple(_reader()(Path(axes), name, series))


@lru_cache(maxsize=16)
def _stamped(axes: str, sid: str, mtime_ns: int) -> bool:
    """Whether the FRED axis stamps `sid`'s points with their own `knowable_at`."""
    try:
        doc = json.loads((Path(axes) / "fred.json").read_text(encoding="utf-8-sig"))
        pts = doc["series"][sid]["points"]
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return bool(pts) and all(isinstance(p, Mapping) and p.get("knowable_at") for p in pts)


def axis_series(name: str, series: str) -> pd.Series | None:
    """{knowable day (UTC midnight): value} for one axis series, or None when absent."""
    pts = _points(str(AXES), name, series, _mtime(name))
    if not pts:
        return None
    s = pd.Series({pd.Timestamp(d, tz="UTC"): v for d, v in pts if len(d) == 10}, dtype=float)
    s = s[np.isfinite(s.to_numpy())].sort_index()
    if name == "fred" and not _stamped(str(AXES), series, _mtime(name)):
        s.index = s.index + pd.Timedelta(days=FRED_PUBLICATION_LAG_D)
    return s if len(s) else None


def net_liquidity() -> pd.Series:
    """WALCL - WTREGEN - RRP (millions of USD) per WALCL knowable day; refuses if one is absent."""
    got: dict[str, pd.Series] = {}
    missing = []
    for sid, mult in NET_LIQUIDITY_SERIES:
        s = axis_series("fred", sid)
        if s is None:
            missing.append(sid)
        else:
            got[sid] = s * mult
    if missing:
        raise MacroFairValueUnavailable(
            f"{ABSENT_FRED}: {', '.join(missing)} absent from {Path(AXES) / 'fred.json'}; "
            "net liquidity is unmeasured on this host and the cell is unjudged")
    base = got["WALCL"].rename("walcl").to_frame()
    for sid in ("WTREGEN", "RRPONTSYD"):
        other = got[sid].rename(sid.lower()).to_frame()
        base = pd.merge_asof(base, other, left_index=True, right_index=True,
                             direction="backward")
    base = base.dropna()
    return (base["walcl"] - base["wtregen"] - base["rrpontsyd"]).rename("net_liquidity")


def prior_z(chg: pd.Series, window: int) -> pd.Series:
    """Each value against the mean and deviation of the `window` values BEFORE it."""
    prior = chg.shift(1).rolling(int(window), min_periods=int(window))
    sd = prior.std()
    return ((chg - prior.mean()) / sd.where(sd > 0)).dropna()


def rate_differential(symbol: str) -> pd.Series:
    s = axis_series("bis", f"{str(symbol).upper()}.carry_differential")
    if s is None:
        raise MacroFairValueUnavailable(
            f"{ABSENT_BIS}: {Path(AXES) / 'bis.json'} carries no {str(symbol).upper()}"
            ".carry_differential; the rate differential is unmeasured and the cell is unjudged")
    return s


def differential_change(s: pd.Series, lookback_days: int) -> pd.Series:
    """Differential on each knowable day minus its value `lookback_days` calendar days before."""
    past = pd.merge_asof(
        pd.DataFrame({"at": s.index - pd.Timedelta(days=int(lookback_days))}),
        pd.DataFrame({"at": s.index, "v": s.to_numpy()}), on="at", direction="backward")
    out = pd.Series(s.to_numpy() - past["v"].to_numpy(), index=s.index)
    return out.dropna()


def _onsets(reading: pd.Series, move: str, min_abs: float) -> pd.Index:
    on = reading >= float(min_abs) if move == "up" else reading <= -float(min_abs)
    on &= reading != 0.0
    first = on & ~on.shift(1, fill_value=False)
    return reading.index[first.to_numpy()]


def _day_events(days: pd.Index) -> list[pd.Timestamp]:
    step = pd.Timedelta(days=1) + pd.Timedelta(hours=BROKER_MAX_OFFSET_H)
    return [pd.Timestamp(d).normalize() + step for d in days]


def tot_residual_z(df: pd.DataFrame, symbol: str, window: int,
                   peers: Mapping[str, pd.DataFrame] | None = None) -> pd.Series:
    """Residual z of log(pair) on its log basket, fitted only on the `window` bars before it."""
    basket = TOT_BASKETS.get(str(symbol).upper())
    if basket is None:
        raise MacroFairValueUnavailable(
            f"{ABSENT_TOT}: {symbol} has no declared terms-of-trade basket "
            f"(declared: {', '.join(sorted(TOT_BASKETS))})")
    from mt5desk.family_inputs import bars_named
    cols = {"y": df["close"].astype(float)}
    missing = []
    for p in basket:
        f = (peers or {}).get(p)
        if f is None:
            f = bars_named(p, df)
        if f is None or "close" not in getattr(f, "columns", ()):
            missing.append(p)
            continue
        cols[p] = f["close"].astype(float)
    if missing:
        raise MacroFairValueUnavailable(
            f"{ABSENT_TOT}: no bars for {', '.join(missing)} on this chart; the terms-of-trade "
            f"fair value of {symbol} is unmeasured and the cell is unjudged")
    j = pd.DataFrame(cols).dropna()
    j = j[(j > 0).all(axis=1)]
    w = int(window)
    if len(j) <= w + 1:
        return pd.Series(dtype=float)
    y = np.log(j["y"].to_numpy())
    x = np.column_stack([np.ones(len(j))] + [np.log(j[p].to_numpy()) for p in basket])
    k = x.shape[1]
    # rolling normal equations over rows [t-w, t-1] from cumulative sums: row t is never in its fit
    xx = np.einsum("ti,tj->tij", x, x)
    xy = x * y[:, None]
    cxx = np.concatenate([np.zeros((1, k, k)), np.cumsum(xx, axis=0)])
    cxy = np.concatenate([np.zeros((1, k)), np.cumsum(xy, axis=0)])
    cyy = np.concatenate([[0.0], np.cumsum(y * y)])
    t = np.arange(w, len(j))
    sxx = cxx[t] - cxx[t - w]
    sxy = cxy[t] - cxy[t - w]
    syy = cyy[t] - cyy[t - w]
    ridge = 1e-10 * np.eye(k)
    try:
        beta = np.linalg.solve(sxx + ridge, sxy[..., None])[..., 0]
    except np.linalg.LinAlgError:
        return pd.Series(dtype=float)
    sse = syy - 2 * np.einsum("ti,ti->t", beta, sxy) + np.einsum("ti,tij,tj->t", beta, sxx, beta)
    sd = np.sqrt(np.clip(sse, 0, None) / max(w - k, 1))
    resid = y[t] - np.einsum("ti,ti->t", x[t], beta)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = np.where(sd > 0, resid / sd, np.nan)
    return pd.Series(z, index=j.index[t]).dropna()


def event_times(df: pd.DataFrame, *, basis: str, symbol: str, move: str, min_abs: float,
                window: int, lookback_days: int,
                peers: Mapping[str, pd.DataFrame] | None = None) -> list[pd.Timestamp]:
    """Bar-frame instants from which each qualifying reading is knowable."""
    if basis == "net_liquidity":
        z = prior_z(net_liquidity().diff().dropna(), window)
        return _day_events(_onsets(z, move, min_abs))
    if basis == "rate_differential":
        chg = differential_change(rate_differential(symbol), lookback_days)
        return _day_events(_onsets(chg, move, min_abs))
    z = tot_residual_z(df, symbol, window, peers)
    if z.empty:
        return []
    idx = df.index
    out = []
    for ts in _onsets(z, move, min_abs):
        pos = int(idx.searchsorted(ts, side="right"))      # the bar after the one that closed
        if pos < len(idx):
            out.append(idx[pos])
    return out


def family_macro_fair_value(
    df: pd.DataFrame,
    *,
    side: int | None = None,
    basis: str = "",
    symbol: str = "",
    move: str = "up",
    min_abs: float = 2.0,
    direction: str = "long",
    window: int = 52,
    lookback_days: int = 63,
    hold_bars: int = 24,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    peers: Mapping[str, pd.DataFrame] | None = None,
) -> list[Signal]:
    # THE RECIPE'S `direction` IS THE SIDE (as in `cb_tone_event`): the sealed gauntlet always
    # passes side=1 and the forward clock passes the cell's own side, so honouring `side` would
    # make the two callers build different trades from one identity.
    del side
    flip = DIRECTIONS.get(str(direction))
    if (basis not in BASES or flip is None or move not in MOVES or float(min_abs) < 0
            or int(window) < 2 or int(lookback_days) < 1 or "close" not in df.columns):
        return []
    if basis != "net_liquidity" and not symbol:
        return []
    times = event_times(df, basis=str(basis), symbol=str(symbol), move=str(move),
                        min_abs=float(min_abs), window=int(window),
                        lookback_days=int(lookback_days), peers=peers)
    if not times:
        return []
    events: list[dict[str, Any]] = [{"symbol": _EVENT_SYMBOL, "at": ts} for ts in times]
    out = family_event_reaction(
        df, events=events, symbol=_EVENT_SYMBOL, mode="drift", side=flip,
        hold_bars=int(hold_bars), atr_n=int(atr_n), stop_atr=float(stop_atr), rr=float(rr),
        ttl_bars=int(hold_bars), cooldown_bars=int(hold_bars), clock="bars")
    tag = f"macro_fair_value:{basis}:{str(symbol).upper() or 'USD'}:{move}:{direction}"
    return [Signal(time=s.time, side=s.side, stop=s.stop, target=s.target, ttl_bars=s.ttl_bars,
                   tag=tag, trigger=s.trigger, wait_bars=s.wait_bars) for s in out]
