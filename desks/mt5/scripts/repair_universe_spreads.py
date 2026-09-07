#!/usr/bin/env python3
"""Give `median_spread_pts` a PROVENANCE by recomputing it from the desk's own H1 bars.

    python scripts/repair_universe_spreads.py            # report only, changes nothing
    python scripts/repair_universe_spreads.py --apply     # write the registry

THE BLOCKER THIS CLEARS. `libs/portfolio/execution_cost.py` prices each sleeve at the hour it
actually fills, and on 2026-09-07 it priced ZERO of 76 sleeves. Not because the surface is
missing -- it covers 196 symbols -- but because the number the replay CHARGED cannot be
attributed to anything:

    241 of 251 symbols carry no `_provenance` entry for median_spread_pts at all
     23 of 195 read 0.0, i.e. the registry says the instrument is free to trade
     GBPJPY reads 1.0 beside a spread_pts_at_collection of 7.0 and hourly medians of 13-50

`universe_registry.py` names the cause and has since it was written: three producers write that
field with three different meanings -- `fetch_universe` takes the median of the H1 spread column,
`expand_universe` and `download_all_symbols` take `symbol_info.spread`, a point-in-time snapshot
that is not a median at all. "EURUSD reads 12 under one producer and 0 under the next."

THE CORRECT VALUE HAS BEEN ON DISK THE WHOLE TIME. Every symbol's H1 parquet carries a `spread`
column -- it is what `cost_surface` builds its whole per-hour surface from. EURUSD's registry says
0.0 and its own bars say 12.0. This recomputes the field from those bars, by the SAME exclusions
`cost_surface.profile_symbol` uses, and stamps where the number came from.

WHY THE EXCLUSIONS ARE SHARED AND NOT RE-DERIVED. Two modules computing "the spread" with
different filters is the producer collapse this file exists to end. Full-session days only (a
spliced short day aggregates the whole day's ticks), non-zero bars only (a zero spread is a
no-quote bar, not a free trade), and at least MIN_OBS of them -- imported from `cost_surface`, so
the surface and the registry cannot disagree about what a spread is.

IT CHANGES SLEEVE IDENTITY, AND THE DESK ALREADY HAS THE SAFE PATH FOR THAT.
`sleeve_registry.rebase_cost` fires on `cost_hash` ALONE: it keeps `forward_start` (a cost
correction does not un-observe a day), the engine replays every pass so no observation survives
priced at the old cost, and any other drifted field leaves the clock terminal. It also sets
`cost_rebase_cheaper` when a correction REDUCES the charge, which is the shape of a desk talking
itself into an edge.

THE DIRECTION HERE IS OVERWHELMINGLY MORE EXPENSIVE -- 0.0 to 12.0, 1.0 to 13.0 -- which is the
safe direction and the reason this is a repair rather than a rebase of convenience. Every symbol
the repair would make CHEAPER is listed by name in the report and counted separately, because
that is the set a reviewer must actually look at.

REPORT BY DEFAULT. `--apply` is a deliberate act: it rewrites the number every backtest, gauntlet
verdict and certificate is priced against, and the clocks rebase on the next pass.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNIVERSE = BASE / "data" / "universe"
REGISTRY = UNIVERSE / "universe.json"
REPORT = BASE / "reports" / "SPREAD_PROVENANCE.json"

#: What the `_provenance` stamp says. A reader must be able to tell this apart from
#: `realized_fills` (the desk's own executions, a strictly better source) and from an unstamped
#: value (which is what this exists to eliminate).
SOURCE = "h1_spread_median"

#: A correction this large is reported as SUSPECT rather than applied silently. Not a cap -- the
#: value is still written under --apply -- but a 50x move in the number every certificate is
#: priced against is a thing a person should see named, not discover later in a P&L.
SUSPECT_RATIO = 50.0


def measured_spread(sym: str) -> tuple[float | None, str, dict[str, Any]]:
    """The median non-zero spread on full-session days, by `cost_surface`'s own exclusions."""
    try:
        import numpy as np
        import pandas as pd

        from research.cost_surface import MIN_OBS, MIN_SESSION_BARS, SESSION_SHARE, session_bars
    except ImportError as exc:
        return None, f"cannot import the shared exclusions ({exc})", {}
    f = UNIVERSE / f"{sym}_H1.parquet"
    if not f.exists():
        return None, "no local H1 bars", {}
    try:
        df = pd.read_parquet(f, columns=["spread"])
    except (OSError, ValueError, KeyError):
        return None, "no spread column in the parquet", {}
    if df.empty:
        return None, "empty frame", {}
    idx = pd.DatetimeIndex(df.index)
    sess = session_bars(idx)
    if sess < MIN_SESSION_BARS:
        return None, "session unestablishable (<2 bars/day at mode and p90)", {}
    thr = max(MIN_SESSION_BARS, int(np.ceil(SESSION_SHARE * sess)))
    per_day = pd.Series(1, index=idx).groupby(idx.date).transform("size")
    kept = df.loc[np.asarray(per_day >= thr), "spread"].astype(float)
    nz = kept[kept > 0]
    if int(nz.size) < MIN_OBS:
        return None, (f"{int(nz.size)} priced bars on full-session days, below the {MIN_OBS} "
                      "floor -- no number is emitted, so no consumer can read one"), {}
    return float(nz.median()), "median non-zero spread on full-session H1 bars", {
        "n_bars_total": int(df.shape[0]), "n_bars_full_session": int(kept.size),
        "n_priced": int(nz.size), "zero_frac": round(1.0 - nz.size / max(kept.size, 1), 4),
        "p75": float(nz.quantile(0.75)), "p90": float(nz.quantile(0.90)),
    }


