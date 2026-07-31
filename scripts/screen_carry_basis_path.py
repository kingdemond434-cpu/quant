"""R0206 / BR-08 -- is the carry sleeve's ENTRY RULE selecting into a widening basis?

THE QUESTION THIS ANSWERS. The desk's only deployed sleeve is cash-and-carry: long spot, short
perp, on the ``top=4`` USDT perps ranked by funding (data/cashcarry_config.json). Over 73
churn-free live round-trips it realised **-58.27 bps net of fees with only 12 bps of commission**,
of which ``price_pnl`` was **-51.74 bps**. For a delta-neutral pair the price legs cancel, so
``price_pnl`` IS the basis change -- and it should be ~0, not -51.74 bps. It also does not
amortize with hold time. That term is the DOMINANT P&L component of the only thing this desk
trades, and it is UNATTRIBUTED (L1.16: every edge understood -- mechanism, source, regime, decay --
or it is not durable).

THE MECHANISM ON TRIAL. Binance funding is computed FROM the premium index. Ranking names by
highest funding is therefore mechanically ranking them by WIDEST PERP PREMIUM. If premium at the
cross-sectional extreme keeps widening rather than converging, the sleeve is not harvesting a free
cashflow -- it is being paid to short the wrong side of an ongoing squeeze, and the funding it
collects is compensation for a basis loss it also takes.

--------------------------------------------------------------------------------------------------
PRE-REGISTRATION (constants below are the hypothesis; changing one is a NEW trial, not a re-run)
--------------------------------------------------------------------------------------------------
H1  Conditional on TOP funding rank at the close of day t, forward basis WIDENS:
    E[basis(t+h) - basis(t)] > 0 for h in HORIZONS.
H2  The effect STRENGTHENS with rank: decile 10 (highest funding) widens more than decile 9, etc.
REFUTED if top-rank forward basis change is flat or NEGATIVE (converging) at both horizons --
    which sends the live -51.74 bps back to the contamination/execution explanation.

DECISION-RELEVANT OUTPUT is not H1 alone but the full decomposition per rank bucket:
    net_bps = funding_harvest_bps + basis_leg_bps
where ``basis_leg_bps = -1e4 * (basis(t+h) - basis(t))`` -- the sign convention is the desk's own
(libs/research/cashcarry.py:38 ``basis_pnl = -(w * dbasis)``; libs/data/crypto_source.py:211
``basis = perp_close/spot_close - 1``, positive = perp premium). A widening basis LOSES money on
the short-perp leg.

--------------------------------------------------------------------------------------------------
TIMESTAMP ALIGNMENT (declared -- an unstated alignment voids a screen)
--------------------------------------------------------------------------------------------------
Bronze D1 bars are Binance klines labelled at the bar OPEN (UTC midnight). On the bar labelled t:
  * ``funding``  = SUM of the funding payments realised DURING day t
                   (libs/data/crypto_source.py:194 ``resample("1D").sum()``) -- fully known at the
                   CLOSE of day t.
  * ``basis``    = perp_close(t)/spot_close(t) - 1 -- measured at the CLOSE of day t
                   (libs/data/crypto_source.py:224).
Both are observable at the close of day t, so ranking on ``funding(t)`` and entering at
``close(t)`` carries NO look-ahead. Forward quantities use strictly later bars only.

KNOWN BIAS, AND ITS DIRECTION (stated because it is the thing that could fake a result). ``basis``
is measured from two non-synchronous closes and a bid-ask, so it carries measurement noise.
Conditioning on HIGH funding(t) partially conditions on positive basis(t) noise, and noise reverts.
That biases measured forward Δbasis DOWNWARD -- i.e. TOWARD apparent convergence, TOWARD the
carry looking good. It works AGAINST H1. A widening result therefore survives its own worst bias;
a converging result must be read with this bias in mind, which is exactly why construction ``lag1``
exists (it ranks on funding(t) but enters at close(t+1), so the entry basis is not the one the
ranking selected noise on).

--------------------------------------------------------------------------------------------------
TRIAL ACCOUNTING (L1.7 / TARGET-HORIZON SWEEP DUTY)
--------------------------------------------------------------------------------------------------
CONSTRUCTIONS x HORIZONS = every cell is a DSR-counted trial and EVERY cell is written to the
artifact, including the ones that print nothing. Reporting only the cell that worked is the
garden of forking paths. Sampling is NON-OVERLAPPING h-day blocks, so observations are
independent and the Newey-West correction has nothing left to remove (it is still applied; it
can only shrink the t-stat, which is the safe direction).

ZERO PROMOTION AUTHORITY (two-stage law). This measures a DEPLOYED sleeve's P&L decomposition.
It cannot promote anything and it cannot size anything. What it can do is tell the desk whether
its only live entry rule is adverse -- which is a REPAIR question, not a promotion question.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.ops.lawful import guard
from libs.validation.forward_stats import nw_tstat

ROOT = Path(__file__).resolve().parent.parent
BRONZE = ROOT / "data/lake/bronze/crypto"
# reports/, NOT data/ -- data/* is gitignored, and this artifact is the cited evidence behind a
# permanent graveyard row. Evidence that lives only on one box's untracked disk is not
# institutional memory; a future clone would find the citation dangling.
OUT = ROOT / "reports/carry_basis_path.json"

# ---------------------------------------------------------------- PRE-REGISTERED CONSTANTS ----
HORIZONS: tuple[int, ...] = (1, 5)          # trading days held
CONSTRUCTIONS: tuple[str, ...] = ("literal", "lag1")
LIVE_TOP_N = 4                              # data/cashcarry_config.json "top"
N_DECILES = 10
MIN_XSEC = 20                               # min symbols on a date to rank cross-sectionally
MIN_BLOCKS = 30                             # min independent blocks or the cell REFUSES to report
MIN_NONZERO_BASIS = 50                      # per-symbol usable-history floor

# Every (construction, horizon) pair is a trial. Recorded so the multiplicity is honest.
N_TRIALS = len(CONSTRUCTIONS) * len(HORIZONS)


def _load_panel() -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Wide (date x symbol) funding and basis panels from the bronze D1 lake.

    Returns ``(funding, basis, skipped)``. Symbols whose basis column is absent or effectively
    all-zero (no matching spot pair -> crypto_source sets basis 0.0) are SKIPPED BY NAME, never
    silently: a symbol with basis==0 everywhere would otherwise enter the panel as a permanent
    zero-Delta observation and dilute every mean toward zero.
    """
    fund: dict[str, pd.Series] = {}
    bas: dict[str, pd.Series] = {}
    skipped: list[str] = []
    if not BRONZE.is_dir():
        raise FileNotFoundError(f"bronze crypto lake missing: {BRONZE}")
    for sym in sorted(os.listdir(BRONZE)):
        files = glob.glob(str(BRONZE / sym / "D1" / "**" / "*.parquet"), recursive=True)
        if not files:
            skipped.append(f"{sym}:no-D1")
            continue
        df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
        if "basis" not in df.columns or "funding" not in df.columns:
            skipped.append(f"{sym}:no-basis-col")
            continue
        df = df.drop_duplicates("timestamp").set_index("timestamp").sort_index()
        if int((df["basis"] != 0).sum()) < MIN_NONZERO_BASIS:
            skipped.append(f"{sym}:basis-degenerate")
            continue
        fund[sym] = df["funding"].astype(float)
        bas[sym] = df["basis"].astype(float)
    if not fund:
        raise ValueError("no symbol in the bronze lake carries usable funding+basis")
    f = pd.DataFrame(fund).sort_index()
    b = pd.DataFrame(bas).sort_index().reindex(f.index)
    return f, b, skipped


