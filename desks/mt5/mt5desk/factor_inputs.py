"""The factor basket a residual clock replays on: its own bars, aligned point in time, or a
DECLARED proxy, or a named refusal. Never a silent zero.

WHY THIS EXISTS (measured 2026-10-14 and 2026-10-18 on the box's published shadow_state.json)

24 cross_asset_residual clocks naming `factor_symbols=['USDX', 'UST10Y']` read ACTIVE with
n = 0 and n_historical = 0 on every pass, while the 36 clocks naming `['USDX']` alone on the same
symbols and charts accrued (AUDNZD M5 USDX-only: n=10, n_historical=77). So USDX was delivered
and the UST10Y leg was what starved them. The chain:

  * UST10Y and UST05Y are CLOSE_ONLY at Fusion (`fetch_universe.py`, the registry's trade_mode),
    and `fetch_universe._fetch_intraday` writes NO intraday parquet for a non-tradeable symbol
    ("NOT_TRADEABLE"); `refresh_tail.refresh_symbol` only extends a file that already exists
    ("no-cache"). So the lake never held UST10Y on M5/M15/M30 -- every one of the 24 is intraday.
  * The certificates were gated 2026-09-24..27, before ef11ff615 (2026-09-28) stopped
    `external_gauntlet.build_cell` silently dropping a missing factor. They were therefore
    certified on the USDX leg alone. After that commit no new USDX+UST10Y certificate was minted
    at all, while USDX-only certificates kept arriving -- the gauntlet could not find the leg.
  * The forward engine then reached the bond through `family_inputs._runtime_bars`' broker
    fallback (dd4e3b4ee), which only checks the leg's first and last stamps. A close-only bond's
    intraday tape is not a regular chart: `families._h1` resamples an irregular frame to H1 and
    the family joins it `how="inner"` onto an M5/M15/M30 primary, which keeps only the hours both
    printed -- far fewer than the `beta_win + 2 * lookback` (720) rows the family requires. It
    returns [] without a reason, and the clock reads as a quiet market.

WHAT THIS MODULE DOES, in order, for each named factor:

  1. OWN BARS, if present and fresh against the primary (the same trading-hours staleness rule
     `h1_source` applies to a primary feed).
  2. Otherwise a DECLARED PROXY -- but only when the certificate's own spec carries
     `factor_proxy` (truthy). USDX -> the ICE geometric basket of the six Fusion majors
     (`research.synthetic_usdx` weights, exact-stamp join, never forward-filled); UST10Y <->
     UST05Y -> the nearest Fusion rates instrument, if fresh. The row is labelled
     `proxy_fed: true` with the proxy named per factor, so the promoter and the judge can tell
     it apart from a clock replayed on the certified inputs.
  3. Otherwise NEEDS_PROXY_FACTOR, naming the factor and the cause. The clock is UNMEASURED by
     name, never n = 0.

  Then ALIGNMENT. If the exact-stamp inner join of primary and factors already holds the
  family's floor, the RAW frames are returned -- byte-identical to the certification path
  (`build_cell` hands the family raw frames too). Only when that join would starve the frame
  are the factors aligned onto the primary's own index AS-OF: each primary bar takes the latest
  factor bar stamped at or before it, within a bounded tolerance, never a later one. A bar on
  the same chart stamped at or before t closes at or before the primary bar stamped t, so no
  value the primary bar could not have seen is used; a factor on a coarser chart is refused
  rather than aligned, because its bar stamped before t can close after t. If even the as-of
  frame cannot reach the floor, the answer is FACTOR_FRAME_STARVED, by name.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

#: The certificate-spec key that permits a declared proxy. Absent means the certified model is
#: the named factors' own bars and nothing else.
PROXY_KEY = "factor_proxy"
NEEDS_PROXY_FACTOR = "NEEDS_PROXY_FACTOR"
FACTOR_FRAME_STARVED = "FACTOR_FRAME_STARVED"

#: Same trading-hours staleness rule `h1_source.STALE_AFTER_H` applies to a primary feed.
STALE_AFTER_TRADING_H = 6.0
#: As-of tolerance: a factor value may stand in for at most this many primary bars, and never
#: less than an hour (a close-only bond prints sparsely inside its own session).
ASOF_TOLERANCE_BARS = 4
ASOF_TOLERANCE_MIN_MINUTES = 60

#: Nearest Fusion rates instrument for each rates factor, nearest first.
RATES_NEIGHBOURS: dict[str, tuple[str, ...]] = {
    "UST10Y": ("UST05Y",),
    "UST05Y": ("UST10Y",),
}
SYNTH_USDX = "SYNTH_USDX_ICE6"

Loader = Callable[[str], Any]


def proxy_allowed(params: dict[str, Any] | None) -> bool:
    """Whether the certificate's own spec permits a declared factor proxy."""
    v = (params or {}).get(PROXY_KEY)
    if isinstance(v, bool):
        return v
    return str(v or "").strip().lower() in {"1", "true", "yes", "allow", "allowed", "declared"}


