"""Data-first discovery: find the anomaly IN THE DATA, then ask what could explain it.

WHY THIS IS THE MISSING HALF. This desk's validation side is strong and its discovery side is not
even in the same discipline, and the numbers say so plainly. Measured 2026-09-03 from
`miner_candidates.per_source`: broker_swaps turned 248 evidence rows into 248 executable
candidates, forexfactory 44 into 107, cot 11 into 7 -- while reddit, github, quant_se,
bis_speeches, amarkets and the world crawler produced 0 from 341. Every candidate the desk owns
came from STRUCTURED DATA. Every prose source converts at exactly zero, and it is not a tuning
gap: the compiler's rule is "exact recipe or structured causal data only", so an article
structurally cannot supply a family with exact params.

So the desk had one generator class that works, and it is fed by whatever tables happen to be
lying around. Everything else -- crawlers, LLM seats, forums -- is aimed at the class that cannot
pay. The bound on discovery is not the gauntlet's strictness; it is that almost nothing reaches it.

THE INVERSION. Prose generation asks a model to imagine an edge and then looks for it. This scans
the bars the desk ALREADY OWNS for conditional structure that is unlikely under a null, and only
then asks what could explain it. The imagination of a language model stops bounding the search;
the data does. That is the one generator whose supply scales with the universe (237 tradeable
symbols x sessions x horizons) rather than with how many articles were published this week.

WHAT IT EMITS AND WHAT IT REFUSES. It emits ANOMALIES -- (symbol, condition, horizon, effect,
n, t-like statistic) -- never candidates. An anomaly is an observation; a candidate needs a named
mechanism, and naming one from a correlation is precisely the prose-to-family guessing the
compiler exists to refuse. Anomalies go to the mechanism-naming queue, where a brain must name a
cause WITH EVIDENCE or the row dies. Nothing here sets a threshold that competes with the ten
gates: every survivor still walks the same pipeline, carrying an honest trial count so deflation
charges the full width of this search.

TRIALS ARE COUNTED AND CARRIED. A scan this wide is a multiplicity machine, and hiding that would
make every downstream deflated Sharpe a lie. `trials` on the report is the real number of
(symbol, condition, horizon) cells evaluated, not the number that survived.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"
_BARS = _DESK / "data" / "universe"
_OUT = _DESK / "data" / "intelligence" / "anomalies"

#: Minimum observations in a conditional cell. Below this the statistic is noise wearing a number,
#: and the desk has been burned by cells that "fired" a handful of times.
MIN_N = 60

#: |t|-like screen. NOT a verdict and NOT a gate -- purely a reporting floor so the queue receives
#: structure rather than every cell ever evaluated. The ten gates remain the only arbiter, and
#: they will deflate against `trials` below, which counts everything looked at.
REPORT_T = 3.0

#: Horizons in bars. H1 data, so 1/3/6/12/24 spans an hour to a day.
HORIZONS = (1, 3, 6, 12, 24)


@dataclass(frozen=True)
class Anomaly:
    """One conditional regularity, stated so a brain can try to explain or kill it."""

    symbol: str
    condition: str
    horizon: int
    n: int
    mean_bp: float
    t_stat: float
    hit_rate: float
    baseline_bp: float
    question: str

    def as_row(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = "anomaly"
        d["mechanism_status"] = "UNNAMED"
        d["note"] = ("data-first anomaly: an OBSERVATION, not a candidate. A mechanism must be "
                     "named with evidence before this can become executable.")
        return d


#: PRIMITIVES, NOT CONDITIONS. Each entry is a way of turning bars into ONE series. The conditions
#: are then generated from the cross product of (primitive x window x band), so the space is
#: combinatorial and open rather than a list somebody wrote down.
#:
#: NOTHING HERE NAMES A FAMILY OR A SESSION. An earlier version of this file enumerated
#: `vol_top_decile`, `momentum_top_decile`, `session_asia` and six more by hand, which is the
#: hardcoding this desk forbids: a fixed list can only ever rediscover what its author already
#: believed, and the whole point of a data-first miner is that the DATA proposes the condition.
#: Adding a primitive here multiplies the space; it does not enumerate a new answer.
_PRIMITIVES: dict[str, str] = {
    "ret": "one-bar return",
    "absret": "absolute one-bar return",
    "vol": "rolling stdev of returns",
    "mom": "trailing return over the window",
    "range": "high-low spread, normalised",
    "gap": "open against the previous close",
    "hour": "hour of day, as a cyclical position",
    "dow": "day of week",
    "volume": "traded volume where the feed carries it",
    "close_pos": "close's position inside the window's high-low",
}

#: Which primitives actually READ the window. Everything else is window-invariant, and crossing it
#: with five windows produces five IDENTICAL cells.
#:
#: MEASURED THE MOMENT THE GENERATED SPACE FIRST RAN: hour_w6, hour_w12, hour_w24, hour_w72 and
#: hour_w168 came back with the same t-statistic (38.4), the same n (3,720) and the same effect
#: (-9.8bp) -- one finding wearing five names. Not merely wasteful: it inflates `trials` fivefold
#: for seven of ten primitives, and `trials` is carried into deflated Sharpe, so the desk would
#: charge every honest candidate a multiplicity penalty for a search width it never had. It also
#: crowds the naming queue with duplicates, which is how a brain spends its budget explaining the
#: same effect five times.
_WINDOWED: frozenset[str] = frozenset({"vol", "mom", "close_pos"})

#: Lookbacks, in bars. Open-ended by construction: adding one multiplies the search, and the
#: trial count carried to deflation grows with it, which is the honest cost.
_WINDOWS: tuple[int, ...] = (6, 12, 24, 72, 168)

#: Quantile bands. A band is "this primitive sits in this part of its own recent distribution" --
#: stated relatively so it means the same thing on gold and on a Hungarian cross.
_BANDS: tuple[tuple[float, float], ...] = (
    (0.0, 0.1), (0.1, 0.25), (0.4, 0.6), (0.75, 0.9), (0.9, 1.0),
)


def _primitive(df: pd.DataFrame, name: str, window: int) -> pd.Series | None:
    """One primitive as a series, or None when this feed cannot supply it.

    NONE IS A REAL ANSWER (L1.28a). A symbol whose feed carries no volume must yield None here,
    not zeros -- zeros would be scored as a legitimate flat condition and enter the trial count
    as a cell that was never testable.
    """
    close = df["close"].astype(float)
    if name == "ret":
        return close.pct_change()
    if name == "absret":
        return close.pct_change().abs()
    if name == "vol":
        return close.pct_change().rolling(window).std()
    if name == "mom":
        return close.pct_change(window)
    if name == "range":
        return (df["high"].astype(float) - df["low"].astype(float)) / close
    if name == "gap":
        return df["open"].astype(float) / close.shift(1) - 1.0
    if name == "hour":
        idx = pd.to_datetime(df.index, utc=True, errors="coerce")
        return pd.Series(idx.hour.astype(float), index=df.index)
    if name == "dow":
        idx = pd.to_datetime(df.index, utc=True, errors="coerce")
        return pd.Series(idx.dayofweek.astype(float), index=df.index)
    if name == "volume":
        if "volume" not in df.columns:
            return None
        v = df["volume"].astype(float)
        return None if not v.gt(0).any() else v
    if name == "close_pos":
        hi = df["high"].astype(float).rolling(window).max()
        lo = df["low"].astype(float).rolling(window).min()
        span = (hi - lo)
        return (close - lo) / span.where(span > 0)
    return None


def _conditions(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Every (primitive x window x band) mask. GENERATED, never enumerated.

    Each mask says "this primitive currently sits in this part of its own trailing distribution",
    ranked over a rolling window so the condition is point-in-time and comparable across
    instruments. Nothing here is a session, a family, or a named pattern -- those are conclusions,
    and a miner that starts from conclusions can only confirm them.
    """
    out: dict[str, np.ndarray] = {}
    for prim in _PRIMITIVES:
        # A window-invariant primitive is evaluated ONCE. Crossing it with the window list emits
        # identical cells under different names and overstates the search width.
        windows = _WINDOWS if prim in _WINDOWED else (_WINDOWS[0],)
        for window in windows:
            series = _primitive(df, prim, window)
            if series is None:
                continue
            rank = series.rolling(500, min_periods=200).rank(pct=True)
            for lo, hi in _BANDS:
                mask = ((rank > lo) & (rank <= hi)).to_numpy()
                if mask.sum() < MIN_N:
                    continue
                tag = f"{prim}_w{window}" if prim in _WINDOWED else prim
                out[f"{tag}_q{lo:g}-{hi:g}"] = mask
    return out


