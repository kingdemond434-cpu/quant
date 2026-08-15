#!/usr/bin/env python3
"""LIVE MECHANISM SLEEVES -- generator signals become target weights, under a DECLARED EXCEPTION.

**THIS RUNS UNDER A SUSPENSION OF THE TWO-STAGE LAW, AT THE PRINCIPAL'S EXPLICIT DIRECTION.**
L1.6 says the backtest gauntlet has ZERO promotion authority and capital comes only from
pre-registered FORWARD evidence. The principal has directed that these sleeves go live now and be
judged on realised P&L: "if they earn they stay n considered validated". That decision is theirs to
make and it is recorded in `docs/research/LIVE_EXCEPTION_LEDGER.json` rather than absorbed silently
into the code -- an exception nobody wrote down becomes the rule nobody remembers agreeing to.

**WHAT THE EXCEPTION COSTS, STATED ONCE AND NOT REPEATED AT EVERY LINE.** Live P&L over weeks is
very weak evidence: at these Sharpes the standard error of a one-month return swamps the mean, so a
sleeve that "earned" over 30 days and one that did not are, statistically, the same observation.
That is not an argument against running it -- forward evidence has to start somewhere and paper
clocks are strictly slower -- it is the reason the KILL RULE below is fixed BEFORE the first fill.

**THE KILL RULE IS PRE-REGISTERED HERE, TODAY, AND IT IS THE WHOLE POINT.** "If they earn they
stay" decided after seeing the returns is not a rule, it is a garden of forking paths with money in
it: whichever sleeve looks best gets kept for a reason invented afterwards. Fixed now:

    * each sleeve carries EQUAL_CLIP_FRAC of the book, and no sleeve is ever sized up for
      performing well -- that is progression, and progression is what III.15 forbids;
    * a sleeve is RETIRED when its realised return since inception is below KILL_DRAWDOWN, or
      when REVIEW_DAYS have elapsed and its realised return is negative;
    * a sleeve that survives the review is NOT thereby validated -- it has bought the right to
      keep its clip while its forward clock keeps accruing. Live P&L starts the evidence; it does
      not finish it.

**WHAT IS ACTUALLY NEW HERE, WHICH IS LESS THAN IT LOOKS.** Of the four mechanisms proposed, one
(`taker_flow`) HAS NO GENERATOR IN THIS REPO at all, and two are already live inside the
discretionary book -- informed_order_flow via H5_cvd_divergence, liquidity_provision_immediacy via
H7/H11. Deploying all four as "four uncorrelated strategies" would have double-counted two of them
and shipped one that does not exist. The genuinely new pair is below, and two is the honest number.

**IT PLACES NOTHING.** It writes target weights. `run_margin_executor` places, the risk kernel
bounds, the gross cap binds, the ruin rails stop everything regardless of what this concluded.

    python scripts/run_mechanism_sleeves.py [--json]
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

_OUT = Path("data/mechanism_sleeve_targets.json")
_STATE = Path("data/mechanism_sleeve_state.json")
_LEDGER = Path("docs/research/LIVE_EXCEPTION_LEDGER.json")
_LAKE = "data/lake"

#: The two mechanisms this sleeve set deploys, each named by its CENSUS class rather than by the
#: generator's search-budget family -- the census is the authority on what mechanism a thing tests,
#: and `funding_stress_reversal` is filed under LIQUIDITY while testing positioning/crowding.
SLEEVES: tuple[tuple[str, str, str, dict[str, float]], ...] = (
    ("positioning_crowding_unwind", "funding_stress_reversal", "fade crowded perp leverage: "
     "positive funding means longs are paying to stay long, and that inventory unwinds on the "
     "venue's schedule rather than the holder's", {"window": 30, "z_entry": 1.5}),
    ("relative_value_convergence", "intermarket_difference", "trade the ATR-normalised residual "
     "against a reference, so the shared market factor both legs carry is differenced away rather "
     "than traded twice", {"lookback": 24, "threshold": 0.25}),
)

#: Fraction of the book each sleeve carries. EQUAL AND FIXED. Sizing by backtest Sharpe would let
#: the gauntlet allocate capital, which is precisely the authority the two-stage law withholds and
#: which this exception did NOT suspend -- the principal suspended the requirement for forward
#: evidence before going live, not the rule against letting a backtest decide position size.
EQUAL_CLIP_FRAC = 0.05

#: Realised return since inception at which a sleeve is retired, no discussion. Fixed before the
#: first fill so it cannot be renegotiated by the sleeve that breaches it.
KILL_DRAWDOWN = -0.15

#: Days after which a non-negative realised return is required to keep the clip.
REVIEW_DAYS = 30

#: Symbols. Deliberately the same liquid set the momentum book trades: a new mechanism tested on a
#: different universe confounds the mechanism with the universe, and then neither is measured.
SYMBOLS: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "LINKUSDT", "ADAUSDT")


def _exception_recorded() -> tuple[bool, str]:
    """Is the principal's suspension on record? NO LEDGER, NO SLEEVES.

    Fail-closed on purpose. This module exists only because a standing law was suspended, and a
    suspension that is not written down is indistinguishable from the law never having applied --
    which is how an exception becomes the default without anyone deciding it should.
    """
    try:
        doc = json.loads(_LEDGER.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return False, (f"{_LEDGER} unreadable ({type(exc).__name__}) -- these sleeves run under a "
                       "SUSPENSION of the two-stage law, and an unrecorded suspension is not one. "
                       "Refusing to publish targets")
    rows = doc.get("exceptions") if isinstance(doc, dict) else None
    for r in rows or []:
        if isinstance(r, dict) and r.get("id") == "live-mechanism-sleeves" and r.get("active"):
            return True, (f"exception on record: granted {r.get('granted')} by "
                          f"{r.get('granted_by')} -- {str(r.get('scope', ''))[:120]}")
    return False, (f"{_LEDGER} carries no ACTIVE 'live-mechanism-sleeves' exception. The law it "
                   "suspends is L1.6; nothing here may run without the record")


def _series(symbols: tuple[str, ...]) -> dict[str, Any]:
    """MarketSeries per symbol from the lake, funding attached where the lake holds it."""
    from libs.autodiscovery.crypto_adapter import lake_provider

    provider = lake_provider(list(symbols), lake_root=_LAKE)
    out: dict[str, Any] = {}
    for s in symbols:
        try:
            ser = provider(s)
        except Exception:
            ser = None
        if ser is not None:
            out[s] = ser
    return out


def _positions(subtype: str, series: Any, params: dict[str, float]) -> np.ndarray | None:
    from libs.autodiscovery.generators import GENERATORS

    for g in GENERATORS:
        if g.subtype == subtype:
            return np.asarray(g.fn(series, params), dtype="float64")
    return None


def build() -> dict[str, Any]:
    ok, why_exc = _exception_recorded()
    rep: dict[str, Any] = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "exception_active": ok, "exception_why": why_exc,
        "law_suspended": "L1.6 -- capital from pre-registered FORWARD evidence only",
        "kill_rule": {"clip_frac": EQUAL_CLIP_FRAC, "kill_drawdown": KILL_DRAWDOWN,
                      "review_days": REVIEW_DAYS,
                      "fixed": "BEFORE the first fill, so it cannot be renegotiated by the sleeve "
                               "that breaches it"},
        "sleeves": [], "target_weights": {}, "refused": [],
    }
    if not ok:
        rep["refused"].append(why_exc)
        return rep

    frames = _series(SYMBOLS)
    if not frames:
        rep["refused"].append(
            f"no lake series for any of {list(SYMBOLS)} -- UNMEASURED. Publishing an empty target "
            "book would read as 'go to cash' and SELL the account, which is a position nobody "
            "chose")
        return rep

    weights: dict[str, float] = {}
    for census_class, subtype, mechanism, params in SLEEVES:
        row: dict[str, Any] = {"census_class": census_class, "generator": subtype,
                               "mechanism": mechanism, "params": params, "symbols": {},
                               "clip_frac": EQUAL_CLIP_FRAC}
        live: dict[str, float] = {}
        for sym, ser in frames.items():
            pos = _positions(subtype, ser, params)
            if pos is None:
                row["error"] = f"no generator named {subtype!r} in this repo"
                break
            if len(pos) == 0:
                continue
            last = float(pos[-1])
            # A GENERATOR THAT DEGRADES TO FLAT IS SAYING ITS INPUT IS MISSING, NOT THAT THE
            # MARKET IS NEUTRAL. funding_stress_reversal returns zeros without funding data, and
            # intermarket_difference returns zeros without the reference's RANGE. Recording the
            # all-zero case separately is what keeps "no data" from being published as "no signal".
            live[sym] = last
        row["symbols"] = live
        nonzero = {k: v for k, v in live.items() if abs(v) > 1e-12}
        if not nonzero and live:
            row["state"] = "FLAT-EVERYWHERE"
            row["why"] = ("every symbol returned 0.0. For this generator that means its INPUT is "
                          "absent (funding series, or the reference's high/low), not that the "
                          "market is neutral -- the two are indistinguishable in the number and "
                          "must not be in the report")
        elif not live:
            row["state"] = "NO-SERIES"
        else:
            row["state"] = "LIVE"
            # LONG-ONLY, because the book settles on a spot-margin account where a short is a
            # borrow of the base asset rather than of quote. Refusals are recorded, never inverted.
            longs = {k: v for k, v in nonzero.items() if v > 0}
            row["shorts_refused"] = sorted(k for k, v in nonzero.items() if v < 0)
            if longs:
                per = EQUAL_CLIP_FRAC / len(longs)
                for k in longs:
                    weights[k] = round(weights.get(k, 0.0) + per, 6)
        rep["sleeves"].append(row)

    rep["target_weights"] = weights
    rep["gross_frac"] = round(sum(weights.values()), 6)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=1))
        return 0

    print(f"mechanism-sleeves: exception={'ACTIVE' if rep['exception_active'] else 'ABSENT'} -- "
          f"{rep['exception_why'][:150]}")
    for r in rep["sleeves"]:
        print(f"  [{r.get('state','?'):<16}] {r['census_class']:<30} {r['generator']}")
        if r.get("why"):
            print(f"      {r['why']}")
        if r.get("shorts_refused"):
            print(f"      shorts refused (long-only book): {', '.join(r['shorts_refused'])}")
    for w in rep["refused"]:
        print(f"  REFUSED: {w}")
    if rep["target_weights"]:
        print(f"  target weights ({rep['gross_frac']:.1%} gross): "
              + ", ".join(f"{k} {v:.3%}" for k, v in sorted(rep["target_weights"].items())))
    print(f"-> {_OUT}")
    return 0 if rep["exception_active"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
