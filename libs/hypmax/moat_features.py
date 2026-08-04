"""MANUFACTURED MOAT FEATURES -- the specs the asymmetry ledger ranks first, actually built.

`libs/hypmax/manufacture.propose_from_owned()` ranks what to build from data the desk ALREADY
holds, by REPLICATION DIFFICULTY rather than predictive power -- an edge on public data is an edge
everyone can find and therefore already priced. Its top entries have sat as proposals:

    liquidity_withdrawal_rate   RECONSTRUCT  moat/day 1.60  TIME-ACCRUING
    replenishment_halflife      RECONSTRUCT  moat/day 1.60  TIME-ACCRUING
    funding_vs_book_pressure    FUSE         moat/day 1.52  TIME-ACCRUING
    resting_depth_true          RECONSTRUCT  "displayed depth minus inferred iceberg residual"
    queue_position_estimate     RECONSTRUCT  "directly sizes adverse selection"

The first two exist in `moat_mine`. The rest did not. This module builds them, and every one is
RECONSTRUCT or FUSE class: a competitor with unlimited capital cannot buy them, because they are
computed from timestamps only this desk holds.

WHY THESE AND NOT MORE INDICATORS. A seventh moving average of a public candle is COLLECT-class --
replication cost roughly zero. Hidden size, queue position and funding-against-book are inferences
that require the raw tape AND the reconstruction; the barrier is the work, which is the only kind
of barrier a small desk can actually build.

EVERY FEATURE IS CAUSAL BY CONSTRUCTION. Each value at snapshot i uses only snapshots <= i and
trades that printed at or before i. That is not a convention here, it is the difference between a
feature and a description of what already happened -- and the moat screen's own history is five
alignment bugs deep.

Pure numpy. No I/O.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from libs.hypmax.moat_mine import DEPTH_KINDS, _depth_snaps

__all__ = [
    "MANUFACTURED",
    "book_pressure_vs_funding",
    "hidden_liquidity",
    "queue_depth_at_touch",
    "spread_regime_shift",
]

#: Trade rows. Binance flat `k="t"`; Bybit nests a list under `v` on `k="trades"`.
_TRADE_KINDS = ("t", "trades")
_META_KIND = "meta"


def _trade_stream(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    """(ms, signed-ish size) for every print, sorted. Size only -- direction is not published."""
    out: list[tuple[int, float]] = []
    for r in rows:
        k = r.get("k")
        if k == "t":
            try:
                out.append((int(r["t"]), float(r["q"])))
            except (KeyError, TypeError, ValueError):
                continue
        elif k == "trades":
            for tr in r.get("v") or []:
                if not isinstance(tr, dict):
                    continue
                try:
                    ms = int(tr.get("T") or r.get("t") or 0)
                    raw = tr.get("v")
                    qty = float(raw if raw is not None else (tr.get("size") or 0.0))
                except (TypeError, ValueError):
                    continue
                if ms:
                    out.append((ms, qty))
    if not out:
        return np.empty(0, dtype="int64"), np.empty(0)
    out.sort(key=lambda x: x[0])
    return (np.array([x[0] for x in out], dtype="int64"),
            np.array([x[1] for x in out], dtype="float64"))


def _volume_between(t_ms: np.ndarray, qty: np.ndarray,
                    lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """Traded size in each (lo, hi] window, by cumulative-sum difference."""
    if t_ms.size == 0:
        return np.zeros(lo.size)
    cum = np.concatenate(([0.0], np.cumsum(qty)))
    i_lo = np.searchsorted(t_ms, lo, side="right")
    i_hi = np.searchsorted(t_ms, hi, side="right")
    return cum[i_hi] - cum[i_lo]


#: Observations required before an expanding z-score means anything. A z against three points is
#: a statement about three points.
_MIN_Z_OBS = 5


def _expanding_z(x: np.ndarray) -> np.ndarray:
    """z-score of x[i] against ONLY x[:i+1] -- the causal version of `(x - x.mean()) / x.std()`.

    THIS REPLACED A FULL-SAMPLE NORMALISATION, WHICH WAS LOOKAHEAD AND MINE. Standardising a
    series against its own complete mean and standard deviation makes every value depend on values
    that had not happened yet: on a tape where funding drifts, the z at hour one is computed
    knowing what hour twenty did. It is the most common leak there is precisely because it looks
    like preprocessing rather than like a decision.

    It survived review here only because the synthetic tape publishes no funding, so the feature
    returned an empty array and the truncation test that would have caught it skipped the
    comparison. An untested branch is not a tested one.

    NaN until `_MIN_Z_OBS` finite observations exist, and wherever dispersion is still zero.
    """
    valid = np.isfinite(x)
    v = np.where(valid, x, 0.0)
    c = np.cumsum(valid.astype("float64"))
    s = np.cumsum(v)
    ss = np.cumsum(v * v)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = s / c
        var = np.maximum(ss / c - mean * mean, 0.0)
        z = (x - mean) / np.sqrt(var)
    return np.where(valid & (c >= _MIN_Z_OBS) & (var > 0), z, np.nan)


def hidden_liquidity(rows: list[dict[str, Any]], *, top_n: int = 10) -> np.ndarray:
    """Traded size MINUS the displayed size that vanished -- inferred iceberg residual.

    THE MANUFACTURE SPEC'S OWN WORDS: "displayed depth minus inferred iceberg residual. Everyone
    sees the displayed book; nobody publishes what is actually resting behind it."

    Between two snapshots, displayed top-N size falls by D and volume V prints. If V exceeds D the
    difference was filled from size that was never shown -- hidden or replenished-instantly. If V
    is far below D, the depth was PULLED rather than hit, which is the withdrawal signature and
    shows up negative here.

    Normalised by displayed depth so it is comparable across symbols and regimes. Causal: window
    (t[i-1], t[i]] uses only prints that had already happened by t[i].
    """
    snaps = _depth_snaps([r for r in rows if r.get("k") in DEPTH_KINDS])
    if len(snaps) < 3:
        return np.empty(0)
    ts = np.array([s[0] for s in snaps], dtype="int64")
    disp = np.array([float(s[2][:top_n].sum() + s[4][:top_n].sum()) for s in snaps])
    t_ms, qty = _trade_stream(rows)
    vol = _volume_between(t_ms, qty, ts[:-1], ts[1:])
    drop = disp[:-1] - disp[1:]
    denom = np.where(disp[:-1] > 0, disp[:-1], np.nan)
    return np.asarray((vol - drop) / denom, dtype="float64")


def queue_depth_at_touch(rows: list[dict[str, Any]]) -> np.ndarray:
    """Resting size at the best bid, in units of the volume that then traded.

    THE SPEC: "where our order sits in the queue, inferred from depth deltas against prints.
    Directly sizes adverse selection -- the cost model's largest unknown."

    High values mean a passive order joins a long queue and waits; low values mean it fills fast,
    which is usually because the price is about to leave. That asymmetry IS adverse selection, and
    it is unobservable without the desk's own book history.
    """
    snaps = _depth_snaps([r for r in rows if r.get("k") in DEPTH_KINDS])
    if len(snaps) < 3:
        return np.empty(0)
    ts = np.array([s[0] for s in snaps], dtype="int64")
    touch = np.array([float(s[2][0]) for s in snaps])      # best-bid resting size
    t_ms, qty = _trade_stream(rows)
    vol = _volume_between(t_ms, qty, ts[:-1], ts[1:])
    # +1 in the denominator keeps a zero-volume window finite rather than infinite: no trade is a
    # real state ("nothing came"), not an undefined one.
    return np.asarray(touch[1:] / (vol + 1e-9), dtype="float64")


def book_pressure_vs_funding(rows: list[dict[str, Any]], *, top_n: int = 10) -> np.ndarray:
    """FUSE-class: book imbalance MINUS the funding rate's implied positioning.

    THE SPEC ranks this at moat/day 1.52. Funding says where the CROWD is paying to be; the book
    says where resting size actually is. When they disagree, positioning is being carried by
    someone who is not showing it -- and a competitor needs BOTH series, timestamp-aligned, which
    is the fusion barrier.

    Returns an empty array when the venue publishes no funding (`k="meta"` with `fr`), because a
    fusion of one input is not a fusion -- and defaulting the missing leg to zero would silently
    turn this into plain imbalance wearing a better name.

    Funding is standardised by `_expanding_z`, not by its full-sample mean and standard deviation:
    see that function for the leak it replaced.
    """
    snaps = _depth_snaps([r for r in rows if r.get("k") in DEPTH_KINDS])
    fr = [(int(r["t"]), float(r["fr"])) for r in rows
          if r.get("k") == _META_KIND and r.get("fr") is not None]
    if len(snaps) < 3 or len(fr) < 2:
        return np.empty(0)
    fr.sort(key=lambda x: x[0])
    f_ms = np.array([x[0] for x in fr], dtype="int64")
    f_v = np.array([x[1] for x in fr], dtype="float64")

    ts = np.array([s[0] for s in snaps], dtype="int64")
    b = np.array([float(s[2][:top_n].sum()) for s in snaps])
    a = np.array([float(s[4][:top_n].sum()) for s in snaps])
    imb = np.divide(b - a, b + a, out=np.zeros_like(b), where=(b + a) > 0)

    # Last funding print AT OR BEFORE each snapshot -- never the next one.
    idx = np.searchsorted(f_ms, ts, side="right") - 1
    known = idx >= 0
    fv = np.where(known, f_v[np.clip(idx, 0, f_v.size - 1)], np.nan)
    return np.asarray(imb - _expanding_z(fv), dtype="float64")


def spread_regime_shift(rows: list[dict[str, Any]], *, window: int = 20) -> np.ndarray:
    """Touch spread against its own trailing median -- a regime change, not a level.

    A wide spread is not news; a spread that just became wide RELATIVE TO ITS OWN RECENT NORM is.
    The trailing window ends at the PREVIOUS snapshot, so the bar being judged never contributes
    to its own threshold -- the normalisation leak that flatters every large observation.
    """
    snaps = _depth_snaps([r for r in rows if r.get("k") in DEPTH_KINDS])
    if len(snaps) < window + 2:
        return np.empty(0)
    mid = np.array([(float(s[1][0]) + float(s[3][0])) / 2.0 for s in snaps])
    spread = np.array([float(s[3][0]) - float(s[1][0]) for s in snaps]) / np.where(mid > 0, mid,
                                                                                   np.nan)
    out = np.full(spread.size, np.nan)
    for i in range(window, spread.size):
        ref = np.median(spread[i - window:i])                # strictly prior
        out[i] = (spread[i] - ref) / ref if ref > 0 else np.nan
    return np.asarray(out[window:], dtype="float64")


#: name -> callable, in the same shape `moat_mine._EXTRACTORS` uses so the screen consumes both
#: without caring which module a mechanism came from.
MANUFACTURED = {
    "hidden_liquidity": hidden_liquidity,
    "queue_depth_at_touch": queue_depth_at_touch,
    "book_pressure_vs_funding": book_pressure_vs_funding,
    "spread_regime_shift": spread_regime_shift,
}
