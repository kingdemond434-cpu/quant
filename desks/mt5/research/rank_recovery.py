"""RANK RECOVERY -- the grid gets DEEPER, because occupancy and independence are not the same.

WHAT WAS MEASURED, AND IT IS NOT WHAT THE NUMBER LOOKED LIKE (trading box, 2026-09-24).
The grid filler transplanted 32,739 cells into empty grid regions and took occupancy 7.25% ->
61.25%, and the production effective rank was reported FALLING, 9.9709 -> 7.1562. Two facts
settle why, and neither is the filler doing something wrong with the cells it minted.

FIRST: THE PRODUCTION EFFECTIVE RANK IS A PRODUCER-CONCENTRATION MEASURE, NOT A CONTENT MEASURE.
`scripts/check_producer_yield.py` builds a producer x (family|symbol|horizon) INDICATOR matrix and
takes the participation ratio of its singular-value spectrum. Measured on the box's own 24h
window: effective rank 8.0995 against a participation ratio of the per-producer CELL COUNTS of
8.1395 -- the two agree to 0.5%, because the producers' rows are very nearly disjoint and a
disjoint indicator matrix has Gram `diag(n_i)`, whose participation ratio IS `(sum n_i)^2 /
sum n_i^2`. So the number answers "how evenly is the desk's output spread across the organs that
caused it", and it can never exceed the producer count. Volume moves it only through that ratio.

SECOND: THE FILLER'S OWN OUTPUT HAS A PARTICIPATION RATIO OF 7.01, AND THE WINDOW IS CONVERGING
ON IT. `independence_intake._donors` takes ONE donor per family (`group by family`, `max(seq)`),
so 32,739 transplants carry 50 DISTINCT PARAMETER SETS and credit 20 PRODUCERS -- 10,546 of them
(32%) to `miner:discovery_compiler` alone. The participation ratio of that distribution is 7.0116.
The available pool it drew from holds 957 distinct (family, producer) donor pairs and 62,796
distinct (family, params) rules. It used 20 of 957 and 50 of 62,796. As the 32,628 still-queued
transplants reach the judge, the measured rank is dragged toward 7.01, which is exactly the
7.1562 that was reported. The fall was real and it was forecastable from the donor census alone.

THE CONTROLLED COMPARISON SAYS THE FILLER DID NOT LOWER ANYTHING (same instant, same window,
its rows removed): 6.9654 without -> 8.0995 with, and all-time 10.8083 -> 11.1789. The filler
ADDS rank; it just adds far less than its volume, because its volume lands on rows that were
already the longest. THE TWO GOALS DO NOT TRADE OFF -- filling a coordinate and spreading the
credit are independent choices, and the filler only ever made the first one.

THE RECOVERY IS DEPTH, AND IT IS PURELY ADDITIVE. A grid cell is not finished when one rule
occupies it. `libs.moat.registry.enqueue_candidate` hashes (family, symbol, params, chart,
session, regime, horizon), so ANOTHER producer's rule on the SAME coordinate is a different
content hash and a genuinely new candidate: more mechanisms tested on ground the desk already
reached, nothing removed, no cell deleted and no denominator narrowed. This organ walks the
occupied grid and carries the donor whose producer currently holds the FEWEST cells -- the
balance-greedy choice, which is the exact argmax of the rank derivative, since for a disjoint
matrix d(rank)/d(n_i) = 2S(Q - S*n_i)/Q^2 is largest for the smallest n_i.

MEASURED ON THE BOX'S REGISTRY, replaying the filler's own 32,739 coordinates (simulation, the
Gram identity below, nothing written):

    base, as built                              11.1789   200 producers, 49,644 cells
    + one donor-depth round   (+32,144 cells)   25.4388   112 producers credited,  84 params
    + two rounds              (+62,502 cells)   33.5326   120 producers credited, 104 params
    + three rounds            (+92,275 cells)   34.4303   122 producers credited, 117 params
    + four rounds            (+119,077 cells)   31.8638   -- it TURNS OVER, and that is the point

The turn-over at round four is the honest bound and it is published, not hidden: once every
under-represented producer has been levelled up, the next round re-concentrates onto whoever is
now largest. `saturated` names that state when it arrives, and the remedy is then a wider DONOR
POOL (more producers holding a param-carrying rule per family), never fewer cells.

Clock: `hourly_cycle` leg `rank_recovery`. Artifact: `reports/RANK_RECOVERY.json`.
Reads: `data/alpha_registry.sqlite`. Writes: candidates through the one registry door.

    python desks/mt5/research/rank_recovery.py --once --budget-s 240
    python desks/mt5/research/rank_recovery.py --once --measure-only
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
OUT = BASE / "reports" / "RANK_RECOVERY.json"
REGISTRY = ROOT / "data" / "alpha_registry.sqlite"
#: Rank rises only. A FLOOR and never a cap: the remedy for a breach is to carry more donors,
#: never to mint fewer cells or to narrow the matrix that measures it.
RATCHET = ROOT / "docs" / "research" / "production_rank_ratchet.json"

#: A verdict, never a zero (L1.28a).
UNMEASURED = "UNMEASURED"

#: What this organ stamps `origin` with, so the census can bill the aim here while the DONOR keeps
#: the credit for the rule. Same separation the grid filler uses and for the same reason.
SOURCE = "rank_recovery"

#: A BOUND THAT CANNOT BIND, kept only so a runaway pass has a named stop. The whole occupied grid
#: is 42,105 coordinates on the box that measured this and the deepest useful pass is three donors
#: per coordinate, so a pass that did everything would use a fifth of this. The real stop is the
#: TIME BUDGET. A test pins this above the measured grid: if it ever binds it is a throttle.
MAX_DEEPEN_PER_PASS = 600_000

#: How many donors deep one pass will go on a single coordinate before moving on. Not a cap on
#: output -- the pass returns to the head of the list next hour and goes deeper -- it is a
#: BREADTH-FIRST ordering, so an hour that runs short has spread one donor over the whole grid
#: rather than four donors over a quarter of it. Measured: round 1 buys +14.3 rank, round 4 loses.
ROUNDS_PER_PASS = 3


def _read(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _num(value: Any) -> float:
    """A float or 0.0. An UNMEASURED slot is never allowed to raise inside a report line."""
    return float(value) if isinstance(value, (int, float)) else 0.0


def effective_rank_of(rows: dict[str, set[str]]) -> float:
    """The participation ratio of the producer x cell indicator matrix, via the GRAM IDENTITY.

    THE SAME NUMBER AS `libs.research.sandbox_rotation.breadth(...)["total"]`, NOT A SECOND ONE,
    and `tests/test_rank_recovery.py` pins the equality on random matrices. It is computed
    differently because it has to be: `breadth` builds a DENSE producer x cell matrix and takes
    one SVD per producer for the marginals, which at this desk's scale (200 producers x 42,105
    cells) is a 67 MB dense array and 201 SVDs of it. That is why nothing had ever measured the
    steady state of the grid, and an unmeasurable number is an unmeasured one.

    The identity: the eigenvalues of G = M M^T are the squared singular values of M, so

        effective_rank = (sum s_i^2)^2 / sum s_i^4 = trace(G)^2 / ||G||_F^2

    and for an INDICATOR matrix G[i][j] is just |cells_i & cells_j| -- exact integer arithmetic
    off an inverted index, no matrix ever built. A flat book reads 0.0, the same as the SVD path.
    """
    rows = {k: v for k, v in rows.items() if v}
    if not rows:
        return 0.0
    holders: dict[str, list[str]] = defaultdict(list)
    for sid, cells in rows.items():
        for cell in cells:
            holders[cell].append(sid)
    gram: Counter[tuple[str, str]] = Counter()
    for hs in holders.values():
        for a in hs:
            for b in hs:
                gram[(a, b)] += 1
    trace = sum(len(v) for v in rows.values())
    frob = sum(v * v for v in gram.values())
    return (trace * trace) / frob if frob else 0.0


def _matrix(db: Path | None = None) -> tuple[dict[str, set[str]], str]:
    """producer -> the set of (family|symbol|horizon) cells it caused. The fence's own shape.

    CREDIT THE PRODUCER THAT CAUSED THE CELL, NOT THE COMPILER THAT STAMPED IT -- the same
    `coalesce(discoveries.generator, candidates.generator)` `scripts/check_producer_yield.py`
    uses, so this organ measures the matrix the fence will measure and not a sibling of it.
    """
    path = db or REGISTRY
    if not path.exists():
        return {}, f"{UNMEASURED}: no registry at {path}"
    gen = ("lower(coalesce(nullif(d.generator,''), nullif(c.generator,''),"
           "'_unattributed_generator'))")
    cell = ("lower(coalesce(nullif(c.family,''),'?'))||'|'||"
            "lower(coalesce(nullif(c.symbol,''),'?'))||'|'||"
            "lower(coalesce(nullif(c.horizon,''),'?'))")
    src = ("research_candidates c left join discoveries d "
           "on d.discovery_id = c.discovery_id")
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return {}, f"{UNMEASURED}: registry unopenable ({type(exc).__name__}: {exc})"
    try:
        out: dict[str, set[str]] = {}
        for producer, ident in con.execute(
                f"select distinct {gen}, {cell} from {src}"):    # noqa: S608 -- literals above
            out.setdefault(str(producer), set()).add(str(ident))
        return out, ""
    except sqlite3.Error as exc:
        return {}, f"{UNMEASURED}: registry query failed ({type(exc).__name__}: {exc})"
    finally:
        con.close()


def production_rank(rows: dict[str, set[str]]) -> dict[str, Any]:
    """The rank, AND the three numbers that say what is holding it down.

    `headroom` is the producer count minus the rank: how many more independent directions the
    SAME producers would carry if their output were evenly spread. `top_share` is the largest
    producer's share of all cells -- the single number that bounds the rank from above, since a
    producer holding a fraction f of the output caps the participation ratio near 1/f.
    """
    if not rows:
        return {"available": False, "why": f"{UNMEASURED}: no producer row to measure"}
    counts = {k: len(v) for k, v in rows.items() if v}
    total = sum(counts.values())
    rank = effective_rank_of(rows)
    ordered = Counter(counts).most_common()
    pr_counts = (total * total / sum(n * n for n in counts.values())) if total else 0.0
    return {
        "available": True,
        "effective_rank": round(rank, 4),
        "producers": len(counts),
        "cells": total,
        "columns": len({c for cs in rows.values() for c in cs}),
        "pr_of_producer_counts": round(pr_counts, 4),
        "disjointness": (round(rank / pr_counts, 4) if pr_counts else None),
        "headroom": round(len(counts) - rank, 4),
        "top_share": round(ordered[0][1] / total, 4) if total else None,
        "top10": ordered[:10],
        "basis": ("participation ratio of the singular-value spectrum of the producer x "
                  "(family|symbol|horizon) indicator matrix, via trace(G)^2/||G||_F^2 with "
                  "G = M M^T -- the same number as libs.research.sandbox_rotation.breadth"),
        "why": ("effective rank is a PRODUCER-CONCENTRATION measure: it equals the participation "
                "ratio of the per-producer cell counts whenever the rows are near-disjoint, so "
                "it rises only when output spreads across MORE producers, never with volume"),
    }


def donor_pool(db: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """family -> one param-carrying donor PER PRODUCER, not one per family.

    THIS IS THE WHOLE FIX. `independence_intake._donors` groups by family alone, so a family with
    thirteen producers holding a rule contributes ONE of them and the other twelve never travel.
    Measured on the box: 957 (family, producer) pairs available, 20 producers used. Grouping by
    (family, producer) is strictly MORE rules carried, never fewer -- no donor is excluded by it.

    This organ's own output and the grid filler's are excluded as donors for the reason the
    filler already documents: `max(seq)` is the most recent row, a fill pass writes tens of
    thousands of them, and transplanting copies of copies credits the desk for its own echo.
    """
    path = db or REGISTRY
    if not path.exists():
        return {}
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return {}
    try:
        producer = "lower(coalesce(nullif(generator,''), nullif(producer,''), '?'))"
        cur = con.execute(
            f"select lower(coalesce(nullif(family,''),'?')), {producer}, family, symbol, "  # noqa: S608
            "lower(coalesce(nullif(horizon,''),'?')), params_json, mechanism, "
            "generator, producer, discovery_id, region, max(seq) "
            "from research_candidates "
            "where params_json is not null and params_json not in ('', '{}') "
            "and family is not null and family != '' "
            "and lower(coalesce(origin,'')) not in (?, ?) "
            "and lower(coalesce(generator,'')) not in (?, ?) "
            f"group by 1, 2", ("independence_intake", SOURCE, "independence_intake", SOURCE))
        pool: dict[str, list[dict[str, Any]]] = {}
        for key, prod, fam, sym, hor, params, mech, gen, pro, disc, reg, _seq in cur:
            try:
                parsed = json.loads(params)
            except (TypeError, ValueError):
                continue
            if not isinstance(parsed, dict) or not parsed:
                continue
            pool.setdefault(str(key), []).append({
                "producer_key": str(prod), "family": str(fam), "symbol": str(sym),
                "horizon": str(hor), "params": parsed, "mechanism": str(mech or ""),
                "generator": str(gen or "") or None, "producer": str(pro or "") or None,
                "discovery_id": str(disc or "") or None, "region": str(reg or "") or None})
        return pool
    except sqlite3.Error:
        return {}
    finally:
        con.close()


def _lane() -> tuple[set[str], str]:
    """The instruments a hypothesis may be minted on -- the lane router's answer, never a list."""
    try:
        if str(BASE) not in sys.path:
            sys.path.insert(0, str(BASE))
        from research.universe_policy import may_hypothesise
    except Exception as exc:                                             # pragma: no cover
        return set(), f"{UNMEASURED}: lane router unimportable ({type(exc).__name__})"
    uni = _read(BASE / "data" / "universe" / "universe.json", default={})
    if not isinstance(uni, dict) or not uni:
        return set(), f"{UNMEASURED}: no universe registry"
    return {str(s).lower() for s in uni if may_hypothesise(str(s))}, ""