def run(apply: bool = False, write: bool = True) -> dict[str, Any]:
    try:
        doc = json.loads(REGISTRY.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": "UNMEASURED", "why": f"registry unreadable: {type(exc).__name__}"}
    rows = doc.get("symbols") if isinstance(doc, dict) and "symbols" in doc else doc
    if not isinstance(rows, dict):
        return {"status": "UNMEASURED", "why": "registry is not a symbol map"}

    corrected: list[dict[str, Any]] = []
    stamped_same: list[str] = []
    cheaper: list[dict[str, Any]] = []
    suspect: list[dict[str, Any]] = []
    kept_better: list[str] = []
    unmeasured: dict[str, str] = {}
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")

    for sym in sorted(rows):
        row = rows[sym]
        if not isinstance(row, dict):
            continue
        src = ((row.get("_provenance") or {}).get("median_spread_pts") or {}).get("source")
        if src == "realized_fills":
            # THE DESK'S OWN EXECUTIONS BEAT AN ESTIMATE FROM BARS, ALWAYS. Ten symbols carry
            # this and none of them is touched: a repair that overwrote a measurement with an
            # inference would be the same producer collapse in a new direction.
            kept_better.append(sym)
            continue
        got, why, detail = measured_spread(sym)
        if got is None:
            unmeasured[sym] = why
            continue
        old = row.get("median_spread_pts")
        old_f = float(old) if isinstance(old, (int, float)) else None
        entry = {"symbol": sym, "old": old_f, "new": got, **detail}
        if old_f is not None and abs(old_f - got) < 1e-9:
            stamped_same.append(sym)                       # right value, missing provenance
        else:
            corrected.append(entry)
            if old_f is not None and old_f > 0 and got < old_f:
                cheaper.append(entry)
            if old_f is not None and old_f > 0 and max(got / old_f, old_f / got) > SUSPECT_RATIO:
                suspect.append(entry)
        if apply:
            row["median_spread_pts"] = got
            prov = row.setdefault("_provenance", {})
            prov["median_spread_pts"] = {"at": now, "source": SOURCE, "was": old_f}

    if apply and write:
        REGISTRY.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", "utf-8")

    out = {
        "status": "MEASURED", "generated_utc": now, "applied": bool(apply),
        "n_symbols": len(rows),
        "n_corrected": len(corrected), "n_already_correct": len(stamped_same),
        "n_kept_realized_fills": len(kept_better), "n_unmeasured": len(unmeasured),
        "n_made_cheaper": len(cheaper), "n_suspect": len(suspect),
        # THE SET A REVIEWER MUST ACTUALLY LOOK AT. A correction that makes a sleeve cheaper is
        # the shape of a desk talking itself into an edge, so it is named rather than counted.
        "made_cheaper": cheaper,
        "suspect": suspect[:40],
        "corrected": corrected[:60],
        "unmeasured": dict(sorted(unmeasured.items())[:40]),
        "kept_realized_fills": sorted(kept_better),
        "rule": ("median_spread_pts is recomputed from each symbol's own H1 spread column using "
                 "cost_surface's exclusions (full-session days, non-zero bars, MIN_OBS floor) "
                 "and stamped with its source. `realized_fills` rows are never overwritten -- an "
                 "execution beats an inference. Identity: this changes cost_hash, and "
                 "sleeve_registry.rebase_cost handles a cost-only change without losing "
                 "forward_start, because the engine replays every pass."),
    }
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(out, indent=1) + "\n", "utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true",
                    help="write the registry (default: report only)")
    ap.add_argument("--no-write", action="store_true", help="do not write the report either")
    a = ap.parse_args(argv)
    r = run(apply=a.apply, write=not a.no_write)
    if r.get("status") != "MEASURED":
        print(f"REFUSED: {r.get('why')}")
        return 1
    print(f"spread provenance: {r['n_symbols']} symbols"
          f"  corrected={r['n_corrected']}  already_correct={r['n_already_correct']}"
          f"  kept_realized_fills={r['n_kept_realized_fills']}  unmeasured={r['n_unmeasured']}")
    print(f"  would make CHEAPER: {r['n_made_cheaper']}"
          + (f"  {[c['symbol'] for c in r['made_cheaper'][:12]]}" if r["made_cheaper"] else ""))
    print(f"  suspect (>{SUSPECT_RATIO:.0f}x move): {r['n_suspect']}")
    for c in r["corrected"][:12]:
        print(f"    {c['symbol']:12s} {c['old']} -> {c['new']}  ({c['n_priced']} priced bars)")
    if not a.apply:
        print("  REPORT ONLY -- nothing written to the registry. Re-run with --apply to repair.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