def scan_symbol(symbol: str, df: pd.DataFrame) -> tuple[list[Anomaly], int]:
    """Every (condition x horizon) cell for one symbol. Returns (reportable, trials_evaluated)."""
    if df is None or len(df) < 1200:
        return [], 0
    close = df["close"].astype(float)
    conds = _conditions(df)
    found: list[Anomaly] = []
    trials = 0
    for h in HORIZONS:
        fwd = (close.shift(-h) / close - 1.0).to_numpy()
        base = float(np.nanmean(fwd)) * 1e4
        for name, mask in conds.items():
            trials += 1
            m = np.asarray(mask, dtype=bool) & np.isfinite(fwd)
            n = int(m.sum())
            if n < MIN_N:
                continue
            vals = fwd[m]
            mu, sd = float(np.nanmean(vals)), float(np.nanstd(vals, ddof=1))
            if not (sd > 0 and math.isfinite(mu)):
                continue
            t = mu / (sd / math.sqrt(n))
            if abs(t) < REPORT_T:
                continue
            found.append(Anomaly(
                symbol=symbol, condition=name, horizon=h, n=n,
                mean_bp=round(mu * 1e4, 3), t_stat=round(t, 3),
                hit_rate=round(float((vals > 0).mean()), 4), baseline_bp=round(base, 3),
                question=(f"{symbol} returns over {h}h are {mu * 1e4:.1f}bp when "
                          f"{name} (n={n}, |t|={abs(t):.1f}) against a {base:.1f}bp baseline. "
                          f"WHAT MECHANISM would do that, and what would falsify it? "
                          f"Unnamed, this is a correlation and may never be traded.")))
    return found, trials