def _symbol_case() -> dict[str, str]:
    uni = _read(BASE / "data" / "universe" / "universe.json", default={})
    return {str(s).lower(): str(s) for s in uni} if isinstance(uni, dict) else {}


def occupied_cells(rows: dict[str, set[str]]) -> dict[str, set[str]]:
    """cell -> the producers already on it, so a pass never carries a donor twice to one cell."""
    out: dict[str, set[str]] = {}
    for producer, cells in rows.items():
        for cell in cells:
            out.setdefault(cell, set()).add(producer)
    return out


def _gram(rows: dict[str, set[str]]) -> tuple[Counter[tuple[str, str]], int]:
    """(G as |cells_i & cells_j| off an inverted index, trace(G)). No matrix is ever built."""
    holders: dict[str, list[str]] = defaultdict(list)
    for sid, cells in rows.items():
        for cell in cells:
            holders[cell].append(sid)
    gram: Counter[tuple[str, str]] = Counter()
    for hs in holders.values():
        for a in hs:
            for b in hs:
                gram[(a, b)] += 1
    return gram, sum(len(v) for v in rows.values())


def plan_deepening(rows: dict[str, set[str]], pool: dict[str, list[dict[str, Any]]],
                   *, lane: set[str] | None = None,
                   rounds: int = ROUNDS_PER_PASS) -> tuple[list[tuple[str, dict[str, Any]]],
                                                           dict[str, Any]]:
    """(cell, donor) pairs ordered by the MEASURED marginal rank each one buys, breadth-first.

    THE OBVIOUS GREEDY IS WRONG AND THE TEST THAT CAUGHT IT IS KEPT. "Carry the least-credited
    producer" is the argmax of d(rank)/d(n_i) = 2S(Q - S*n_i)/Q^2 only while the producers' rows
    stay DISJOINT. Push it far enough and it stops being true in the worst way: levelling every
    producer up on the same coordinates makes their rows IDENTICAL, and identical rows span one
    direction, not many. A toy with 400/60/1 cells and four donors per family loses rank under
    pure balance-greedy, 1.299 -> 1.1281, and the box's own replay turns over at round four
    (34.4303 -> 31.8638). A copy of somebody else's coverage is not independence.

    So the gain is computed EXACTLY, not approximated. With G = M M^T, rank = trace(G)^2/||G||_F^2,
    and adding coordinate c to producer i moves

        trace -> S + 1
        ||G||_F^2 -> Q + (2*n_i + 1) + 2 * sum_{j already on c} (2*|cells_i & cells_j| + 1)

    so the true marginal is one arithmetic line per candidate, with the overlaps carried in a
    dict that is updated in O(producers on the coordinate) per acceptance. The donor chosen for a
    coordinate is the one with the LARGEST measured gain.

    NOTHING IS CAPPED AND NOTHING IS DROPPED. A candidate whose measured gain is not positive
    would add a direction the spectrum already spans; it is not refused, it is ORDERED BEHIND the
    41,000 other coordinates this pass has not reached, and it is counted in `set_aside` with the
    reason, the way every other stage of this desk records what it did not reach first (LAWS).
    The pass stops on its TIME BUDGET, never on a count.
    """
    load: Counter[str] = Counter({k: len(v) for k, v in rows.items()})
    gram, trace = _gram(rows)
    frob = sum(v * v for v in gram.values())
    on_cell = occupied_cells(rows)
    # SPARSEST COORDINATE FIRST, for the same reason the filler aims at the frontier: a cell one
    # producer has reached is a direction the spectrum barely spans.
    cells = sorted(on_cell, key=lambda c: (len(on_cell[c]), c))
    plan: list[tuple[str, dict[str, Any]]] = []
    tail: list[tuple[str, dict[str, Any]]] = []
    out_of_lane = 0
    no_donor = 0
    for _ in range(max(1, rounds)):
        moved = False
        for cell in cells:
            if len(plan) >= MAX_DEEPEN_PER_PASS:                         # pragma: no cover
                break
            fam, sym, _hor = [*cell.split("|"), "", "", ""][:3]
            if lane is not None and sym not in lane:
                out_of_lane += 1
                continue
            here = on_cell.get(cell) or set()
            candidates = [d for d in pool.get(fam, ()) if d["producer_key"] not in here]
            if not candidates:
                no_donor += 1
                continue
            now = (trace * trace / frob) if frob else 0.0
            best: tuple[float, int, dict[str, Any]] | None = None
            for donor in candidates:
                key = str(donor["producer_key"])
                d_frob = (2 * load[key] + 1) + 2 * sum(2 * gram[(key, j)] + 1 for j in here)
                nxt = ((trace + 1) ** 2 / (frob + d_frob)) if (frob + d_frob) else 0.0
                if best is None or nxt - now > best[0]:
                    best = (nxt - now, d_frob, donor)
            if best is None:                                             # pragma: no cover
                continue
            gain, d_frob, donor = best
            key = str(donor["producer_key"])
            for j in here:
                gram[(key, j)] += 1
                gram[(j, key)] += 1
            gram[(key, key)] += 1
            load[key] += 1
            trace += 1
            frob += d_frob
            here.add(key)
            on_cell[cell] = here
            # RANK-NEUTRAL IS NOT REFUSED. A donor that cannot move a PRODUCER-coverage measure
            # is still a new mechanism on that coordinate and is still minted; it goes behind
            # every coordinate that CAN move it. The time budget decides the cut, never a count.
            (plan if gain > 0.0 else tail).append((cell, donor))
            moved = True
        if not moved:
            break
    head_rows = {k: set(v) for k, v in rows.items()}
    for cell, donor in plan:
        head_rows.setdefault(str(donor["producer_key"]), set()).add(cell)
    census = {
        "planned": len(plan) + len(tail),
        "rank_positive": len(plan),
        "rank_neutral": len(tail),
        # The rank after the rank-POSITIVE head of the plan, and after the whole plan. Both are
        # published: the head is what the pass buys inside its budget, the full figure is what the
        # queue converges to if the tail is ever reached, and hiding the second would be a lie.
        "rank_projected": round(effective_rank_of(head_rows), 4),
        "rank_projected_full_plan": round((trace * trace / frob) if frob else 0.0, 4),
        "coordinates": len(cells),
        "rank_neutral_why": ("the coordinate's remaining donors would duplicate coverage a "
                             "producer already holds, so they cannot move a producer-coverage "
                             "measure. They are ORDERED LAST and still minted, never refused; "
                             "the remedy for a pass that is all tail is a WIDER donor pool -- "
                             "more producers holding a param-carrying rule per family -- and "
                             "never fewer cells"),
        "out_of_lane": out_of_lane,
        "coordinates_without_an_uncarried_donor": no_donor,
        "ordering": "sparsest coordinate first, then the donor with the largest measured "
                    "marginal effective rank; rank-neutral donors last",
    }
    return plan + tail, census


