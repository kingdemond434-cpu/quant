"""THE STATE-GATE PROPOSER -- every hypothesis-lane H1 instrument, crossed with the price-only
base families, minted as `sync_gated`, `entropy_gated`, `fisher_rao_gated` and `absorption_gated`
cells and donated to the one gauntlet.

WHAT IT MINTS, per (wrapper, base, symbol) on H1 -- ONE cell each, at registered defaults:

    sync_gated      the base kept where the FX+gold panel's Kuramoto R sits on the side the
                    base's mechanism class fixes (trend/breakout high, reversion low).
    entropy_gated   the base kept where the symbol's own permutation-entropy z is low.
    fisher_rao_gated  the base kept in the tail of the symbol's own Fisher-Rao distribution
                    velocity its class fixes (trend/breakout slow, reversion fast).
    absorption_gated  the base kept in the tail of the hypothesis-lane panel's standardised
                    absorption-ratio shift its class fixes (trend/breakout high, reversion low).

A base whose class is none of trend, breakout or reversion is not minted for the three
class-directed wrappers (CLASS_DIRECTED): it would return [] on every bar.

NO PARAMETER SWEEP, ON PURPOSE. The gate direction is fixed by the mechanism (sync) or by the
hypothesis itself (entropy "low"), and window / threshold sit at their registered defaults, so
each cell is ONE trial and the bar every other hypothesis must clear is never inflated by a
search over gate settings. `tests_run` on every donation is the number of cells minted, so
`libs.research.experiment_ledger` charges each one.

EACH CELL IS CHARGED EXACTLY ONCE (audit of #395). `libs.research.experiment_ledger` sums
`tests_run` across donations with no dedupe, so re-donating the same 320 cells every hour would
have charged ~7,680 phantom trials a day to the lifetime DSR and the per-family shrinkage. The
charged set is DERIVED from the proposer's own contracts -- every row in
`data/intelligence/state_gate_proposer/discoveries_*.json`, the very files the ledger counts -- so
a side ledger cannot drift from the charge, a crash after donate cannot lose it, and a box
migration carries it with the intake. Each pass donates only cells in no contract yet;
`tests_run` is that count. A cell `donate` refused is in no contract, so it is retried, never
silently dropped (refusals are counted by reason). A contract that cannot be read makes the pass
UNREADABLE and donate nothing: an unknown charged set is never read as empty.

NOT A SCREEN AND NOT A SECOND JUDGE. The whole grid is minted, at most MINT_ROWS_PER_PASS new
cells per pass, so every cell reaches the gauntlet and the ten gates remain the only thing that
certifies.

SYNC AND ABSORPTION ARE NOT MINTED ON CRYPTO CFDs (PANEL_WRAPPERS). They trade through the
weekend, when the panel's FX, metals and index members are closed: the state would be read off
bars up to MAX_STALE_HOURS old (audit of #395). fisher_rao_gated reads only the symbol's own
bars, so it is minted on crypto like entropy_gated.

Share CFDs never appear: the symbol list is filtered by
`research.universe_policy.may_hypothesise`, and `proposer_common.donate` refuses anything the
two-lane order does not hunt in any case.

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
INTEL = DESK / "data" / "intelligence" / SEAT
REPORT = DESK / "reports" / "STATE_GATE_PROPOSER.json"
#: New rows donated per pass. NOT A BRAKE ON BREADTH: every never-donated cell is minted within
#: `passes_to_cover_grid` hours; the bound keeps the registry write inside the hour (see
#: proposer_common._record_in_registry).
MINT_ROWS_PER_PASS = 1500
CHARTS: tuple[str, ...] = ("H1",)
WRAPPERS: tuple[str, ...] = ("sync_gated", "entropy_gated", "fisher_rao_gated",
                             "absorption_gated")
#: Wrappers whose gate direction is read off the base's mechanism class.
CLASS_DIRECTED: frozenset[str] = frozenset({"sync_gated", "fisher_rao_gated", "absorption_gated"})
#: Wrappers whose state is a weekday-closed PANEL, so a weekend-trading class is not minted.
PANEL_WRAPPERS: frozenset[str] = frozenset({"sync_gated", "absorption_gated"})
#: Price-only base families each wrapper gates, at their registered defaults. The un-gated base
#: cell is the control arm and is already an ordinary docket candidate.
BASES: tuple[str, ...] = ("session_range_breakout", "trend_ma_cross", "volatility_squeeze",
                          "mean_reversion_rsi", "range_reversion")
#: The registered defaults each wrapper is minted at -- written on the recipe so the identity is
#: explicit, never a parameter search.
DEFAULTS: dict[str, dict[str, Any]] = {
    "sync_gated": {"window": 128, "tail": 1.0 / 3.0, "min_history": 30, "min_symbols": 12},
    "entropy_gated": {"order": 4, "window": 168, "z_window": 24 * 60, "threshold": 1.0},
    "fisher_rao_gated": {"window": 120, "nu": 5.0, "tail": 1.0 / 3.0, "min_history": 30},
    "absorption_gated": {"window": 360, "short": 24, "step": 6, "k_divisor": 5,
                         "min_members": 20, "tail": 1.0 / 3.0, "min_history": 30},
}


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


#: Asset classes whose sessions the FX+gold panel does not cover (they trade when it is closed).
SYNC_EXCLUDED_CLASSES: frozenset[str] = frozenset({"crypto"})


def sync_applies(symbol: str) -> bool | None:
    """True/False from the symbol's asset class, None when the class cannot be read here."""
    try:
        from research.universe_policy import asset_class_of
        klass = str(asset_class_of(symbol)).lower()
    except Exception:
        return None
    if not klass:
        return None
    return klass not in SYNC_EXCLUDED_CLASSES