def _cell(f: pd.DataFrame, b: pd.DataFrame, *, construction: str, h: int) -> dict[str, Any]:
    """One pre-registered (construction, horizon) trial.

    ``literal``: rank on funding(t), enter close(t), exit close(t+h)  -- what the sleeve does.
    ``lag1``   : rank on funding(t), enter close(t+1), exit close(t+1+h) -- decouples the entry
                 basis from the noise the ranking selected on (see the bias note in the header).
    """
    entry_off = 0 if construction == "literal" else 1
    dates = list(f.index)
    step = h                                        # NON-OVERLAPPING blocks -> independent obs
    # per-block, per-bucket accumulators
    dec_basis: dict[int, list[float]] = {d: [] for d in range(1, N_DECILES + 1)}
    dec_fund: dict[int, list[float]] = {d: [] for d in range(1, N_DECILES + 1)}
    top_basis: list[float] = []
    top_fund: list[float] = []
    n_blocks = 0
    i = 0
    while i < len(dates):
        t = dates[i]
        i += step
        ei = f.index.get_loc(t) + entry_off
        xi = ei + h
        if xi >= len(dates):
            continue
        rank_row = f.loc[t]
        entry_b = b.iloc[ei]
        exit_b = b.iloc[xi]
        # a name is usable only if it has a funding rank AND both basis marks
        ok = rank_row.notna() & entry_b.notna() & exit_b.notna()
        if int(ok.sum()) < MIN_XSEC:
            continue
        r = rank_row[ok]
        # funding actually harvested over the HOLD -- strictly after entry, never the ranking bar
        harvest = f.iloc[ei + 1:xi + 1].loc[:, r.index].sum(axis=0, min_count=1)
        dbasis = (exit_b[r.index] - entry_b[r.index])
        basis_leg = -1e4 * dbasis                    # bps, desk sign convention (cashcarry.py:38)
        fund_leg = 1e4 * harvest                     # bps received by the short-perp leg
        order = r.sort_values(ascending=False)
        # the LIVE rule: top-N by funding
        top = order.index[:LIVE_TOP_N]
        tb, tf = basis_leg[top].mean(), fund_leg[top].mean()
        if np.isfinite(tb) and np.isfinite(tf):
            top_basis.append(float(tb))
            top_fund.append(float(tf))
        # deciles: 10 = highest funding
        lbl = pd.qcut(order.rank(method="first"), N_DECILES, labels=False, duplicates="drop") + 1
        for d in range(1, N_DECILES + 1):
            names = lbl.index[lbl == d]
            if len(names) == 0:
                continue
            vb, vf = basis_leg[names].mean(), fund_leg[names].mean()
            if np.isfinite(vb) and np.isfinite(vf):
                dec_basis[d].append(float(vb))
                dec_fund[d].append(float(vf))
        n_blocks += 1

    cell: dict[str, Any] = {
        "construction": construction, "horizon_d": h, "n_blocks": n_blocks,
        "sampling": "non-overlapping", "min_xsec": MIN_XSEC,
    }
    # ---- REFUSAL PATH: too little independent evidence is UNMEASURED, never a verdict -----------
    if n_blocks < MIN_BLOCKS or len(top_basis) < MIN_BLOCKS:
        cell["verdict"] = "UNMEASURED"
        cell["reason"] = (f"{n_blocks} independent blocks (< MIN_BLOCKS={MIN_BLOCKS}); "
                          "refusing to report a mean this thin as evidence")
        return cell

    tb = np.asarray(top_basis, float)
    tf = np.asarray(top_fund, float)
    net = tb + tf
    ppy = 365.0 / h
    cell["top_n"] = LIVE_TOP_N
    cell["basis_leg_bps"] = round(float(tb.mean()), 3)
    cell["basis_leg_t"] = round(float(nw_tstat(tb / 1e4, ppy=ppy)), 3)
    cell["funding_leg_bps"] = round(float(tf.mean()), 3)
    cell["net_bps"] = round(float(net.mean()), 3)
    cell["net_t"] = round(float(nw_tstat(net / 1e4, ppy=ppy)), 3)
    cell["deciles"] = {
        str(d): {
            "basis_leg_bps": round(float(np.mean(dec_basis[d])), 3),
            "funding_leg_bps": round(float(np.mean(dec_fund[d])), 3),
            "net_bps": round(float(np.mean(dec_basis[d]) + np.mean(dec_fund[d])), 3),
            "n": len(dec_basis[d]),
        } for d in range(1, N_DECILES + 1) if dec_basis[d]
    }
    # H1: does the top bucket WIDEN? widening => basis_leg_bps < 0 (the short-perp leg loses)
    widens = cell["basis_leg_bps"] < 0
    # H2: monotone strengthening -- top decile's basis leg worse than the bottom decile's
    d10 = cell["deciles"].get("10", {}).get("basis_leg_bps")
    d1 = cell["deciles"].get("1", {}).get("basis_leg_bps")
    cell["h2_rank_strengthens"] = bool(d10 is not None and d1 is not None and d10 < d1)
    sig = abs(cell["basis_leg_t"]) >= 1.96
    if widens and sig:
        cell["verdict"] = "CONFIRMED-WIDENING"
    elif (not widens) and sig:
        cell["verdict"] = "REFUTED-CONVERGING"
    else:
        cell["verdict"] = "INCONCLUSIVE"
    return cell