def residual_floor(params: dict[str, Any] | None) -> int:
    """Rows `family_cross_asset_residual` needs before it will emit anything at all."""
    p = params or {}
    lookback = int(p.get("lookback") or 240)
    bwin = int(p.get("beta_win") or lookback)
    return bwin + 2 * lookback


def _frame(df: Any) -> pd.DataFrame | None:
    """A bar frame with a sorted, unique, tz-aware UTC index at ns, or None."""
    if df is None or not hasattr(df, "index") or len(df) == 0 or "close" not in df.columns:
        return None
    out = df.copy()
    idx = pd.DatetimeIndex(pd.to_datetime(out.index, utc=True))
    out.index = idx.as_unit("ns")
    out = out.sort_index()
    return out[~out.index.duplicated(keep="last")]


def _minutes(df: pd.DataFrame) -> int | None:
    try:
        from mt5desk.families import bar_minutes
        return bar_minutes(df)
    except Exception:
        return None


def _family_view(df: pd.DataFrame) -> pd.DataFrame:
    """The frame as the residual family sees it after `families._h1`."""
    try:
        from mt5desk.families import _h1
        return _h1(df)
    except Exception:
        return df


def _min_gap_minutes(df: pd.DataFrame) -> float | None:
    """The smallest spacing between consecutive bars: a coarser CHART has none below its bar."""
    if len(df) < 2:
        return None
    gaps = np.diff(df.index.asi8) / 6e10
    gaps = gaps[gaps > 0]
    return float(gaps.min()) if gaps.size else None


def staleness(factor: pd.DataFrame, primary: pd.DataFrame) -> str | None:
    """None when `factor` keeps up with `primary`; otherwise why it does not."""
    from research.h1_source import trading_lag_hours
    f_last, p_last = factor.index.max(), primary.index.max()
    lag = trading_lag_hours(f_last, p_last.to_pydatetime())
    if lag > STALE_AFTER_TRADING_H:
        return (f"last bar {f_last.isoformat()} is {lag:.1f} trading hours behind the primary's "
                f"{p_last.isoformat()}")
    return None


def synthetic_usdx(load: Loader) -> tuple[pd.DataFrame | None, str]:
    """The ICE dollar index from the six Fusion legs, exact-stamp join, never forward-filled."""
    from research.synthetic_usdx import CONSTANT, WEIGHTS
    legs: dict[str, pd.DataFrame] = {}
    for sym in WEIGHTS:
        f = _frame(load(sym))
        if f is None:
            return None, f"leg {sym} has no bars"
        legs[sym] = f
    idx: pd.DatetimeIndex | None = None
    for f in legs.values():
        idx = f.index if idx is None else idx.intersection(f.index)
    if idx is None or len(idx) == 0:
        return None, "the six legs share no bar stamp"
    out: dict[str, np.ndarray] = {}
    for col in ("open", "close"):
        log = np.log(CONSTANT) + sum(
            w * np.log(legs[s].loc[idx, col if col in legs[s].columns else "close"]
                       .to_numpy(dtype=float)) for s, w in WEIGHTS.items())
        out[col] = np.exp(log)
    frame = pd.DataFrame(out, index=idx).sort_index()
    frame["high"] = frame[["open", "close"]].max(axis=1)
    frame["low"] = frame[["open", "close"]].min(axis=1)
    return frame[["open", "high", "low", "close"]], "ok"


def _proxy(name: str, load: Loader, primary: pd.DataFrame) -> tuple[pd.DataFrame | None, str, str]:
    """(frame, proxy label, why) for `name`'s declared proxy, or (None, '', why not)."""
    if name.upper() == "USDX":
        f, why = synthetic_usdx(load)
        if f is None:
            return None, "", f"{SYNTH_USDX} unavailable: {why}"
        stale = staleness(f, primary)
        if stale:
            return None, "", f"{SYNTH_USDX} stale: {stale}"
        return f, SYNTH_USDX, "ok"
    tried: list[str] = []
    for cand in RATES_NEIGHBOURS.get(name.upper(), ()):
        f = _frame(load(cand))
        if f is None:
            tried.append(f"{cand}: no bars")
            continue
        stale = staleness(f, primary)
        if stale:
            tried.append(f"{cand}: {stale}")
            continue
        return f, cand, "ok"
    if not tried:
        return None, "", "no declared proxy exists for this factor"
    return None, "", "no fresh Fusion rates neighbour (" + "; ".join(tried) + ")"