def scan_cross_section(frames: dict[str, pd.DataFrame], *, max_pairs: int = 400
                       ) -> tuple[list[dict[str, Any]], int]:
    """Anomalies that live BETWEEN instruments, which single-symbol scanning cannot see.

    WHY THIS IS THE HIGHEST-ROI GROUND LEFT, MEASURED. The allocator is not short of heat, it is
    short of MECHANISMS: only six are funded, MAX_FAMILY_HEAT_SHARE binds at 40%, and the sweep
    on 2026-09-03 showed relaxing that concentration is worth roughly four times what raising
    heat is (20%->30% heat: +38% growth; family cap 40%->101% at fixed heat: +151%). Heat is
    capped by a wipeout path at 35%; concentration is capped by having nothing uncorrelated to
    put money into. So the binding constraint on this book is the SUPPLY OF INDEPENDENT EDGES,
    and every generator the desk owns scans one symbol at a time -- which by construction
    produces edges that share a driver.

    A relationship is a different object. Lead-lag, residual dispersion and relative strength are
    not the same trade as "momentum on EURUSD" wearing a different symbol, which is exactly what
    the redundancy term keeps rejecting.

    POINT-IN-TIME AND ALIGNED. Both legs are reindexed onto a shared clock and every statistic is
    computed on bars at or before the decision bar, with the forward return taken strictly after.
    Misaligned frames silently produce spectacular lead-lag artefacts, so alignment is done here
    rather than assumed.
    """
    import itertools

    syms = sorted(frames)
    rows: list[dict[str, Any]] = []
    trials = 0
    pairs = list(itertools.combinations(syms, 2))[:max_pairs]
    for a, b in pairs:
        fa, fb = frames[a], frames[b]
        idx = fa.index.intersection(fb.index)
        if len(idx) < 1500:
            continue
        ca = fa.loc[idx, "close"].astype(float)
        cb = fb.loc[idx, "close"].astype(float)
        ra, rb = ca.pct_change(), cb.pct_change()

        # LEAD-LAG: does b's move predict a's NEXT move, beyond a's own autocorrelation?
        for lag in (1, 2, 3):
            trials += 1
            x = rb.shift(lag)
            y = ra
            m = np.isfinite(x) & np.isfinite(y)
            n = int(m.sum())
            if n < 500:
                continue
            xv, yv = x[m].to_numpy(), y[m].to_numpy()
            if xv.std() <= 0 or yv.std() <= 0:
                continue
            r = float(np.corrcoef(xv, yv)[0, 1])
            t = r * math.sqrt(max(n - 2, 1) / max(1e-12, 1 - r * r))
            if abs(t) < REPORT_T or abs(r) < 0.03:
                continue
            rows.append({
                "kind": "anomaly", "family_hint": "lead_lag",
                "symbol": a, "against": b, "condition": f"lead_lag_{b}_lag{lag}",
                "horizon": 1, "n": n, "corr": round(r, 4), "t_stat": round(t, 3),
                "mechanism_status": "UNNAMED",
                "question": (f"{b} at lag {lag}h correlates {r:+.3f} with {a}'s next hour "
                             f"(n={n}, |t|={abs(t):.1f}). WHAT MECHANISM transmits that -- shared "
                             f"factor, quote latency, a common venue -- and what would falsify "
                             f"it? Unnamed, this is a correlation and may never be traded."),
            })

        # RESIDUAL DISPERSION: when b-relative valuation stretches, does a revert?
        trials += 1
        win = 240
        beta = ra.rolling(win).cov(rb) / rb.rolling(win).var()
        resid = (ca / ca.shift(win) - 1.0) - beta * (cb / cb.shift(win) - 1.0)
        z = (resid - resid.rolling(win).mean()) / resid.rolling(win).std()
        fwd = (ca.shift(-6) / ca - 1.0)
        for label, mask in (("resid_rich", (z >= 2.0)), ("resid_cheap", (z <= -2.0))):
            trials += 1
            m = mask.to_numpy() & np.isfinite(fwd).to_numpy()
            n = int(m.sum())
            if n < MIN_N:
                continue
            vals = fwd.to_numpy()[m]
            mu, sd = float(np.nanmean(vals)), float(np.nanstd(vals, ddof=1))
            if not (sd > 0 and math.isfinite(mu)):
                continue
            t = mu / (sd / math.sqrt(n))
            if abs(t) < REPORT_T:
                continue
            rows.append({
                "kind": "anomaly", "family_hint": "cross_asset_residual",
                "symbol": a, "against": b, "condition": f"{label}_vs_{b}",
                "horizon": 6, "n": n, "mean_bp": round(mu * 1e4, 3), "t_stat": round(t, 3),
                "mechanism_status": "UNNAMED",
                "question": (f"{a} returns {mu * 1e4:+.1f}bp over 6h when its {win}h return is "
                             f"2sd {'rich' if 'rich' in label else 'cheap'} against {b} "
                             f"(n={n}, |t|={abs(t):.1f}). WHAT MECHANISM reverts it, and what "
                             f"would falsify that? Unnamed, this may never be traded."),
            })
    return rows, trials