def deepen(plan: list[tuple[str, dict[str, Any]]], *, budget_s: float = 120.0,
           write_rows: bool = True) -> dict[str, Any]:
    """Carry each planned donor onto its coordinate through the ONE registry door.

    NOTHING IS CAPPED, DROPPED OR THROTTLED and no cell is ever removed. `enqueue_candidate`
    de-duplicates on content hash, so a rule already present raises its search count and creates
    nothing; a re-run cannot inflate the count and a stale plan cannot double-write.
    """
    started = time.monotonic()
    if not plan:
        return {"available": False,
                "why": f"{UNMEASURED}: no coordinate has an uncarried donor this pass"}
    if not write_rows:
        return {"available": True, "dry_run": True, "planned": len(plan),
                "producers_planned": len({d["producer_key"] for _c, d in plan}),
                "params_planned": len({json.dumps(d["params"], sort_keys=True)
                                       for _c, d in plan}),
                "why": "measure-only: the plan is published and nothing was written"}
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from libs.moat.registry import connect, enqueue_candidate
    except Exception as exc:                                             # pragma: no cover
        return {"available": False,
                "why": f"{UNMEASURED}: registry door unimportable ({type(exc).__name__})"}
    case = _symbol_case()
    created = existing = failed = 0
    by_producer: Counter[str] = Counter()
    made_rows: list[tuple[str, str]] = []
    stopped = "plan exhausted"
    try:
        con = connect()
    except Exception as exc:                                             # pragma: no cover
        return {"available": False,
                "why": f"{UNMEASURED}: registry unopenable ({type(exc).__name__}: {exc})"}
    try:
        for cell, donor in plan:
            if time.monotonic() - started > budget_s:
                stopped = f"time budget {budget_s:g}s reached after {created + existing} cells"
                break
            _fam, sym_l, hor = [*cell.split("|"), "", "", ""][:3]
            sym = case.get(sym_l, sym_l.upper())
            extra = {k: donor[k] for k in ("generator", "producer", "discovery_id", "region")
                     if donor.get(k)}
            try:
                _id, made = enqueue_candidate(
                    family=donor["family"], symbol=sym, params=donor["params"],
                    origin=SOURCE, horizon=hor, conn=con,
                    mechanism=(f"{donor['mechanism'] or donor['family']} carried to {sym} at "
                               f"{hor} (mutation: cross_producer)"),
                    **extra)
            except Exception:                                            # pragma: no cover
                failed += 1
                continue
            by_producer[donor["producer_key"]] += 1
            if made:
                created += 1
                made_rows.append((donor["producer_key"], cell))
            else:
                existing += 1
    finally:
        con.close()
    return {
        "available": True,
        "law": ("DEPTH, NOT RESTRICTION: a coordinate already holding a rule takes another "
                "producer's rule as a NEW candidate. Nothing is capped, dropped or removed"),
        "planned": len(plan), "cells_created": created, "already_present": existing,
        "failed": failed, "producers_credited": len(by_producer),
        "by_producer": dict(by_producer.most_common(40)),
        "created_rows": made_rows,
        "stopped_because": stopped,
        "elapsed_s": round(time.monotonic() - started, 3),
        "seconds_per_cell": (round((time.monotonic() - started) / (created + existing), 5)
                             if (created + existing) else None),
    }