def main() -> int:
    guard()                                        # L1.42 -- no act is exempt from the laws
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    f, b, skipped = _load_panel()
    cells = [_cell(f, b, construction=c, h=h) for c in CONSTRUCTIONS for h in HORIZONS]
    measured = [c for c in cells if c["verdict"] != "UNMEASURED"]

    if not measured:
        overall = "UNMEASURED"
    elif all(c["verdict"] == "CONFIRMED-WIDENING" for c in measured):
        overall = "CONFIRMED-WIDENING"
    elif all(c["verdict"] == "REFUTED-CONVERGING" for c in measured):
        overall = "REFUTED-CONVERGING"
    else:
        overall = "MIXED"

    doc = {
        "generated": datetime.now(UTC).isoformat(),
        "law": "L1.16 alpha attribution; L1.4 reality anchoring; R0206/BR-08",
        "row": "R0206",
        "question": ("does ranking perps by funding select into a WIDENING basis, making the "
                     "carry sleeve's -51.74 bps price_pnl a structural feature of its entry rule?"),
        "n_symbols": int(f.shape[1]),
        "span": [str(f.index.min())[:10], str(f.index.max())[:10]],
        "skipped_symbols": len(skipped),
        "trials_declared": N_TRIALS,
        "trials_run": len(cells),
        "promotion_authority": "NONE (two-stage law) -- this is a repair diagnostic, not a screen",
        "overall": overall,
        "cells": cells,
    }
    Path(args.out).write_text(json.dumps(doc, indent=2), "utf-8")

    print(f"CARRY BASIS PATH (R0206/BR-08) -- {overall}")
    print(f"  panel {f.shape[1]} symbols  {doc['span'][0]}..{doc['span'][1]}  "
          f"({len(skipped)} symbols skipped)   trials {len(cells)}")
    for c in cells:
        if c["verdict"] == "UNMEASURED":
            print(f"  {c['construction']:>8s} h={c['horizon_d']:<2d} UNMEASURED -- {c['reason']}")
            continue
        print(f"  {c['construction']:>8s} h={c['horizon_d']:<2d} n={c['n_blocks']:<4d} "
              f"top{LIVE_TOP_N}: basis {c['basis_leg_bps']:+8.2f}bps (t {c['basis_leg_t']:+.2f})  "
              f"funding {c['funding_leg_bps']:+7.2f}  NET {c['net_bps']:+8.2f}bps "
              f"(t {c['net_t']:+.2f})  {c['verdict']}")
        d = c["deciles"]
        if d:
            row = "  ".join(f"d{k}:{v['net_bps']:+.1f}" for k, v in sorted(
                d.items(), key=lambda kv: int(kv[0])))
            print(f"            net by funding decile (1=low .. 10=high):  {row}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
