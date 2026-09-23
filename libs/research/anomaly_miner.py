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
HORIZONS = (1, 2, 3, 6, 12, 24, 48, 72)


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


#: THE DESK'S OWN PRIMITIVE LIBRARY IS THE VOCABULARY. Not a list written here.
#:
#: This file previously defined its own 21 primitives -- skew, accel, streak, dist_high and the
#: rest -- and generated conditions from them. They were reasonable primitives and they were
#: USELESS, because `family_discovered` resolves a feature name through
#: `edge_search.build_primitives`, and only 5 of the 21 existed there. The other 16 would have
#: resolved to None at execution time, so every candidate this miner produced would have been
#: unexecutable: thousands of anomalies, each carrying a mechanism and a falsifier, that the
#: gauntlet could never have evaluated. Conversion would have been exactly zero, and the reason
#: would have looked like "the gates are strict" rather than "the producer and the executor speak
#: different languages" -- which is this desk's single most expensive defect shape and had already
#: happened four times today.
#:
#: So the vocabulary is IMPORTED. build_primitives supplies 106 features, already windowed
#: (dd_12, dd_24, kurt_96, path_efficiency_12 ...), and every one of them is by construction a
#: name the executor can resolve. It also removes the last hardcoded list from this file: the
#: search space is now whatever the desk can actually compute, which widens the moment a
#: primitive is added there and needs no change here.
_BANDS: tuple[tuple[float, float], ...] = (
    (0.0, 0.05), (0.0, 0.1), (0.1, 0.25), (0.25, 0.4), (0.4, 0.6),
    (0.6, 0.75), (0.75, 0.9), (0.9, 1.0), (0.95, 1.0),
)


def _conditions(df: pd.DataFrame, symbol: str = "") -> dict[str, np.ndarray]:
    """Every (canonical primitive x band) mask. The vocabulary is the executor's, not ours.

    Each mask says "this primitive sits in this part of its own trailing distribution", ranked
    over a rolling window so the condition is point-in-time and comparable across instruments.
    The KEY is `<feature>_q<lo>-<hi>`, and `<feature>` is a name `build_primitives` supplies --
    which is what makes the resulting anomaly directly compilable into
    `family_discovered(feature=..., band=..., horizon=..., side=...)`.
    """
    try:
        import sys as _sys
        _d = str(_DESK)
        if _d not in _sys.path:
            _sys.path.insert(0, _d)
        _r = str(_DESK / "research")
        if _r not in _sys.path:
            _sys.path.insert(0, _r)
        from research.edge_search import build_primitives  # type: ignore[import-not-found]
    except ImportError:
        try:
            from edge_search import build_primitives  # type: ignore[import-not-found]
        except ImportError:
            return {}                    # UNMEASURED: no vocabulary, so no conditions at all
    # THE ACQUIRED VOCABULARY IS PART OF THE SEARCH, not a separate one. Everything price-native
    # is derived from the same OHLCV, so conditions built only on it produce edges that share a
    # driver -- which is exactly why the allocator's family cap binds at 40% on five mechanisms.
    # Positioning, rate differentials and cross-currency reference rates are a DIFFERENT driver,
    # and they are the raw material for the uncorrelated mechanisms the book is starved of.
    # Passed as `extra`, so they arrive as `ext_<name>` -- names `family_discovered` resolves
    # through this same function, which is what makes an anomaly found here executable there.
    extra: dict[str, Any] = {}
    try:
        from research.acquire_datasets import acquired_series  # type: ignore[import-not-found]
        extra = acquired_series(df.index)
    except Exception:
        extra = {}                       # no acquired data is fewer conditions, never a failure
    try:
        prim = build_primitives(df, symbol, extra)
    except Exception:
        return {}

    out: dict[str, np.ndarray] = {}
    for name, series in prim.items():
        try:
            ser = pd.Series(series, index=df.index).astype(float)
        except Exception:
            continue
        if not np.isfinite(ser.to_numpy()).any():
            continue
        rank = ser.rolling(500, min_periods=200).rank(pct=True)
        for lo, hi in _BANDS:
            mask = ((rank > lo) & (rank <= hi)).to_numpy()
            if mask.sum() < MIN_N:
                continue
            out[f"{name}_q{lo:g}-{hi:g}"] = mask
    return out


