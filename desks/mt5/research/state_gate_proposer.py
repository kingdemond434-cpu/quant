"""THE STATE-GATE PROPOSER -- every hypothesis-lane H1 instrument, crossed with the price-only
base families, minted as `sync_gated` and `entropy_gated` cells and donated to the one gauntlet.

WHAT IT MINTS, per (wrapper, base, symbol) on H1 -- ONE cell each, at registered defaults:

    sync_gated      the base kept where the FX+gold panel's Kuramoto R sits on the side the
                    base's mechanism class fixes (trend/breakout high, reversion low). A base
                    whose class is neither is not minted: it would return [] on every bar.
    entropy_gated   the base kept where the symbol's own permutation-entropy z is low.

NO PARAMETER SWEEP, ON PURPOSE. The gate direction is fixed by the mechanism (sync) or by the
hypothesis itself (entropy "low"), and window / threshold sit at their registered defaults, so
each cell is ONE trial and the bar every other hypothesis must clear is never inflated by a
search over gate settings. `tests_run` on every donation is the number of cells minted, so
`libs.research.experiment_ledger` charges each one.

NOT A SCREEN AND NOT A SECOND JUDGE. The whole grid is minted, a rotating slice per pass from a
saved ring cursor (the `free_stack_proposer` pattern), so every cell reaches the gauntlet and the
ten gates remain the only thing that certifies. Share CFDs never appear: the symbol list is
filtered by `research.universe_policy.may_hypothesise`, and `proposer_common.donate` refuses
anything the two-lane order does not hunt in any case.

    python desks/mt5/research/state_gate_proposer.py --once
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SEAT = "state_gate_proposer"
UNIVERSE = DESK / "data" / "universe"
CURSOR = DESK / "data" / "state_gate" / "proposer_cursor.json"
REPORT = DESK / "reports" / "STATE_GATE_PROPOSER.json"
#: Rows donated per pass. NOT A BRAKE ON BREADTH: the ring cursor walks the whole grid, so every
#: cell is minted within `passes_to_cover_grid` hours; the bound keeps the registry write inside
#: the hour (see proposer_common._record_in_registry).
MINT_ROWS_PER_PASS = 1500
CHARTS: tuple[str, ...] = ("H1",)
WRAPPERS: tuple[str, ...] = ("sync_gated", "entropy_gated")
#: Price-only base families each wrapper gates, at their registered defaults. The un-gated base
#: cell is the control arm and is already an ordinary docket candidate.
BASES: tuple[str, ...] = ("session_range_breakout", "trend_ma_cross", "volatility_squeeze",
                          "mean_reversion_rsi", "range_reversion")
#: The registered defaults each wrapper is minted at -- written on the recipe so the identity is
#: explicit, never a parameter search.
DEFAULTS: dict[str, dict[str, Any]] = {
    "sync_gated": {"window": 128, "r_threshold": 0.5, "min_symbols": 12},
    "entropy_gated": {"order": 4, "window": 168, "z_window": 24 * 60, "threshold": 1.0},
}


def _read(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def store_symbols() -> list[str]:
    """Every symbol with an H1 file in the bar store."""
    try:
        return sorted(p.name[:-len("_H1.parquet")] for p in UNIVERSE.glob("*_H1.parquet"))
    except OSError:
        return []


def allowed(symbol: str, family: str) -> bool:
    try:
        from research.universe_policy import may_hypothesise
    except Exception:
        return False
    try:
        return bool(may_hypothesise(symbol, family))
    except Exception:
        return False


def mechanism_class(base: str) -> str:
    from mt5desk.family_state_gates import mechanism_class as mc
    return mc(base)


def bases_for(wrapper: str) -> list[str]:
    """The bases `wrapper` can gate: sync only where the base's class fixes a direction."""
    if wrapper != "sync_gated":
        return list(BASES)
    from mt5desk.family_state_gates import SYNC_HIGH, SYNC_LOW
    return [b for b in BASES if mechanism_class(b) in SYNC_HIGH | SYNC_LOW]


