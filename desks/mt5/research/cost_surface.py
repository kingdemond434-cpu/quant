#!/usr/bin/env python3
"""COST SURFACE (L1.5 / L1.28a) -- spread is a symbol x HOUR state, not one scalar per symbol.

WHAT WAS MISSING. `universe.json` carries exactly ONE cost number per symbol,
`median_spread_pts`, and it is the number every gate, certificate, stress scenario and forward
clock divides by. It is created by collapsing the per-bar `spread` column at ingest
(`fetch_universe.py:103`, `expand_universe.py:136`: `float(df["spread"].median())`), so the hour
structure is destroyed BEFORE any consumer exists and no consumer can miss it. `Costs.from_symbol`
has no hour parameter; `engine.run_backtest` computes `per_oz_cost` ONCE per cell (engine.py:248)
and charges it identically at every fill (engine.py:422) although it knows each fill bar's
timestamp. ~25 hunt/screen modules read the same scalar, so every cross-check agrees.

The desk DID already measure per-hour spread -- `moat/moat_miner.mine_symbol` builds exactly this
profile from the tick tape. It emits SEARCH POINTERS (hypothesis cards ranked by
`dear_over_cheap`) and feeds no cost model, runs on a 40-symbol rotation, and needs
`bronze/mt5_ticks`, which exists only on the trading box. That is the producer/consumer collapse
this desk keeps paying for: the distinction was computed and the consumer flattened it.

WHAT IT COSTS, measured 2026-08-29 on the desk's own artifacts with the engine's own backtest.
`family_overnight_gap_decay` signals on the first bar of the day and `wait_bars=1` puts the FILL
on the next bar -- hour 01 broker time, in a book carrying ~3% of the day's peak tick volume.

    symbol   pooled scalar   spread on its OWN fill bars   error
    USDZAR       329 pts              2028 pts            6.16x   (p90 5544 pts = 16.9x)
    EURZAR       310 pts              1918 pts            6.19x   (p90 6108 pts = 19.7x)

Both hold ten-gate certificates in `UNIVERSAL_SURVIVORS.canon.json` and both are on LIVE forward
clocks (`sleeve_registry.json`, forward_start 2026-08-27). Re-priced at their own fill-hour
spread, with the mult held EQUAL on both arms so only the spread number moves:

    mult=1.0   USDZAR +0.2951R -> +0.0802R      EURZAR +0.3316R -> +0.1293R
    mult=2.0   USDZAR +0.2535R -> -0.1764R      EURZAR +0.2926R -> -0.1120R   <-- NEGATIVE

mult=2.0 is the desk's own declared honest baseline (`Costs.from_symbol`: "a round trip crosses
the spread on the way in and again on the way out"). At that baseline both live sleeves are
LOSING sleeves, and the two-stage law is currently deciding their fate on a number 6x wrong.

THE DAMAGE IS NOT UNIFORM, which is why sampling never caught it: EURUSD is EXACTLY 12 pts at all
24 hours and XAUUSD EXACTLY 16 -- administered spreads, flat by construction -- so any spot-check
on the majors returns clean. The error concentrates in the crosses and exotics.

THE OTHER DIRECTION MATTERS MORE. A cell whose fill hour is CHEAPER than the pooled scalar is
being OVERCHARGED, and an overcharged cell dies in the gauntlet without ever raising an alert.
That is the false-null direction, the only one this desk has no instrument for.

TWO EXCLUSIONS, BOTH VERIFIED NECESSARY (not judgement calls):

1. PARTIAL DAYS are the D1/H1 splice recorded in the vault -- days carrying less than 75% of
   THIS SYMBOL'S OWN session length (`session_bars`), never a fixed bar count; see SESSION_SHARE
   for the 74-symbol defect a fixed count caused on this module's first run. They are separable
   with certainty, not by assumption: on USDZAR the h00 bar of a partial day carries median
   tick_volume 66,507 and `spread == 0` in 99.9% of cases, while the h00 bar of a full day
   carries 127 ticks and a 3,606-pt spread. A spliced DAILY bar aggregates a whole day of ticks;
   a genuine dead-book hour cannot. 524x apart -- two populations, not one noisy one. The ratio
   is PUBLISHED per symbol as `splice_tickvol_ratio` so the exclusion is auditable rather than
   asserted (measured: USDZAR 18.4x, EURZAR 14.8x; 3M 0.7x, i.e. 3M's dropped days are ordinary
   half-sessions and only 0.7% of its days).

2. `spread == 0` BARS are absence, not a free trade. They are dropped from the percentiles and
   their share is PUBLISHED as `zero_frac`, because a symbol whose spread column is mostly zero
   has no cost observable at all and must not be able to report a confident cheap number.

`n_nonzero` below `MIN_OBS` yields `UNMEASURED` for that cell and never a value. Absence never
resolves to a clean verdict (L1.28a / WS-005).

WHAT IS NOT CLOSED HERE, stated plainly. The `spread` column is the broker's own recorded spread
for the bar; whether it is EXECUTABLE at hour 01 needs `symbol_info_tick` from the trading box,
which this box cannot reach. The tape evidence says the quotes are live rather than frozen -- the
h01 bar's own high-low range is a median 2.2x its spread on USDZAR, so price moves through the
wide book -- but a live-tick confirmation is owed and is recorded as such.

Run:  .venv/bin/python desks/mt5/research/cost_surface.py [--out PATH]
Fence: scripts/check_cost_surface.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parent.parent
_UNIVERSE = _DESK / "data" / "universe"
_OUT = _DESK / "data" / "cost_surface.json"

#: Minimum non-zero spread observations in a symbol x hour cell before it may carry a number.
#: Below this the cell is UNMEASURED and consumers must refuse it, not round it to the pooled
#: scalar -- rounding to the pooled scalar is exactly the defect this module exists to end.
MIN_OBS = 200

#: A day carrying less than this SHARE of the symbol's own normal session is the D1/H1 splice.
#:
#: THIS IS DELIBERATELY NOT A BAR COUNT, and the first run of this module is why. The obvious
#: version -- "a real day has >= 20 H1 bars" -- is a 24-hour-FX threshold applied as a universal
#: boundary, and it silently excluded ALL 74 US share CFDs, which trade a 6.5-hour cash session
#: and can never carry 20 bars. Their spread columns are 96%+ non-zero and perfectly usable; the
#: artifact reported them as "no usable spread column" and read as successfully built. That is
#: the anti-hardcode law (LAWS section 1) and WS-005 in one defect: a literal calibrated on one
#: asset class capping exploration, with the resulting absence rendered as a clean verdict.
#:
#: The session length is measured PER SYMBOL from its own tape instead (`session_bars`), so a
#: 24-bar FX day and a 7-bar equity day are both handled with no asset-class list anywhere.
SESSION_SHARE = 0.75

#: Never trust a session estimate below this many bars -- one bar cannot evidence a session.
MIN_SESSION_BARS = 2

#: Cells whose |log ratio| to the pooled scalar exceeds this are reported as material. 2.0x in
#: EITHER direction: undercharging manufactures survivors, overcharging kills real edges silently.
MATERIAL_RATIO = 2.0

SCHEMA = "cost-surface-1"


def session_bars(idx: pd.DatetimeIndex) -> int:
    """How many H1 bars this symbol's own NORMAL day carries.

    `max(mode, p90)` rather than the median, because on the spliced series the splice is the
    MAJORITY: USDZAR's median bars/day is 1 (58% of its days are single daily bars), so a median
    would declare a one-bar day normal and exclude nothing. The mode fails the same way on
    Accenture (mode 1 over 6,305 days). Either statistic alone is defeated by a different symbol;
    the max of the two is defeated by neither, and both describe the FULL day rather than the
    contaminated middle of the distribution.
    """
    bpd = pd.Series(1, index=idx).groupby(idx.date).size()
    if bpd.empty:
        return 0
    mode = int(bpd.mode().iloc[0]) if not bpd.mode().empty else 0
    return max(mode, int(bpd.quantile(0.90)))


def profile_symbol(df: pd.DataFrame) -> dict | None:
    """Per-hour spread percentiles for one symbol, splice-excluded and zero-excluded.

    Returns None when the frame carries no usable `spread` column at all -- distinct from a
    frame that yields UNMEASURED hours, which is a real (and reportable) measurement.
    """
    if "spread" not in df.columns or df.empty:
        return None
    idx = pd.DatetimeIndex(df.index)
    # Exclusion 1: keep only days carrying a full session BY THIS SYMBOL'S OWN STANDARD.
    sess = session_bars(idx)
    if sess < MIN_SESSION_BARS:
        return None
    thr = max(MIN_SESSION_BARS, int(np.ceil(SESSION_SHARE * sess)))
    per_day = pd.Series(1, index=idx).groupby(idx.date).transform("size")
    full = np.asarray(per_day >= thr)
    d = df.loc[full]
    if d.empty:
        return None
    hours: dict[str, dict] = {}
    hh = pd.DatetimeIndex(d.index).hour
    for h in range(24):
        cell = d.loc[hh == h, "spread"]
        n_bars = int(cell.size)
        if n_bars == 0:
            continue
        nz = cell[cell > 0].astype(float)
        n_nz = int(nz.size)
        row: dict[str, object] = {
            "n_bars": n_bars,
            "n_nonzero": n_nz,
            "zero_frac": round(float(1.0 - n_nz / n_bars), 4),
        }
        if n_nz < MIN_OBS:
            # Exclusion 2 + L1.28a: too few priced bars to state a cost. No number is emitted,
            # so no consumer can accidentally read one.
            row["status"] = "UNMEASURED"
        else:
            row["status"] = "MEASURED"
            row["p50"] = round(float(nz.median()), 2)
            row["p75"] = round(float(nz.quantile(0.75)), 2)
            row["p90"] = round(float(nz.quantile(0.90)), 2)
        hours[str(h)] = row
    if not hours:
        return None
    measured = {h: r for h, r in hours.items() if r["status"] == "MEASURED"}
    out: dict[str, object] = {
        "session_bars": int(sess),
        "session_threshold": int(thr),
        "bars_used": len(d),
        "bars_total": len(df),
        "days_full": int(np.unique(pd.DatetimeIndex(d.index).date).size),
        "days_total": int(np.unique(idx.date).size),
        "first": str(idx.min()),
        "last": str(idx.max()),
        "hours": hours,
        "n_hours_measured": len(measured),
    }
    # PUBLISH THE EVIDENCE FOR THE EXCLUSION, never just the exclusion (L2.4). A spliced DAILY
    # bar aggregates the whole day's ticks, so if the dropped days really are the splice their
    # tick volume dwarfs the kept days' (measured: USDZAR 18x, Accenture 4120x). A ratio near 1
    # means the dropped days were ordinary short sessions -- holidays and early closes -- and
    # the exclusion is costing real data rather than removing an artifact. That distinction is
    # not assertable from the bar count alone, and this is the number that settles it.
    if "tick_volume" in df.columns and len(d) < len(df):
        kept_tv = float(df.loc[full, "tick_volume"].median())
        drop_tv = float(df.loc[~full, "tick_volume"].median())
        out["excluded_days"] = int(np.unique(idx[~full].date).size)
        out["splice_tickvol_ratio"] = (round(drop_tv / kept_tv, 1) if kept_tv > 0 else None)
    if measured:
        p50s = {int(h): float(r["p50"]) for h, r in measured.items()}  # type: ignore[arg-type]
        cheap = min(p50s, key=lambda k: p50s[k])
        dear = max(p50s, key=lambda k: p50s[k])
        out["cheapest_hour"] = cheap
        out["dearest_hour"] = dear
        out["dear_over_cheap"] = round(p50s[dear] / p50s[cheap], 2) if p50s[cheap] else None
        # A flat 24h profile is an ADMINISTERED spread (the broker marks it up to a constant)
        # rather than a passed-through market one. Nothing else on this desk records which
        # symbols are which, and it decides whether an hour-conditioned cost is even meaningful.
        out["administered"] = bool(len(set(p50s.values())) == 1)
        # The desk's cost-stress multiple is a GUESSED 3x. This is the measured one.
        p90s = {int(h): float(r["p90"]) for h, r in measured.items()}  # type: ignore[arg-type]
        ratios = [p90s[h] / p50s[h] for h in p50s if p50s[h] > 0]
        out["stress_p90_over_p50"] = round(float(np.median(ratios)), 2) if ratios else None
    return out


def build(universe_dir: Path | None = None) -> dict:
    """Build the whole surface from the H1 parquets the engine already loads."""
    u = universe_dir or _UNIVERSE
    reg_path = u / "universe.json"
    registry = json.loads(reg_path.read_text("utf-8")) if reg_path.exists() else {}
    surface: dict[str, dict] = {}
    skipped: list[str] = []
    for f in sorted(u.glob("*_H1.parquet")):
        sym = f.name[: -len("_H1.parquet")]
        try:
            df = pd.read_parquet(f, columns=["spread", "tick_volume"])
        except (OSError, ValueError, KeyError) as exc:      # unreadable / column absent
            skipped.append(f"{sym}: unreadable ({type(exc).__name__})")
            continue
        prof = profile_symbol(df)
        if prof is None:
            # SAY WHICH REFUSAL THIS IS. The first version reported every skip as "no usable
            # spread column", which was false for the 74 equity CFDs it was actually dropping
            # for a session-length reason -- and a wrong reason is worse than no reason,
            # because it closes the investigation.
            if "spread" not in df.columns or df.empty:
                why = "no spread column" if not df.empty else "empty frame"
            elif session_bars(pd.DatetimeIndex(df.index)) < MIN_SESSION_BARS:
                why = "session unestablishable (<2 bars/day at mode and p90)"
            else:
                why = "no day meets its own session threshold"
            skipped.append(f"{sym}: {why}")
            continue
        meta = registry.get(sym) or {}
        pooled = meta.get("median_spread_pts")
        prof["pooled_median_spread_pts"] = float(pooled) if pooled is not None else None
        prof["tick_size"] = float(meta.get("tick_size", 0.0) or 0.0)
        prof["contract_size"] = float(meta.get("contract_size", 0.0) or 0.0)
        surface[sym] = prof
    return {
        "schema": SCHEMA,
        "built_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "min_obs": MIN_OBS,
        "session_share": SESSION_SHARE,
        "source": str(u.relative_to(_DESK.parent.parent)) if u == _UNIVERSE else str(u),
        "n_symbols": len(surface),
        "n_skipped": len(skipped),
        "skipped": skipped[:50],
        "symbols": surface,
    }


def spread_pts(surface: dict, symbol: str, hour: int | None) -> float | None:
    """The measured spread in POINTS for one symbol at one hour, or None.

    None means "this desk does not know", and every caller must treat it as a refusal rather
    than substituting the pooled scalar (L1.28a). `hour=None` returns None deliberately: a
    caller that has not said WHEN it fills has not asked this question.
    """
    if hour is None:
        return None
    sym = (surface.get("symbols") or {}).get(symbol)
    if not sym:
        return None
    cell = (sym.get("hours") or {}).get(str(int(hour)))
    if not cell or cell.get("status") != "MEASURED":
        return None
    v = cell.get("p50")
    return float(v) if v is not None else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=_OUT)
    ap.add_argument("--universe", type=Path, default=None)
    args = ap.parse_args(argv)

    rep = build(args.universe)
    if not rep["symbols"]:
        print("cost_surface: NO SYMBOLS PROFILED -- refusing to write an empty surface "
              f"(looked in {args.universe or _UNIVERSE}). Unmeasured is not OK (L1.28a).")
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n", "utf-8")

    syms = rep["symbols"]
    admin = sum(1 for v in syms.values() if v.get("administered"))
    unmeas = sum(1 for v in syms.values() for c in v["hours"].values()
                 if c["status"] == "UNMEASURED")
    total_cells = sum(len(v["hours"]) for v in syms.values())
    ratios = [(s, v["dear_over_cheap"]) for s, v in syms.items()
              if v.get("dear_over_cheap")]
    ratios.sort(key=lambda kv: -kv[1])
    print(f"cost_surface: {rep['n_symbols']} symbols, {total_cells} symbol-hour cells, "
          f"{unmeas} UNMEASURED, {admin} administered (flat 24h), "
          f"{rep['n_skipped']} skipped -> {args.out}")
    print("  widest dear/cheap ratios: " +
          ", ".join(f"{s} {r}x" for s, r in ratios[:8]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