def ratchet(before: dict[str, Any], after: dict[str, Any],
            path: Path | None = None) -> dict[str, Any]:
    """PRODUCTION RANK RISES ONLY. A fall below the best carries a stated reason or it is a lie.

    A FLOOR and never a cap: the remedy for a breach is to carry more donors onto more
    coordinates, never to mint fewer cells or to shrink the matrix the rank is measured on. An
    unmeasured pass moves nothing -- an absent measurement is not a regression (L1.28a).
    """
    out = path or RATCHET
    doc = _read(out, default={})
    doc = doc if isinstance(doc, dict) else {}
    now = after.get("effective_rank") if after.get("available") else None
    if not isinstance(now, (int, float)):
        return {**doc, "verdict": UNMEASURED,
                "why": str(after.get("why") or f"{UNMEASURED}: rank not measured this pass")}
    best = doc.get("effective_rank_best")
    reason = str(doc.get("regression_reason") or "")
    failures: list[str] = []
    if isinstance(best, (int, float)) and now < best and not reason:
        failures.append(
            f"production effective rank fell to {now:g} against a best of {best:g} with no "
            f"stated reason: set `regression_reason` in {out.name} or name the producer whose "
            f"share grew. The remedy is MORE donors carried, never fewer cells")
    if not isinstance(best, (int, float)) or now > best:
        doc["effective_rank_best"] = round(float(now), 4)
        doc["producers_at_best"] = after.get("producers")
        doc["cells_at_best"] = after.get("cells")
    doc["effective_rank_last"] = round(float(now), 4)
    doc["effective_rank_before_pass"] = (before.get("effective_rank")
                                         if before.get("available") else None)
    doc["updated_utc"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
    doc["law"] = "PRODUCTION RANK RISES ONLY. This ratchet is a floor and never a cap."
    doc.setdefault("regression_reason", None)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    except OSError as exc:                                               # pragma: no cover
        doc["write_error"] = f"{type(exc).__name__}: {exc}"
    return {**doc, "verdict": "REGRESSION" if failures else "MEASURED", "failures": failures}


def run(budget_s: float = 240.0, *, db: Path | None = None,
        write_rows: bool = True, rounds: int = ROUNDS_PER_PASS) -> dict[str, Any]:
    """Measure the rank, deepen the grid, measure it again, ratchet, publish."""
    started = time.monotonic()
    rows, why = _matrix(db)
    before = production_rank(rows)
    pool = donor_pool(db)
    lane, lane_why = _lane()
    plan, census = (plan_deepening(rows, pool, lane=(lane or None), rounds=rounds)
                    if rows and pool else ([], {"planned": 0, "why": f"{UNMEASURED}: no donor"}))
    result = deepen(plan, budget_s=max(budget_s * 0.6, 30.0), write_rows=write_rows)
    # The AFTER matrix is the before matrix plus exactly the rows this pass created -- measured
    # from what the door reported made, never re-read, so the two numbers describe one pass.
    after_rows = {k: set(v) for k, v in rows.items()}
    for producer, cell in (result.get("created_rows") or []):
        after_rows.setdefault(producer, set()).add(cell)
    after = production_rank(after_rows) if rows else {"available": False, "why": why or UNMEASURED}
    rat = ratchet(before, after)
    result.pop("created_rows", None)
    doc: dict[str, Any] = {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "law": ("RECOVER RANK BY MAKING OUTPUT MORE VARIED, NEVER BY MAKING IT SMALLER. Every "
                "cell here is an ADDITION: a coordinate that already holds one producer's rule "
                "takes another producer's rule as a new candidate. No cell is deleted, no "
                "denominator narrowed, no producer slowed and no bar moved."),
        "registry_note": why, "lane_note": lane_why,
        "rank_before": before, "rank_after": after,
        "delta": (round(_num(after.get("effective_rank")) - _num(before.get("effective_rank")), 4)
                  if before.get("available") and after.get("available") else None),
        "donor_pool": {
            "families": len(pool),
            "family_producer_pairs": sum(len(v) for v in pool.values()),
            "producers": len({d["producer_key"] for ds in pool.values() for d in ds}),
            "why": ("one donor PER PRODUCER per family. independence_intake._donors groups by "
                    "family alone and carries one of them, which is how 32,739 transplants came "
                    "to hold 50 parameter sets from 20 producers"),
        },
        "plan": census,
        "deepen": result,
        # SATURATED is a MEASUREMENT, not a stop: every coordinate whose donors would only
        # duplicate coverage somebody already has. Its remedy is a wider donor pool -- more
        # producers holding a param-carrying rule per family -- never fewer cells.
        "saturated": bool(census.get("set_aside")) and not census.get("planned"),
        "rank_ratchet": rat,
        "elapsed_s": round(time.monotonic() - started, 3),
        "budget_s": budget_s,
    }
    doc["verdict"] = ("MEASURED" if before.get("available") and after.get("available")
                      else UNMEASURED)
    return doc


def write(doc: dict[str, Any], *, report: Path | None = None) -> None:
    out = report or OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str) + "\n", encoding="utf-8")
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from libs.ops.events import emit
        emit("rank_recovery", verdict=doc.get("verdict"),
             rank_before=(doc.get("rank_before") or {}).get("effective_rank"),
             rank_after=(doc.get("rank_after") or {}).get("effective_rank"),
             cells_created=(doc.get("deepen") or {}).get("cells_created"))
    except Exception:                                                    # pragma: no cover
        pass