def _contract_rows(doc: Any) -> list[dict[str, Any]] | None:
    rows = doc.get("discoveries") if isinstance(doc, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else None


def charged_cells(root: Path | None = None) -> tuple[set[str] | None, list[str]]:
    """(the cell keys of every row in this seat's contracts, unreadable contract paths). The set
    is None when any contract cannot be read: the charge is then unknown, not empty.

    BOTH FORMS OF A CONTRACT ARE READ (audit of #395 v3). `scripts/disk_guard.py` packs
    discoveries_*.json older than three days into rollup_YYYYMMDD.jsonl.gz -- one contract
    document per line -- and deletes the originals, so a reader of the .json files alone forgets
    every cell charged more than three days ago and re-charges it."""
    import gzip
    d = INTEL if root is None else root
    keys: set[str] = set()
    bad: list[str] = []
    if not d.is_dir():
        return keys, bad
    for f in sorted(d.glob("discoveries_*.json")):
        try:
            rows = _contract_rows(json.loads(f.read_text("utf-8")))
        except (OSError, ValueError):
            rows = None
        if rows is None:
            bad.append(str(f))
            continue
        keys.update(cell_key(r) for r in rows)
    for f in sorted(d.glob("rollup_*.jsonl.gz")):
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                docs = [json.loads(line) for line in fh if line.strip()]
        except (OSError, ValueError, EOFError):
            bad.append(str(f))
            continue
        for doc in docs:
            rows = _contract_rows(doc)
            if rows is None:
                bad.append(f"{f} (a line that is not a contract)")
                break
            keys.update(cell_key(r) for r in rows)
    return (None if bad else keys), bad


def through_the_door(cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The candidates `proposer_common.donate` will WRITE, decided before it is called.

    donate records `tests_run` in the contract it writes, before its door refuses rows, so the
    count the ledger reads is the count passed in. Running the same two refusing checks here --
    the two-lane filter and the point-in-time stamp -- and donating only what passes means the
    contract is written ONCE with the true count (audit of #395 v4: a post-write rewrite left a
    window where the ledger read an inflated count, permanently if the leg died inside it). The
    blinding pass that also runs in donate strips fields and never refuses, so it is not needed
    here. The originals are returned, unstamped: donate stamps them itself."""
    from proposer_common import _lane_filtered, _stamped
    lane_ok, _ = _lane_filtered(list(cands))
    ok_ids = {id(c) for c in lane_ok}
    passing = [c for c in cands if id(c) in ok_ids]
    stamped, _ = _stamped(SEAT, [dict(c) for c in passing])
    keep = {cell_key(r) for r in stamped}
    return [c for c in passing if cell_key(c) in keep]


def _settle_charge(path: Path | None) -> int:
    """Rewrite the contract's tests_run to the rows it actually holds, and return that count.

    `donate` takes tests_run BEFORE its door refuses rows, and a refused row is retried on the
    next pass -- so charging the pre-door count would charge every refused cell again each hour
    (audit of #395 v3). The contract is this seat's own file, written a moment ago; the rewrite
    is atomic, and the ledger then charges exactly the rows donated."""
    if path is None:
        return 0
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return 0
    rows = _contract_rows(doc)
    n = len(rows or [])
    if isinstance(doc, dict) and doc.get("tests_run") != n:
        # Only reached if donate's door refused a row through_the_door passed (a race on the
        # policy or the stamper). Correct it, but never crash the leg after a donation: a
        # Windows replace onto an open file raises, and the donation has already happened.
        doc["tests_run"] = n
        tmp = path.with_name(path.name + ".tmp")
        try:
            tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
            tmp.replace(path)
        except OSError:
            return n
    return n


def cell_key(c: dict[str, Any]) -> str:
    """The identity a charge is keyed on: family, symbol and the full recipe."""
    return json.dumps([c.get("family"), c.get("symbol"), c.get("params")], sort_keys=True,
                      default=str)


def mechanism_class(base: str) -> str:
    from mt5desk.family_state_gates import mechanism_class as mc
    return mc(base)


def bases_for(wrapper: str) -> list[str]:
    """The bases `wrapper` can gate: a class-directed wrapper only where the base's class fixes
    a direction."""
    if wrapper not in CLASS_DIRECTED:
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
    elif wrapper == "fisher_rao_gated":
        side = "slow" if mech in ("trend", "breakout") else "fast"
        why = (f"{base} ({mech}) on {sym} pays only where the Fisher-Rao velocity of its own "
               f"return distribution is {side}: a {mech} entry "
               + ("rides a stable regime" if side == "slow"
                  else "fades a distribution that has just dislocated"))
        falsifier = (f"{base} on {sym} {chart} kept in {side} distribution drift earns no more "
                     "out of sample than the ungated base")
    elif wrapper == "absorption_gated":
        side = "rising" if mech in ("trend", "breakout") else "falling"
        why = (f"{base} ({mech}) on {sym} pays only where the hypothesis-lane panel's "
               f"absorption ratio is {side} against its 15-day mean: a {mech} entry "
               + ("needs a coupled, fragile market whose shocks propagate" if side == "rising"
                  else "needs a decoupled market whose moves stay local and revert"))
        falsifier = (f"{base} on {sym} {chart} kept where the absorption shift is {side} earns "
                     "no more out of sample than the ungated base")
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
                if wrapper in PANEL_WRAPPERS:
                    ok = sync_applies(sym)
                    if not ok:
                        why = (f"{wrapper}:off_panel_session" if ok is False
                               else f"{wrapper}:class_UNMEASURED")
                        refused[why] = refused.get(why, 0) + 1
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
    charged, unreadable = charged_cells()
    if charged is None:
        doc.update({"built": 0, "minted": 0, "trials_charged": 0, "status": "UNREADABLE",
                    "unreadable_contracts": unreadable,
                    "why": ("a contract of this seat cannot be read, so which cells were already "
                            "charged is unknown; nothing is donated until it is repaired, because "
                            "an unknown charge read as empty would re-charge the grid")})
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1), "utf-8")
        print(f"state_gate_proposer: UNREADABLE -- {len(unreadable)} contract(s)")
        return 2                       # the leg goes RED: a silent stand-down is not a pass
    fresh = [c for c in grid if cell_key(c) not in charged]
    cands = fresh[:MINT_ROWS_PER_PASS]
    arms: dict[str, int] = {}
    for c in cands:
        arms[str(c["family"])] = arms.get(str(c["family"]), 0) + 1
    path = None
    counts: dict[str, Any] = {}
    charged_now = 0
    # donate names its contract to the minute, so a second pass in the same minute would
    # overwrite the first contract and lose its charged cells: that pass stands down.
    clash = INTEL / f"discoveries_{time.strftime('%Y%m%d_%H%M', time.gmtime())}.json"
    if cands and not a.dry_run and clash.exists():
        doc["same_minute"] = str(clash)
        cands = []
    if cands and not a.dry_run:
        from proposer_common import donate, donation_counts
        door = through_the_door(cands)
        doc["refused_before_donate"] = len(cands) - len(door)
        path = donate(source=SEAT, candidates=door, tests_run=len(door)) if door else None
        counts = donation_counts()
        charged_now = _settle_charge(path)
    doc.update({"status": "DRY_RUN" if a.dry_run else ("RAN" if cands else (
                    "SAME_MINUTE" if doc.get("same_minute") else "ALL_CHARGED")),
                "already_charged": len(grid) - len(fresh), "uncharged": len(fresh),
                "passes_to_cover_grid": -(-len(fresh) // MINT_ROWS_PER_PASS),
                "built": len(cands), "by_family": arms,
                "minted": counts.get("donated", 0),
                "refused_wrong_lane": counts.get("refused_wrong_lane", 0),
                "refused_unstamped": counts.get("refused_unstamped", 0),
                "refused_by_reason": {r: n for r, n in (
                    ("wrong_lane", counts.get("refused_wrong_lane", 0)),
                    ("unstamped", counts.get("refused_unstamped", 0))) if n},
                "trials_charged": charged_now,
                "contract": str(path) if path else None,
                "seconds": round(time.monotonic() - t0, 1),
                "rule": ("one cell per (wrapper, base, symbol) at registered defaults; each is "
                         "donated and charged exactly once; the charged set is read from this "
                         "seat's own contracts, and a refused cell is retried")})
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"state_gate_proposer: grid {len(grid)}, built {len(cands)}, minted "
          f"{doc['minted']}, by family {arms}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
