#!/usr/bin/env python3
"""FULL-UNIVERSE SWEEP -- run the whole declared space at once, then hunt survivors in it.

Binds to docs/research/FULL_SWEEP_PREREGISTRATION.md. The universe (898,560), the hurdle (5.236)
and kill criteria F1-F8 were fixed in that document BEFORE this file was written. Nothing here
chooses a threshold, and nothing here may be tuned after a result is seen.

    898,560 PRE-REGISTERED CANDIDATES
      -> FAST SCREEN          full-sample IC and net-of-cost, EVERY cell, no sampling
      -> COST MODEL           10bp round trip charged on realised turnover
      -> DEFLATION            |t| >= sqrt(2 ln 898560), from the DECLARED count
      -> LEAKAGE PROBE        one extra bar of lag; a collapse is a leak, not an edge
      -> WALK-FORWARD         70/30 time split; sign agreement and magnitude retention
      -> INDEPENDENCE         cluster realised returns -- MECHANISMS, not formulas
      -> LIQUIDITY DISCLOSURE where the net actually came from, beside the spread it paid

THE ONE THING THIS SCRIPT WILL NOT DO IS INVENT DATA. With no bars it reports BLOCKED and exits 0,
carrying the declared budget and hurdle into the artifact so the pre-registration is on the record
even when the run cannot happen. A verdict computed on synthesised prices is a fact about the
generator, and it would enter the funnel wearing the vocabulary of a real one.

**IT ALSO REFUSES TO START A RUN IT CANNOT FINISH.** The projected runtime is measured on a
calibration batch and compared against `--max-minutes` BEFORE the sweep begins. This box collects
tape that cannot be re-acquired at any price; an eight-hour single-core job that nobody projected,
competing with the recorders, is how the desk would lose the one asset it cannot rebuild. Refusing
with arithmetic and a suggested `--tail-bars` costs a second.

WHAT THIS DOES NOT DO. It promotes nothing, sizes nothing, trades nothing. A survivor here has
cleared Stage A and owes CPCV/DSR and a portfolio-contribution test -- the last two of L1.52(a)'s
four counts -- before the word "discovery" applies to it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.alpha_factory.combination_engine import (  # noqa: E402
    HORIZONS,
    REGIMES,
    TRANSFORMS,
    Combination,
    enumerate_space,
    space_size,
)
from libs.alpha_factory.evaluator import (  # noqa: E402
    DEFAULT_COST_BP,
    MIN_OBS,
    CellResult,
    evaluate,
    sweep,
    transform,
)
from libs.alpha_factory.independence import cluster  # noqa: E402

BARS = ROOT / "data" / "bars"
OUT = ROOT / "data" / "full_sweep.json"
PREREG = ROOT / "docs" / "research" / "FULL_SWEEP_PREREGISTRATION.md"

#: THE THIRTEEN FEATURES THE DECLARED UNIVERSE IS BUILT FROM. Written out rather than derived from
#: `hypothesis_engine._TEMPLATES` deliberately: deriving it would let a future template edit change
#: the universe size silently, and the universe size IS the hurdle. `test_full_sweep` asserts this
#: tuple still matches the templates AND still produces exactly 898,560, so drift fails loudly
#: instead of quietly buying a weaker significance bar.
DECLARED_FEATURES: tuple[str, ...] = (
    "momentum", "volatility_regime", "rel_strength", "dispersion", "trend",
    "regime_transition", "carry", "volatility_gate", "zscore", "liquidity",
    "vol_compression", "breakout", "lead_lag",
)

#: Fixed in the pre-registration BEFORE the first cell was evaluated. The hurdle is computed from
#: THIS, never from how many cells turned out to be measurable -- deflating on the measurable
#: denominator would shrink the bar in exact proportion to how many cells failed.
PREREGISTERED_UNIVERSE: int = 898_560

#: F4 / F6, stated numerically because a kill criterion that is not a number is not a criterion.
OOS_FRACTION: float = 0.30      # last 30% of the common window is out of sample
OOS_RETENTION: float = 0.25     # F4: OOS net must be >= 25% of IS net
LEAK_RETENTION: float = 0.25    # F6: one extra bar of lag must retain >= 25% of net, same sign

#: Bars per horizon are DERIVED from the tape's own sampling interval, never assumed. A hardcoded
#: "1d = 24 bars" is correct for hourly bars and wrong by 1440x for minute bars, and the error is
#: invisible in the output.
_HORIZON_SECONDS: dict[str, float] = {"1h": 3600.0, "4h": 14400.0, "1d": 86400.0, "1w": 604800.0}

#: NaN rows inserted between symbols when their series are concatenated into one pooled sample.
#: Two, because the deepest backward reach in the pipeline is two single-bar shifts (`lead`'s own
#: shift, then the evaluator's). Without the gap, the first bar of ETH would be predicted by the
#: last bar of BTC -- a leak across a boundary that does not exist in time.
_POOL_GAP: int = 2


def hurdle() -> float:
    """sqrt(2 ln N) at the DECLARED N."""
    return float(np.sqrt(2.0 * np.log(PREREGISTERED_UNIVERSE)))


def universe_check() -> tuple[int, bool]:
    """Does the code still enumerate the space the pre-registration declared?"""
    n = space_size(len(DECLARED_FEATURES), n_transforms=len(TRANSFORMS))
    return n, n == PREREGISTERED_UNIVERSE


# --------------------------------------------------------------------------- data


def _read(path: Path) -> pd.DataFrame | None:
    try:
        df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    except Exception:
        return None
    cols = {c.lower(): c for c in df.columns}
    if "close" not in cols or "timestamp" not in cols:
        return None
    keep = {cols[k]: k for k in ("timestamp", "close", "volume", "spread", "spread_bp", "funding",
                                "funding_rate") if k in cols}
    df = df[list(keep)].rename(columns=keep)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)


def discover(symbols: list[str] | None, bars: Path = BARS) -> dict[str, pd.DataFrame]:
    """Load every usable bar file, keyed by symbol. An empty dict means NOT PRESENT."""
    if not bars.exists():
        return {}
    out: dict[str, pd.DataFrame] = {}
    for f in sorted([*bars.rglob("*.parquet"), *bars.rglob("*.csv")]):
        df = _read(f)
        if df is None or df.empty:
            continue
        sym = next((s for s in (symbols or []) if s.upper() in f.stem.upper()), None)
        if symbols and sym is None:
            continue
        # `<SYMBOL>_15min.parquet` -> BTCUSDT. The frequency is a property of the
        # file, not part of the instrument's name, and carrying it into the symbol
        # breaks every lookup that matches on the ticker.
        sym = sym or re.sub(r'_(\d+[A-Z]+)$', '', f.stem.upper())
        if sym not in out or len(df) > len(out[sym]):
            out[sym] = df
    return out


def bar_seconds(index: pd.DatetimeIndex) -> float:
    """Median sampling interval, MEASURED. Returns 0.0 when it cannot be determined."""
    if len(index) < 3:
        return 0.0
    d = np.diff(index.asi8) / 1e9
    med = float(np.median(d))
    return med if med > 0 else 0.0


#: A timestamp is kept when at least this many symbols traded in it. TWO, because that is the
#: minimum a cross-sectional operator can rank against -- below it `rank`/`zscore` degenerate and
#: correctly refuse, so keeping such bars buys nothing.
MIN_SYMBOLS_PER_BAR: int = 2

#: A symbol is kept when it covers at least this share of the retained grid. A name present for 3%
#: of the window contributes almost nothing to the cross-section while dragging the whole grid
#: toward its own short span.
MIN_SYMBOL_COVERAGE: float = 0.25


def align(frames: dict[str, pd.DataFrame], tail: int, *,
          min_symbols: int = MIN_SYMBOLS_PER_BAR,
          min_coverage: float = MIN_SYMBOL_COVERAGE,
          ) -> tuple[pd.DatetimeIndex, dict[str, pd.DataFrame], list[str]]:
    """One clock for the cross-section, built by COVERAGE rather than by strict intersection.

    THE STRICT INTERSECTION WAS WRONG AND THE LIVE RUN PROVED IT. Requiring every symbol to be
    present at every timestamp gave `common grid is 0 bars across 45 symbols` on real tape: the
    recorders cover names raggedly -- BTCUSDT started 08-04 while 1000CATUSDT ended 08-04 -- so the
    intersection of forty-five ragged spans is empty, and the whole panel was discarded because one
    name was absent. With more symbols the intersection can only shrink, so the study got WORSE the
    more data it was given, which is exactly backwards.

    WHAT REPLACES IT. Keep a timestamp when `min_symbols` traded in it, keep a symbol when it
    covers `min_coverage` of that grid, and leave NaN where a symbol is genuinely absent. Nothing
    is forward-filled: a carried close is a price nothing traded at, and the cross-sectional
    operators skip NaN by construction, so a bar simply ranks across the names that were there.

    THE DROPPED NAMES ARE RETURNED, NOT SWALLOWED. A panel that quietly shed thirty symbols would
    report a cross-section far narrower than the one the reader believes was searched.
    """
    if not frames:
        return pd.DatetimeIndex([], tz=UTC), {}, []
    per_symbol = {s: pd.DatetimeIndex(df["timestamp"]) for s, df in frames.items()}
    union = per_symbol[next(iter(per_symbol))]
    for ts in per_symbol.values():
        union = union.union(ts)
    union = union.sort_values()

    present = pd.DataFrame({s: union.isin(ts) for s, ts in per_symbol.items()}, index=union)
    idx = pd.DatetimeIndex(present.index[present.sum(axis=1) >= min_symbols])
    if len(idx) == 0:
        return pd.DatetimeIndex([], tz=UTC), {}, sorted(frames)

    keep, dropped = [], []
    for s in sorted(frames):
        cover = float(present.loc[idx, s].mean())
        (keep if cover >= min_coverage else dropped).append(s)
    if len(keep) < min_symbols:
        return pd.DatetimeIndex([], tz=UTC), {}, sorted(frames)

    # Re-tighten the grid to the kept names only, so a bar retained on the strength of a symbol
    # that was then dropped does not survive as an empty row.
    idx = pd.DatetimeIndex(present.loc[idx, keep].index[present.loc[idx, keep].sum(axis=1)
                                                        >= min_symbols])
    if tail > 0:
        idx = idx[-tail:]
    return idx, {s: frames[s].set_index("timestamp").reindex(idx) for s in keep}, dropped


# ----------------------------------------------------------------- feature construction


def feature_panels(aligned: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Build the 13 declared features as (timestamps x symbols) panels.

    EVERY WINDOW IS TRAILING AND EVERY COMPARISON IS EXPANDING. Nothing here may see its own
    future: a full-sample percentile used as a regime threshold is the single most common way a
    sweep of this width manufactures a result, because the threshold itself encodes the answer.

    Features whose input column is absent are returned as ABSENT WITH A REASON rather than as
    zeros. A zero-filled feature is not a missing feature, it is a constant one, and a constant
    consumes a trial while testing nothing (L1.28a).
    """
    close = pd.DataFrame({s: d["close"] for s, d in aligned.items()}).astype(float)
    ret = np.log(close).diff()
    panels: dict[str, pd.DataFrame] = {}
    absent: dict[str, str] = {}

    vol60 = ret.rolling(60, min_periods=30).std()
    vol20 = ret.rolling(20, min_periods=10).std()
    vol120 = ret.rolling(120, min_periods=60).std()
    sma60 = close.rolling(60, min_periods=30).mean()

    panels["momentum"] = ret.rolling(24, min_periods=12).sum()
    panels["volatility_regime"] = vol60 / vol60.expanding(min_periods=200).median()
    panels["trend"] = (close - sma60) / sma60.replace(0.0, np.nan)
    panels["regime_transition"] = (vol20 - vol120).abs() / vol120.replace(0.0, np.nan)
    panels["volatility_gate"] = vol60.rank(axis=0, pct=True).where(vol60.notna())
    panels["zscore"] = (close - sma60) / (close.rolling(60, min_periods=30).std()
                                          .replace(0.0, np.nan))
    panels["vol_compression"] = vol20 / vol120.replace(0.0, np.nan)
    roll_max = close.rolling(60, min_periods=30).max()
    panels["breakout"] = (close - roll_max) / roll_max.replace(0.0, np.nan)

    # CROSS-SECTIONAL BY CONSTRUCTION -- degenerate on one symbol, so they are refused there
    # rather than computed into a constant that would still consume 69,120 trials apiece.
    if close.shape[1] >= 2:
        panels["rel_strength"] = ret.sub(ret.mean(axis=1), axis=0)
        panels["dispersion"] = pd.DataFrame(
            np.repeat(ret.std(axis=1).to_numpy()[:, None], close.shape[1], axis=1),
            index=close.index, columns=close.columns)
        ref = close.columns[0]
        panels["lead_lag"] = ret.sub(ret[ref].shift(1), axis=0)
    else:
        for name in ("rel_strength", "dispersion", "lead_lag"):
            absent[name] = ("cross-sectional feature with one symbol on the common grid -- it "
                            "would be identically zero, which is a constant rather than a feature")

    vols = {s: d["volume"] for s, d in aligned.items() if "volume" in d}
    if len(vols) == len(aligned) and aligned:
        panels["liquidity"] = np.log1p(pd.DataFrame(vols).astype(float).clip(lower=0.0)
                                       .rolling(60, min_periods=30).mean())
    else:
        absent["liquidity"] = "no `volume` column on every symbol's bars"

    fund = {s: (d["funding"] if "funding" in d else d["funding_rate"])
            for s, d in aligned.items() if "funding" in d or "funding_rate" in d}
    if len(fund) == len(aligned) and aligned:
        panels["carry"] = pd.DataFrame(fund).astype(float)
    else:
        absent["carry"] = ("no `funding`/`funding_rate` column -- carry is a moat-tape field and "
                           "the bar files do not carry it; join it in before claiming this axis")

    for name in DECLARED_FEATURES:
        if name not in panels and name not in absent:
            absent[name] = "no builder produced it"
    return panels, absent


