"""Candidates from the tick tape -- the one dataset nobody else can buy.

WHAT THE MOAT WAS WORTH BEFORE THIS, MEASURED 2026-09-07. `mined_ground.scan_moat` awards a
symbol `MOAT_WEIGHT * days_of_tape` and that is the tape's ENTIRE contribution to research. On
the live docket that is a flat +36 for the 245 symbols with coverage, against XAUUSD's total
score of 5233 -- 0.7%. So 5.66 GB of broker-native ticks, the desk's only genuinely proprietary
asset and the direct cause of a disk crisis, produced ZERO candidates. It re-ordered a list.

Attention is not a hypothesis. A ranking nudge cannot be backtested, cannot pass a gate and
cannot become a sleeve, so no amount of tape could ever reach the money path through it.

WHAT ONLY TICKS CAN SAY. Bars are a summary of the tape with the microstructure removed --
that removal is the whole point of a bar, and it is also everything the desk paid to record:

    spread regime       the cost of trading, per hour, in the venue's own quotes. A bar cannot
                        say whether its range was crossed cheaply or expensively.
    tick intensity      how hard the book worked to produce that bar. Two identical H1 candles,
                        one built from 80 quotes and one from 4,000, are different events.
    signed flow         the net sign of mid changes inside the bar -- direction of pressure,
                        not just of outcome.

Each is a CONDITIONING VARIABLE, and the desk already has families that consume exactly these:
`liquidity_regime` and `orderflow_imbalance` read `orthogonal_sweep._tape_series`. So the gap was
never the machinery; nothing was proposing cells for it.

THE BAR HERE IS DELIBERATELY LOW, AND THAT IS NOT A LOOSENED GATE. This proposes; it does not
judge. Every row it writes enters the same docket as every other candidate and faces the same ten
gates, the same CPCV, the same lockbox. Setting a high bar HERE would be a second, unaudited
judge upstream of the real one, tuned by whoever wrote this file -- which is precisely the
overfitting the gauntlet exists to catch. What this must not do is emit noise at cost, so it
requires a minimum sample and a minimum separation and states both.

SPLIT IN TIME, ALWAYS. The effect is measured on the first 70% of the window and must survive the
last 30% with the same sign at Welch |t| >= 2. A candidate whose edge exists only in the part it
was found in is not proposed -- not because it would fail a gate later (it would), but because
spending gauntlet compute on it is the conversion problem this desk already has. Sign agreement
ALONE was the first rule here and pure noise cleared it: a synthetic random walk produced a
candidate at -0.186 sd in sample and -0.116 out, same sign, on terciles whose standard error was
0.10 sd. Two standard errors on held-out data is the minimum that means anything.

    python desks/mt5/research/moat_miner.py            # measure, write candidates
    python desks/mt5/research/moat_miner.py --dry-run  # measure, write nothing
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

TICKS = BASE / "data" / "tape" / "ticks"
UNIVERSE = BASE / "data" / "universe"
OUT = BASE / "data" / "hypotheses" / "moat_candidates.json"

#: Day-partitions read per symbol. The same 30 every other tape reader takes, so this never asks
#: for a file `archive_tape` may have shipped off the box.
TAPE_DAYS = 30
#: Bars a (symbol, feature, regime) cell needs before its number means anything. Below this the
#: tercile split is a handful of observations wearing a percentile.
MIN_BARS = 240
#: Bars required in the out-of-sample third alone.
MIN_OOS_BARS = 60
#: Minimum |mean forward return| separation between the top and bottom tercile, in units of the
#: bar's own return standard deviation. Small on purpose -- see the note above on why the bar is
#: low here -- but not zero: below this the cell is indistinguishable from the noise floor and
#: proposing it spends gauntlet compute to learn nothing.
MIN_SEPARATION_SD = 0.06
#: Fraction of the window the terciles are FITTED on. The rest is held out and is where the
#: effect has to survive.
IS_FRACTION = 0.70
#: Welch t the held-out separation must clear. Two is the conventional "distinguishable from
#: zero", and it is a PROPOSAL filter rather than one of the ten gates -- it asks only whether
#: this is worth the gauntlet's compute, and the gauntlet still decides everything else.
#: Sign agreement alone was the first rule here and pure noise cleared it; see `scan_symbol`.
MIN_OOS_T = 2.0

#: (feature name, the family that consumes it, what the family needs). The families already exist
#: and already read the tape through `orthogonal_sweep._tape_series`; this only proposes cells.
FEATURES = (
    ("spread_z", "liquidity_regime", "spread series from the tick tape"),
    ("flow_z", "orderflow_imbalance", "signed tick flow from the tick tape"),
    ("tick_intensity_z", "liquidity_regime", "tick counts from the tick tape"),
)


def _tape_frame(symbol: str, days: int = TAPE_DAYS):
    """The symbol's recent ticks as one frame, or None. Same window every other reader uses."""
    import pandas as pd
    d = TICKS / symbol
    if not d.exists():
        return None
    frames = []
    for f in sorted(d.glob("*.parquet"))[-days:]:
        try:
            frames.append(pd.read_parquet(f, columns=["ts", "bid", "ask"]))
        except Exception:                                       # noqa: BLE001
            continue                                            # a torn partition is not fatal
    if not frames:
        return None
    t = pd.concat(frames, ignore_index=True)
    t["ts"] = pd.to_datetime(t["ts"], utc=True)
    return t.dropna(subset=["bid", "ask"]).sort_values("ts").set_index("ts")