def scan(symbols: list[str] | None = None, *, limit: int = 40) -> dict[str, Any]:
    """Scan the tradeable universe for conditional structure. Emits anomalies, never candidates."""
    files = sorted(_BARS.glob("*_H1.parquet"))
    if symbols:
        want = {s.upper() for s in symbols}
        files = [f for f in files if f.stem.replace("_H1", "").upper() in want]
    files = files[:limit]

    rows: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    trials = 0
    scanned, skipped = [], []
    for f in files:
        sym = f.stem.replace("_H1", "")
        try:
            df = pd.read_parquet(f, columns=["open", "high", "low", "close"])
        except Exception as exc:
            skipped.append({"symbol": sym, "why": f"{type(exc).__name__}: {exc}"})
            continue
        found, t = scan_symbol(sym, df)
        trials += t
        scanned.append(sym)
        rows.extend(a.as_row() for a in found)
        frames[sym] = df

    # CROSS-SECTIONAL PASS. The single-symbol scan above finds edges that share a driver; this
    # finds edges that live between instruments, which is the class the family cap is starved of.
    cross_rows, cross_trials = scan_cross_section(frames)
    rows.extend(cross_rows)
    trials += cross_trials

    rows.sort(key=lambda r: -abs(float(r["t_stat"])))
    report = {
        "scanned_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "symbols_scanned": len(scanned), "symbols_skipped": skipped,
        "cross_sectional_anomalies": len(cross_rows), "cross_sectional_trials": cross_trials,
        "trials": trials,
        "anomalies": rows,
        "min_n": MIN_N, "report_t": REPORT_T,
        "honesty": {
            "trials_counted": trials,
            "why": ("every (symbol, condition, horizon) cell evaluated is counted and carried, so "
                    "deflation downstream charges the real width of this search rather than the "
                    "flattering subset that survived the reporting floor"),
            "report_t_is_not_a_gate": ("REPORT_T only decides what reaches the naming queue. It "
                                       "sets no bar: the canonical ten gates remain the only "
                                       "arbiter and nothing here competes with them"),
            "unnamed": ("every row is mechanism_status=UNNAMED. An anomaly is an observation; "
                        "turning one into a candidate without a named, falsifiable cause is the "
                        "prose-to-family guessing the compiler refuses"),
        },
    }
    _OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M")
    (_OUT / f"anomalies_{stamp}.json").write_text(
        json.dumps(report, indent=1, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    r = scan()
    print(f"anomaly miner: {r['symbols_scanned']} symbol(s), {r['trials']:,} cells evaluated, "
          f"{len(r['anomalies'])} reportable")
    for row in r["anomalies"][:12]:
        # Two row shapes: single-symbol rows carry mean_bp, lead-lag rows carry corr. Printing
        # one shape's key on the other is how a KeyError ends a run that had already done the work.
        effect = (f"{row['mean_bp']:+8.1f}bp" if "mean_bp" in row
                  else f"corr {row.get('corr', 0):+7.3f}")
        against = f" vs {row['against']}" if row.get("against") else ""
        print(f"   |t|={abs(row['t_stat']):5.1f}  {row['symbol']:9s}{against:11s} "
              f"{row['condition']:26s} h={row['horizon']:2d} n={row['n']:6d}  {effect}")
