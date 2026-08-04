#!/usr/bin/env python3
"""FAILED-BREAKOUT REVERSION -- the study, run in the order the pre-registration demands.

    docs/research/FAILED_BREAKOUT_PREREGISTRATION.md  <- kill criteria, written before this file

ORDER OF OPERATIONS, AND IT IS NOT NEGOTIABLE:

    1. MECHANISM      does forced-liquidation flow measurably collapse OI across swept levels?
    2. PATTERN        only then, and only on the pre-declared grid
    3. VALIDATION     CPCV, DSR on the HONEST trial count, PBO, White's Reality Check, Brier
    4. COSTS          modelled BEFORE scoring; net only, gross Sharpe never printed
    5. CAPACITY       the size at which impact eats the edge
    6. GO / NO-GO     one verdict, and no variants proposed in the same report

Mining first and explaining afterwards is how a pattern search becomes a mechanism story. The
mechanism step can only ever DOWNGRADE the claim -- it never rescues a dead edge -- so running it
first costs nothing and running it last is worthless.

WHAT THIS SCRIPT WILL NOT DO. It will not synthesise bars, funding, open interest or liquidation
prints. A verdict computed on generated data is a fact about the generator, and it would enter the
funnel wearing the same vocabulary as a real one. With no data it reports BLOCKED and names the
producer -- which is a finding about the desk, not about the hypothesis.

Read-only. Writes one artifact. No keys, no order paths, no sizing.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.failed_breakout import LevelParams, find_events  # noqa: E402
from libs.research.liquidation_mechanism import mechanism_evidence  # noqa: E402
from libs.research.oi_divergence import classify, quadrant_evidence  # noqa: E402

BARS = ROOT / "data/bars"
REPORT = ROOT / "data/failed_breakout_study.json"
PREREG = ROOT / "docs/research/FAILED_BREAKOUT_PREREGISTRATION.md"

#: The pre-declared grid. Every axis here was written into the pre-registration BEFORE this file
#: existed; adding one without amending that document voids the deflation.
GRID = {
    "k": (20, 50, 100),
    "n_touch": (1, 2, 3),
    "theta_atr": (0.1, 0.25, 0.5),
    "n_fail": (1, 3, 5),
    "timeframe": ("1m", "5m"),
    "hold": ("fixed", "atr_stop", "retest"),
}
N_SYMBOLS_PLANNED = 10

#: Kill thresholds, mirrored from the pre-registration. Mirrored, not re-decided: the test
#: `test_kill_criteria_match_the_preregistration` fails if these drift from the document.
KILL = {"dsr_min": 0.95, "pbo_max": 0.30, "rc_p_max": 0.05, "net_sharpe_min": 0.5,
        "decay_min_frac": 0.40, "capacity_min_usd": 50_000.0, "k7_effect_floor": 0.2}


def nominal_trials() -> int:
    n = N_SYMBOLS_PLANNED
    for v in GRID.values():
        n *= len(v)
    return n


#: Independent-bet count for the 10-symbol axis. THE PRE-REGISTRATION AND THE FORMULA DISAGREED
#: AND THE DISAGREEMENT WAS IN THE STRATEGY'S FAVOUR, which is the only direction that matters.
#: The document estimated "~3 effective"; the standard equicorrelated formula
#: N/(1+(N-1)rho) at rho=0.8 gives 1.22, i.e. 593 effective trials against the document's 1,458.
#: Fewer trials means LESS deflation and an EASIER bar, so taking the formula would have quietly
#: handed the strategy credit the pre-registration never granted it.
#:
#: Rule applied, and it generalises: when an estimate and a formula disagree about how much credit
#: a strategy gets, take the one that gives it LESS. The deflation is a courtesy; it must never be
#: the thing that saves the result.
N_EFF_SYMBOLS = 3.0


def effective_trials() -> int:
    """Trials with the SYMBOL axis deflated, because crypto perps are not independent bets.

    Both this and the nominal count are reported, and per the pre-registration the NOMINAL count
    governs if the verdict differs between them.
    """
    n = N_EFF_SYMBOLS
    for v in GRID.values():
        n *= len(v)
    return round(n)


def _load_bars() -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    if not BARS.exists():
        return out
    for f in sorted([*BARS.rglob("*.parquet"), *BARS.rglob("*.csv")]):
        try:
            df = pd.read_parquet(f) if f.suffix == ".parquet" else pd.read_csv(f)
        except Exception:
            continue
        cols = {c.lower(): c for c in df.columns}
        if not {"high", "low", "close"} <= set(cols):
            continue
        out[f.stem] = df.rename(columns={cols[c]: c for c in ("high", "low", "close")})
    return out


def _series(df: pd.DataFrame, *names: str) -> pd.Series | None:
    """First matching column, or None. None means NOT PUBLISHED -- never a column of zeros."""
    low = {c.lower(): c for c in df.columns}
    for n in names:
        if n in low:
            return df[low[n]]
    return None


def blocked(reason: str, missing: list[str]) -> dict:
    return {
        "ts": datetime.now(tz=UTC).isoformat(),
        "verdict": "BLOCKED -- NOT RUN",
        "stage_reached": "0 of 6 (data acquisition)",
        "reason": reason,
        "missing": missing,
        "preregistration": str(PREREG.relative_to(ROOT)),
        "nominal_trials": nominal_trials(),
        "effective_trials": effective_trials(),
        "note": ("NOTHING IS SYNTHESISED. A verdict computed on generated bars is a fact about the "
                 "generator and would enter the funnel wearing the same vocabulary as a real one. "
                 "The kill criteria are already pre-registered and binding, so when the data "
                 "lands this runs against thresholds nobody chose after seeing it."),
        "authority": "NONE. Stage A. Nothing here pre-registers, promotes, sizes or trades.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbol", default=None, help="restrict to one symbol")
    a = ap.parse_args()

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    bars = _load_bars()
    if a.symbol:
        bars = {k: v for k, v in bars.items() if a.symbol.lower() in k.lower()}

    if not bars:
        out = blocked(
            "data/bars holds no OHLCV. The recorders have never written on this machine and both "
            "venues answer 403 to CONNECT from this container, so neither history nor a live "
            "feed is reachable. This is the upstream blocker, not a property of the hypothesis.",
            ["perp OHLCV 1m/5m", "aggregated open interest", "funding history",
             "liquidation prints", "order-book depth snapshots"])
        REPORT.write_text(json.dumps(out, indent=1), "utf-8")
        print("failed-breakout: BLOCKED -- no OHLCV under data/bars, and no venue reachable.")
        print(f"  trial budget already declared: {out['nominal_trials']} nominal / "
              f"{out['effective_trials']} effective")
        print(f"  kill criteria already binding:  {PREREG.relative_to(ROOT)}")
        print("  Nothing is synthesised: a verdict on generated bars measures the generator.")
        return 0

    # ---------------------------------------------------------------- STAGE 1: MECHANISM
    per_symbol = []
    for sym, df in sorted(bars.items()):
        p = LevelParams()
        events = find_events(df, p)
        swept = np.array([e.sweep_idx for e in events], dtype="int64")
        # THE CONTROL IS LEVELS THAT WERE NOT SWEPT, not bars before the sweep. A before/after
        # split would confirm the hypothesis on any series with a trend in it.
        all_levels = {e.level_idx for e in events}
        unswept = np.array(sorted(set(range(p.k, len(df) - p.k)) - all_levels - set(swept.tolist())
                                  ), dtype="int64")
        rng = np.random.default_rng(0)
        if unswept.size > swept.size and swept.size:
            unswept = rng.choice(unswept, swept.size, replace=False)

        ev = mechanism_evidence(
            swept, unswept,
            oi=_series(df, "open_interest", "oi", "sum_open_interest"),
            funding=_series(df, "funding", "funding_rate", "fr"),
            liq=_series(df, "liquidation_notional", "liq_notional", "liquidations"))
        row = {"symbol": sym, "n_events": len(events), **ev.as_dict()}

        # OI DIVERGENCE, MEASURED ON THE SAME PASS. It asks the same question the sweep study
        # asks -- who paid for the move -- but needs neither a level nor a sweep, so it resolves
        # on strictly less data and its failure is more informative: if the quadrants do not
        # separate at all, no rule built on top of them can create the effect.
        oi_s = _series(df, "open_interest", "oi", "sum_open_interest")
        if oi_s is not None:
            fwd = df["close"].pct_change().shift(-1)          # return AFTER the bar, never before
            q = classify(df["close"], oi_s, window=12, price_eps=1e-4, oi_eps=1e-4)
            row["oi_quadrants"] = quadrant_evidence(q, fwd).as_dict()
        per_symbol.append(row)

    unmeasurable = [r for r in per_symbol if r["verdict"] == "UNMEASURABLE"]
    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "stage_reached": "1 of 6 (mechanism)",
        "preregistration": str(PREREG.relative_to(ROOT)),
        "nominal_trials": nominal_trials(), "effective_trials": effective_trials(),
        "kill_criteria": KILL,
        "mechanism": per_symbol,
    }
    if unmeasurable:
        out["verdict"] = "MECHANISM UNMEASURABLE -- study halted before the pattern search"
        out["why"] = (
            f"{len(unmeasurable)}/{len(per_symbol)} symbol(s) lack open interest, which is the "
            "PRIMARY discriminator between forced liquidation and discretionary supply. Without "
            "it the two hypotheses are observationally identical, and any pattern edge found "
            "downstream would be an UNEXPLAINED regularity rather than evidence for this "
            "mechanism. Running the pattern search now would produce a number that could not be "
            "attributed, which is how a search becomes a story. Acquire OI first.")
        print("failed-breakout: MECHANISM UNMEASURABLE -- halted before the pattern search")
    else:
        out["verdict"] = "MECHANISM MEASURED -- pattern search is next"
        out["why"] = "stages 2-6 require the cost model and the full grid; not run in this pass"
        print("failed-breakout: mechanism measured on all symbols")
    for r in per_symbol:
        print(f"  {r['symbol']:<20} events={r['n_events']:<5} {r['verdict']:<14} "
              f"oi_d={r['oi_collapse_d']}")
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