def tape_features(symbol: str, rule: str = "1h"):
    """Hourly spread / flow / intensity from the ticks, as z-scores. None when there is no tape.

    Z-SCORED, NOT RAW, because the candidate has to be about a REGIME rather than about a level.
    A raw spread of 0.3 means something different on XAUUSD and on EURUSD, and a rule keyed to a
    level would be a rule about the instrument's units. The trailing window is long enough to
    describe "normal for this symbol" and short enough that a structural repricing moves it.
    """
    import numpy as np
    t = _tape_frame(symbol)
    if t is None or len(t) < 500:
        return None
    spread = (t["ask"] - t["bid"]).resample(rule).mean()
    mid = (t["ask"] + t["bid"]) / 2.0
    step = mid.diff()
    flow = np.sign(step).resample(rule).sum()
    intensity = mid.resample(rule).count()
    import pandas as pd
    out = pd.DataFrame({"spread": spread, "flow": flow, "intensity": intensity}).dropna()
    if len(out) < MIN_BARS:
        return None
    # A TRAILING PERCENTILE RANK, NOT A Z-SCORE, and the difference is not cosmetic.
    #
    # The first version scored each feature as a rolling z and cut terciles at thresholds FITTED
    # on the in-sample period. Those thresholds do not partition the held-out period: measured on
    # a synthetic symbol with a large planted effect, the out-of-sample third landed 76
    # observations in the top tercile and ONE in the bottom, so a 1.68 sd in-sample effect could
    # not be evaluated out of sample at all and the candidate was silently dropped. On live data
    # the same thing happens whenever the regime MIX drifts, which is most of the time, and it
    # fails toward "the tape has no edges" -- the most expensive possible wrong answer here.
    #
    # A rank over the trailing window is causal (it uses only bars already past), needs no fitted
    # threshold, and is stable by construction: the top third is the top third in every period.
    # It is also what a live rule would actually compute, so what the gauntlet receives is the
    # rule this proposed rather than a translation of it. A degenerate series ranks 0.5
    # everywhere and simply yields no tercile members, which is declined cleanly.
    for src, name in (("spread", "spread_z"), ("flow", "flow_z"), ("intensity", "tick_intensity_z")):
        out[name] = out[src].rolling(168, min_periods=48).rank(pct=True)
    # NO FRAME-WIDE dropna, AND THAT IS THE WHOLE POINT OF THIS COMMENT. `DataFrame.dropna()`
    # removes a row if ANY column is NaN, so a single degenerate feature empties the frame and
    # every OTHER feature is silently lost with it. Measured while writing this: a synthetic
    # symbol with a constant tick count gives `intensity` a rolling std of zero, which
    # `replace(0.0, nan)` turns into an all-NaN `tick_intensity_z` -- and the frame-wide dropna
    # then returned ZERO rows, so a large, deliberately planted spread effect was not proposed.
    # A real instrument that quotes at a fixed cadence, or a session where the spread is pegged,
    # would have done the same thing on the box and looked exactly like "the tape has no edges".
    #
    # Each feature is therefore dropped on its own, by its consumer in `scan_symbol`. A feature
    # that cannot be computed costs that feature and nothing else.
    return out


