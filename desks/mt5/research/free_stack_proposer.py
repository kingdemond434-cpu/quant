"""THE FREE-STACK PROPOSER -- every alt column the hunter published, minted as DIRECT and INDIRECT
cells on every hypothesis-lane instrument it maps to, and donated to the one gauntlet.

WHAT IT MINTS, per (source, column, mapped instrument):

    DIRECT    exogenous_conditioner   the column's level / change at an extreme
                                      (transform x threshold x side)
              alt_series_momentum     the column's momentum CROSSING an extreme
                                      (lookback x threshold x side)
    INDIRECT  alt_conditioned         a price-only base family on the same instrument, kept only
                                      in the column's high / low regime

Every row carries the source row's culture provenance (`source_culture`,
`participant_structure`, `failure_mode_hypothesis`, principal 2026-09-30) and its `uses`.

NOT A SCREEN AND NOT A SECOND JUDGE. The whole grid is minted, a rotating slice per pass from a
saved ring cursor (the `htf_anchor_proposer` pattern), so every cell reaches the gauntlet and the
ten gates remain the only thing that certifies. `tests_run` on every donation file is the number
of cells minted, so `libs.research.experiment_ledger` charges each one to its family.

Share CFDs never appear here: the hunter maps company-level columns to their index / FX proxies
for this lane and `proposer_common.donate` refuses anything the two-lane order does not hunt.

    python desks/mt5/research/free_stack_proposer.py --once
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from itertools import product
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SEAT = "free_stack_proposer"
COLUMNS = DESK / "data" / "free_stack" / "columns.json"
ROSTER = DESK / "data" / "free_stack_sources.json"
CURSOR = DESK / "data" / "free_stack" / "proposer_cursor.json"
SERIES = DESK / "data" / "lake" / "series"
REPORT = DESK / "reports" / "FREE_STACK_PROPOSER.json"
#: Rows donated per pass. NOT A BRAKE ON BREADTH: the ring cursor walks the whole grid, so every
#: cell is minted within `passes_to_cover_grid` hours; the bound keeps the registry write inside
#: the hour (measured on the box: ~4 rows/s before batching; see
#: proposer_common._record_in_registry).
MINT_ROWS_PER_PASS = 1500
CHARTS: tuple[str, ...] = ("H1", "H4")
#: THE REST OF THE LADDER, minted wherever the instrument's own bars for that chart exist
#: (principal 2026-10-06: "all timeframes ... not just h1 fully, so we can get intraday
#: mechanisms"). The three families declare every chart expressible
#: (`families_orthogonal.FAMILY_TIMEFRAMES` names none of them), and the conditioned price-only
#: bases -- session_range_breakout, overnight_drift, volatility_squeeze -- are intraday
#: mechanisms in their own right. M1 and M5 are LEFT: a free-stack column updates hourly at the
#: fastest, so below fifteen minutes the conditioner re-emits one reading many times and only
#: multiplies the trial count; that is the same reasoning the daily-panel families declare.
EXTRA_CHARTS: tuple[str, ...] = ("M15", "M30", "D1")
UNIVERSE = DESK / "data" / "universe"


def charts_for(sym: str) -> list[str]:
    """H1 and H4 always (the grid's historical charts), plus every extra chart whose bars this
    instrument holds -- a chart the desk holds no bars for is a cell the judge cannot replay."""
    return list(CHARTS) + [c for c in EXTRA_CHARTS
                           if (UNIVERSE / f"{sym}_{c}.parquet").exists()]
EXO_GRID = {"transform": ("level_z", "delta_z"), "threshold": (1.0, 1.5), "side_when_high": (1, -1)}
MOM_GRID = {"lookback": (1, 4), "threshold": (1.0, 1.5), "side_when_up": (1, -1)}
#: Price-only base families the INDIRECT arm conditions, each at its registered defaults. The
#: un-conditioned base cell is the control arm and is already an ordinary docket candidate.
BASES: tuple[str, ...] = ("session_range_breakout", "trend_ma_cross", "mean_reversion_rsi",
                          "momentum_volgate", "overnight_drift", "volatility_squeeze")
REGIMES: tuple[str, ...] = ("high", "low")
CULTURE_KEYS = ("source_culture", "participant_structure", "failure_mode_hypothesis")


def _read(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def roster_rows() -> dict[str, dict[str, Any]]:
    doc = _read(ROSTER, {}) or {}
    return {str(r.get("id")): r for r in doc.get("sources") or [] if isinstance(r, dict)}


def series_exists(sid: str) -> bool:
    return any((SERIES / f"fs_{sid}{ext}").exists() for ext in (".parquet", ".csv"))


def _row(sid: str, src: dict[str, Any], col: str, meta: dict[str, Any], sym: str, chart: str,
         family: str, params: dict[str, Any], arm: str) -> dict[str, Any]:
    from proposer_common import candidate
    mech = (f"{src.get('mechanism') or sid}; column {col} ({meta.get('why', '')}) "
            f"conditions {sym}")
    c = candidate(SEAT, sym, family, {**params, "timeframe": chart}, mech,
                  f"{family} on fs_{sid}.{col} -> {sym} {chart} [{arm}]",
                  {"source_row": sid, "column": col, "arm": arm})
    c.update({k: src.get(k, "UNMEASURED") for k in CULTURE_KEYS})
    c["chart"] = chart
    c["required_data"] = [f"desks/mt5/data/lake/series/fs_{sid}.parquet"]
    c["uses"] = src.get("uses")
    c["falsifier"] = (f"fs_{sid}.{col} ({arm}) has no measurable relation to {sym} at {chart} "
                      "out of sample")
    return c


def build_grid(columns: dict[str, Any], roster: dict[str, dict[str, Any]]
               ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The full grid, in a stable order (source, column, symbol, chart, arm)."""
    out: list[dict[str, Any]] = []
    skipped: dict[str, str] = {}
    for sid in sorted(columns):
        src = roster.get(sid)
        if src is None:
            skipped[sid] = "no roster row"
            continue
        if not series_exists(sid):
            skipped[sid] = "no data/lake/series/fs_<id> frame on this host yet"
            continue
        for col in sorted(columns[sid]):
            meta = columns[sid][col] or {}
            for sym, chart in ((hs, c) for hs in (meta.get("hypothesis") or [])
                               for c in charts_for(str(hs))):
                base = {"source": f"fs_{sid}", "signal": col}
                for t, thr, side in product(*EXO_GRID.values()):
                    out.append(_row(sid, src, col, meta, sym, chart, "exogenous_conditioner",
                                    {**base, "transform": t, "threshold": thr,
                                     "side_when_high": side}, "direct:level"))
                for lb, thr, side in product(*MOM_GRID.values()):
                    out.append(_row(sid, src, col, meta, sym, chart, "alt_series_momentum",
                                    {**base, "lookback": lb, "threshold": thr,
                                     "side_when_up": side}, "direct:momentum"))
                for fam, reg in product(BASES, REGIMES):
                    out.append(_row(sid, src, col, meta, sym, chart, "alt_conditioned",
                                    {**base, "base_family": fam, "base_params": {},
                                     "transform": "level_z", "regime": reg, "threshold": 1.0},
                                    f"indirect:{fam}|{reg}"))
    return out, skipped


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    columns = _read(COLUMNS, {}) or {}
    grid, skipped = build_grid(columns, roster_rows())
    doc: dict[str, Any] = {"built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                           "writer": "research/free_stack_proposer.py", "seat": SEAT,
                           "sources_with_columns": len(columns), "skipped": skipped,
                           "grid_total": len(grid)}
    if not grid:
        doc.update({"built": 0, "minted": 0, "status": "NO_SERIES" if columns else "NO_COLUMNS",
                    "why": ("no free-stack source has published a series on this host yet; "
                            "the hunter's FREE_STACK_YIELD.json says which door is shut")})
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1), "utf-8")
        print(f"free_stack_proposer: {doc['status']} -- nothing to mint")
        return 0
    start = int((_read(CURSOR, {}) or {}).get("at") or 0) % len(grid)
    cands = grid[start:start + MINT_ROWS_PER_PASS]
    if len(cands) < MINT_ROWS_PER_PASS:
        cands += grid[:min(MINT_ROWS_PER_PASS - len(cands), start)]
    nxt = (start + len(cands)) % len(grid)
    arms: dict[str, int] = {}
    for c in cands:
        arm = str((c.get("evidence") or {}).get("arm") or "").split(":")[0]
        arms[arm] = arms.get(arm, 0) + 1
    path = None
    counts: dict[str, Any] = {}
    if not a.dry_run:
        from proposer_common import donate, donation_counts
        path = donate(source=SEAT, candidates=cands, tests_run=len(cands))
        counts = donation_counts()
        CURSOR.parent.mkdir(parents=True, exist_ok=True)
        CURSOR.write_text(json.dumps({"at": nxt, "of": len(grid)}), "utf-8")
    doc.update({"status": "DRY_RUN" if a.dry_run else "RAN", "cursor_from": start,
                "cursor_to": nxt, "passes_to_cover_grid": -(-len(grid) // MINT_ROWS_PER_PASS),
                "built": len(cands), "by_arm": arms,
                "minted": counts.get("donated", 0),
                "refused_wrong_lane": counts.get("refused_wrong_lane", 0),
                "refused_unstamped": counts.get("refused_unstamped", 0),
                "trials_charged": len(cands) if path else 0,
                "contract": str(path) if path else None,
                "seconds": round(time.monotonic() - t0, 1),
                "rule": ("the full grid is minted in a ring; tests_run on the contract charges "
                         "every minted cell to the lifetime experiment ledger")})
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"free_stack_proposer: grid {len(grid)}, built {len(cands)}, minted "
          f"{doc['minted']}, by arm {arms}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
