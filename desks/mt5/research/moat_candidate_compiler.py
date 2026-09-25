#!/usr/bin/env python3
"""THE MOAT CANDIDATE EXCHANGE, PRICED AND CLAIMED -- Tier-1 M6 (the record) and M4 (the claims).

    python desks/mt5/research/moat_candidate_compiler.py --once --budget-s 240

WHAT WAS WRONG, MEASURED 2026-09-23. `libs.moat.registry` holds the 24-field candidate record and
`score_candidate` -- V = P(edge) x Novelty x Independence x DataQuality x MechanismStrength x
Capacity x InformationGain / ResearchCost, with an empty-cell bonus -- and the registry held
17,978 candidates of which 8,949 were queued and 8,741 carried NO novelty measurement at all.
Every one of those scored on `PRIOR = 0.5` for novelty AND independence, which means READY_PRIORITY
was ordering the queue on a constant. A priority queue whose priority is a constant is a FIFO with
extra arithmetic, and the exchange's whole claim -- that a department bidding compute gets the
most valuable unmined cell -- was unpaid.

`claim_candidates` had the matching defect from the other end: `queue_census` records that it "is
the intended lease and has zero callers outside tests". The exchange could be bid into and nobody
ever bid.

WHAT THIS ORGAN DOES, in two halves that must run in this order.

  1. PRICE (M6). For a bounded batch of queued candidates missing them, MEASURE the three fields
     the score multiplies and cannot guess:
       novelty_vs_live       -- against the certified canon and the live sleeve roster;
       novelty_vs_graveyard  -- against every cell the gate verdict ledger records as dead;
       expected_return_independence -- 1 - the family's share of the certified canon, so the
                                       eleventh trend candidate is independent of nothing.
     The measurement is written back through `registry.mark_candidate` WITH a recomputed `score`,
     because a field the score never re-reads is a field that changed nothing.

  2. CLAIM (M4). Each department bids for the head of its own priority queue through
     `registry.claim_candidates(department, n)`, and the claimed rows are DONATED to
     `data/intelligence/moat_factory/` -- the one intake `miner_candidate_compiler` reads and the
     docket the gauntlet judges is built from. THE GAUNTLET IS SEALED AND IS NOT EDITED: the
     priority queue reaches it the way every other proposer reaches it, through the intake, which
     is why a claim here is backed by work rather than by a status change.

NOTHING HERE VETOES, CAPS OR SHRINKS ANYTHING. It re-ORDERS a queue and moves rows towards the
judge; no candidate is refused, no family is capped, and a row that cannot be priced keeps the
PRIOR it already had and is COUNTED as unpriced (L1.28a) rather than dropped.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402

SOURCE = "moat_factory"
REPORT = BASE / "reports" / "MOAT_FACTORY.json"
CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
SLEEVES = ROOT / "data" / "sleeves.json"
VERDICTS = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
#: How many queued rows one pass may price. Bounded by TIME as well (`--budget-s`); this only
#: stops a single pass from holding the sqlite write lock for the whole hour.
MAX_PRICE = 4000
#: THE HISTORIC LEASE, KEPT ONLY AS A FLOOR. It was 12 rows per department per pass, "small on
#: purpose", and on the trading box 2026-09-24 that was 276 rows an hour (12 x 23 departments)
#: against 356,087 registry candidates -- the single door out of the database, sized to walk the
#: population once every 54 days while the judge on the other side had already recorded 44,310
#: verdicts inside one hour. A lease smaller than what the judge can drink is a throttle on the
#: desk's whole judged-cells rate, and the principal's standing order forbids throttles.
#: `registry.lease_size` now MEASURES the judge's own busiest recorded hour and splits it across
#: the bidding departments, floored here so an unreadable ledger can only ever leave the door
#: where it was.
CLAIM_PER_DEPARTMENT = 12
#: Departments that bid. Read from the hourly cycle's own table when it imports, so a department
#: added there starts bidding without an edit here.
FALLBACK_DEPARTMENTS: tuple[str, ...] = ("discovery", "validate", "macro", "execution", "forward")
#: The floor under independence. A family that already owns the whole canon is not INDEPENDENT of
#: it, but it is not worthless either -- the eleventh trend signal still gets a hearing, at the
#: back of the queue. Zero would remove it from the exchange entirely, which is a veto.
INDEPENDENCE_FLOOR = 0.05
#: The three novelty levels, stated once: an exact (family, symbol) match is not novel; the same
#: family on another instrument is half-novel; a family the reference set has never held is novel.
NOVEL_EXACT, NOVEL_FAMILY, NOVEL_NEW = 0.0, 0.5, 1.0


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def departments() -> tuple[str, ...]:
    try:
        import hourly_cycle  # type: ignore[import-not-found]
        got = tuple(str(d) for d in hourly_cycle.DEPARTMENTS)
        return got or FALLBACK_DEPARTMENTS
    except Exception:
        return FALLBACK_DEPARTMENTS


# --------------------------------------------------------------------- the reference sets
def live_reference() -> tuple[set[tuple[str, str]], Counter[str], dict[str, Any]]:
    """(exact (family, symbol) pairs, family counts, provenance) for what the desk ALREADY owns.

    The certified canon plus the live sleeve roster. Absence is recorded and is not a zero: a
    missing canon means novelty_vs_live is UNMEASURED for this pass, never 1.0 for everything.
    """
    pairs: set[tuple[str, str]] = set()
    fams: Counter[str] = Counter()
    note: dict[str, Any] = {}
    doc = _read_json(CANON)
    if isinstance(doc, dict):
        rows = doc.get("survivors") or {}
        for cert in rows.values() if isinstance(rows, dict) else []:
            if not isinstance(cert, dict):
                continue
            _spec = cert.get("shadow_spec")
            spec: dict[str, Any] = _spec if isinstance(_spec, dict) else {}
            cell = str(cert.get("cell") or "").split(".")
            fam = str(spec.get("family") or cert.get("family")
                      or (cell[1] if len(cell) > 1 else "")).lower()
            sym = str(spec.get("symbol") or cert.get("sym")
                      or (cell[0] if cell else "")).upper()
            if fam:
                fams[fam] += 1
                pairs.add((fam, sym))
        note["canon"] = {"status": "READ", "n": len(pairs)}
    else:
        note["canon"] = {"status": "ABSENT", "path": str(CANON)}
    sl = _read_json(SLEEVES)
    n_sleeves = 0
    if isinstance(sl, (dict, list)):
        rows2: Any = sl.get("sleeves") if isinstance(sl, dict) else sl
        for row in rows2 if isinstance(rows2, list) else []:
            if not isinstance(row, dict):
                continue
            fam = str(row.get("family") or "").lower()
            sym = str(row.get("symbol") or "").upper()
            if fam:
                fams[fam] += 1
                pairs.add((fam, sym))
                n_sleeves += 1
        note["sleeves"] = {"status": "READ", "n": n_sleeves}
    else:
        note["sleeves"] = {"status": "ABSENT", "path": str(SLEEVES)}
    return pairs, fams, note


def graveyard_reference(limit: int = 60000) -> tuple[set[tuple[str, str]], set[str],
                                                     dict[str, Any]]:
    """(dead (family, symbol) pairs, dead families, provenance) from the gate verdict ledger."""
    pairs: set[tuple[str, str]] = set()
    fams: set[str] = set()
    if not VERDICTS.exists():
        return pairs, fams, {"status": "ABSENT", "path": str(VERDICTS)}
    n = 0
    try:
        with VERDICTS.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if n >= limit:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                n += 1
                if row.get("passed"):
                    continue
                fam = str(row.get("family") or "").lower()
                sym = str(row.get("symbol") or "").upper()
                if not fam:
                    cell = str(row.get("cell") or "").split(".")
                    if len(cell) > 1:
                        sym, fam = cell[0].upper(), cell[1].lower()
                if fam:
                    fams.add(fam)
                    pairs.add((fam, sym))
    except OSError as exc:
        return pairs, fams, {"status": f"UNREADABLE: {type(exc).__name__}", "path": str(VERDICTS)}
    return pairs, fams, {"status": "READ", "rows": n, "dead_pairs": len(pairs)}


def novelty(fam: str, sym: str, pairs: set[tuple[str, str]], fams: Any) -> float:
    """1.0 the reference set has never held this family, 0.5 it holds it elsewhere, 0.0 exact."""
    f, s = fam.lower(), sym.upper()
    if (f, s) in pairs:
        return NOVEL_EXACT
    if f in fams:
        return NOVEL_FAMILY
    return NOVEL_NEW


def independence(fam: str, canon_fams: Counter[str]) -> float:
    """1 - this family's share of the certified canon, floored. The eleventh trend signal is
    independent of almost nothing and says so as a number; it is never refused."""
    total = sum(canon_fams.values())
    if total <= 0:
        return 0.5
    share = float(canon_fams.get(fam.lower(), 0)) / float(total)
    return max(INDEPENDENCE_FLOOR, 1.0 - share)


# ------------------------------------------------------------------------------ the passes
def price(conn: Any, *, deadline: float, limit: int = MAX_PRICE) -> dict[str, Any]:
    """Measure the three missing fields on queued candidates and RESCORE them."""
    live_pairs, canon_fams, live_note = live_reference()
    dead_pairs, dead_fams, dead_note = graveyard_reference()
    if not live_pairs and not dead_pairs:
        return {"status": "UNMEASURED", "priced": 0,
                "why": "neither the certified canon nor the verdict ledger could be read; the "
                       "three fields cannot be measured and no row is touched",
                "live": live_note, "graveyard": dead_note}
    rows = R._rows(conn.execute(
        "SELECT id, family, symbol, mechanism, grid_cell, empty_axis_bonus, p_edge, data_quality,"
        " mechanism_strength, expected_capacity, expected_info_gain, research_cost, search_count"
        " FROM research_candidates WHERE status='queued' AND novelty_vs_live IS NULL"
        " ORDER BY created_at DESC LIMIT ?", (int(limit),)))
    priced = 0
    empty_cells = 0
    dist: Counter[str] = Counter()
    for r in rows:
        if time.monotonic() > deadline:
            break
        fam = str(r.get("family") or "")
        sym = str(r.get("symbol") or "")
        if not fam:
            dist["no_family"] += 1
            continue
        nl = novelty(fam, sym, live_pairs, canon_fams)
        ng = novelty(fam, sym, dead_pairs, dead_fams)
        ind = independence(fam, canon_fams)
        empty = bool(float(r.get("empty_axis_bonus") or 0.0) > 0.0)
        empty_cells += 1 if empty else 0
        merged = {k: r.get(k) for k in ("p_edge", "data_quality", "mechanism_strength",
                                        "expected_capacity", "expected_info_gain",
                                        "research_cost", "mechanism")}
        merged.update({"novelty_vs_live": nl, "novelty_vs_graveyard": ng,
                       "expected_return_independence": ind})
        score = R.score_candidate(merged, empty)
        R.mark_candidate(str(r["id"]), "queued", conn=conn, novelty_vs_live=nl,
                         novelty_vs_graveyard=ng, expected_return_independence=ind,
                         score=float(score))
        priced += 1
        dist[f"novel_live={nl}"] += 1
    conn.commit()
    return {"status": "MEASURED" if priced else "NOTHING_TO_PRICE", "priced": priced,
            "candidates_seen": len(rows), "empty_cell_rows": empty_cells,
            "distribution": dict(dist), "live": live_note, "graveyard": dead_note,
            "rule": ("novelty_vs_live and novelty_vs_graveyard in {0.0 exact, 0.5 same family "
                     "elsewhere, 1.0 unheld}; independence = 1 - the family's share of the "
                     "certified canon, floored at "
                     f"{INDEPENDENCE_FLOOR}; the score is recomputed from the same fields")}


def ready(conn: Any, n: int = 25) -> dict[str, Any]:
    """READY_PRIORITY (score order) and READY_ALL (the queued count) -- the exchange's two views."""
    head = R._rows(conn.execute(
        "SELECT id, family, symbol, score, grid_cell, novelty_vs_live, novelty_vs_graveyard,"
        " expected_return_independence FROM research_candidates WHERE status='queued'"
        " ORDER BY score DESC, created_at LIMIT ?", (int(n),)))
    total = conn.execute(
        "SELECT COUNT(*) n FROM research_candidates WHERE status='queued'").fetchone()
    unpriced = conn.execute(
        "SELECT COUNT(*) n FROM research_candidates WHERE status='queued'"
        " AND novelty_vs_live IS NULL").fetchone()
    return {"ready_all": int(total["n"] if total else 0),
            "unpriced": int(unpriced["n"] if unpriced else 0),
            "ready_priority": [{k: row.get(k) for k in
                                ("id", "family", "symbol", "score", "grid_cell",
                                 "novelty_vs_live", "novelty_vs_graveyard",
                                 "expected_return_independence")} for row in head]}