def asof_align(factor: pd.DataFrame, index: pd.DatetimeIndex,
               tolerance: pd.Timedelta) -> pd.DataFrame:
    """`factor` on `index`: each stamp takes the latest factor bar at or before it, within
    `tolerance`; NaN beyond it. Backward only -- a later bar is never read."""
    return factor.reindex(index, method="ffill", tolerance=tolerance)


def tolerance_for(primary: pd.DataFrame) -> pd.Timedelta:
    m = _minutes(primary) or 60
    return pd.Timedelta(minutes=max(ASOF_TOLERANCE_MIN_MINUTES, ASOF_TOLERANCE_BARS * m))


def build_basket(names: list[str], params: dict[str, Any], primary: Any,
                 load: Loader) -> tuple[list[pd.DataFrame] | None, str, dict[str, Any]]:
    """(factor frames | None, why, provenance) for a residual cell's named basket."""
    prov: dict[str, Any] = {"factors": [], "proxy_fed": False, "alignment": None,
                            "proxy_allowed": proxy_allowed(params)}
    p = _frame(primary)
    chosen: list[tuple[str, pd.DataFrame]] = []
    needs: list[str] = []
    for name in names:
        own = _frame(load(str(name)))
        cause = ("no bars on this chart from any source" if own is None
                 else (staleness(own, p) if p is not None else None))
        if own is not None and cause is None:
            chosen.append((str(name), own))
            prov["factors"].append({"factor": str(name), "source": "OWN"})
            continue
        if prov["proxy_allowed"] and p is not None:
            f, label, why = _proxy(str(name), load, p)
            if f is not None:
                chosen.append((str(name), f))
                prov["proxy_fed"] = True
                prov["factors"].append({"factor": str(name), "source": "PROXY", "proxy": label,
                                        "own_bars": cause})
                continue
            needs.append(f"{name} ({cause}; {why})")
        elif p is None:
            needs.append(f"{name} ({cause}; no primary bars to qualify a proxy against)")
        else:
            _f, label, why = _proxy(str(name), load, p)
            avail = f"declared proxy {label} is available" if label else why
            needs.append(f"{name} ({cause}; the certificate spec does not set `{PROXY_KEY}`, "
                         f"so no proxy is substituted -- {avail})")
        prov["factors"].append({"factor": str(name), "source": "MISSING", "own_bars": cause})
    if needs:
        prov["needs"] = [n.split(" (", 1)[0] for n in needs]
        return None, (f"{NEEDS_PROXY_FACTOR}: factor bars unavailable for " + "; ".join(needs)
                      + f" -- all {len(names)} named factors are required to preserve the "
                        "certified model"), prov
    if p is None:
        # Nothing to align against: hand over the frames exactly as the certifier did.
        prov["alignment"] = "UNALIGNED_NO_PRIMARY"
        return [f for _n, f in chosen], "ok", prov

    floor = residual_floor(params)
    # THE JOIN THE FAMILY WILL ACTUALLY MAKE: `families._h1` resamples an irregular frame to H1
    # before the inner join, so the count is taken on the same normalised frames.
    pview = _family_view(p)
    common = pview.index
    for _n, f in chosen:
        common = common.intersection(_family_view(f).index)
    # A PRIMARY SHORTER THAN THE FLOOR IS NOT THE BASKET'S FAULT: the family refuses it on its own
    # terms, exactly as it did for the certifier. Starvation is rows the FACTORS took away.
    need = min(floor, len(pview))
    prov["floor_rows"] = floor
    prov["exact_rows"] = len(common)
    tail = staleness(pd.DataFrame({"close": 1.0}, index=common), p) if len(common) else "empty"
    if len(common) >= need and tail is None:
        prov["alignment"] = "EXACT"
        return [f for _n, f in chosen], "ok", prov

    pm = _minutes(p)
    for n, f in chosen:
        fm = _min_gap_minutes(f)
        if pm is not None and fm is not None and fm > pm:
            return None, (f"{FACTOR_FRAME_STARVED}: {n}'s finest bar spacing is {fm} minutes, "
                          f"coarser than the primary's {pm}; aligning it would read a bar that "
                          f"closes after the primary bar it prices"), prov
    tol = tolerance_for(p)
    aligned = [asof_align(f, p.index, tol) for _n, f in chosen]
    dense = pd.Series(True, index=p.index)
    for a in aligned:
        dense &= a["close"].notna()
    prov["alignment"] = "ASOF"
    prov["asof_tolerance_min"] = int(tol.total_seconds() // 60)
    prov["asof_rows"] = int(dense.sum())
    if int(dense.sum()) < need:
        return None, (f"{FACTOR_FRAME_STARVED}: {int(dense.sum())} primary bars carry every factor "
                      f"even as-of within {prov['asof_tolerance_min']} min (exact join "
                      f"{len(common)}), below the family's {floor}-row floor"), prov
    return aligned, "ok", prov
