"""F15 -- WHO ELSE IS IN THIS TAPE, and what happens to an edge as they learn it.

THE PRINCIPAL, 2026-09-12:

    Model other participants -- dealer hedging, CTA flows, retail crowding, benchmark flows,
    producer hedging, systematic rebalance, vol-control funds, market makers, diffusion of public
    strategies -- and estimate how an edge decays as competitors learn it and how OWN size changes
    the market.

THE GAP, AS THE LEDGER STATES IT: crowding hazard exists and is useful; participant modelling does
not. And the desk's own mechanism contract already demands a PAYER -- a participant who must
transact regardless of price -- for every hypothesis. So the desk requires every candidate to name
an opponent and has never measured one.

WHAT CAN HONESTLY BE MEASURED FROM WHAT THIS BOX HOLDS. Not positioning: the COT and macro axes are
empty, so retail crowding and producer hedging are UNMEASURED and say so. What IS measurable is
each participant class's FOOTPRINT in the tape -- the pattern it must leave if it is there at all:

    systematic_rebalance  month-end and quarter-end, when index and balanced funds must trade a
                          calendar rather than a price
    vol_control           after a volatility spike, vol-target funds must reduce exposure, so the
                          spike should be followed by more selling pressure than a random bar
    cta_trigger           Donchian 20/55/100 breaks are the published trend-following levels; if
                          CTAs are there, continuation after them exceeds continuation after a
                          matched random level
    dealer_gamma          on option expiry Fridays, hedged dealers pin price toward strikes, so
                          closes should sit nearer round numbers than on other days
    round_number_magnet   the same clustering on ordinary days, which is retail and resting
                          orders rather than dealers
    market_maker          spread and range at session handovers, where the maker of record changes

EVERY FOOTPRINT IS SCORED AGAINST A MATCHED NULL. A month-end effect measured against the
unconditional mean is mostly the fact that month-ends are five days and the sample is a thousand;
each effect here is compared to a block-permuted null that keeps the series' own autocorrelation,
so what survives is the calendar and not the volatility clustering.

AND THE CLAUSE THAT MATTERS MOST: EDGE DECAY. "How an edge decays as competitors learn it" is
measurable on this desk's own certificates -- fit expectancy against calendar time per family and
report the slope. A mechanism whose edge is falling is being learned; one whose edge is flat is
either private or was never there.

OWN SIZE CHANGING THE MARKET is UNMEASURED and belongs to F21. It needs fills at different sizes
and the live book holds 16 deals across 3 days.

    python desks/mt5/research/market_ecology.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNI = DESK / "data" / "universe"
SLEEVES = DESK / "data" / "sleeves.json"
AXES = DESK / "data" / "axes"
SHADOW = (DESK / "reports" / "shadow" / "shadow_state.json",
          DESK / "reports" / "shadow" / "qquant_shadow_state.json",
          DESK / "reports" / "shadow" / "scalp_shadow_state.json")
OUT = DESK / "reports" / "MARKET_ECOLOGY.json"

BARS = 8000
MAX_SYMBOLS = 12

#: Permutation draws and the block length that keeps volatility clustering intact. An i.i.d.
#: shuffle makes every calendar effect look significant, which is exactly how a desk convinces
#: itself that month-end is an edge.
NULL_DRAWS = 400
NULL_BLOCK = 24

#: Donchian lookbacks, in HOURS. 20/55/100 days are the published trend-following parameters --
#: Turtle and its descendants -- which is the point: a CTA footprint should appear at the levels
#: people actually trade, not at levels this desk picked.
CTA_LOOKBACKS_DAYS: tuple[int, ...] = (20, 55, 100)

SEED = 20260912


def _live_symbols(limit: int = MAX_SYMBOLS) -> list[str]:
    try:
        doc = json.loads(SLEEVES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc if isinstance(doc, list) else (doc.get("sleeves") or [])
    out: list[str] = []
    for r in rows:
        if isinstance(r, dict) and str(r.get("status", "")).upper() == "LIVE":
            s = str(r.get("symbol") or "").strip()
            if s and s not in out:
                out.append(s)
    return out[:limit]


@lru_cache(maxsize=64)
def _frame(symbol: str) -> Any:
    """The symbol's last BARS H1 bars, read once per pass: the F1 footprint reads the same
    thirteen peer frames for each of its seven targets."""
    try:
        import pandas as pd
    except ImportError:
        return None
    p = UNI / f"{symbol}_H1.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
    except (OSError, ValueError):
        return None
    if "close" not in df.columns or len(df) < 2000:
        return None
    return df.tail(BARS)


def _null_p(observed: float, sample: Any, stat: Any) -> dict[str, Any]:
    """Where the observed effect sits in a BLOCK-permuted null of the same series."""
    import numpy as np
    rng = np.random.default_rng(SEED)
    a = np.asarray(sample, dtype=float)
    a = a[np.isfinite(a)]
    n = a.size
    if n < NULL_BLOCK * 8 or not math.isfinite(observed):
        return {"status": "UNMEASURED", "why": f"{n} usable bar(s) -- too few for a block null"}
    nb = n // NULL_BLOCK
    blocks = a[:nb * NULL_BLOCK].reshape(nb, NULL_BLOCK)
    draws: list[float] = []
    for _ in range(NULL_DRAWS):
        perm = blocks[rng.permutation(nb)].reshape(-1)
        try:
            v = float(stat(perm))
        except Exception:
            continue
        if math.isfinite(v):
            draws.append(v)
    if not draws:
        return {"status": "UNMEASURED", "why": "no finite null draw"}
    arr = np.asarray(draws, dtype=float)
    p = float(np.mean(np.abs(arr) >= abs(observed)))
    return {"status": "OK", "observed": round(observed, 8),
            "null_mean": round(float(np.mean(arr)), 8),
            "null_sd": round(float(np.std(arr)), 8),
            "p_two_sided": round(p, 4),
            "z": (round((observed - float(np.mean(arr))) / float(np.std(arr)), 3)
                  if float(np.std(arr)) > 0 else None)}


# ------------------------------------------------------------------ participant footprints

def _systematic_rebalance(df: Any, r: Any) -> dict[str, Any]:
    """Month-end and quarter-end: funds that must trade a calendar rather than a price."""
    import numpy as np
    import pandas as pd
    idx = pd.DatetimeIndex(df.index)
    days = idx.normalize()
    # `days == ...` on two DatetimeIndexes returns a plain ndarray, not a Series -- the first run
    # died on .to_numpy(). Compared through a Series so the result is a Series either way.
    ds = pd.Series(days, index=range(len(days)))
    last_of_month = ds.groupby([days.year, days.month]).transform("max")
    is_me = (ds == last_of_month).to_numpy()
    a = np.asarray(r, dtype=float)
    m = np.isfinite(a)
    if is_me[m].sum() < 40:
        return {"status": "UNMEASURED", "why": "fewer than 40 month-end bars"}
    diff = float(np.mean(np.abs(a[m][is_me[m]])) - np.mean(np.abs(a[m][~is_me[m]])))
    share = float(is_me[m].mean())

    def stat(x: Any) -> float:
        k = max(1, int(len(x) * share))
        return float(np.mean(np.abs(x[:k])) - np.mean(np.abs(x[k:])))

    return {"participant": "systematic_rebalance / index and balanced funds",
            "footprint": "absolute return on the last trading day of a month vs every other day",
            "effect": round(diff, 8), "n_month_end_bars": int(is_me[m].sum()),
            "null": _null_p(diff, a[m], stat),
            "reads": ("a fund tracking an index must trade the calendar whatever the price is. "
                      "If nobody is doing that here the month-end bar is an ordinary bar.")}


def _vol_control(r: Any) -> dict[str, Any]:
    """After a vol spike, vol-target funds must cut. Does the tape show forced selling?"""
    import numpy as np
    a = np.asarray(r, dtype=float)
    a = a[np.isfinite(a)]
    if a.size < 1000:
        return {"status": "UNMEASURED", "why": "fewer than 1000 usable bars"}
    import pandas as pd
    s = pd.Series(a)
    rv = s.rolling(24).std()
    hi = rv >= rv.quantile(0.90)
    nxt = s.shift(-24).rolling(24).sum().shift(0)
    sel = nxt[hi.fillna(False)].dropna()
    rest = nxt[~hi.fillna(False)].dropna()
    if len(sel) < 100 or len(rest) < 100:
        return {"status": "UNMEASURED", "why": "too few post-spike windows"}
    diff = float(sel.mean() - rest.mean())
    share = float(len(sel) / (len(sel) + len(rest)))

    def stat(x: Any) -> float:
        k = max(1, int(len(x) * share))
        return float(np.mean(x[:k]) - np.mean(x[k:]))

    return {"participant": "vol-control / risk-parity funds",
            "footprint": ("24h return AFTER a top-decile volatility window, against every other "
                          "window -- a vol-target fund must reduce exposure into a spike"),
            "effect": round(diff, 8), "n_post_spike": len(sel),
            "null": _null_p(diff, a, stat),
            "reads": ("a NEGATIVE effect is the footprint: forced selling after a spike. A "
                      "positive one says the spike is bought, which is a different ecology.")}


def _cta_trigger(df: Any) -> dict[str, Any]:
    """Donchian 20/55/100-day breaks -- the levels trend followers actually publish."""
    import numpy as np
    c = df["close"].astype(float)
    out: list[dict[str, Any]] = []
    for d in CTA_LOOKBACKS_DAYS:
        w = d * 24
        if len(c) < w * 2 + 200:
            continue
        hi = c.rolling(w).max()
        brk = (c >= hi) & (c.shift(1) < hi.shift(1))
        fwd = np.log(c).diff(24).shift(-24)
        on = fwd[brk.fillna(False)].dropna()
        off = fwd[~brk.fillna(False)].dropna()
        if len(on) < 30:
            continue
        diff = float(on.mean() - off.mean())
        share = float(len(on) / max(len(on) + len(off), 1))

        def stat(x: Any, _s: float = share) -> float:
            k = max(1, int(len(x) * _s))
            return float(np.mean(x[:k]) - np.mean(x[k:]))

        out.append({"lookback_days": d, "n_breaks": len(on),
                    "continuation_24h": round(diff, 8),
                    "null": _null_p(diff, np.asarray(fwd.dropna(), dtype=float), stat)})
    if not out:
        return {"status": "UNMEASURED", "why": "not enough history for a Donchian break sample"}
    return {"participant": "trend followers / CTAs",
            "footprint": ("24h continuation after a Donchian break, at the 20/55/100-day "
                          "lookbacks trend following actually publishes"),
            "levels": out,
            "reads": ("the lookbacks are theirs, not ours. A continuation that appears only at "
                      "20 and not at 55 or 100 is a different population from one that appears "
                      "at all three.")}


def _dealer_gamma(df: Any) -> dict[str, Any]:
    """Expiry-Friday pinning: hedged dealers pull price toward strikes, which are round."""
    import numpy as np
    import pandas as pd
    c = df["close"].astype(float)
    idx = pd.DatetimeIndex(df.index)
    # Third Friday of the month -- the standard listed expiry.
    is_fri = idx.dayofweek == 4
    third = is_fri & (idx.day >= 15) & (idx.day <= 21)
    step = _round_step(float(c.median()))
    scaled = (c / step).to_numpy()
    dist = np.abs(scaled - np.round(scaled))
    m = np.isfinite(dist)
    if third[m].sum() < 40:
        return {"status": "UNMEASURED", "why": "fewer than 40 expiry-Friday bars"}
    diff = float(np.mean(dist[m][third[m]]) - np.mean(dist[m][~third[m]]))
    share = float(third[m].mean())

    def stat(x: Any) -> float:
        k = max(1, int(len(x) * share))
        return float(np.mean(x[:k]) - np.mean(x[k:]))

    return {"participant": "dealers hedging listed options",
            "footprint": ("distance from the nearest round level on the third Friday of a month "
                          "vs every other bar; NEGATIVE means closer, i.e. pinned"),
            "round_step": step, "effect": round(diff, 8),
            "n_expiry_bars": int(third[m].sum()),
            "null": _null_p(diff, dist[m], stat),
            "reads": ("a hedged dealer short gamma must buy weakness and sell strength into "
                      "expiry. The footprint is closes sitting nearer strikes, and strikes are "
                      "round.")}


def _round_step(level: float) -> float:
    """The round level that matters at this price scale: 0.0050 for FX, 5.0 for gold."""
    if level <= 0:
        return 1.0
    mag = 10 ** math.floor(math.log10(level))
    return float(mag / 200.0)


def _round_magnet(df: Any) -> dict[str, Any]:
    """Clustering near round numbers on ORDINARY days -- resting orders, not dealers."""
    import numpy as np
    c = df["close"].astype(float)
    step = _round_step(float(c.median()))
    scaled = (c / step).to_numpy()
    frac = scaled - np.floor(scaled)
    frac = frac[np.isfinite(frac)]
    if frac.size < 1000:
        return {"status": "UNMEASURED", "why": "fewer than 1000 usable closes"}
    # Under no clustering the fractional part is uniform. Chi-square over ten bins measures the
    # departure, and a permutation of the SERIES cannot change it -- so the null here is the
    # uniform distribution itself, stated rather than bootstrapped.
    hist, _ = np.histogram(frac, bins=10, range=(0.0, 1.0))
    exp = frac.size / 10.0
    chi2 = float(np.sum((hist - exp) ** 2 / exp))
    return {"participant": "resting retail and institutional limit orders",
            "footprint": ("chi-square of the close's fractional position between round levels, "
                          "against the uniform distribution it would follow if nobody placed "
                          "orders at round numbers"),
            "round_step": step, "chi2_10bins": round(chi2, 3),
            "critical_5pct": 16.92, "n": int(frac.size),
            "clustered": bool(chi2 > 16.92),
            "reads": ("9 degrees of freedom, so 16.92 is the 5% point. This null is the uniform "
                      "distribution and is stated rather than bootstrapped: permuting the series "
                      "cannot change a histogram of its own values.")}


def _market_maker(df: Any) -> dict[str, Any]:
    """Session handovers, where the maker of record changes and the spread says so."""
    import numpy as np
    import pandas as pd
    if "spread" not in df.columns or float(df["spread"].abs().max() or 0) <= 0:
        rng_ = ((df["high"].astype(float) - df["low"].astype(float))
                / df["close"].astype(float))
        basis = "bar RANGE, because the feed records spread 0 on every bar"
    else:
        rng_ = df["spread"].astype(float)
        basis = "recorded spread"
    idx = pd.DatetimeIndex(df.index)
    # THE BASELINE IS THE TWO HOURS BEFORE EACH HANDOVER, NOT "every other hour".
    #
    # The first run compared 07:00/13:00/21:00 against all 21 remaining hours and reported a
    # HUGE negative effect on 11 of 12 symbols -- spreads tighter at handovers. That is real
    # arithmetic and the wrong question: the all-hours baseline contains the daily rollover,
    # where spreads blow out by an order of magnitude, so the contrast was measuring "handovers
    # are not the rollover". A local contrast against the immediately preceding two hours
    # isolates the handover itself, which is what the participant claim is about.
    hours = idx.hour.to_numpy()
    handover = np.isin(hours, [7, 13, 21])
    baseline = np.isin(hours, [5, 6, 11, 12, 19, 20])
    a = np.asarray(rng_, dtype=float)
    m = np.isfinite(a)
    if handover[m].sum() < 100 or baseline[m].sum() < 100:
        return {"status": "UNMEASURED",
                "why": "fewer than 100 bars in the handover or its local baseline"}
    diff = float(np.mean(a[m][handover[m]]) - np.mean(a[m][baseline[m]]))
    pool = a[m][handover[m] | baseline[m]]
    share = float(handover[m].sum() / max(int(handover[m].sum() + baseline[m].sum()), 1))

    def stat(x: Any) -> float:
        k = max(1, int(len(x) * share))
        return float(np.mean(x[:k]) - np.mean(x[k:]))

    return {"participant": "market makers at the session handover",
            "footprint": (f"{basis} at 07:00, 13:00 and 21:00 UTC against the TWO HOURS BEFORE "
                          f"each (05-06, 11-12, 19-20) -- a local contrast, not a whole-day one"),
            "effect": round(diff, 8), "basis": basis,
            "baseline": "the two hours preceding each handover",
            "null": _null_p(diff, pool, stat),
            "reads": ("the maker of record changes at a handover and prices the risk of a book "
                      "it has not seen. A desk that trades those hours pays for that. Compared "
                      "against ALL other hours this test measures the daily rollover instead, "
                      "where spreads blow out by an order of magnitude.")}


# ---------------------------------------------------------------------------- flow pressure

#: F1's donation ledger: the cells already donated, so the hourly --apply donates each once.
F1_STATE = DESK / "data" / "f1_idio_volume_state.json"
F1_SOURCE = "f1_idio_volume"


def _flow_pressure(symbol: str, holds: tuple[int, ...] = (1, 2, 4),
                   z_threshold: float = 3.0) -> dict[str, Any]:
    """GAP_MAP row 42 / F1: does a tick-volume burst peculiar to this instrument retrace?

    The footprint of an inventory-laden dealer: after the cross-sectional activity factor and
    the hour-of-week rhythm are removed (`family_idio_volume.idio_volume_z`), a spike bar's move
    should be partly given back over the next hours. The statistic is the mean forward return
    from the next bar's open, signed AGAINST the spike bar's move; the null block-permutes the
    same signed-return series, so a spike landing on a random stretch of the same tape -- with
    its own volatility clustering -- is what the observed effect has to beat.
    """
    import numpy as np
    from mt5desk.family_idio_volume import DEFAULT_PEERS, idio_volume_z

    df = _frame(symbol)
    if df is None:
        return {"status": "UNMEASURED", "why": f"no usable H1 history for {symbol}"}
    peers = [f for f in (_frame(p) for p in DEFAULT_PEERS if p != symbol) if f is not None]
    z = idio_volume_z(df, peers)
    if z is None:
        return {"status": "UNMEASURED",
                "why": f"{len(peers)} peer(s) with H1 tick volume -- the factor needs at least 4"}
    o = df["open"].astype(float).to_numpy()
    c = df["close"].astype(float).to_numpy()
    zv = z.to_numpy()
    sign = -np.sign(c - o)
    out: dict[str, Any] = {"participant": "inventory-laden dealer absorbing idiosyncratic flow",
                           "footprint": ("log tick volume regressed on the peer factor, "
                                         "residual z-scored within hour of week; spike z > "
                                         f"{z_threshold:g}, faded from the next bar's open"),
                           "n_spikes": int(np.sum(np.nan_to_num(zv) > z_threshold)),
                           "holds": {}}
    for h in holds:
        fwd = np.full(len(c), np.nan)
        if len(c) > h + 1:
            fwd[:-h - 1] = (c[h:-1] - o[1:-h]) / o[1:-h] if h > 0 else np.nan
        signed = sign * fwd
        spike = np.nan_to_num(zv) > z_threshold
        ok = np.isfinite(signed)
        if int((spike & ok).sum()) < 20:
            out["holds"][str(h)] = {"status": "UNMEASURED",
                                    "why": f"{int((spike & ok).sum())} spike(s) with a "
                                           f"{h}-bar forward return; 20 needed"}
            continue
        observed = float(np.mean(signed[spike & ok]))
        mask = spike[ok]
        pool = signed[ok]

        def stat(x: Any, _m: Any = mask) -> float:
            return float(np.mean(x[_m[:len(x)]])) if _m[:len(x)].any() else float("nan")

        out["holds"][str(h)] = {"effect": round(observed, 8),
                                "n": int((spike & ok).sum()),
                                "null": _null_p(observed, pool, stat)}
    head = out["holds"].get("2") or {}
    out["effect"] = head.get("effect")
    out["null"] = head.get("null")
    return out


def donate_f1(apply: bool) -> dict[str, Any]:
    """Donate every F1 cell not donated before: one trial each, charged at the docket."""
    from mt5desk.family_idio_volume import f1_cells
    cells = f1_cells()
    try:
        state = json.loads(F1_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    done = set(state.get("donated") or [])

    def ident(c: dict[str, Any]) -> str:
        return json.dumps({"symbol": c["symbol"], "family": c["family"],
                           "params": c["params"]}, sort_keys=True)

    new = [c for c in cells if ident(c) not in done]
    out: dict[str, Any] = {"cells": len(cells), "new": len(new),
                           "already": len(cells) - len(new)}
    if not apply or not new:
        return out
    import proposer_common as pc  # type: ignore[import-not-found]
    path = pc.donate(F1_SOURCE, new, tests_run=len(new))
    out["path"] = str(path) if path else None
    out["donation"] = {k: pc.LAST_DONATION.get(k)
                       for k in ("donated", "refused_unstamped", "refused_wrong_lane")}
    if path:
        state["donated"] = sorted(done | {ident(c) for c in new})
        state["updated_utc"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
        F1_STATE.parent.mkdir(parents=True, exist_ok=True)
        F1_STATE.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------- edge decay

def _edge_decay() -> dict[str, Any]:
    """Is the desk's own measured edge falling over calendar time? That is competitors learning.

    THE ONLY CLAUSE OF F15 THE DESK CAN ANSWER ABOUT ITSELF. Footprints say who else is in the
    tape; this says whether they have found what we found.
    """
    rows: list[dict[str, Any]] = []
    for p in SHADOW:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for key, r in (d or {}).items():
            if not isinstance(r, dict):
                continue
            e, n = r.get("exp_r"), r.get("n")
            start = r.get("first_entry") or r.get("forward_start")
            if isinstance(e, (int, float)) and isinstance(n, (int, float)) and n >= 8 and start:
                rows.append({"clock": key, "exp_r": float(e), "n": int(n),
                             "started": str(start)[:10],
                             "family": key.split(".")[-1] if "." in key else key})
    if len(rows) < 8:
        return {"status": "UNMEASURED", "n_clocks": len(rows),
                "why": (f"only {len(rows)} clock(s) carry an expectancy, a trade count and a "
                        f"start date. Edge decay is a SLOPE and a slope needs a spread of start "
                        f"dates; with this few the answer would be one clock's noise.")}
    rows.sort(key=lambda r: r["started"])
    import numpy as np
    x = np.arange(len(rows), dtype=float)
    y = np.asarray([r["exp_r"] for r in rows], dtype=float)
    xm, ym = x.mean(), y.mean()
    denom = float(((x - xm) ** 2).sum())
    slope = float(((x - xm) * (y - ym)).sum() / denom) if denom > 0 else 0.0
    resid = y - (ym + slope * (x - xm))
    se = (float(np.sqrt((resid ** 2).sum() / max(len(rows) - 2, 1) / denom))
          if denom > 0 else float("nan"))
    return {"status": "OK", "n_clocks": len(rows),
            "slope_exp_r_per_clock_in_start_order": round(slope, 8),
            "standard_error": None if not math.isfinite(se) else round(se, 8),
            "t": None if not math.isfinite(se) or se == 0 else round(slope / se, 3),
            "earliest": rows[0]["started"], "latest": rows[-1]["started"],
            "caveat": ("clocks are ordered by START DATE, not measured over a common window, so "
                       "this is a cohort slope rather than a decay curve for one mechanism. It "
                       "answers 'is what we are finding now worth less than what we found "
                       "before', which is the competitive question."),
            "reads": ("a NEGATIVE slope is the diffusion of public strategies: later cohorts "
                      "earn less because the mechanism is being learned. A flat slope says the "
                      "edge is private, or was never there.")}


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    try:
        import numpy as np
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"numpy unavailable ({exc})"}

    per_symbol: dict[str, Any] = {}
    for sym in _live_symbols():
        df = _frame(sym)
        if df is None:
            continue
        r = np.log(df["close"].astype(float)).diff().dropna()
        per_symbol[sym] = {
            "systematic_rebalance": _systematic_rebalance(df.iloc[1:], r),
            "vol_control": _vol_control(r),
            "cta_trigger": _cta_trigger(df),
            "dealer_gamma": _dealer_gamma(df),
            "round_number_magnet": _round_magnet(df),
            "market_maker": _market_maker(df),
        }
    # F1 FLOW PRESSURE (GAP_MAP row 42) on its own target set, whatever is live: the footprint
    # is measured where the F1 cells trade, not only where the book already is.
    from mt5desk.family_idio_volume import F1_SYMBOLS
    flow = {sym: _flow_pressure(sym) for sym in F1_SYMBOLS}
    if not per_symbol and not any(v.get("holds") for v in flow.values()):
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": "no live symbol has usable H1 history on this box"}
    for sym, v in flow.items():
        per_symbol.setdefault(sym, {})["flow_pressure"] = v

    # WHAT SURVIVED ITS OWN NULL. A footprint that does not is a shape in the noise, and the
    # count of those is the honest headline rather than the list of everything measured.
    detected: list[dict[str, Any]] = []
    for sym, row in per_symbol.items():
        for name, v in row.items():
            if not isinstance(v, dict):
                continue
            nul = v.get("null")
            if isinstance(nul, dict) and nul.get("status") == "OK" \
                    and float(nul.get("p_two_sided", 1.0)) <= 0.05:
                detected.append({"symbol": sym, "participant_class": name,
                                 "participant": v.get("participant"),
                                 "effect": v.get("effect"), "p": nul.get("p_two_sided"),
                                 "z": nul.get("z")})
            if name == "cta_trigger":
                for lv in (v.get("levels") or []):
                    n2 = lv.get("null") or {}
                    if n2.get("status") == "OK" and float(n2.get("p_two_sided", 1.0)) <= 0.05:
                        detected.append({"symbol": sym, "participant_class": "cta_trigger",
                                         "participant": v.get("participant"),
                                         "lookback_days": lv.get("lookback_days"),
                                         "effect": lv.get("continuation_24h"),
                                         "p": n2.get("p_two_sided"), "z": n2.get("z")})
            if name == "round_number_magnet" and v.get("clustered"):
                detected.append({"symbol": sym, "participant_class": "round_number_magnet",
                                 "participant": v.get("participant"),
                                 "effect": v.get("chi2_10bins"), "p": "<0.05 (chi2 vs uniform)"})
    detected.sort(key=lambda r: str(r["participant_class"]))

    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK",
        "n_symbols": len(per_symbol),
        "symbols": per_symbol,
        "detected": detected,
        "n_detected": len(detected),
        "edge_decay": _edge_decay(),
        "unmeasured_participants": {
            "retail_crowding": ("needs positioning data. The COT and macro axes are empty on this "
                                "box, so there is nothing to read a crowd off. The round-number "
                                "magnet is a WEAK proxy for resting retail orders and is not the "
                                "same measurement."),
            "producer_hedging": ("needs commercial positioning -- the COT commercial series -- "
                                 "which is the same empty axis."),
            "own_size_impact": ("belongs to F21 and needs fills at different sizes. The live book "
                                "holds 16 deals across 3 days; an impact curve off that would be "
                                "a line through one point."),
        },
        "method": (
            "every footprint is scored against a BLOCK-permuted null of its own series, which "
            "keeps the volatility clustering a calendar effect would otherwise borrow. A "
            "month-end effect measured against the unconditional mean is mostly the fact that "
            "month-ends are rare. The round-number test is the exception and says so: its null "
            "is the uniform distribution, because permuting a series cannot change a histogram "
            "of its own values."),
        "boundary": (
            "NOTHING HERE TRADES OR SIZES. A detected footprint is evidence that a participant "
            "class is present, never a signal; anything built on one faces the same ten gates."),
        "why": (
            "this desk's mechanism contract already demands a PAYER -- a participant who must "
            "transact regardless of price -- for every hypothesis. It has required every "
            "candidate to name an opponent and never measured one."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if doc.get("status") != "OK":
        print(f"market ecology: {doc.get('status')} -- {doc.get('why')}")
        return 0
    print(f"market ecology: OK   {doc['n_symbols']} symbol(s), "
          f"{doc['n_detected']} footprint(s) survived their own null")
    seen: dict[str, int] = {}
    for d in doc["detected"]:
        seen[str(d["participant_class"])] = seen.get(str(d["participant_class"]), 0) + 1
    for k, v in sorted(seen.items(), key=lambda t: -t[1]):
        print(f"  {k:<24} detected on {v} symbol-test(s)")
    for d in doc["detected"][:10]:
        print(f"    {d['symbol']:<10} {d['participant_class']:<22} effect {d['effect']} "
              f"p={d['p']}")
    ed = doc["edge_decay"]
    if ed.get("status") == "OK":
        print(f"  edge decay: slope {ed['slope_exp_r_per_clock_in_start_order']:+.6f} R per "
              f"clock in start order, t={ed['t']} over {ed['n_clocks']} clock(s) "
              f"({ed['earliest']} -> {ed['latest']})")
    else:
        print(f"  edge decay: {ed.get('status')} -- {str(ed.get('why'))[:130]}")
    for k, v in doc["unmeasured_participants"].items():
        print(f"  UNMEASURED {k:<20} {v[:90]}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    # THE F1 CELLS GO TO THE GAUNTLET WHATEVER THE FOOTPRINT SAYS: the footprint is evidence that
    # the participant is present, never a filter on which hypotheses are judged (L1.60).
    doc["f1_donation"] = donate_f1(apply=True)
    print(f"  F1 idio-volume cells: {doc['f1_donation']}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