def claim_and_donate(conn: Any, *, per_department: int | None = None,
                     dry_run: bool = False) -> dict[str, Any]:
    """Departments bid for the head of the priority queue; the claims reach the intake (M4).

    `per_department=None` (the default, and what the hourly leg passes) means MEASURE it: the
    judge's own busiest recorded hour split across the bidding departments, never the shipped 12.
    """
    depts = departments()
    measured: dict[str, Any] | None = None
    if per_department is None:
        per_department, measured = R.lease_size(len(depts))
    per_department = max(int(per_department), CLAIM_PER_DEPARTMENT)
    out: dict[str, Any] = {"per_department": int(per_department), "by_department": {},
                           "donated": 0, "donation_path": None, "lease": measured}
    if dry_run:
        out["status"] = "DRY_RUN"
        return out
    claimed: list[dict[str, Any]] = []
    for dept in depts:
        rows = R.claim_candidates(dept, int(per_department), conn=conn)
        out["by_department"][dept] = len(rows)
        for r in rows:
            r["_department"] = dept
        claimed.extend(rows)
    if not claimed:
        out["status"] = "NOTHING_CLAIMED"
        out["why"] = "the queued pool is empty; a measured zero, not a failure"
        return out
    try:
        from research import proposer_common as pc
    except Exception as exc:                                   # pragma: no cover - import guard
        out["status"] = f"INTAKE_UNAVAILABLE: {type(exc).__name__}: {exc}"
        return out
    cands: list[dict[str, Any]] = []
    for r in claimed:
        params = _read_params(r.get("params_json"))
        fam, sym = str(r.get("family") or ""), str(r.get("symbol") or "")
        if not fam or not sym:
            continue
        cands.append(pc.candidate(
            SOURCE, sym, fam, params, str(r.get("mechanism") or ""),
            f"{sym} {fam}: claimed by {r['_department']} from the moat exchange",
            {"candidate_id": r.get("id"), "grid_cell": r.get("grid_cell"),
             "score": r.get("score"), "department": r.get("_department"),
             "novelty_vs_live": r.get("novelty_vs_live"),
             "novelty_vs_graveyard": r.get("novelty_vs_graveyard"),
             "expected_return_independence": r.get("expected_return_independence"),
             "search_count": r.get("search_count")}))
    path = pc.donate(SOURCE, cands, len(claimed)) if cands else None
    out["status"] = "CLAIMED"
    out["claimed"] = len(claimed)
    out["donated"] = int(pc.donation_counts().get("donated") or 0) if cands else 0
    out["donation_path"] = str(path) if path else None
    out["refusals"] = pc.donation_counts()
    return out