def _forward_returns(symbol: str, index):
    """Next-bar return on the H1 chart, aligned to `index`. None when the bars are absent.

    THE RETURN IS THE NEXT BAR'S, NOT THIS ONE'S. Conditioning this bar's return on this bar's
    own tick statistics is a tautology -- a violent bar has a wide spread and a high tick count
    BECAUSE it moved -- and it would manufacture an enormous effect out of nothing. The feature
    must precede the return it claims to predict.
    """
    import pandas as pd
    f = UNIVERSE / f"{symbol}_H1.parquet"
    if not f.is_file():
        return None
    try:
        df = pd.read_parquet(f)
    except Exception:                                           # noqa: BLE001
        return None
    col = "time" if "time" in df.columns else ("ts" if "ts" in df.columns else None)
    if col is None or "close" not in df.columns:
        return None
    df[col] = pd.to_datetime(df[col], utc=True)
    px = df.set_index(col)["close"].sort_index()
    ret = px.pct_change().shift(-1)                             # the NEXT bar's return
    return ret.reindex(index).dropna()


def scan_symbol(symbol: str) -> list[dict]:
    """Candidate rows this symbol's tape supports. Empty list is a normal, common answer."""
    feats = tape_features(symbol)
    if feats is None:
        return []
    fwd = _forward_returns(symbol, feats.index)
    if fwd is None or len(fwd) < MIN_BARS:
        return []

    rows: list[dict] = []
    for feature, family, needs in FEATURES:
        if feature not in feats.columns:
            continue
        # PER-FEATURE ALIGNMENT. Each feature is dropped on its own and intersected with the
        # returns on its own, so a feature that cannot be computed on this symbol costs that
        # feature and not the sweep. See the note in `tape_features` for what a frame-wide
        # dropna did instead.
        col = feats[feature].dropna()
        common = col.index.intersection(fwd.index)
        if len(common) < MIN_BARS:
            continue
        x_all, y_all = col.loc[common], fwd.loc[common]
        sd = float(y_all.std())
        if not (sd > 0):
            continue
        cut = int(len(common) * IS_FRACTION)
        if cut < MIN_BARS - MIN_OOS_BARS or len(common) - cut < MIN_OOS_BARS:
            continue
        x_is, y_is = x_all.iloc[:cut], y_all.iloc[:cut]
        x_os, y_os = x_all.iloc[cut:], y_all.iloc[cut:]
        # FIXED at the terciles of a percentile rank, so nothing is fitted and both periods are
        # partitioned identically. See the note in `tape_features`.
        lo_q, hi_q = 1 / 3, 2 / 3
        hi_is, lo_is = y_is[x_is >= hi_q], y_is[x_is <= lo_q]
        if len(hi_is) < 40 or len(lo_is) < 40:
            continue
        sep_is = (float(hi_is.mean()) - float(lo_is.mean())) / sd
        if abs(sep_is) < MIN_SEPARATION_SD:
            continue
        hi_os, lo_os = y_os[x_os >= hi_q], y_os[x_os <= lo_q]
        if len(hi_os) < 30 or len(lo_os) < 30:
            continue
        sep_os = (float(hi_os.mean()) - float(lo_os.mean())) / sd
        # SIGN AGREEMENT ALONE IS NOT A TEST, and this is the correction that mattered. The first
        # version of this function required only that the out-of-sample separation kept its sign,
        # and pure noise cleared it: measured on a synthetic random-walk symbol, spread_z produced
        # a candidate at -0.186 sd in sample and -0.116 out, same sign, n=656. With ~218
        # observations per tercile the standard error of that difference is sqrt(2/218) ~ 0.10 sd,
        # so -0.186 is under two standard errors and the sign match is close to a coin flip.
        # Shipping that to the gauntlet is the conversion problem this desk already has, paid for
        # with the compute meant to find real edges.
        #
        # Welch's t on the HELD-OUT third is the honest replacement -- unequal variances, unequal
        # sizes, no pooled-variance assumption. It is still a PROPOSAL filter and not one of the
        # ten gates: it asks only whether the difference is distinguishable from zero on data the
        # terciles were not fitted on, which is the minimum a hypothesis must clear to be worth
        # anyone's compute.
        n_hi, n_lo = len(hi_os), len(lo_os)
        var_hi = float(hi_os.var(ddof=1)) / n_hi
        var_lo = float(lo_os.var(ddof=1)) / n_lo
        denom = (var_hi + var_lo) ** 0.5
        if not (denom > 0):
            continue
        t_os = (float(hi_os.mean()) - float(lo_os.mean())) / denom
        if sep_is * sep_os <= 0 or abs(t_os) < MIN_OOS_T:
            continue
        side = "LONG" if sep_is > 0 else "SHORT"
        rows.append({
            "symbol": symbol,
            "family": family,
            "params": {"conditioning": feature, "regime": "top_tercile",
                       "rank_window_bars": 168, "threshold_pct": round(hi_q, 4),
                       "side": side, "timeframe": "H1"},
            "n": int(len(common)),
            # `exp_r` here is the IS separation expressed per unit of the bar's own risk. It is a
            # PROPOSAL statistic, not a backtested expectancy, and the field is named to match the
            # docket's schema rather than to claim more than was measured -- `source` says which.
            "exp_r": round(float(sep_is), 4),
            "max_dd_r": None,
            "source": f"moat_miner:{feature}",
            "mechanism_status": "NAMED",
            "mechanism_note": (f"{needs}; {side} when {feature} is in its top tercile "
                               f"(in-sample separation {sep_is:+.3f} sd, out-of-sample "
                               f"{sep_os:+.3f} sd at t={t_os:+.2f}, n={len(common)})"),
            "oos_separation_sd": round(float(sep_os), 4),
            "oos_t": round(float(t_os), 3),
        })
    return rows