def regime_masks(ret: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Per-bar regime membership, from TRAILING statistics against an EXPANDING reference.

    `high_vol` and `low_vol` do not partition `all`, and that is correct rather than a bug: bars
    before the expanding reference has 200 observations belong to NEITHER, because their regime is
    not yet determinable. Forcing them into one would put the early tape -- the part with the least
    context -- into whichever arm the comparison operator happened to favour.
    """
    vol = ret.rolling(60, min_periods=30).std().shift(1)
    vref = vol.expanding(min_periods=200).median()
    strength = ((ret.rolling(60, min_periods=30).sum().abs()
                 / (ret.rolling(60, min_periods=30).std().replace(0.0, np.nan) * np.sqrt(60)))
                .shift(1))
    sref = strength.expanding(min_periods=200).median()
    return {
        "all": pd.DataFrame(True, index=ret.index, columns=ret.columns),
        "high_vol": vol > vref,
        "low_vol": vol <= vref,
        "trending": strength > sref,
        "ranging": strength <= sref,
    }


def forward(close: pd.DataFrame, h: int) -> pd.DataFrame:
    """h-bar forward return, EXPRESSED PER BAR.

    The division by `h` is not cosmetic. Turnover cost is charged per bar, so comparing a raw
    7-day return against a per-bar cost would make the weekly horizon look 168x more profitable
    than the hourly one for arithmetic reasons alone -- and a sweep this wide would find its
    survivors there every time. Correlation is scale-free, so the IC is unaffected.
    """
    return (close.shift(-h) / close - 1.0) / float(h)


# ----------------------------------------------------------------------- pooling


def pool(parts: list[pd.Series]) -> pd.Series:
    """Concatenate per-symbol series into one sample, separated by NaN gaps.

    POOLING IS WHAT KEEPS THE TRIAL COUNT AT 898,560. Evaluating each candidate once per symbol
    would be 898,560 x S trials against a hurdle declared for 898,560, which is the same error as
    testing a sample and deflating for it. One candidate, one pooled statistic, one trial -- and
    the cell has to work across the book rather than on the one symbol that happened to cooperate.
    """
    blocks: list[pd.Series] = []
    for i, p in enumerate(parts):
        if i:
            blocks.append(pd.Series([np.nan] * _POOL_GAP, dtype=float))
        blocks.append(pd.Series(p.to_numpy(dtype=float), dtype=float))
    return pd.concat(blocks, ignore_index=True) if blocks else pd.Series(dtype=float)


def transform_name(feat: str, tf: str) -> str:
    return feat if tf == "identity" else f"{tf}({feat})"


def pooled_features(panels: dict[str, pd.DataFrame], symbols: list[str],
                    ) -> tuple[dict[str, pd.Series], dict[str, str]]:
    """Apply all 8 transforms per symbol, then pool. 13 x 8 series, computed ONCE.

    Transforms are applied PER SYMBOL BEFORE pooling, and this ordering is the whole correctness
    argument: `delta` or `ts_rank` computed on an already-concatenated series would difference the
    last bar of one symbol against the first bar of the next, and a cross-sectional `rank` needs
    the panel at a timestamp, which pooling destroys.
    """
    out: dict[str, pd.Series] = {}
    unavailable: dict[str, str] = {}
    for feat, panel in panels.items():
        for tf in TRANSFORMS:
            name = transform_name(feat, tf)
            parts = [transform(panel[s], tf, panel=panel) for s in symbols]
            if any(p is None for p in parts):
                unavailable[name] = "cross-sectional transform needs a panel of 2+ symbols"
                continue
            out[name] = pool([p for p in parts if p is not None])
    return out, unavailable


# ------------------------------------------------------------------- statistics


def t_stat(ic: float, n: int, h: int) -> float:
    """t on the IC, with OVERLAPPING FORWARD RETURNS DISCOUNTED.

    An h-bar forward return sampled every bar reuses each observation h times. Treating n bars as
    n independent observations inflates t by roughly sqrt(h) -- a factor of 13 at the weekly
    horizon on hourly bars -- so the effective sample is n/h. This is deliberately crude and
    deliberately conservative: it is the direction that costs the desk nothing.
    """
    n_eff = max(0.0, n / float(max(1, h)))
    if n_eff <= 2.0 or not np.isfinite(ic) or abs(ic) >= 1.0:
        return 0.0
    return float(ic * np.sqrt(n_eff - 2.0) / np.sqrt(1.0 - ic * ic))


def base_feature(name: str) -> str:
    """`rank(funding)` -> `funding`. The transform is a parameterisation, not a different idea."""
    return name.split("(", 1)[1].rstrip(")") if name.endswith(")") and "(" in name else name


def family_of(key: list[str]) -> tuple[str, ...]:
    """FAMILY per L1.52(a): distinct parameterisations of ONE idea collapse to one entry.

    Transform, horizon and regime are all knobs on the same claim -- `rank(funding)` at 1h in
    high-vol and `delta(funding)` at 1d unconditional are two settings of "funding relates to
    forward returns", and counting them as two discoveries is exactly the inflation the law names.
    Only the relation and the two underlying features survive into the identity.
    """
    op, left, right = key[1], base_feature(key[-2]), base_feature(key[-1])
    return (op, *sorted((left, right)))


def _remap(c: Combination) -> Combination:
    """Rewrite a candidate to name its ALREADY-TRANSFORMED inputs.

    `Combination.key` builds its identity from `_name(feature, transform)`, so a candidate over
    `rank(x)` with transform `identity` has the IDENTICAL key to one over `x` with transform
    `rank`. The reported key is therefore the true candidate's key, and this is bookkeeping rather
    than a different hypothesis -- it exists so the 104 transforms are computed once instead of
    898,560 times.
    """
    return Combination(c.category, transform_name(c.left, c.left_tf),
                       transform_name(c.right, c.right_tf), c.operator, c.horizon, c.regime)


def group_space(horizon: str, regime: str) -> tuple[Combination, ...]:
    space = enumerate_space(DECLARED_FEATURES, horizons=[horizon], regimes=[regime],
                            transforms=TRANSFORMS)
    return tuple(_remap(c) for c in space.combinations)


# ---------------------------------------------------------------------- report


def verdict(n_survivors: int, n_screened: int, evaluated: int, measurable: int) -> str:
    """The headline, and the one line in this file most likely to be quoted without its report.

    AN EARLIER VERSION OF THIS SAID "NO SURVIVORS -- the expression space is bounded" whenever the
    survivor list was empty. That is WS-005 in the desk's own harness: it reads an empty result as
    a statement ABOUT THE SPACE, when the same empty list is produced by a run where nothing
    reached the screen and 22,869 cells were never measurable at all. The three cases are different
    findings and only one of them bounds anything:

      - cells cleared the screen and the kill criteria killed them  -> the criteria did work
      - nothing cleared the screen                                  -> no cell was ever a candidate
      - a large unmeasured share                                    -> the denominator is not the
                                                                       universe, so bound nothing
    """
    unmeasured = evaluated - measurable
    frac = unmeasured / evaluated if evaluated else 1.0
    if n_survivors:
        head = f"{n_survivors} STAGE-A SURVIVOR(S)"
    elif n_screened:
        head = (f"NO SURVIVORS -- {n_screened} cell(s) cleared the deflated screen and the kill "
                "criteria killed every one")
    else:
        head = ("NO SURVIVORS -- and NOT ONE CELL cleared the deflated screen, so the kill "
                "criteria were never exercised")
    tail = (f"; {measurable}/{evaluated} cells measurable ({frac:.1%} UNMEASURED, which is not "
            "'no edge')")
    if not n_survivors:
        tail += (". This bounds the expression language ONLY over the measurable cells, this "
                 "sample and this cost model -- it is not a statement about alpha.")
    return head + tail


def blocked(reason: str, detail: dict[str, object]) -> dict[str, object]:
    n, ok = universe_check()
    return {
        "ts": datetime.now(tz=UTC).isoformat(),
        "verdict": "BLOCKED -- NOT RUN",
        "reason": reason,
        **detail,
        "declared_universe": PREREGISTERED_UNIVERSE,
        "enumerated_universe": n,
        "universe_matches_preregistration": ok,
        "hurdle": round(hurdle(), 3),
        "preregistration": str(PREREG.relative_to(ROOT)),
        "note": ("NOTHING IS SYNTHESISED. The budget and hurdle above were fixed before any cell "
                 "was evaluated and stand whether or not the run happens."),
        "authority": "NONE. Stage A. Promotes nothing, sizes nothing, trades nothing.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bars", type=Path, default=BARS,
                    help="bar directory; default data/bars, which is where the collecting box "
                         "keeps it")
    ap.add_argument("--symbols", nargs="*", default=None,
                    help="restrict to these symbols; default is every usable file under data/bars")
    ap.add_argument("--tail-bars", type=int, default=0,
                    help="use only the last N bars of the common grid (0 = the whole intersection)")
    ap.add_argument("--cost-bp", type=float, default=DEFAULT_COST_BP)
    ap.add_argument("--min-obs", type=int, default=MIN_OBS)
    ap.add_argument("--max-minutes", type=float, default=240.0,
                    help="refuse to start if the projected sweep exceeds this")
    ap.add_argument("--max-detail", type=int, default=200, help="survivor rows written in full")
    ap.add_argument("--max-cluster", type=int, default=500,
                    help="cluster at most this many survivors (top by |t|); the mechanism count is "
                         "a LOWER bound when the cap binds")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()

    enumerated, ok = universe_check()
    if not ok:
        print(f"REFUSED: the code enumerates {enumerated} candidates but the pre-registration "
              f"declares {PREREGISTERED_UNIVERSE}.")
        print("  The universe size IS the hurdle. A space that changed after pre-registration must "
              "be re-declared in a new document, not absorbed silently.")
        return 1

    frames = discover(a.symbols, a.bars)
    if len(frames) < 1:
        rep = blocked("no usable bar files under data/bars",
                      {"bars_dir": str(a.bars), "bars_present": a.bars.exists()})
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(rep, indent=1), "utf-8")
        print("full-sweep: BLOCKED -- no bars on this box (data/ is gitignored; it lives on the "
              "collecting box).")
        print(f"  budget already declared: {PREREGISTERED_UNIVERSE} candidates, "
              f"hurdle {hurdle():.3f}")
        print(f"  kill criteria already binding: {PREREG.relative_to(ROOT)}")
        return 0

    symbols = sorted(frames)
    idx, aligned, dropped = align(frames, a.tail_bars)
    secs = bar_seconds(idx)
    if len(idx) < a.min_obs * 2 or secs <= 0:
        rep = blocked(
            (f"the retained grid across {len(symbols)} symbol(s) has {len(idx)} bars -- fewer "
             f"than {MIN_SYMBOLS_PER_BAR} symbol(s) overlap anywhere, or none covers "
             f"{MIN_SYMBOL_COVERAGE:.0%} of the grid. The recorders cover names raggedly, so this "
             "usually means the per-symbol bar windows do not intersect: widen BARS_FILE_BUDGET so "
             "each symbol reaches further back, or rebuild bars over a common window."),
            {"symbols": symbols, "common_bars": len(idx),
             "per_symbol_bars": {s: len(d) for s, d in frames.items()},
             "bar_seconds": secs})
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(rep, indent=1), "utf-8")
        print(f"full-sweep: BLOCKED -- common grid is {len(idx)} bars across {symbols}.")
        return 0

    panels, absent = feature_panels(aligned)
    feats, unavailable = pooled_features(panels, symbols)
    close = pd.DataFrame({s: d["close"] for s, d in aligned.items()}).astype(float)
    ret = np.log(close).diff()
    masks = regime_masks(ret)

    pooled_len = len(idx) * len(symbols) + _POOL_GAP * (len(symbols) - 1)
    split = int(len(idx) * (1.0 - OOS_FRACTION))
    is_mask = pd.DataFrame(False, index=idx, columns=symbols)
    is_mask.iloc[:split] = True

    # PROJECT BEFORE COMMITTING. One calibration group, timed, extrapolated to all twenty.
    #
    # THE BATCH IS STRIDED, NOT THE FIRST N, and the difference is the whole guard. Enumeration
    # walks operators in order, so the first 300 cells are all `interaction` -- one multiply, the
    # cheapest relation in the set. `divergence` ranks BOTH sides and costs several times more, so
    # a head sample under-projects the run by a factor that grows with the operator mix, and a
    # guard that under-projects is a guard that lets the job through.
    cal_h = max(1, round(_HORIZON_SECONDS[HORIZONS[0]] / secs))
    cal_fwd = pool([forward(close, cal_h)[s] for s in symbols])
    cal_group = group_space(HORIZONS[0], "all")
    cal_cells = cal_group[::max(1, len(cal_group) // 300)][:300]
    t0 = time.perf_counter()
    sweep(cal_cells, feats, cal_fwd, cost_bp=a.cost_bp, min_obs=a.min_obs)
    per_cell = (time.perf_counter() - t0) / max(1, len(cal_cells))
    projected_min = per_cell * PREREGISTERED_UNIVERSE / 60.0
    if projected_min > a.max_minutes:
        want = int(len(idx) * a.max_minutes / projected_min)
        print(f"REFUSED: projected {projected_min:.0f} min at {per_cell * 1e3:.2f} ms/cell over "
              f"{pooled_len} pooled rows; --max-minutes is {a.max_minutes:.0f}.")
        print(f"  This box collects tape that cannot be re-acquired. Re-run with "
              f"--tail-bars {max(1000, want)} (a WINDOW result, and the report will say so), "
              f"or raise --max-minutes deliberately.")
        rep = blocked("projected runtime exceeds --max-minutes; nothing was swept",
                      {"symbols": symbols, "common_bars": len(idx), "pooled_rows": pooled_len,
                       "ms_per_cell": round(per_cell * 1e3, 3),
                       "projected_minutes": round(projected_min, 1),
                       "max_minutes": a.max_minutes,
                       "suggested_tail_bars": max(1000, want)})
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(rep, indent=1), "utf-8")
        return 0

    print(f"full-sweep: {PREREGISTERED_UNIVERSE} candidates, hurdle {hurdle():.3f}, "
          f"{len(symbols)} symbol(s), {len(idx)} common bars, {pooled_len} pooled rows, "
          f"~{projected_min:.0f} min projected")

    bar = hurdle()
    evaluated = measurable = net_positive = 0
    reasons: Counter[str] = Counter()
    screened: list[tuple[Combination, CellResult, int]] = []

    for horizon in HORIZONS:
        h = max(1, round(_HORIZON_SECONDS[horizon] / secs))
        fwd_panel = forward(close, h)
        for regime in REGIMES:
            m = masks[regime]
            fwd = pool([fwd_panel[s].where(m[s]) for s in symbols])
            cands = group_space(horizon, regime)
            for c in cands:
                r = evaluate(c, feats, fwd, cost_bp=a.cost_bp, min_obs=a.min_obs)
                evaluated += 1
                if not r.ok:
                    reasons[_reason_class(r.reason, unavailable, absent)] += 1
                    continue
                measurable += 1
                if r.net_bps > 0.0:
                    net_positive += 1
                if abs(t_stat(r.ic, r.n, h)) >= bar and r.net_bps > 0.0:
                    screened.append((c, r, h))
            print(f"  {horizon:>3} / {regime:<10} evaluated {evaluated:>7} | measurable "
                  f"{measurable:>7} | net+ {net_positive:>6} | screened {len(screened):>4}",
                  flush=True)

    # STAGE 2 -- walk-forward and leakage probe, on the screen's survivors only.
    survivors: list[dict[str, object]] = []
    kept: list[tuple[Combination, int]] = []
    killed: Counter[str] = Counter()
    # Cached by horizon rather than recomputed per survivor: `forward()` is a full-panel op, and
    # `setdefault` would evaluate it on every hit -- a per-survivor cost that is invisible at three
    # survivors and dominant at three thousand.
    fwd_cache: dict[int, pd.DataFrame] = {}

    def fwd_for(h: int) -> pd.DataFrame:
        if h not in fwd_cache:
            fwd_cache[h] = forward(close, h)
        return fwd_cache[h]

    for c, r, h in screened:
        fwd_panel = fwd_for(h)
        m = masks[c.regime]
        base = pool([fwd_panel[s].where(m[s]) for s in symbols])
        f_is = pool([fwd_panel[s].where(m[s] & is_mask[s]) for s in symbols])
        f_oos = pool([fwd_panel[s].where(m[s] & ~is_mask[s]) for s in symbols])
        r_is = evaluate(c, feats, f_is, cost_bp=a.cost_bp, min_obs=a.min_obs)
        r_oos = evaluate(c, feats, f_oos, cost_bp=a.cost_bp, min_obs=a.min_obs)
        r_leak = evaluate(c, feats, base.shift(-1), cost_bp=a.cost_bp, min_obs=a.min_obs)

        fired: list[str] = []
        if not (r_is.ok and r_oos.ok):
            fired.append("F5 SAMPLE FLOOR: one split arm is UNMEASURED -- not 'no edge'")
        else:
            # BOTH ARMS POSITIVE, not merely agreeing. Two negative arms "share a sign" and would
            # pass a naive sign test while describing a cell that loses money in both halves of
            # the sample -- reachable because the full-sample net that cleared F2 is not the sum
            # of the arms once turnover is recomputed on each.
            if r_is.net_bps <= 0.0 or np.sign(r_is.net_bps) != np.sign(r_oos.net_bps):
                fired.append(f"F3 WALK-FORWARD SIGN: IS {r_is.net_bps:+.4f} vs OOS "
                             f"{r_oos.net_bps:+.4f} bp/bar (both arms must be positive)")
            elif r_oos.net_bps < OOS_RETENTION * r_is.net_bps:
                fired.append(f"F4 OOS MAGNITUDE: OOS {r_oos.net_bps:+.4f} < "
                             f"{OOS_RETENTION:.0%} of IS {r_is.net_bps:+.4f}")
        if not r_leak.ok:
            fired.append("F6 LEAKAGE PROBE: UNMEASURED under one extra bar of lag")
        elif (np.sign(r_leak.net_bps) != np.sign(r.net_bps)
              or r_leak.net_bps < LEAK_RETENTION * r.net_bps):
            fired.append(f"F6 LEAKAGE: net collapses from {r.net_bps:+.4f} to "
                         f"{r_leak.net_bps:+.4f} on one extra bar of lag")
        for f in fired:
            killed[f.split(":")[0]] += 1
        if fired:
            continue

        kept.append((c, h))
        survivors.append({
            "key": list(c.key), "n": r.n, "horizon_bars": h,
            "ic": round(r.ic, 5), "t": round(t_stat(r.ic, r.n, h), 3),
            "gross_bps": round(r.gross_bps, 4), "turnover": round(r.turnover, 5),
            "net_bps": round(r.net_bps, 4),
            "is_net_bps": round(r_is.net_bps, 4), "oos_net_bps": round(r_oos.net_bps, 4),
            "leak_net_bps": round(r_leak.net_bps, 4),
        })

    # F7 -- INDEPENDENCE, ON A BOUNDED SUBSET, AND THE BOUND IS NOT AN OPTIMISATION.
    #
    # `cluster()` is O(k^2) pairwise correlations over full-length return series, and it holds one
    # series per survivor. At 5,000 survivors on a 2M-row tape that is 12.5M correlations and 80GB
    # of retained pnl -- the study would hang or die exactly when it had FOUND something, which is
    # the worst possible failure mode and the one nobody tests for. Measured 2026-08-07: a planted
    # edge over a 17,280-cell universe pushed this past six minutes on 4,200-row series alone.
    #
    # THE SUBSET IS THE TOP `--max-cluster` BY |t|, AND THE ERROR RUNS THE SAFE WAY. Clustering
    # fewer items can only yield fewer clusters, so the reported mechanism count is a LOWER bound
    # on the pool -- it under-claims discoveries rather than over-claiming them. The report says so
    # whenever the cap binds.
    ranked = sorted(zip(kept, survivors, strict=True),
                    key=lambda t: -abs(float(t[1]["t"])))  # type: ignore[arg-type]
    capped = len(ranked) > a.max_cluster
    pnl: dict[str, np.ndarray] = {}
    for (c, h), _row in ranked[:a.max_cluster]:
        m = masks[c.regime]
        base = pool([fwd_for(h)[s].where(m[s]) for s in symbols])
        full = evaluate(c, feats, base, cost_bp=a.cost_bp, min_obs=a.min_obs, keep_pnl=True)
        if full.pnl is not None:
            pnl["|".join(c.key)] = full.pnl.to_numpy(dtype=float)

    div = cluster(pnl) if pnl else None
    families = {family_of([str(x) for x in row["key"]]) for row in survivors}  # type: ignore[arg-type]
    liquidity = _liquidity_disclosure(aligned, survivors, feats, close, masks, symbols, a, secs)

    rep: dict[str, object] = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "verdict": verdict(len(survivors), len(screened), evaluated, measurable),
        "preregistration": str(PREREG.relative_to(ROOT)),
        "declared_universe": PREREGISTERED_UNIVERSE,
        "hurdle": round(bar, 3),
        "sample": {
            "symbols": symbols, "common_bars": len(idx), "pooled_rows": pooled_len,
            "symbols_dropped_for_coverage": dropped,
            "coverage_note": (
                f"{len(dropped)} symbol(s) covered under {MIN_SYMBOL_COVERAGE:.0%} of the retained "
                "grid and were dropped; bars are kept where at least "
                f"{MIN_SYMBOLS_PER_BAR} symbol(s) traded. NOTHING IS FORWARD-FILLED -- a carried "
                "close is a price nothing traded at, and the cross-sectional operators skip NaN, "
                "so a bar ranks across the names that were actually there."),
            "bar_seconds": secs, "tail_bars": a.tail_bars,
            "window": [str(idx[0]), str(idx[-1])],
            "per_symbol_bars": {s: len(d) for s, d in frames.items()},
            "is_oos_split": f"{100 * (1 - OOS_FRACTION):.0f}/{100 * OOS_FRACTION:.0f} by time",
            "cost_bp": a.cost_bp, "min_obs": a.min_obs,
        },
        "features": {
            "declared": list(DECLARED_FEATURES),
            "built": sorted(panels),
            "absent": absent,
            "transforms_unavailable": sorted(unavailable),
        },
        "counts": {
            "declared": PREREGISTERED_UNIVERSE,
            "evaluated": evaluated,
            "measurable": measurable,
            "net_positive_before_deflation": net_positive,
            "cleared_screen_F1_F2": len(screened),
            "FORMULA": len(survivors),
            "FAMILY": len(families),
            "INDEPENDENT_MECHANISM": (div.n_independent if div else 0),
            "PORTFOLIO_CONTRIBUTING": None,
        },
        "counts_note": (
            "L1.52(a): FORMULA and FAMILY are INVENTORY. Only INDEPENDENT_MECHANISM and "
            "PORTFOLIO_CONTRIBUTING may be called discoveries, and PORTFOLIO_CONTRIBUTING is null "
            "because this harness builds no portfolio -- that is UNMEASURED, not zero."),
        "unmeasurable_reasons": dict(reasons.most_common()),
        "kill_criteria_fired": dict(killed.most_common()),
        "independence": ({"headline": div.headline, "clusters": [list(c) for c in div.clusters],
                          "unmeasured_pairs": div.unmeasured_pairs, "notes": list(div.notes),
                          "clustered": len(pnl), "capped_at": a.max_cluster if capped else None,
                          "cap_note": (
                              f"clustering ran on the top {a.max_cluster} survivor(s) by |t| of "
                              f"{len(survivors)}. Fewer items can only produce fewer clusters, so "
                              "INDEPENDENT_MECHANISM is a LOWER bound on the pool."
                              if capped else "every survivor was clustered")}
                         if div else None),
        "liquidity_disclosure_F8": liquidity,
        "survivors": survivors[:a.max_detail],
        "survivors_truncated": max(0, len(survivors) - a.max_detail),
        "authority": ("NONE. Stage A. A survivor here owes CPCV/DSR and a portfolio-contribution "
                      "test before the word discovery applies."),
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, indent=1, default=str), "utf-8")

    print(f"\nfull-sweep: {rep['verdict']}")
    print(f"  evaluated {evaluated} / declared {PREREGISTERED_UNIVERSE}; measurable {measurable}; "
          f"cleared screen {len(screened)}")
    print(f"  FORMULA {len(survivors)} | FAMILY {len(families)} | INDEPENDENT MECHANISM "
          f"{div.n_independent if div else 0} | PORTFOLIO-CONTRIBUTING unmeasured")
    for k, v in killed.most_common():
        print(f"  killed by {k}: {v}")
    print(f"  artifact: {a.out}")
    return 0


def _reason_class(reason: str, unavailable: dict[str, str], absent: dict[str, str]) -> str:
    """Bucket an unmeasurable cell, distinguishing 'we could not build it' from 'too few bars'.

    Pooling pre-applies the transforms, so a cross-sectional transform that could not be computed
    reaches the evaluator as a MISSING FEATURE. Left unclassified, the report would say 'feature
    missing' for a feature that exists -- true of the pooled name, misleading about the cause.
    """
    if reason.startswith("feature missing"):
        names = reason.split(":", 1)[1].strip().split("/")
        if any(n in unavailable for n in names):
            return "cross-sectional transform unavailable (needs 2+ symbols on the common grid)"
        if any(n.split("(")[-1].rstrip(")") in absent for n in names):
            return "declared feature could not be built from this tape"
        return "feature missing"
    return reason.split(":")[0] if reason.startswith("UNMEASURED") else reason[:80]


def _liquidity_disclosure(aligned: dict[str, pd.DataFrame], survivors: list[dict[str, object]],
                          feats: dict[str, pd.Series], close: pd.DataFrame,
                          masks: dict[str, pd.DataFrame], symbols: list[str],
                          a: argparse.Namespace, secs: float) -> dict[str, object]:
    """F8: where the net came from, beside the spread that venue charged.

    WS-006's finding was that the desk's nine net-positive cells sat at a median spread 48x tighter
    than the rest of the book -- a liquidity finding wearing a signal's clothes. This sweep can
    falsify that prediction or reproduce it, but ONLY if the spread is on the tape. With no spread
    column the honest answer is UNMEASURED: reporting "no concentration detected" from an absent
    column is WS-005 exactly, and it is the reading that flatters every survivor.
    """
    spread_col = {s: next((c for c in ("spread_bp", "spread") if c in d), None)
                  for s, d in aligned.items()}
    have = {s: c for s, c in spread_col.items() if c}
    if len(have) != len(aligned) or not aligned:
        return {"verdict": "UNMEASURED",
                "reason": ("no spread column on every symbol's bars, so the WS-006 prediction "
                           "cannot be tested here. This is an inability to check, NOT an absence "
                           "of concentration."),
                "symbols_with_spread": sorted(have)}
    med = {s: float(pd.to_numeric(aligned[s][have[s]], errors="coerce").median()) for s in symbols}
    per_symbol: dict[str, dict[str, float]] = {}
    for row in survivors[:a.max_detail]:
        key = tuple(str(x) for x in row["key"])          # (category, op, horizon, regime, l, r)
        c = Combination(key[0], key[4], key[5], key[1], key[2], key[3])
        h = max(1, round(_HORIZON_SECONDS[key[2]] / secs))
        m = masks[key[3]]
        nets = {}
        for s in symbols:
            one = evaluate(c, feats, _one_symbol(forward(close, h)[s].where(m[s]), symbols, s),
                           cost_bp=a.cost_bp, min_obs=a.min_obs)
            nets[s] = round(one.net_bps, 4) if one.ok else float("nan")
        per_symbol["|".join(key)] = nets
    return {"verdict": "MEASURED", "median_spread_by_symbol": med, "survivor_net_by_symbol":
            per_symbol,
            "note": ("WS-006 predicts survivors concentrate in the tightest-spread symbols. Compare "
                     "the two maps above: if the net lives where the spread is smallest, this is "
                     "the liquidity finding again rather than a new one.")}


def _one_symbol(series: pd.Series, symbols: list[str], keep: str) -> pd.Series:
    """The pooled target with every symbol but one masked out -- same grid, one contributor.

    Rebuilding a shorter pooled vector would misalign against the pooled features, which are
    positionally aligned by construction. Masking preserves the geometry and lets the evaluator's
    own finiteness filter do the selection.
    """
    parts = [series if s == keep else pd.Series(np.nan, index=series.index) for s in symbols]
    return pool(parts)


if __name__ == "__main__":
    raise SystemExit(main())
