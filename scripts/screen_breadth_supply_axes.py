#!/usr/bin/env python3
"""Owed generate runs 2026-08-11: market_breadth (matured clock, 40d) + circulating_supply
(data-utilization-paralysis: 21st ingested axis with zero screened hypotheses).

MECHANISM-FIRST, grid PRE-DECLARED, every cell logged -- the ones that fail included. Verdicts
come exclusively from libs.research.axis_screen.stage_a_screen (angle-20 de-contamination baked
in). ZERO PROMOTION AUTHORITY: a pass earns a pre-registered forward clock, never a cent.

MARKET BREADTH -- timing hypothesis (TARGET/HORIZON duty: breadth is an AGGREGATE regime signal,
so the mechanism-appropriate target is ABSOLUTE timing return on the tradeable aggregate, not a
cross-section). Mechanism: breadth measures participation; narrow rallies (few names above their
own trend) are distribution-shaped and precede weaker aggregate returns; broad participation is
accumulation-shaped. Signals: pct_above_20dma, pct_above_50dma, pct_new_20d_high (levels,
z-scored by the harness). Target: BTCUSDT forward return, h in {1, 5} on NON-OVERLAPPING blocks
(sampling step == horizon; zwin scaled h=1->20, h=5->12, the screen_idle_axes convention).
6 cells = 6 DSR-counted trials. VARIANT CONSIDERED AND NOT RUN (counted as considered, so the
trial record is honest): equal-weight basket target over the same 78-symbol universe -- deferred
because the basket is not the desk's tradeable timing instrument today; if any BTC cell reads
SCREEN-INTERESTING the basket construction runs BEFORE any clock registration.

WITH 50 BREADTH ROWS ON DISK the h=5 cells have ~9 usable blocks: the expected verdict there is
SCREEN-UNDERPOWERED, which is the harness saying "could not tell" -- recorded, never graveyarded.

CIRCULATING SUPPLY -- PRE-REGISTRATION ONLY, deliberately. The collector is 5 days old: 61 rows
over 4 point-in-time vintages, one cross-section per day. A supply-GROWTH series does not exist
yet, and screening TODAY's float_fraction against HISTORICAL returns is precisely the
pct_circ_now conditioning-variable look-ahead this desk already paid for on the unlock axis
(desk lesson, data/unlock_event_screen.json). The honest conversion of an axis with one vintage
is a FROZEN forward design, so the hypothesis is pre-registered here -- direction, construction,
horizons, and the screenable date -- and the screen runs when the window exists. Attempting the
backward screen today would convert a coverage gap into a fabricated trial.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.lawful import guard as _law_guard  # noqa: E402

OUT = ROOT / "reports/axis_screens/breadth_supply_20260811.json"
BREADTH = ROOT / "data/market_breadth.parquet"
BTC = ROOT / "data/lake/bronze/futclose_daily/BTCUSDT.jsonl"

#: Pre-declared grid: (signal column, horizon days). Executed in full, logged in full.
GRID = [("pct_above_20dma", 1), ("pct_above_20dma", 5),
        ("pct_above_50dma", 1), ("pct_above_50dma", 5),
        ("pct_new_20d_high", 1), ("pct_new_20d_high", 5)]
_ZWIN = {1: 20, 5: 12}

SUPPLY_PREREG = {
    "axis": "circulating_supply",
    "registered": None,  # stamped at write time
    "status": "ACCRUING -- screen frozen until the vintage series exists",
    "hypothesis": (
        "Cross-sectional DILUTION: names with high 20d circulating-supply growth underperform "
        "low-dilution names in RELATIVE (cross-sectionally demeaned) forward returns. Mechanism: "
        "emission and unlock recipients are structural sellers; float expansion must be absorbed "
        "by new demand at the margin."),
    "direction": "NEGATIVE (high dilution -> low relative forward return)",
    "construction": (
        "signal[t] = 20d log growth of point-in-time circulating_supply per symbol, from "
        "data/circulating_supply.jsonl vintages only (known_from <= t; never a *_now field). "
        "Target: cross-sectionally demeaned h-day forward futclose return, h in {5, 20}, "
        "non-overlapping blocks, panel stacked symbol-major -- the screen_oi_ls_axes "
        "construction."),
    "trials_declared": "2 cells (h=5, h=20). Each is DSR-counted when run.",
    "screenable_when": (
        "earliest 2026-10-06 (~60 daily vintages -> 40 usable 20d-growth observations per "
        "symbol at h=5). The date is a DATA-WINDOW definition (L1.48 exemption class), not a "
        "probation."),
    "float_fraction_variant": (
        "float_fraction level (low float -> unlock overhang -> negative relative return) is a "
        "DECLARED SECOND TRIAL, runnable forward-only from first vintage; it shares the unlock "
        "axis's mechanism family, so its novelty screen must cite the unlock graveyard rows."),
}


def _breadth_cells() -> list[dict]:
    import numpy as np
    import pandas as pd

    from libs.research.axis_screen import stage_a_screen

    bdf = pd.read_parquet(BREADTH)
    bdf["date"] = pd.to_datetime(bdf["ts"], utc=True).dt.strftime("%Y-%m-%d")
    px = pd.DataFrame([json.loads(ln) for ln in BTC.read_text("utf-8").splitlines()])
    joined = bdf.merge(px, on="date", how="inner").sort_values("date").reset_index(drop=True)
    closes = joined["close"].to_numpy("float64")
    cells: list[dict] = []
    for col, h in GRID:
        sig = joined[col].to_numpy("float64")
        # Non-overlapping h-day blocks: sample every h days; ret[k] spans the block ending at
        # sample k, so signal[k] (observed at block end) predicts ret[k+1] -- the harness's own
        # convention, kept exactly (see screen_idle_axes SAMPLING CONVENTION).
        idx = list(range(0, len(joined), h))
        s = sig[idx][1:]
        c = closes[idx]
        r = c[1:] / c[:-1] - 1.0
        cell = stage_a_screen(
            np.asarray(s), np.asarray(r), name=f"breadth_{col}_h{h}",
            zwin=_ZWIN[h], horizon_days=float(h), target_symbol="BTCUSDT")
        cell["signal"], cell["horizon_days"] = col, h
        cell["n_samples"] = len(r)
        cells.append(cell)
    return cells


def main() -> int:
    _law_guard()
    now = datetime.now(UTC).isoformat()

    # Novelty gate BEFORE compute (universal duty): screen the breadth hypothesis against the
    # graveyard. Advisory -- a redundant verdict skips the screen and says so loudly.
    novelty: dict[str, object] = {"checked": False}
    try:
        from scripts.build_graveyard_priors import build

        from libs.alpha_factory.hypothesis_novelty import hypothesis_novelty
        priors, _counts = build()
        res = hypothesis_novelty(
            "market breadth participation timing: share of perp universe above own 20d/50d "
            "moving average and 20d-high share, z-scored, predicting BTCUSDT forward absolute "
            "return 1d and 5d",
            features=("market_breadth", "timing", "btc", "participation"), priors=priors)
        novelty = {"checked": True, "novel": bool(res), "nearest_id": res.nearest_id,
                   "nearest_similarity": res.nearest_similarity,
                   "nearest_lesson": res.nearest_lesson}
    except Exception as exc:  # the gate being unbuildable must be LOUD, never a silent pass
        novelty = {"checked": False, "error": f"{type(exc).__name__}: {exc}"}

    cells: list[dict] = []
    if novelty.get("checked") and not novelty.get("novel", True):
        verdict = "SKIPPED-REDUNDANT (graveyard match; see novelty block)"
    else:
        cells = _breadth_cells()
        verdict = "; ".join(f"{c['name']}: {c.get('verdict')}" for c in cells)

    SUPPLY_PREREG["registered"] = now
    payload = {
        "generated": now,
        "owed_by": ("cadence generation_due 2026-08-09 (market_breadth matured 40d) + "
                    "max_audit data-utilization-paralysis (circulating_supply 0 screened)"),
        "novelty_gate": novelty,
        "breadth_cells": cells,
        "breadth_verdict": verdict,
        "trials_counted": len(cells),
        "variants_considered_not_run": ["equal-weight basket timing target (declared above)"],
        "supply_preregistration": SUPPLY_PREREG,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1) + "\n", "utf-8")
    print(f"breadth+supply screen -> {OUT}")
    print(f"  novelty: {novelty}")
    for c in cells:
        print(f"  {c['name']}: {c.get('verdict')} ic={c.get('ic')} n_eff={c.get('n_eff')}")
    print(f"  supply: {SUPPLY_PREREG['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
