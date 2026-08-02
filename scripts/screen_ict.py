#!/usr/bin/env python3
"""SCREEN THE ICT FAMILY -- the organ that makes libs/ict more than a library nobody calls.

WHY THIS EXISTS, AND IT IS AN ADMISSION. Fourteen detectors landed with full test suites and no
caller, which is the desk's own "built but never runs" class -- the one this codebase keeps finding
in itself, most recently in the governing layer and in breadth_expander. Building a family and
wiring it to nothing produces exactly as much E[log W] as not building it, and takes longer.

WHAT IT DOES. Loads bars, computes every ICT detector, and puts each one through
`libs.research.axis_screen.stage_a_screen` -- the desk's own audited screen, chosen over anything
bespoke for three reasons that matter more here than usual:

  IT CATCHES LOOKAHEAD A SECOND TIME. SUSPECT-LOOKAHEAD fires on |IC| > 0.35 or timing Sharpe > 6.
  The detectors already pass a future-invariance proof, but that proof checks the FEATURE; this
  checks the feature-against-target ALIGNMENT, which is a different leak and the one that produced
  the desk's bithumb IC-0.72 fake. An ICT family is exactly where a too-good number should be
  disbelieved first.
  IT DISTINGUISHES REFUTED FROM UNDERPOWERED. SCREEN-WEAK is graveyard-grade negative knowledge;
  SCREEN-UNDERPOWERED means the sample could not resolve the question either way. Recording the
  second as the first would let this family be "killed" by a thin sample, and negative knowledge
  the desk did not earn is worse than none.
  IT REQUIRES THE SIGNAL TO LEAD. The de-contamination gate kills signals that merely COINCIDE
  with the target -- and a great many pattern features are coincident by construction.

EVERY RESULT IS LOGGED, WIN OR LOSE (§26.3: reporting only the printer is p-hacking). Fourteen
detectors screened and fourteen weak is a publishable outcome and the one the desk's 420/420 prior
expects.

NO PROMOTION AUTHORITY. Screening is stage A. Nothing here pre-registers, promotes, or sizes.

Read-only over bars. Writes one artifact. No keys, no order paths.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ict import crypto as ict_crypto  # noqa: E402
from libs.ict import patterns as ict  # noqa: E402
from libs.research.axis_screen import stage_a_screen  # noqa: E402

BARS = ROOT / "data/bars"
REPORT = ROOT / "data/ict_screen.json"
HISTORY = ROOT / "data/ict_screen_history.jsonl"

#: name -> callable. Both halves of the family, screened together: the classical detectors run on
#: any OHLC, the crypto-native ones need perp columns and say so when they are missing.
DETECTORS = {
    "ict_fvg": ict.fair_value_gap,
    "ict_fvg_size": ict.fvg_size,
    "ict_displacement": ict.displacement,
    "ict_sweep": ict.liquidity_sweep,
    "ict_mss": ict.market_structure_shift,
    "ict_order_block": ict.order_block,
    "ict_breaker": ict.breaker_block,
    "ict_premium_discount": ict.premium_discount,
    "ict_funding_window": ict_crypto.funding_window,
    "ict_session": ict_crypto.session_partition,
    "ict_equal_highs": ict_crypto.equal_highs,
    "ict_equal_lows": ict_crypto.equal_lows,
    "ict_oi_flush": ict_crypto.oi_flush,
    "ict_sweep_into_funding": ict_crypto.sweep_into_funding,
}


def _rel(p: Path) -> str:
    """Display path, repo-relative when it is inside the repo.

    SECOND OCCURRENCE OF THIS BUG IN ONE SESSION -- `relative_to` RAISES on a path outside ROOT,
    so an unguarded call turns an honest "the file is missing" report into a ValueError exactly
    when the missing-file path is being exercised. scripts/acquire_data.py had it too. A third
    instance means this belongs in a shared util rather than being fixed locally again.
    """
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def load_bars() -> tuple[pd.DataFrame | None, str]:
    """Bars from data/bars/*.parquet|csv, or an honest reason there are none.

    Deliberately NOT synthesised. A screen run on generated data produces verdicts about the
    generator, and those verdicts would enter the funnel wearing the same vocabulary as real ones.
    """
    if not BARS.exists():
        return None, (f"{_rel(BARS)} does not exist. data/ is gitignored, so this is "
                      "expected in a fresh checkout and a REAL blocker on the VPS.")
    files = sorted([*BARS.glob("*.parquet"), *BARS.glob("*.csv")])
    if not files:
        return None, f"no parquet/csv under {_rel(BARS)}"
    f = files[0]
    try:
        df = pd.read_parquet(f) if f.suffix == ".parquet" else pd.read_csv(f)
    except (OSError, ValueError) as e:
        return None, f"{f.name} unreadable: {str(e)[:80]}"
    need = {"open", "high", "low", "close"}
    if not need <= set(df.columns):
        return None, f"{f.name} lacks OHLC -- has {sorted(df.columns)[:8]}"
    return df, f.name


def screen_one(name: str, fn, df: pd.DataFrame, horizon_days: float) -> dict:
    """One detector through the desk's own audited screen."""
    try:
        sig = fn(df).to_numpy(dtype="float64")
    except KeyError as e:
        return {"detector": name, "verdict": "INPUT-MISSING", "why": str(e)[:140],
                "note": ("the crypto-native detectors need perp columns (open_interest, "
                         "timestamp); absence is reported, never imputed")}
    except Exception as e:
        return {"detector": name, "verdict": "ERROR", "why": f"{type(e).__name__}: {str(e)[:120]}"}
    if not np.isfinite(sig).any() or float(np.nanstd(sig)) <= 0:
        return {"detector": name, "verdict": "DEGENERATE",
                "why": ("zero dispersion -- a constant cannot separate two states of the world. "
                        "Recorded as barren rather than screened, the same rule the moat miner "
                        "applies")}
    ret = df["close"].pct_change().fillna(0.0).to_numpy(dtype="float64")
    out = stage_a_screen(sig, ret, name=name, horizon_days=horizon_days)
    return {"detector": name, **{k: v for k, v in out.items() if k != "name"}}


def main() -> int:
    t0 = time.time()
    df, src = load_bars()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    if df is None:
        out = {"ts": datetime.now(tz=UTC).isoformat(), "state": "NO BARS", "reason": src,
               "screened": 0,
               "next": ("build a bar panel from the moat tape (data/moat/<venue>/<symbol>/) or "
                        "point BARS at an existing one. The tape is 15s-resolution L2+trades; "
                        "resampling it to bars is the missing step, not the data."),
               "note": ("bars are NOT synthesised when absent -- a screen run on generated data "
                        "produces verdicts about the generator, and they would enter the funnel "
                        "wearing the same vocabulary as real ones")}
        REPORT.write_text(json.dumps(out, indent=1), "utf-8")
        print(f"ict-screen: NO BARS -- {src}")
        print("  refused to synthesise: a verdict about a generator is not one about a market")
        return 0

    horizon = 1.0
    rows = [screen_one(n, f, df, horizon) for n, f in DETECTORS.items()]
    tally: dict[str, int] = {}
    for r in rows:
        tally[str(r.get("verdict", "?"))] = tally.get(str(r.get("verdict", "?")), 0) + 1
    interesting = [r for r in rows if r.get("verdict") == "SCREEN-INTERESTING"]
    suspect = [r for r in rows if r.get("verdict") == "SUSPECT-LOOKAHEAD"]

    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "seconds": round(time.time() - t0, 2),
        "source": src, "bars": len(df), "horizon_days": horizon,
        "screened": len(rows), "tally": tally,
        "interesting": [r["detector"] for r in interesting],
        "suspect_lookahead": [r["detector"] for r in suspect],
        "results": rows,
        "note": ("EVERY detector logged, win or lose (§26.3 -- reporting only the printer is "
                 "p-hacking). Fourteen screened and fourteen weak is a publishable outcome and "
                 "the one the desk's 420/420 prior expects. SCREEN-UNDERPOWERED is NOT a "
                 "refutation: it means the sample could not resolve the question either way, and "
                 "recording it as negative knowledge the desk did not earn is worse than none."),
        "authority": "NONE -- stage A only. Nothing here pre-registers, promotes or sizes.",
    }
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": out["ts"], "screened": len(rows), "tally": tally},
                            separators=(",", ":")) + "\n")

    print(f"ict-screen: {len(rows)} detectors on {len(df)} bars from {src} | {out['seconds']}s")
    for v, c in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {v:<22} {c}")
    if suspect:
        print(f"  SUSPECT-LOOKAHEAD on {', '.join(r['detector'] for r in suspect)} -- disbelieve "
              "first: a too-good IC here is alignment leakage, not edge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