def symbols_with_tape() -> list[str]:
    if not TICKS.exists():
        return []
    return sorted(d.name.upper() for d in TICKS.iterdir()
                  if d.is_dir() and any(d.glob("*.parquet")))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="measure, write nothing")
    ap.add_argument("--limit", type=int, default=0, help="stop after N symbols (debugging)")
    args = ap.parse_args(argv)

    syms = symbols_with_tape()
    if not syms:
        print("no tick tape on this host -- the moat miner runs on the box that records it")
        return 0
    if args.limit:
        syms = syms[:args.limit]

    rows: list[dict] = []
    scanned = skipped = 0
    for sym in syms:
        try:
            got = scan_symbol(sym)
        except Exception as exc:                                # noqa: BLE001
            # One bad symbol must never cost the whole sweep: the tape is written by more than
            # one generation of the recorder and a frame can read back with an unexpected shape.
            print(f"  {sym}: skipped ({type(exc).__name__}: {exc})")
            skipped += 1
            continue
        scanned += 1
        rows.extend(got)
        if got:
            print(f"  {sym}: {len(got)} candidate(s) -- "
                  + ", ".join(f"{r['params']['conditioning']} {r['params']['side']}"
                              for r in got))

    doc = {
        "compiled_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "hypotheses": rows,
        "symbols_scanned": scanned, "symbols_skipped": skipped,
        "symbols_with_tape": len(syms),
        "rule": (f"per (symbol, tape feature): terciles fitted on the first {IS_FRACTION:.0%} of "
                 f"{TAPE_DAYS}d of ticks, separation >= {MIN_SEPARATION_SD} sd in sample, and "
                 f"held out of sample with the same sign at Welch |t| >= {MIN_OOS_T}. "
                 f"Proposes only -- the ten gates judge."),
    }
    print(f"\n{len(rows)} candidate(s) from {scanned} symbol(s) with tape "
          f"({skipped} skipped)")
    if args.dry_run:
        print("dry run -- nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), "utf-8")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