def _row(wrapper: str, base: str, sym: str, chart: str) -> dict[str, Any]:
    from proposer_common import candidate
    mech = mechanism_class(base)
    if wrapper == "sync_gated":
        side = "high" if mech in ("trend", "breakout") else "low"
        why = (f"{base} ({mech}) on {sym} pays only where the FX+gold panel's phase "
               f"synchronisation is {side}: a {mech} entry "
               + ("needs a common driver to carry the move" if side == "high"
                  else "needs idiosyncratic, self-correcting noise"))
        falsifier = (f"{base} on {sym} {chart} kept in {side} panel synchronisation earns no more "
                     "out of sample than the ungated base")
    else:
        why = (f"{base} ({mech}) on {sym} pays more inside low permutation-entropy windows, "
               "where the path's ordinal structure is predictable")
        falsifier = (f"{base} on {sym} {chart} kept in low-entropy windows earns no more out of "
                     "sample than the ungated base")
    params = {"base_family": base, "base_params": {}, **DEFAULTS[wrapper], "timeframe": chart}
    c = candidate(SEAT, sym, wrapper, params, why, f"{wrapper}[{base}] -> {sym} {chart}",
                  {"base_family": base, "base_mechanism": mech, "arm": f"{wrapper}:{base}"})
    c["chart"] = chart
    c["required_data"] = ["desks/mt5/data/universe/*_H1.parquet"]
    c["falsifier"] = falsifier
    return c


def build_grid(symbols: list[str]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """The full grid, in a stable order (wrapper, base, symbol, chart): one cell per
    (wrapper, base, symbol) on each chart, and the symbols the lane policy set aside."""
    out: list[dict[str, Any]] = []
    refused: dict[str, int] = {}
    for wrapper in WRAPPERS:
        for base in bases_for(wrapper):
            for sym in symbols:
                if not allowed(sym, wrapper):
                    refused[wrapper] = refused.get(wrapper, 0) + 1
                    continue
                for chart in CHARTS:
                    out.append(_row(wrapper, base, sym, chart))
    return out, refused


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    symbols = store_symbols()
    grid, refused = build_grid(symbols)
    doc: dict[str, Any] = {"built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                           "writer": "research/state_gate_proposer.py", "seat": SEAT,
                           "store_symbols": len(symbols), "lane_refused": refused,
                           "bases": {w: bases_for(w) for w in WRAPPERS},
                           "grid_total": len(grid)}
    if not grid:
        doc.update({"built": 0, "minted": 0, "trials_charged": 0,
                    "status": "NO_SYMBOLS" if not symbols else "NO_HYPOTHESIS_LANE_SYMBOLS",
                    "why": "no hypothesis-lane H1 file in data/universe on this host"})
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1), "utf-8")
        print(f"state_gate_proposer: {doc['status']} -- nothing to mint")
        return 0
    start = int((_read(CURSOR, {}) or {}).get("at") or 0) % len(grid)
    cands = grid[start:start + MINT_ROWS_PER_PASS]
    if len(cands) < MINT_ROWS_PER_PASS:
        cands += grid[:min(MINT_ROWS_PER_PASS - len(cands), start)]
    nxt = (start + len(cands)) % len(grid)
    arms: dict[str, int] = {}
    for c in cands:
        arms[str(c["family"])] = arms.get(str(c["family"]), 0) + 1
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
                "built": len(cands), "by_family": arms,
                "minted": counts.get("donated", 0),
                "refused_wrong_lane": counts.get("refused_wrong_lane", 0),
                "refused_unstamped": counts.get("refused_unstamped", 0),
                "trials_charged": len(cands) if path else 0,
                "contract": str(path) if path else None,
                "seconds": round(time.monotonic() - t0, 1),
                "rule": ("one cell per (wrapper, base, symbol) at registered defaults, minted in "
                         "a ring; tests_run on the contract charges every minted cell")})
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"state_gate_proposer: grid {len(grid)}, built {len(cands)}, minted "
          f"{doc['minted']}, by family {arms}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