def scan_symbol(symbol: str, df: pd.DataFrame) -> tuple[list[Anomaly], int]:
    """Every (condition x horizon) cell for one symbol. Returns (reportable, trials_evaluated)."""
    if df is None or len(df) < 1200:
        return [], 0
    close = df["close"].astype(float)
    conds = _conditions(df, symbol)
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
            # OVERLAPPING FORWARD RETURNS DESTROY THE SAMPLE SIZE, and using raw n inflated
            # every statistic this miner produced. A horizon-h forward return shares h-1 bars
            # with its neighbour, so consecutive observations are not independent draws: the
            # effective count is ~n/h, and t computed on n is too large by sqrt(h). At h=24 that
            # is a factor of 4.9, which is exactly why the top hits were reading |t|=38.
            #
            # MEASURED 2026-09-03: 68,899 of 315,982 cells cleared |t|>=3 -- a 21.8% hit rate
            # against a null expectation near 0.3%. Seventy times the null is not structure, it
            # is a broken denominator, and every one of those rows would have carried its
            # inflated statistic into the compiler, the naming queue and the trial accounting.
            #
            # The condition mask is also persistent (a quantile band holds for runs of bars), so
            # n/h remains OPTIMISTIC. It is the floor of the correction, not the whole of it --
            # the gates still do the real work, and this only stops the miner lying to them.
            n_eff = max(2.0, n / float(max(1, h)))
            t = mu / (sd / math.sqrt(n_eff))
            if abs(t) < REPORT_T:
                continue
            found.append(Anomaly(
                symbol=symbol, condition=name, horizon=h, n=int(n_eff),
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
            # OVERLAPPING FORWARD RETURNS DESTROY THE SAMPLE SIZE, and using raw n inflated
            # every statistic this miner produced. A horizon-h forward return shares h-1 bars
            # with its neighbour, so consecutive observations are not independent draws: the
            # effective count is ~n/h, and t computed on n is too large by sqrt(h). At h=24 that
            # is a factor of 4.9, which is exactly why the top hits were reading |t|=38.
            #
            # MEASURED 2026-09-03: 68,899 of 315,982 cells cleared |t|>=3 -- a 21.8% hit rate
            # against a null expectation near 0.3%. Seventy times the null is not structure, it
            # is a broken denominator, and every one of those rows would have carried its
            # inflated statistic into the compiler, the naming queue and the trial accounting.
            #
            # The condition mask is also persistent (a quantile band holds for runs of bars), so
            # n/h remains OPTIMISTIC. It is the floor of the correction, not the whole of it --
            # the gates still do the real work, and this only stops the miner lying to them.
            n_eff = max(2.0, n / 6.0)  # h=6: fwd is ca.shift(-6)
            t = mu / (sd / math.sqrt(n_eff))
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


#: Where the rotation cursor lives. The scan covers the WHOLE universe every run; this only
#: rotates which symbols are retained for the pairwise pass, whose cost is quadratic.
_CURSOR = _DESK / "data" / "intelligence" / "anomaly_cursor.json"

#: Symbols given the FULL widened space per run. The space is 9,288 cells per symbol and the
#: universe is 251, so an all-symbols run is 2.3M cells and hours of wall clock -- far past the
#: cycle it is scheduled on. Rotating means no symbol is excluded, only deferred: the cursor
#: advances every run, so the whole universe is covered across a day rather than the first 40
#: names alphabetically being covered forever. Deferred is a schedule; excluded is a bias.
_SCAN_PER_RUN = 30

#: Symbols kept in memory for the cross-sectional pass per run. Not a limit on what is SCANNED --
#: every symbol is scanned every run -- but on how many frames are held at once, because pairs
#: grow as n^2 and this box has 3.8GB and no swap. The cursor advances so every symbol enters the
#: pairwise pass in turn; over a day's runs the pair space is covered without a single run that
#: cannot fit.
_CROSS_FRAMES = 60


def _cursor_take(all_syms: list[str], k: int) -> list[str]:
    """The next k symbols for the pairwise pass, rotating. Never the same slice twice running."""
    try:
        pos = int(json.loads(_CURSOR.read_text("utf-8")).get("pos") or 0)
    except (OSError, ValueError, AttributeError):
        pos = 0
    n = len(all_syms)
    if n == 0:
        return []
    take = [all_syms[(pos + i) % n] for i in range(min(k, n))]
    try:
        _CURSOR.parent.mkdir(parents=True, exist_ok=True)
        _CURSOR.write_text(json.dumps({"pos": (pos + len(take)) % n,
                                       "of": n, "at": datetime.now(UTC).isoformat()}), "utf-8")
    except OSError:
        pass
    return take


def scan(symbols: list[str] | None = None, *, limit: int | None = None) -> dict[str, Any]:
    """Scan the tradeable universe for conditional structure. Emits anomalies, never candidates.

    EVERY SYMBOL, EVERY RUN. This took `files[:40]` on an alphabetically sorted list, so it
    scanned 40 of 251 symbols -- 3M, Accenture, ADAUSD, Adobe ... AUDCAD, AUDCHF, AUDHUF -- and
    never touched the other 211. Every result it produced was dominated by AUD crosses, and that
    was not the market's structure, it was the slice's: exotic crosses with strong session effects
    happen to sort early. A discovery engine that only ever looks at the front of the alphabet
    reports the alphabet, and every downstream count -- trials, mechanism mix, family yield --
    inherits that bias while looking like a measurement of the universe.

    `limit` is now None by default and exists only for tests. The pairwise pass, whose cost is
    quadratic, rotates through the universe on a cursor instead.
    """
    files = sorted(_BARS.glob("*.parquet"))
    if symbols:
        want = {s.upper() for s in symbols}
        files = [f for f in files
                 if (f.stem.rpartition("_")[0] or f.stem).upper() in want]
    if limit is not None:
        files = files[:limit]

    rows: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    trials = 0
    scanned, skipped = [], []
    all_syms = [f.stem.replace("_H1", "") for f in files]
    scan_want = _cursor_take(all_syms, _SCAN_PER_RUN)
    if symbols is None and limit is None:
        want = set(scan_want)
        files = [f for f in files if f.stem.replace("_H1", "") in want]
    cross_want = set(scan_want[:_CROSS_FRAMES])
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
        # TRIALS ARE PER-SYMBOL, NOT GLOBAL, AND THE DIFFERENCE IS NOT COSMETIC. Deflation charges
        # a candidate for the width of the search THAT COULD HAVE PRODUCED IT. Every cell here is
        # evaluated independently and reported on its own merits -- there is no global tournament
        # picking one winner -- so a EURUSD anomaly competed against EURUSD's own 9,288 cells, not
        # against all 2.3M in the universe. Charging the global total would over-deflate by two
        # orders of magnitude and no honest candidate would ever clear gate 3, which is as wrong
        # as under-counting and fails in the direction that looks rigorous.
        for a in found:
            row = a.as_row()
            row["selection_trials"] = t
            rows.append(row)
        # HOLD ONLY WHAT THE PAIRWISE PASS WILL USE. Retaining all 251 frames would hold several
        # GB on a 3.8GB swapless box; the single-symbol scan above already ran on every one.
        if sym in cross_want:
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
        "cross_sectional_symbols": sorted(cross_want),
        "universe_coverage": {
            "symbols_with_bars": len(all_syms), "scanned": len(scanned),
            "rotating_per_run": _SCAN_PER_RUN,
            "note": ("the cursor advances every run so the whole universe is covered across a "
                     "day. No symbol is excluded -- only deferred. The previous behaviour took "
                     "the first 40 names ALPHABETICALLY and never touched the other 211."),
        },
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