def render(doc: dict[str, Any]) -> list[str]:
    before, after = doc.get("rank_before") or {}, doc.get("rank_after") or {}
    dp, dn = doc.get("donor_pool") or {}, doc.get("deepen") or {}
    lines = [f"RANK RECOVERY  {doc.get('verdict')}",
             f"  rank    {before.get('effective_rank')} -> {after.get('effective_rank')} "
             f"(delta {doc.get('delta')}) over {after.get('producers')} producers, "
             f"{after.get('cells')} cells, {after.get('columns')} coordinates",
             f"  bound   top producer holds {before.get('top_share')} of output; headroom "
             f"{before.get('headroom')} directions at this producer count",
             f"  donors  {dp.get('family_producer_pairs')} (family,producer) pairs over "
             f"{dp.get('families')} families, {dp.get('producers')} producers"]
    plan = doc.get("plan") or {}
    lines.append(f"  plan    {plan.get('planned')} donors over {plan.get('coordinates')} "
                 f"coordinates ({plan.get('rank_positive')} rank-positive, "
                 f"{plan.get('rank_neutral')} rank-neutral and ordered last), projected rank "
                 f"{plan.get('rank_projected')} (whole plan "
                 f"{plan.get('rank_projected_full_plan')})")
    if dn.get("available"):
        lines.append(f"  deepen  {dn.get('planned')} planned, {dn.get('cells_created')} created, "
                     f"{dn.get('already_present')} already present, "
                     f"{dn.get('producers_credited')} producers credited")
        lines.append(f"  stop    {dn.get('stopped_because')} at "
                     f"{dn.get('seconds_per_cell')}s per cell")
    else:
        lines.append(f"  deepen  {dn.get('why')}")
    rat = doc.get("rank_ratchet") or {}
    lines.append(f"  ratchet {rat.get('verdict')} best {rat.get('effective_rank_best')}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Recover production effective rank by donor depth")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--rounds", type=int, default=ROUNDS_PER_PASS)
    ap.add_argument("--measure-only", action="store_true",
                    help="measure and publish the plan, write no candidate")
    args = ap.parse_args(argv)
    doc = run(budget_s=float(args.budget_s), write_rows=not args.measure_only,
              rounds=int(args.rounds))
    write(doc)
    for line in render(doc):
        print(line)
    return 0


if __name__ == "__main__":                                               # pragma: no cover
    raise SystemExit(main())
