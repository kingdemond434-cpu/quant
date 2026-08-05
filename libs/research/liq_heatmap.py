"""Liquidation-heatmap / cost-basis RECONSTRUCTION from data the desk already owns (R0100 axis 2).

THE MECHANISM (watchlist, CN OSS batch axis 2): clustered liquidation prices are PRE-COMMITTED
forced flow -- a long liquidated at its band MUST sell, immediately, at market. The fuel for a
cascade is therefore measurable EX-ANTE if you know where positions were entered and at what
leverage. The proprietary products (Coinglass/Hyblock class) sell exactly this surface; this
module rebuilds a defensible free construction from the desk's OWN 5-minute Binance metrics
archive (open interest + its USDT valuation), never buying the feed.

THE RECONSTRUCTION, stated honestly:
  1. COST BASIS. Positive OI deltas at bar t are attributed to entries at that bar's mark price
     (the implied mark IS in the same row: sum_open_interest_value / sum_open_interest, so the
     OI->price join is internally synchronous by construction). Negative deltas close positions
     PRO-RATA across the existing entry distribution. Because net OI hides gross churn, the
     distribution additionally CHURNS toward the current price with a configurable half-life:
     each bar, a (1 - 0.5**(1/half_life)) fraction of every old entry bucket is re-entered at
     the current bar's price. Total histogram mass therefore tracks venue OI EXACTLY (a tested
     invariant), and the half-life is the single behavioural assumption -- it is a declared
     TRIAL PARAMETER upstream, never a tuned constant.
  2. LIQUIDATION BANDS. Each entry bucket is projected to liquidation prices at the standard
     public leverage tiers (constants below, from Binance's published leverage-bracket system):
         long  liquidates near  P_entry * (1 - 1/L + mmr)
         short liquidates near  P_entry * (1 + 1/L - mmr)
     (isolated USDT-margined first-bracket approximation; funding and fee terms ignored --
     documented, they move the band by bps while the tier spacing moves it by percent).
     Every open contract has BOTH a long and a short side, so each entry bucket contributes
     symmetric long fuel (bands below entry) and short fuel (bands above entry); the ASYMMETRY
     in the features comes from where price now sits inside the historical entry distribution.
  3. FEATURES. fuel_below(x) at bar t = notional (quote units) of projected LONG liquidation
     levels within x below the current price -- ex-ante DOWN-cascade fuel; fuel_above(x)
     symmetric for shorts / UP-cascades.

Pure functions, no I/O -- materialisation lives in scripts/build_liq_heatmap.py.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# ------------------------------------------------------------------ documented constants ----
#: Standard public leverage tiers with assumed OI weights. Binance USDT-M offers up to 125x on
#: majors, but positioning surveys and every public heatmap product concentrate retail mass on
#: the round tiers below. The weights are an ASSUMPTION, declared here once, shared by every
#: variant -- the screen's proximity/half-life grid, not these weights, carries the trial
#: multiplicity. Source for the tier ladder: Binance Futures "Leverage & Margin" public table
#: (bracket-1 initial margins 1/125..1/5); mass concentrated at 10x-25x per Binance's own
#: published "most used leverage" communications.
LEVERAGE_TIERS: tuple[tuple[float, float], ...] = (
    (5.0, 0.15),
    (10.0, 0.30),
    (25.0, 0.30),
    (50.0, 0.15),
    (100.0, 0.10),
)

#: First-bracket maintenance-margin rate by symbol, Binance public leverage-bracket table
#: (BTCUSDT 0.40%, ETHUSDT 0.50%; 1% is the common first bracket for large alts). Approximation:
#: positions large enough to sit in higher brackets carry higher mmr (band moves TOWARD entry).
MMR_BY_SYMBOL: dict[str, float] = {"BTCUSDT": 0.004, "ETHUSDT": 0.005}
MMR_DEFAULT: float = 0.01


def effective_tiers(mmr: float, tiers: tuple[tuple[float, float], ...] = LEVERAGE_TIERS,
                    ) -> tuple[tuple[float, float], ...]:
    """Tier ladder intersected with what a venue's margin schedule can actually offer.

    A tier with 1/L <= mmr is unofferable (the maintenance requirement meets or exceeds the
    initial margin -- liquidation at or above entry), which is exactly why Binance caps max
    leverage lower on symbols with higher first-bracket mmr. Such tiers are DROPPED and the
    remaining weights renormalised. Raises if nothing survives -- an empty ladder is a config
    error, not a quiet zero."""
    keep = [(lv, wt) for lv, wt in tiers if 1.0 / lv > mmr]
    if not keep:
        raise ValueError(f"no leverage tier survives mmr={mmr}")
    total = sum(wt for _, wt in keep)
    return tuple((lv, wt / total) for lv, wt in keep)


def liq_price(entry: float, leverage: float, side: str, mmr: float) -> float:
    """Projected liquidation price for an isolated USDT-margined position (first bracket).

    long:  entry * (1 - 1/L + mmr)     short: entry * (1 + 1/L - mmr)
    Raises on non-positive inputs or an unknown side -- a silent 0.0 here would flow straight
    into a feature as fake fuel.
    """
    if entry <= 0 or leverage <= 0:
        raise ValueError(f"entry/leverage must be positive, got {entry}/{leverage}")
    if side == "long":
        return entry * (1.0 - 1.0 / leverage + mmr)
    if side == "short":
        return entry * (1.0 + 1.0 / leverage - mmr)
    raise ValueError(f"side must be 'long' or 'short', got {side!r}")


@dataclass(frozen=True)
class FuelResult:
    """Per-bar reconstruction output. Arrays share the input's length; the first bar is warm-up
    (histogram seeded with the whole of OI at bar-0 price -- callers must drop a declared
    warm-up window before using features for inference)."""

    below: dict[float, np.ndarray]   # proximity -> quote-notional long-liq fuel within x below
    above: dict[float, np.ndarray]   # proximity -> quote-notional short-liq fuel within x above
    mass: np.ndarray                 # histogram total (base units) -- MUST track oi (invariant)


def _bucket_grid(price: np.ndarray, bucket_bps: float) -> tuple[float, float, int]:
    """Log-price grid covering the series plus head-room for the widest liquidation offset
    (5x long band sits ~20% below entry; pad generously so no projection can leave the grid)."""
    lo = math.log(float(price.min())) - 0.35
    hi = math.log(float(price.max())) + 0.35
    w = bucket_bps / 1e4
    n = math.ceil((hi - lo) / w) + 1
    return lo, w, n


def fuel_series(price: np.ndarray, oi: np.ndarray, *, half_life_bars: float,
                proximities: tuple[float, ...],
                tiers: tuple[tuple[float, float], ...] = LEVERAGE_TIERS,
                mmr: float = MMR_DEFAULT, bucket_bps: float = 10.0) -> FuelResult:
    """Run the reconstruction over aligned price/OI arrays (same clock, one row per bar).

    price : implied mark per bar (venue snapshot clock -- caller declares provenance)
    oi    : open interest in BASE units at the same snapshots
    half_life_bars : churn half-life IN BARS (trial parameter upstream)
    proximities    : fractional windows, e.g. (0.02, 0.05)

    Refuses (raises ValueError) on: length mismatch, empty/short input, non-positive prices or
    OI -- the caller owns filtering; feeding junk in must be loud, not smoothed over.
    """
    p = np.asarray(price, dtype="float64")
    q = np.asarray(oi, dtype="float64")
    if p.shape != q.shape or p.ndim != 1:
        raise ValueError(f"price/oi must be same-shape 1-D, got {p.shape} vs {q.shape}")
    if len(p) < 2:
        raise ValueError(f"need >=2 bars, got {len(p)}")
    if not (np.all(p > 0) and np.all(q > 0)):
        raise ValueError("non-positive price or OI reached the reconstruction -- filter upstream")
    if half_life_bars <= 0:
        raise ValueError(f"half_life_bars must be positive, got {half_life_bars}")

    lo, w, n = _bucket_grid(p, bucket_bps)
    b = np.floor((np.log(p) - lo) / w).astype(np.int64)          # bucket index per bar
    if b.min() < 0 or b.max() >= n:
        raise ValueError("price escaped the bucket grid -- grid construction bug")

    # Constant integer offsets: liq price = entry * k in log space is a SHIFT, so the entry
    # buckets whose tier-L liq band lands within (p*(1-x), p] form a fixed window around b[t].
    # below window (long side, band in (p(1-x), p]):  entry bucket in (b - s_L + lo_x, b - s_L]
    # where s_L = round(log(k_long)/w) (negative -> -s_L above spot: a long whose band sits just
    # under CURRENT price entered ABOVE it) and lo_x = round(log(1-x)/w) (negative). Windows are
    # (lo, hi] half-open to match the cumsum difference cs[hi]-cs[lo].
    npx = len(proximities)
    lo_b, hi_b, lo_a, hi_a, wts = [], [], [], [], []   # per (tier x proximity) window
    for lev, wt in tiers:
        k_long = 1.0 - 1.0 / lev + mmr
        k_short = 1.0 + 1.0 / lev - mmr
        if not (0.0 < k_long < 1.0 < k_short):
            raise ValueError(f"degenerate tier {lev}x with mmr {mmr} -- use effective_tiers()")
        s_long = round(math.log(k_long) / w)
        s_short = round(math.log(k_short) / w)
        for x in proximities:
            off_lo = round(math.log(1.0 - x) / w)                # negative: x below spot
            off_hi = round(math.log(1.0 + x) / w)                # positive: x above spot
            lo_b.append(-s_long + off_lo)
            hi_b.append(-s_long)
            lo_a.append(-s_short)
            hi_a.append(-s_short + off_hi)
            wts.append(wt)
    lo_b, hi_b = np.array(lo_b), np.array(hi_b)
    lo_a, hi_a = np.array(lo_a), np.array(hi_a)
    # weight matrix folding tier weights into per-proximity rows: feature = W @ window_sums
    weight = np.zeros((npx, len(wts)))
    for j, wt in enumerate(wts):
        weight[j % npx, j] = wt

    hist = np.zeros(n)
    hist[b[0]] = q[0]                                            # seed: all OI at bar-0 price
    mass = np.empty(len(p))
    mass[0] = q[0]
    below_m = np.zeros((npx, len(p)))
    above_m = np.zeros((npx, len(p)))
    d = 0.5 ** (1.0 / half_life_bars)
    churn = 1.0 - d
    tot = q[0]
    nm1 = n - 1

    for t in range(1, len(p)):
        bt = b[t]
        # 1. churn: a (1-d) fraction of every old entry re-enters at the current price --
        #    mass-conserving, so the histogram total keeps tracking venue OI exactly.
        hist *= d
        hist[bt] += tot * churn
        # 2. OI delta: entries at this bar's price, closes pro-rata across the distribution.
        doi = q[t] - q[t - 1]
        if doi >= 0:
            hist[bt] += doi
        else:
            hist *= q[t] / q[t - 1]
        tot = q[t]
        # 3. features: windowed sums via one cumsum, tier-weighted, in quote notional at p[t].
        cs = hist.cumsum()
        mass[t] = cs[nm1]                    # exact histogram total -- the tested OI invariant
        sums_b = cs[np.clip(bt + hi_b, 0, nm1)] - cs[np.clip(bt + lo_b, 0, nm1)]
        sums_a = cs[np.clip(bt + hi_a, 0, nm1)] - cs[np.clip(bt + lo_a, 0, nm1)]
        below_m[:, t] = weight @ sums_b
        above_m[:, t] = weight @ sums_a
    below_m *= p
    above_m *= p

    return FuelResult(below={x: below_m[i] for i, x in enumerate(proximities)},
                      above={x: above_m[i] for i, x in enumerate(proximities)},
                      mass=mass)


def capture_lift(fuel: np.ndarray, event_notional: np.ndarray, *, top_frac: float = 0.20,
                 min_events: int = 50) -> dict[str, float]:
    """DESCRIPTIVE validation stat (not a screen): share of realised liquidation notional that
    fell in the top `top_frac` fuel bars, versus the unconditional baseline `top_frac`.

    lift > 1 means the reconstruction concentrates realised forced flow better than chance.
    Returns {"lift": .., "share": .., "n_event_bars": ..}; refuses (lift nan + reason) below
    `min_events` event bars -- an unpowered lift is decoration, not validation.
    """
    f = np.asarray(fuel, dtype="float64")
    e = np.asarray(event_notional, dtype="float64")
    if f.shape != e.shape or f.ndim != 1:
        raise ValueError(f"fuel/events must be same-shape 1-D, got {f.shape} vs {e.shape}")
    n_event_bars = int((e > 0).sum())
    total = float(e.sum())
    if n_event_bars < min_events or total <= 0:
        return {"lift": float("nan"), "share": float("nan"),
                "n_event_bars": n_event_bars, "refused": 1.0}
    k = max(round(top_frac * len(f)), 1)
    thresh = np.partition(f, -k)[-k]
    share = float(e[f >= thresh].sum() / total)
    return {"lift": share / top_frac, "share": share,
            "n_event_bars": n_event_bars, "refused": 0.0}