def _read_params(blob: Any) -> dict[str, Any]:
    if isinstance(blob, dict):
        return dict(blob)
    try:
        got = json.loads(blob or "{}")
        return got if isinstance(got, dict) else {}
    except (TypeError, ValueError):
        return {}


def run(*, budget_s: float = 240.0, limit: int = MAX_PRICE,
        per_department: int | None = None, dry_run: bool = False,
        out: Path | None = None) -> dict[str, Any]:
    """PRICE then CLAIM, inside a wall-clock budget. The report is the artifact either way."""
    started = time.monotonic()
    deadline = started + max(1.0, float(budget_s))
    conn = R.connect()
    try:
        priced = price(conn, deadline=deadline, limit=limit)
        exchange = ready(conn)
        claims = claim_and_donate(conn, per_department=per_department, dry_run=dry_run)
    finally:
        conn.close()
    doc = {
        "at": _now(), "budget_s": float(budget_s), "dry_run": bool(dry_run),
        "elapsed_s": round(time.monotonic() - started, 2),
        "priced": priced, "exchange": exchange, "claims": claims,
        "score_formula": ("V = P(edge) x Novelty x Independence x DataQuality x "
                          "MechanismStrength x Capacity x InformationGain / ResearchCost, "
                          f"x (1 + {R.EMPTY_CELL_BONUS}) on an empty breadth cell "
                          "(libs/moat/registry.score_candidate)"),
        "consumer": ("libs/moat/registry.claim_candidates (departments bid) -> "
                     "data/intelligence/moat_factory/ -> miner_candidate_compiler -> the docket "
                     "-> desks/mt5/scripts/external_gauntlet.py (sealed; reached through the "
                     "intake, never edited)"),
        "rule": ("an unpriced candidate scores on PRIOR=0.5 for novelty AND independence, so a "
                 "priority queue nobody prices is a FIFO. This measures the three fields the "
                 "score multiplies, rescores the row, and then lets each department bid. It "
                 "refuses nothing and caps nothing."),
    }
    target = out or REPORT
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    except OSError as exc:                                     # pragma: no cover - disk
        doc["write_error"] = f"{type(exc).__name__}: {exc}"
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the default)")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--limit", type=int, default=MAX_PRICE)
    ap.add_argument("--per-department", type=int, default=None,
                    help="override the measured lease (default: the judge's own busiest hour "
                         "split across the bidding departments)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, limit=a.limit, per_department=a.per_department,
              dry_run=a.dry_run)
    p, e, c = doc["priced"], doc["exchange"], doc["claims"]
    print(f"MOAT FACTORY  priced {p.get('priced')} of {p.get('candidates_seen')} "
          f"({p.get('status')}); READY_ALL {e.get('ready_all')} "
          f"({e.get('unpriced')} still unpriced); claims {c.get('status')} "
          f"{c.get('claimed', 0)} -> {c.get('donation_path')}")
    for row in (e.get("ready_priority") or [])[:5]:
        print(f"  {float(row.get('score') or 0.0):.4f}  {row.get('symbol'):<10} "
              f"{row.get('family')}  nov_live={row.get('novelty_vs_live')} "
              f"ind={row.get('expected_return_independence')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
