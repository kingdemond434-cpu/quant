"""Mine the market's plumbing: every fix, settlement, handoff and rollover, on every instrument.

    for each instrument x catalogue moment x stamp hour x mode x side:
        signals = family_clock_transition(...)
        score   = forward return at the family's own TTL, net of cost, non-overlapping
    deflate everything by everything; donate what survives as EXACT_RECIPE

This is a PROPOSER, exactly as `factor_residual_engine` is one. It admits nothing; it knocks on
the same door the miners knock on, and the ten gates decide.

THE OFFSET IS MEASURED, NEVER ASSUMED. The catalogue is written in UTC by season because that is
how the venues publish their clocks; the family wants broker stamp-hours because that is what the
bars carry. The conversion uses `session_phase.broker_utc_offset_h`, and when the offset is
unknown the sweep RUNS NOTHING rather than assuming UTC -- a plumbing cell certified three hours
off its moment is a time-of-day curve fit with a good story.

Usage:
    python research/plumbing_miner.py
    python research/plumbing_miner.py --shuffle          # control: expect nothing
    python research/plumbing_miner.py --symbol XAUUSD
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk.family_clock_transition import CATALOGUE, MODES, family_clock_transition, stamp_hours_for  # noqa: E402
from research import proposer_common as pc                                                           # noqa: E402

SOURCE = "plumbing"
REPORT = _DESK / "reports" / "plumbing_miner.json"
HOLDS = (2, 4, 8)
LEADS = (1, 2, 4)


def _relabel_clock(d: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """The null for a CLOCK claim: keep every bar exactly as it is and move the clock.

    A return shuffle is the wrong control here. It permutes close-to-close returns and leaves the
    structure INSIDE each bar untouched, so a bar-construction artifact -- the broker's rollover
    mark printed into the hour-0 open -- survives it intact and the "control" proposes the same
    cells the real run does. Measured on the first run: seven such proposals.

    Shifting the index by a random number of hours that is not a multiple of 24 keeps every open,
    high, low, close and every artifact exactly where it was relative to its neighbours, and
    breaks only the thing the hypothesis is about: that THIS NAMED HOUR is special. The artifact
    guard applies to both runs alike, so what is left for the control to find is the clock claim
    alone, which is what a control is for.
    """
    rng = np.random.default_rng(seed)
    shift = int(rng.integers(3, 21))
    out = d.copy()
    out.index = d.index + pd.Timedelta(hours=shift)
    return out


def run(symbols: list[str] | None = None, shuffle: bool = False,
        budget_s: float = 1500.0, _inner: bool = False) -> dict:
    from research.session_phase import broker_utc_offset_h

    off, off_src = broker_utc_offset_h()
    meta = pc.universe_meta()
    have = sorted(p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet"))
    if symbols:
        want = {s.upper() for s in symbols}
        have = [s for s in have if s.upper() in want]

    rows: list[dict] = []
    skipped: dict[str, str] = {}
    artifacts: dict[str, dict[int, float]] = {}
    if off is None:
        skipped["*"] = ("broker UTC offset unknown; refusing to place catalogue moments on the "
                        "bars by assuming UTC")
        have = []
    started = time.monotonic()
    for sym in have:
        if time.monotonic() - started > budget_s:
            skipped[sym] = "sweep budget exhausted"
            continue
        d = pc.bars(sym)
        if d is None or len(d) < 24 * 250:
            skipped[sym] = "under 250 days of H1 bars"
            continue
        if shuffle:
            d = _relabel_clock(d)
        cost = pc.cost_frac(sym, meta, d["close"])
        if cost is None:
            skipped[sym] = "no contract terms to price the round trip"
            continue
        unfillable = pc.artifact_hours(d)
        if unfillable:
            artifacts[sym] = unfillable
        for label, spec in CATALOGUE.items():
            for hour in stamp_hours_for(label, off):
                for mode in MODES:
                    for side in (1, -1):
                        for hold in (HOLDS if mode != "into" else (0,)):
                            for lead in (LEADS if mode != "out_of" else (0,)):
                                params = {"label": label, "stamp_hour": int(hour), "mode": mode,
                                          "side": int(side), "lead_bars": int(lead or 2),
                                          "hold_bars": int(hold or 4)}
                                sig = family_clock_transition(d, **params)
                                sc = pc.screen(d, sig, cost, unfillable)
                                if sc is None:
                                    continue
                                rows.append({"cell": f"{sym}.{label}@{hour}.{mode}",
                                             "symbol": sym, "label": label, "why": spec["why"],
                                             "params": params, **sc})
    rows = pc.deflate(rows)
    # THE CONTROL IS PAIRED INTO THE VERDICT, not run beside it. With the artifact guard alone
    # the relabelled control still proposed exactly as many cells as the real run (10 and 10):
    # hour-of-day structure on this feed is broad enough that ANY named hour lands near
    # something. So a cell is proposed only when its t beats the SAME cell's t under a relabelled
    # clock by the proposing margin. That is "beat the placebo" implemented as arithmetic rather
    # than as a report somebody compares by eye.
    if not shuffle and rows:
        ctrl = run(symbols=symbols, shuffle=True, budget_s=budget_s, _inner=True)
        ctrl_t = {(r["cell"], json.dumps(r["params"], sort_keys=True)): float(r["t_gross"])
                  for r in ctrl.get("all", [])}
        for r in rows:
            key = (r["cell"], json.dumps(r["params"], sort_keys=True))
            t_c = ctrl_t.get(key)
            r["t_control"] = t_c
            r["t_over_control"] = (round(float(r["t_gross"]) - t_c, 3) if t_c is not None
                                   else None)
            r["proposed"] = bool(r.get("proposed") and t_c is not None
                                 and (float(r["t_gross"]) - t_c) > pc.PROPOSE_T)
    proposals = pc.best_per_cell(rows)
    cands = [pc.candidate(
        SOURCE, r["symbol"], "clock_transition", dict(r["params"]),
        mechanism=(f"{r['label']} ({r['why']}): {r['params']['mode']} at stamp hour "
                   f"{r['params']['stamp_hour']}, side {r['params']['side']:+d}"),
        title=f"{r['cell']} side={r['params']['side']:+d}",
        evidence={k: r[k] for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                    "cost_frac", "t_gross", "t_deflated_sweep",
                                    "n_tests_sweep")},
    ) for r in proposals]

    report = {"generated_at": datetime.now(tz=UTC).isoformat(), "shuffled_control": shuffle,
              "broker_utc_offset_h": off, "offset_source": off_src,
              "symbols_swept": len(have), "tests_run": len(rows),
              "cells_proposed": len(proposals), "skipped": skipped,
              # Stamp hours whose OPEN is a marked price, per symbol, with the gap's t. Reported
              # because every hour-of-day family on this desk fills at an open, and a marked
              # open pays a return nobody can collect.
              "unfillable_open_hours": artifacts,
              "proposals": proposals, "all": rows}
    if _inner:
        return report
    out = REPORT.with_name(f"{REPORT.stem}_shuffled{REPORT.suffix}") if shuffle else REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    report["report_path"] = str(out)
    if cands and not shuffle:
        report["donated"] = str(pc.donate(SOURCE, cands, len(rows)))
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--shuffle", action="store_true")
    ap.add_argument("--budget-s", type=float, default=1500.0)
    a = ap.parse_args()
    rep = run(symbols=a.symbol, shuffle=a.shuffle, budget_s=a.budget_s)
    tag = "  [SHUFFLED CONTROL]" if a.shuffle else ""
    print(f"PLUMBING MINER{tag}  offset={rep['broker_utc_offset_h']} ({rep['offset_source']})")
    print(f"  {rep['symbols_swept']} symbols, {rep['tests_run']} tests, "
          f"{rep['cells_proposed']} proposed")
    for sym, hrs in rep["unfillable_open_hours"].items():
        print(f"  UNFILLABLE OPEN {sym}: hours {hrs}  (marked prices; fills there refused)")
    for r in rep["proposals"][:25]:
        print(f"  {r['cell']:36s} side={r['params']['side']:+d} n={r['n_independent']:4d} "
              f"net={r['net_per_trade']:+.6f} t={r['t_gross']:+.2f} "
              f"t_defl={r['t_deflated_sweep']:+.2f}")
    for k, v in list(rep["skipped"].items())[:5]:
        print(f"  skipped {k}: {v}")
    print(f"written: {rep['report_path']}" + (f"  donated: {rep['donated']}"
                                              if rep.get("donated") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
