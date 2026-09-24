"""INDEPENDENCE AT INTAKE -- the same judge-hours buying more independent ground.

THE MEASUREMENT THAT FORCED THIS (2026-09-23). `scripts/check_producer_yield.py` measures
227.5 cells an hour reaching the judge and an ORTHOGONALITY-WEIGHTED equivalent of 23.4: the
desk emits ten times more volume than independent ground. Its dedup ladder says why. 18,201
raw cells collapse to 18,201 distinct content hashes -- the dedup door works and has nothing
to catch, because every row genuinely differs -- then to 2,844 distinct GRID cells (6.4x) and
to 583 distinct MECHANISMS (31x). Effective rank is 5.15 across 1,132 family-symbol-horizon
cells. The desk is generating parameter variants of the same rule on the same instrument, and
the judge is spending its hours on them.

NOTHING HERE REDUCES ANYTHING, AND THAT IS THE DESIGN. No cap, no throttle, no producer slowed,
no variant dropped, no queue shortened. The queue is uncapped; only the ORDER changes, and the
generators are aimed at ground they have not touched. Three levers, all of them additive:

    ORDER       a parameter variant of a rule already queued on the same symbol and horizon
                adds almost no independent ground, so it must not consume a judge slot ahead of
                an unseen mechanism. `judge_coverage.variant_split` marks them and
                `judge_coverage.coverage_order` ranks them below -- inside the family stream,
                after the never-judged test, so the family floors and the value ranking are
                untouched. This file reads what that ordering freed and publishes it.

    MUTATE      `survivor_distiller`'s operators are `step_<param>_up`, `step_<param>_down` and
                `swap_<param>` -- every one of them a nudge to a constant. `condition_on_state`
                is the only move that changes the MECHANISM, and it competed for the same
                MAX_TASKS slots on raw score, so it lost to whichever constant happened to score
                highest. `declared_mechanism_share()` is the share of those slots that goes to
                mechanism-changing moves, and it is TUNED by measured orthogonality gain: the
                distinct grid cells each operator class opens per cell it emits. The desk learns
                which mutations buy independence instead of being told.

    SPREAD      1,132 occupied cells against 145 hypothesis-lane instruments, 79 live families
                and the axis registry's five horizons is a small corner of the grid. The empty
                cells are exactly where independent ground lives, so they are published as
                ranked TARGETS and the mechanism arm aims at them first. `libs/moat/registry.py`
                already pays `EMPTY_CELL_BONUS` to a cell that lands on an empty grid cell; this
                is what lets a generator find one on purpose rather than by accident.

EIGHT CELLS AN HOUR, AND NONE OF THE OBVIOUS SUSPECTS DID IT (measured on the trading box,
2026-09-23). The pass reported `8 empty cells aimed at, 8 cells created` against a 400 cap and
8,418 reachable empty cells. Not the cap: the loop never reached 400. Not the donors: all 400
published targets had one. Not reachability: 8,410 cells were reachable. It was the TIME BUDGET,
and the time went into the registry door -- `enqueue_candidate` asks whether a breadth cell is
empty with `WHERE grid_cell=?`, that column carried no index, and EXPLAIN answered
`SCAN research_candidates` over 321,168 rows. One cell cost 0.927 s, the fill holds a 75 s slice,
75 / 0.927 = 8. The index (`ix_candidates_gridcell`, in `libs/moat/registry._evolve`) takes the
same call to 0.0012 s: a 772x fall, and the same 75 s now buys sixty thousand cells.

THE SHAPE TO RECOGNISE, because it will happen again somewhere else. An organ that prints
`8 of 400` looks throttled by its own cap, every reading of its code agrees, and raising the cap
would have changed nothing. The limit was a table scan two modules away that no artifact named.
When a bound does not bind, the thing to measure is SECONDS PER UNIT, not the bound -- which is
why `fill` now publishes `seconds_per_cell`, `targets_available` and `stopped_because`.

TWO MORE BOUNDS FELL WITH IT, both of them the same confusion between a REPORT and the WORK.
`MAX_TARGETS` truncated the published target list to 400 and the filler read that published
slice, so a JSON size limit was silently a ceiling on the grid; the filler is now handed the
whole in-memory list and the artifact is truncated afterwards. And `grid_occupancy` called a
family or an instrument with zero load UNREACHABLE -- but what a transplant needs is a rule to
carry, which is a DONOR, so a family holding one whose cells all sat outside the hypothesis lane
was skipped while being a whole empty ROW of the grid. Ranking was backwards for the same
reason: it put the BUSIEST family-symbol pairs first, adding mass to directions the spectrum
already spanned. Frontier first, then ascending load.

WHAT THIS FILE DOES NOT OWN. The headline throughput number belongs to the yield fence, which
ratchets it (`docs/research/producer_yield_ratchet.json`: the orthogonality-weighted figure may
not fall below its own best without a stated reason). It is READ here and republished in
context, never re-derived -- two implementations of one number are two numbers.

THE NEXT WIRING POINT, NAMED SO NOBODY HAS TO FIND IT AGAIN. `empty_pairs()` is consumed today by
`survivor_distiller.mix_by_mechanism` (order) and `expression_factory.hypothesis_symbols` (which
instruments a pass loads first), and `fill_empty_cells` mints into the empties directly. The
island seeding in `desks/mt5/research/factor_model_coevolution.py` and `joint_evolution.py` is
NOT wired: each island still seeds from its own population, so an island can spend a whole run
inside ground the grid already holds. Seed one island per pass from the head of `grid.targets`
and it becomes a third filler -- same helper, same artifact, no new organ.

Clock: `hourly_cycle` leg `independence_intake`. Artifact: `reports/INDEPENDENCE_INTAKE.json`.
Consumers: `survivor_distiller` (the mix share and the empty targets), the yield fence's
context, `tier1_scorecard`.

    python desks/mt5/research/independence_intake.py --once --budget-s 240
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
OUT = BASE / "reports" / "INDEPENDENCE_INTAKE.json"
YIELD = BASE / "reports" / "PRODUCER_YIELD.json"
COVERAGE = BASE / "reports" / "JUDGE_COVERAGE.json"
UNIVERSE = BASE / "data" / "universe" / "universe.json"
#: The declared mix, persisted so the tuning is a record and not a coin flip each hour.
MIX = BASE / "data" / "mechanism_mutation_mix.json"
REGISTRY = ROOT / "data" / "alpha_registry.sqlite"

#: A verdict, never a zero (L1.28a).
UNMEASURED = "UNMEASURED"

#: Where the declared mechanism share starts before anything is measured. Not a cap: it is the
#: share of an ALREADY truncated task list that goes to mechanism-changing moves, so raising it
#: moves slots between operator classes and never removes a slot.
DEFAULT_MECHANISM_SHARE = 0.35
#: The share stays two-sided and inside these bounds (Rule 2): it may rise when mechanism moves
#: are measured to open more ground and fall when they are not. Never 0 and never 1, because a
#: class with no slots at all can never be measured again.
SHARE_BOUNDS = (0.2, 0.8)
#: How many empty grid cells are published IN THE ARTIFACT as targets. This bounds one JSON file
#: and NOTHING ELSE -- the filler is handed the whole in-memory list and never this slice. It used
#: to be both, which is how a 400-row report became a 400-cell ceiling on the grid (measured
#: 2026-09-23: 8,410 reachable empties, 400 published, 8 filled). `targets_total` publishes the
#: full count beside the slice so the truncation is never mistaken for the frontier.
MAX_TARGETS = 5_000
#: Rows read from the registry for the ladder. The ladder is a count of DISTINCT keys, which
#: saturates long before this; the bound keeps the scan off an 8 GB box's memory.
MAX_ROWS = 400_000

#: A BOUND THAT CANNOT BIND, kept only so a runaway grid has a named stop. The nominal grid is
#: families x instruments x horizons -- 20,935 cells on the box that measured this -- so a pass
#: that filled EVERY empty cell on the board would use a fifth of this. The real stop is the time
#: budget, and with the `ix_candidates_gridcell` index one cell costs 0.0012 s, so 75 s buys
#: sixty thousand. A test pins this above the nominal grid: if it ever binds it is a throttle.
MAX_FILLS_PER_PASS = 100_000
#: Occupancy rises only. A floor, never a cap -- the remedy for a breach is to fill more cells.
OCCUPANCY_RATCHET = ROOT / "docs" / "research" / "grid_occupancy_ratchet.json"
#: What the filled cells are stamped with, so the census and the yield fence can bill this organ.
SOURCE = "independence_intake"

#: Operator name prefixes that change the MECHANISM rather than a constant. `condition_on_state`
#: conditions the rule on a different market state; `cross_` moves it to another family, horizon
#: or instrument class. Everything else -- `step_*`, `swap_*`, `drop_*` -- is a parameter move.
MECHANISM_OPERATORS: tuple[str, ...] = ("condition_on_state", "cross_")


def _read(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def mechanism_class(operator: str | None) -> str:
    """`mechanism` if this operator changes the mechanism, else `parameter`. Never raises."""
    op = str(operator or "").strip().lower()
    return "mechanism" if any(op.startswith(p) for p in MECHANISM_OPERATORS) else "parameter"


def _rows(db: Path | None = None) -> tuple[list[tuple[str, str, str, str, str]], str]:
    """(family, symbol, horizon, content_hash, mechanism) for every candidate. Never raises."""
    path = db or REGISTRY
    if not path.exists():
        return [], f"{UNMEASURED}: no registry at {path}"
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return [], f"{UNMEASURED}: registry unopenable ({type(exc).__name__}: {exc})"
    try:
        cur = con.execute(
            "select lower(coalesce(nullif(family,''),'?')), "
            "lower(coalesce(nullif(symbol,''),'?')), "
            "lower(coalesce(nullif(horizon,''),'?')), "
            "coalesce(content_hash,''), lower(coalesce(mechanism,'')) "
            "from research_candidates limit ?", (MAX_ROWS,))
        return [(str(a), str(b), str(c), str(d), str(e)) for a, b, c, d, e in cur], ""
    except sqlite3.Error as exc:
        return [], f"{UNMEASURED}: registry query failed ({type(exc).__name__}: {exc})"
    finally:
        con.close()


def dedup_ladder(rows: list[tuple[str, str, str, str, str]]) -> dict[str, Any]:
    """Raw cells -> content hashes -> grid cells -> mechanisms, and what each rung collapses.

    The rung that matters is the LAST one that still moves. Raw == hashes means the dedup door
    is working and has nothing to catch; hashes >> grid cells means the desk is minting variants.
    """
    if not rows:
        return {"available": False, "why": f"{UNMEASURED}: no candidate row to walk"}
    raw = len(rows)
    hashes = len({h for *_, h, _ in rows if h})
    cells = len({f"{f}|{s}|{h}" for f, s, h, _, _ in rows})
    mechs = len({m for *_, m in rows if m})
    out: dict[str, Any] = {"available": True, "raw_cells": raw, "content_hashes": hashes,
                           "grid_cells": cells, "mechanisms": mechs}
    out["collapse"] = {
        "raw_per_hash": round(raw / hashes, 3) if hashes else None,
        "raw_per_grid_cell": round(raw / cells, 3) if cells else None,
        "raw_per_mechanism": round(raw / mechs, 3) if mechs else None,
    }
    out["why"] = (f"{raw} raw cells collapse to {hashes} content hashes, {cells} grid cells and "
                  f"{mechs} mechanisms: the door catches nothing and the variants are real rows "
                  f"on ground the desk already holds")
    return out


def hypothesis_instruments() -> tuple[list[str], str]:
    """The instruments a hypothesis may be minted on -- the lane router's answer, never a list.

    `universe_policy.may_hypothesise` routes by ASSET CLASS from MetaTrader's own registry
    (the two-lane order of 2026-09-06). A symbol absent from the registry is UNCLASSIFIED and is
    not counted as available ground, because absence is not a permission.
    """
    uni = _read(UNIVERSE, default={})
    if not isinstance(uni, dict) or not uni:
        return [], f"{UNMEASURED}: no universe registry at {UNIVERSE}"
    try:
        if str(BASE) not in sys.path:
            sys.path.insert(0, str(BASE))
        from research.universe_policy import may_hypothesise
    except Exception as exc:                                             # pragma: no cover
        return [], f"{UNMEASURED}: lane router unimportable ({type(exc).__name__})"
    return sorted(s.lower() for s in uni if may_hypothesise(str(s))), ""


def _axes() -> tuple[list[str], list[str], list[str], dict[str, str]]:
    """(instruments, families, horizons) of the grid, each from the organ that owns it."""
    why: dict[str, str] = {}
    instruments, note = hypothesis_instruments()
    if note:
        why["instruments"] = note
    families: list[str] = []
    horizons: list[str] = []
    try:
        if str(BASE) not in sys.path:
            sys.path.insert(0, str(BASE))
        from research.axis_registry import HORIZONS
        from research.judge_coverage import live_families
        families = sorted(live_families())
        horizons = [str(h).lower() for h in HORIZONS]
    except Exception as exc:                                             # pragma: no cover
        why["families"] = f"{UNMEASURED}: family/horizon axes unimportable ({type(exc).__name__})"
    return instruments, families, horizons, why


def grid_occupancy(rows: list[tuple[str, str, str, str, str]],
                   *, mintable: set[str] | None = None) -> dict[str, Any]:
    """The family x instrument x horizon grid: how much of it is occupied, and what is empty.

    TWO THINGS WERE CONFUSED HERE AND BOTH COST THE DESK ITS BREADTH (measured 2026-09-23).

    REACHABILITY IS A DONOR QUESTION, NOT A CROWDING QUESTION. This used to skip any family or
    any instrument with zero load, on the reading that an untouched axis is "a family module
    question, not a generation target". But a transplant carries a family's OWN rule onto another
    instrument: what it needs is a rule to carry, which is a DONOR, and nothing else. A family
    holding a donor whose registry cells all sit outside the hypothesis lane scored zero load and
    was skipped -- and it is a whole empty ROW of the grid, the single most orthogonal thing on
    the board. Same for an instrument: the lane router already decided it may be hypothesised on,
    and that IS the permission (absence from the router's answer is still not one). So a cell is
    reachable when its family can be minted and its symbol is in the lane. `mintable` is the set
    of families holding a transplantable donor; passing None keeps the old load-only reading, so
    a caller with no donor census loses nothing.

    ORDER AIMS AT THE SPARSE FRONTIER, NOT THE DENSE MIDDLE. The old sort put the empty cells
    whose family AND symbol were ALREADY the busiest at the head -- exactly backwards for
    effective rank, because a cell added to a crowded row adds mass to a direction the spectrum
    already spans. Cells are now ranked FRONTIER FIRST (a family or an instrument with zero load:
    a new row or column), then by ASCENDING load, so the sparsest reachable ground is aimed at
    first. Reachability was never what the old ranking measured; it measured crowding, and
    preferred it.
    """
    instruments, families, horizons, why = _axes()
    if not instruments or not families or not horizons:
        return {"available": False, "why": why or {"axes": f"{UNMEASURED}: empty axis"}}
    occupied = {f"{f}|{s}|{h}" for f, s, h, _, _ in rows}
    fam_set, sym_set, hor_set = set(families), set(instruments), set(horizons)
    in_grid = {c for c in occupied
               if (p := c.split("|"))[0] in fam_set and p[1] in sym_set and p[2] in hor_set}
    fam_load = Counter(c.split("|")[0] for c in in_grid)
    sym_load = Counter(c.split("|")[1] for c in in_grid)
    nominal = len(families) * len(instruments) * len(horizons)
    can_mint = set(mintable or ())
    targets: list[dict[str, Any]] = []
    frontier = 0
    for fam in families:
        if not fam_load.get(fam) and fam not in can_mint:
            continue                       # nothing to carry: no load and no donor to transplant
        for sym in instruments:
            for hor in horizons:
                if hor == "unknown":
                    continue               # UNKNOWN is a verdict on a cell, not a cell to fill
                cell = f"{fam}|{sym}|{hor}"
                if cell in in_grid:
                    continue
                fl, sl = fam_load.get(fam, 0), sym_load.get(sym, 0)
                is_frontier = not fl or not sl
                frontier += int(is_frontier)
                targets.append({"cell": cell, "family": fam, "symbol": sym, "horizon": hor,
                                "family_load": fl, "symbol_load": sl,
                                "frontier": is_frontier})
    # Frontier first, then the sparsest reachable ground: ascending min-load, ascending total.
    targets.sort(key=lambda t: (not t["frontier"],
                                min(int(t["family_load"]), int(t["symbol_load"])),
                                int(t["family_load"]) + int(t["symbol_load"]), t["cell"]))
    return {
        "available": True, "why": why,
        "axes": {"instruments": len(instruments), "families": len(families),
                 "horizons": len(horizons)},
        "nominal_cells": nominal, "occupied_cells": len(in_grid),
        "occupied_anywhere": len(occupied),
        "occupancy": round(len(in_grid) / nominal, 6) if nominal else None,
        "empty_cells": nominal - len(in_grid),
        "reachable_empty_cells": len(targets),
        "frontier_empty_cells": frontier,
        "mintable_families": len(can_mint),
        "families_never_minted": sorted(f for f in families if not fam_load.get(f))[:40],
        "instruments_never_minted": sorted(s for s in instruments if not sym_load.get(s))[:40],
        "targets_total": len(targets),
        "targets_published": min(len(targets), MAX_TARGETS),
        "targets": targets,
    }


def orthogonality_gain(rows: list[tuple[str, str, str, str, str]]) -> dict[str, Any]:
    """Distinct grid cells opened per cell emitted, per OPERATOR CLASS -- the tuning signal.

    `survivor_distiller` stamps the operator into the mechanism text it enqueues
    ("<mechanism> (mutation: <operator>)"), so the registry already records which class minted
    each cell. A class that emits a hundred cells onto three grid cells scores 0.03 and a class
    that opens a new cell every time scores 1.0. Unmeasured when neither class has emitted.
    """
    per: dict[str, set[str]] = {"mechanism": set(), "parameter": set()}
    emitted: Counter[str] = Counter()
    for fam, sym, hor, _h, mech in rows:
        if "(mutation:" not in mech:
            continue
        op = mech.split("(mutation:", 1)[1].split(")", 1)[0].strip()
        klass = mechanism_class(op)
        emitted[klass] += 1
        per[klass].add(f"{fam}|{sym}|{hor}")
    out: dict[str, Any] = {"available": bool(emitted), "emitted": dict(emitted)}
    for klass in ("mechanism", "parameter"):
        n = emitted.get(klass, 0)
        out[klass] = round(len(per[klass]) / n, 4) if n else None
    if not emitted:
        out["why"] = (f"{UNMEASURED}: no candidate carries an operator stamp, so neither class "
                      f"has a measured gain and the declared share stands unchanged")
    return out


def declared_mechanism_share(path: Path | None = None) -> float:
    """THE SHARE `survivor_distiller` READS. The declared fraction of its task slots that goes
    to mechanism-changing moves. Bounded, two-sided, and never a cap on total output."""
    doc = _read(path or MIX, default={})
    if isinstance(doc, dict):
        raw = doc.get("declared_mechanism_share")
        if isinstance(raw, (int, float)):
            return min(max(float(raw), SHARE_BOUNDS[0]), SHARE_BOUNDS[1])
    return DEFAULT_MECHANISM_SHARE


def empty_pairs(report: Path | None = None) -> set[str]:
    """The (family|symbol) pairs holding a reachable EMPTY horizon -- the generation targets.

    Read from the published artifact, so a generator pays one file read rather than a grid scan
    it would have to repeat every pass. An absent artifact returns an empty set and nothing is
    preferred over anything, which is what an unmeasured target list is worth (L1.28a).
    """
    doc = _read(report or OUT, default={})
    grid = doc.get("grid") if isinstance(doc, dict) else None
    if not isinstance(grid, dict):
        return set()
    return {f"{t.get('family')}|{t.get('symbol')}".lower()
            for t in (grid.get("targets") or []) if isinstance(t, dict)}


def tune_mix(gain: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    """Move the declared share toward the class that is measured to open more ground.

    next = gain(mechanism) / (gain(mechanism) + gain(parameter)), clipped to SHARE_BOUNDS and
    moved halfway from the standing share so one noisy hour cannot swing the mix. An unmeasured
    gain leaves the share exactly where it was, which is what an absent measurement is worth.
    """
    target = out_path = path or MIX
    standing = declared_mechanism_share(out_path)
    m, p = gain.get("mechanism"), gain.get("parameter")
    if not isinstance(m, (int, float)) or not isinstance(p, (int, float)) or (m + p) <= 0:
        doc = {"declared_mechanism_share": round(standing, 4), "standing": round(standing, 4),
               "updated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
               "why": str(gain.get("why") or f"{UNMEASURED}: no measured gain; share unchanged")}
    else:
        want = float(m) / (float(m) + float(p))
        nxt = standing + 0.5 * (want - standing)
        nxt = min(max(nxt, SHARE_BOUNDS[0]), SHARE_BOUNDS[1])
        doc = {"declared_mechanism_share": round(nxt, 4), "standing": round(standing, 4),
               "target_from_gain": round(want, 4),
               "gain": {"mechanism": m, "parameter": p},
               "updated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
               "why": (f"mechanism moves open {m:g} new grid cells per cell against {p:g} for "
                       f"parameter moves, so the share moves {standing:.3f} -> {nxt:.3f}")}
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    except OSError as exc:                                               # pragma: no cover
        doc["write_error"] = f"{type(exc).__name__}: {exc}"
    return doc


def _donors(db: Path | None = None) -> dict[str, dict[str, Any]]:
    """One real, param-carrying candidate per family: the rule a transplant carries with it.

    SQLite's bare-column rule returns the row holding `max(seq)`, so this is the family's most
    recent candidate rather than an arbitrary one.

    THIS ORGAN'S OWN TRANSPLANTS ARE EXCLUDED, and the day it was written without that exclusion
    is the reason the line exists. `max(seq)` means the most recent row, a fill pass writes tens
    of thousands of rows, and on the very next pass 62 of 76 families had one of THIS ORGAN'S
    copies as their donor. The params survive that (a transplant carries the rule unchanged) but
    the lineage does not: the desk would have been transplanting copies of copies and crediting
    itself for every one. A donor must be somebody else's work.

    THE DONOR'S ATTRIBUTION TRAVELS WITH THE RULE. `generator`, `producer` and `discovery_id`
    come back with the params because the transplanted cell IS that producer's rule on new
    ground -- `scripts/check_producer_yield.py` states the law in its own words ("CREDIT THE
    PRODUCER THAT CAUSED THE CELL, NOT THE COMPILER THAT STAMPED IT ... reading the candidate's
    stamp alone credits one pass-through with the desk's whole output"), and a filler that
    carries other people's rules is exactly such a pass-through. `origin` stays this organ, so
    the aim is still billed here and the two questions -- who wrote the rule, who chose the
    ground -- keep separate columns.
    """
    path = db or REGISTRY
    if not path.exists():
        return {}
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return {}
    try:
        cur = con.execute(
            "select lower(coalesce(nullif(family,''),'?')), family, symbol, "
            "lower(coalesce(nullif(horizon,''),'?')), params_json, mechanism, "
            "generator, producer, discovery_id, region, max(seq) "
            "from research_candidates "
            "where params_json is not null and params_json not in ('', '{}') "
            "and family is not null and family != '' "
            "and lower(coalesce(origin,'')) != ? "
            "and lower(coalesce(generator,'')) != ? group by 1", (SOURCE, SOURCE))
        out: dict[str, dict[str, Any]] = {}
        for key, fam, sym, hor, params, mech, gen, prod, disc, reg, _seq in cur:
            try:
                parsed = json.loads(params)
            except (TypeError, ValueError):
                continue
            if isinstance(parsed, dict) and parsed:
                out[str(key)] = {"family": str(fam), "symbol": str(sym), "horizon": str(hor),
                                 "params": parsed, "mechanism": str(mech or ""),
                                 "generator": str(gen or "") or None,
                                 "producer": str(prod or "") or None,
                                 "discovery_id": str(disc or "") or None,
                                 "region": str(reg or "") or None}
        return out
    except sqlite3.Error:
        return {}
    finally:
        con.close()


def _symbol_case() -> dict[str, str]:
    """lower(symbol) -> the registry's own spelling, so a transplant names a real instrument."""
    uni = _read(UNIVERSE, default={})
    return {str(s).lower(): str(s) for s in uni} if isinstance(uni, dict) else {}


def fill_empty_cells(grid: dict[str, Any], *, budget_s: float = 120.0,
                     db: Path | None = None) -> dict[str, Any]:
    """AIM, NOT A LIST: transplant a family's own rule onto the empty cells it has not reached.

    PUBLISHING TARGETS IS NOT FILLING THE GRID (the principal, 2026-09-23). 889 of 57,275 cells
    occupied is 1.55%, and a ranked list of 12,835 reachable empties changes nothing on its own.
    The distiller's mechanism arm cannot reach them either: its moves step from a certificate that
    ALREADY occupies its (family|symbol) pair, so an empty-cell preference can never fire there.

    What reaches an empty cell is a CROSS move. This takes the family's own most recent
    param-carrying rule and enqueues it, unchanged, on the empty (symbol, horizon) the grid names
    -- `cross_instrument` when the instrument differs, `cross_horizon` when only the horizon does.
    Both are mechanism-class operators, stamped so `orthogonality_gain` bills them and the
    declared mix learns what they bought.

    NOTHING IS CAPPED, DROPPED OR THROTTLED. Every cell goes through `enqueue_candidate`, the one
    registry door, which de-duplicates on content hash: a rule already present raises its search
    count and creates nothing, so a re-run cannot inflate the count.

    WHAT ACTUALLY BOUND THIS TO EIGHT CELLS AN HOUR, and it was none of the things anyone would
    look at (measured on the trading box, 2026-09-23). Not the cap: 400 was never reached. Not
    the donors: all 400 published targets had one. Not reachability: 8,410 cells were reachable.
    It was the TIME BUDGET, spent inside the registry door -- `enqueue_candidate` asks whether a
    breadth cell is empty with `WHERE grid_cell=?`, that column had no index, and EXPLAIN read
    `SCAN research_candidates` over 321,168 rows. One cell cost 0.927 s, the fill gets a 75 s
    slice, 75 / 0.927 = 8. With `ix_candidates_gridcell` (added to `libs/moat/registry._evolve`)
    the same call costs 0.0012 s and the same 75 s buys sixty thousand.

    THE SHAPE TO RECOGNISE: an organ that reports `8 of 400` looks throttled by its cap, and
    every reading of the code agrees, because the real limit was a table scan two modules away
    that no artifact named. The cap was innocent and raising it would have changed nothing.

    ONE CONNECTION, not one per cell: `enqueue_candidate` opens, evolves and closes the registry
    on every call it is not handed a connection for. That is cheap here (4 ms) and it is still
    four seconds over a full grid, so the pass holds one open and hands it down.
    """
    started = time.monotonic()
    targets = [t for t in (grid.get("targets") or []) if isinstance(t, dict)]
    if not targets:
        return {"available": False,
                "why": f"{UNMEASURED}: no reachable empty cell to aim at this pass"}
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from libs.moat.registry import connect, enqueue_candidate
    except Exception as exc:                                             # pragma: no cover
        return {"available": False,
                "why": f"{UNMEASURED}: registry door unimportable ({type(exc).__name__})"}
    donors = _donors(db)
    case = _symbol_case()
    occupied_before = int(grid.get("occupied_cells") or 0)
    nominal = int(grid.get("nominal_cells") or 0)
    created: set[str] = set()
    created_rows: list[tuple[str, str, str, str]] = []
    targeted = existing = failed = frontier_hits = 0
    by_operator: Counter[str] = Counter()
    by_producer: Counter[str] = Counter()
    stopped = "list exhausted"
    try:
        con = connect()
    except Exception as exc:                                             # pragma: no cover
        return {"available": False,
                "why": f"{UNMEASURED}: registry unopenable ({type(exc).__name__}: {exc})"}
    try:
        for t in targets[:MAX_FILLS_PER_PASS]:
            if time.monotonic() - started > budget_s:
                stopped = f"time budget {budget_s:g}s reached after {targeted} cells"
                break
            donor = donors.get(str(t.get("family") or ""))
            if not donor:
                continue
            sym = case.get(str(t.get("symbol") or ""), str(t.get("symbol") or "").upper())
            hor = str(t.get("horizon") or "")
            op = "cross_instrument" if sym.lower() != donor["symbol"].lower() else "cross_horizon"
            targeted += 1
            extra = {k: donor[k] for k in ("generator", "producer", "discovery_id", "region")
                     if donor.get(k)}
            try:
                _id, made = enqueue_candidate(
                    family=donor["family"], symbol=sym, params=donor["params"],
                    origin=SOURCE, horizon=hor, conn=con,
                    mechanism=(f"{donor['mechanism'] or donor['family']} carried to {sym} at "
                               f"{hor} (mutation: {op})"),
                    **extra)
            except Exception:                                            # pragma: no cover
                failed += 1
                continue
            by_producer[str(extra.get("generator") or extra.get("producer") or SOURCE)] += 1
            by_operator[op] += 1
            if made:
                created.add(str(t.get("cell") or f"{t.get('family')}|{sym.lower()}|{hor}"))
                created_rows.append((
                    str(extra.get("generator") or extra.get("producer") or SOURCE).lower(),
                    str(t.get("family") or ""), sym.lower(), hor))
                frontier_hits += int(bool(t.get("frontier")))
            else:
                existing += 1
    finally:
        con.close()
    after = occupied_before + len(created)
    return {
        "available": True,
        "law": ("AIM, NOT RESTRICTION: every cell is minted through the one registry door, which "
                "de-duplicates on content hash. Nothing is capped, dropped or slowed"),
        "empty_cells_targeted": targeted,
        "cells_created_in_empty_cells": len(created),
        "frontier_cells_created": frontier_hits,
        "already_present": existing, "failed": failed,
        "by_operator": dict(by_operator),
        # WHOSE RULE WENT WHERE. The transplant carries the donor's attribution because the cell
        # is that producer's rule on new ground; this organ keeps `origin`. A single key here
        # means the fill is crediting itself, which is the pass-through defect, not a measurement.
        "by_donor_producer": dict(by_producer.most_common(40)),
        "donor_producers": len(by_producer),
        "targets_available": len(targets),
        "stopped_because": stopped,
        "occupied_cells_before": occupied_before, "occupied_cells_after": after,
        "occupancy_before": round(occupied_before / nominal, 6) if nominal else None,
        "occupancy_after": round(after / nominal, 6) if nominal else None,
        "newly_occupied_cells": len(created),
        "reachable_empty_after": max(int(grid.get("reachable_empty_cells") or 0) - len(created), 0),
        "orthogonality": fill_orthogonality(created_rows),
        "elapsed_s": round(time.monotonic() - started, 3),
        "seconds_per_cell": (round((time.monotonic() - started) / targeted, 5)
                             if targeted else None),
    }


def fill_orthogonality(created: list[tuple[str, str, str, str]]) -> dict[str, Any]:
    """The effective rank of what THIS PASS minted, on the desk's own breadth machinery.

    NOT THE HEADLINE. The yield fence owns the desk-wide orthogonality-weighted throughput and
    ratchets it; that figure is read here, never re-derived (see `headline`). This measures only
    the cells this filler just created, and it answers the one question raw volume cannot: did
    the hour's fill spread across independent ground, or pile onto one direction?

    TWO MATRICES, BECAUSE THEY ANSWER DIFFERENT QUESTIONS AND ONE OF THEM IS A TRAP.
    `by_producer` is the fence's own shape -- producer x (family|symbol|horizon) -- and its
    participation ratio measures PRODUCER CONCENTRATION: one organ covering all the ground reads
    ~1.0 no matter how much ground that is, which is the number that caught this filler crediting
    itself for 32,585 cells. `by_family` is the same arithmetic over families and measures how
    many independent MECHANISMS the fill touched. Raw count moves neither; both are published so
    a pass that bought volume and no independence says so in its own artifact.

    Effective rank is the participation ratio of the singular-value spectrum,
    (sum s^2)^2 / sum s^4 (`libs.risk.fx_exposure.effective_rank`, reached through
    `sandbox_rotation.breadth`).
    """
    if not created:
        return {"available": False, "why": f"{UNMEASURED}: this pass created no cell to measure"}
    by_family: dict[str, list[str]] = {}
    by_producer: dict[str, list[str]] = {}
    for prod, fam, sym, hor in created:
        cell = f"{fam}|{sym}|{hor}"
        by_family.setdefault(fam or "?", []).append(cell)
        by_producer.setdefault(prod or "?", []).append(cell)
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from libs.research.sandbox_rotation import breadth
    except Exception as exc:                                             # pragma: no cover
        return {"available": False,
                "why": f"{UNMEASURED}: breadth machinery unimportable ({type(exc).__name__})"}
    try:
        fam_b = breadth(by_family)
        prod_b = breadth(by_producer)
    except Exception as exc:                                             # pragma: no cover
        return {"available": False,
                "why": f"{UNMEASURED}: breadth failed ({type(exc).__name__}: {exc})"}
    cells = len({c for cs in by_family.values() for c in cs})
    prod_counts = sorted(((k, len(set(v))) for k, v in by_producer.items()),
                         key=lambda kv: -kv[1])
    total = sum(n for _k, n in prod_counts)
    sq = sum(n * n for _k, n in prod_counts)
    prod_pr = (total * total / sq) if sq else 0.0
    prod_rank = float(prod_b.get("total") or 0.0)
    return {"available": True,
            "effective_rank": fam_b.get("total"),
            "producer_effective_rank": prod_b.get("total"),
            "cells": cells,
            "families": len(by_family), "producers": len(by_producer),
            "symbols": len({s for _p, _f, s, _h in created}),
            "horizons": len({h for _p, _f, _s, h in created}),
            "rank_per_cell": (round(float(fam_b.get("total") or 0.0) / cells, 5)
                              if cells else None),
            # WHAT BOUNDS THE NUMBER, PUBLISHED SO NOBODY READS VOLUME INTO IT AGAIN (2026-09-24).
            # Producer rows here are near-disjoint, so the producer effective rank IS the
            # participation ratio of the per-producer cell COUNTS -- measured on the box's own
            # 24h window, 8.0995 against 8.1395, agreeing to 0.5%. That makes it a CONCENTRATION
            # measure: it can never exceed the producer count, and a pass that lands its cells on
            # the producers who already had the most adds volume and almost no rank. Measured the
            # night the grid filled: 32,739 transplants, 50 distinct parameter sets, 20 producers,
            # 32% of them one producer -- participation ratio 7.0116, which is the 7.1562 the
            # desk saw. `desks/mt5/research/rank_recovery.py` is the organ that widens it, by
            # carrying the LEAST-credited producers' rules onto ground already reached.
            "producer_count_participation_ratio": round(prod_pr, 4),
            "producer_rank_is_a_concentration_measure": (
                abs(prod_rank - prod_pr) <= 0.02 * max(prod_pr, 1.0)),
            "producer_headroom": round(len(by_producer) - prod_rank, 4),
            "top_producer_share": (round(prod_counts[0][1] / total, 4)
                                   if prod_counts and total else None),
            "top_producers": prod_counts[:10],
            "recovered_by": ("desks/mt5/research/rank_recovery.py -- hourly leg `rank_recovery`, "
                             "artifact reports/RANK_RECOVERY.json. The remedy for a low reading "
                             "is MORE producers carried onto the same ground, never fewer cells"),
            "basis": ("participation ratio of the singular-value spectrum of the family x and "
                      "producer x (family|symbol|horizon) indicator matrices of the cells THIS "
                      "PASS created; the desk-wide figure belongs to "
                      "scripts/check_producer_yield.py and is read, never re-derived")}


def ratchet_occupancy(fill: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    """GRID OCCUPANCY RISES ONLY. A fall below the best carries a stated reason or it is a lie.

    The ratchet is a FLOOR and never a cap: the remedy for a breach is to fill more cells, never
    to mint fewer. An unmeasured pass moves nothing -- an absent measurement is not a regression.
    """
    out = path or OCCUPANCY_RATCHET
    doc = _read(out, default={})
    doc = doc if isinstance(doc, dict) else {}
    if not fill.get("available"):
        return {**doc, "verdict": UNMEASURED,
                "why": str(fill.get("why") or f"{UNMEASURED}: nothing measured this pass")}
    now_cells = int(fill.get("occupied_cells_after") or 0)
    best = doc.get("occupied_cells_best")
    reason = str(doc.get("regression_reason") or "")
    failures: list[str] = []
    if isinstance(best, (int, float)) and now_cells < best and not reason:
        failures.append(
            f"grid occupancy fell to {now_cells} occupied cells against a best of {best:g} with "
            f"no stated reason: set `regression_reason` in {out.name} or name the generator that "
            f"stopped filling. The remedy is more cells, never fewer")
    if not isinstance(best, (int, float)) or now_cells > best:
        doc["occupied_cells_best"] = now_cells
        doc["occupancy_best"] = fill.get("occupancy_after")
    doc["updated_utc"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
    doc["law"] = "GRID OCCUPANCY RISES ONLY. This ratchet is a floor and never a cap."
    doc.setdefault("regression_reason", None)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    except OSError as exc:                                               # pragma: no cover
        doc["write_error"] = f"{type(exc).__name__}: {exc}"
    return {**doc, "verdict": "REGRESSION" if failures else "MEASURED", "failures": failures}


def headline() -> dict[str, Any]:
    """The yield fence's own orthogonality-weighted throughput, READ and never re-derived."""
    doc = _read(YIELD, default={})
    owed = doc.get("cells_owed") if isinstance(doc, dict) else None
    if not isinstance(owed, dict):
        return {"available": False,
                "why": f"{UNMEASURED}: no cells_owed block in {YIELD.name}"}
    return {
        "available": True,
        "cells_to_judge_per_hour": owed.get("cells_to_judge_per_hour"),
        "orthogonal_cells_to_judge_per_hour": owed.get("orthogonal_cells_to_judge_per_hour"),
        "orthogonality_weight": owed.get("orthogonality_weight"),
        "effective_rank": (owed.get("breadth") or {}).get("total"),
        "columns": (owed.get("breadth") or {}).get("columns"),
        "ratchet": owed.get("ratchet"),
        "owner": ("scripts/check_producer_yield.py -- it measures and RATCHETS this figure; "
                  "read here, never recomputed"),
    }


def intake_split() -> dict[str, Any]:
    """What the intake ordering did this hour, from the organ that did it."""
    doc = _read(COVERAGE, default={})
    block = doc.get("variant_demotion") if isinstance(doc, dict) else None
    if not isinstance(block, dict):
        return {"available": False,
                "why": (f"{UNMEASURED}: {COVERAGE.name} carries no variant_demotion block yet "
                        f"-- the next docket that ships through judge_coverage writes one")}
    return {"available": True, **block}


def run(budget_s: float = 240.0, *, db: Path | None = None) -> dict[str, Any]:
    """Measure the ladder, the grid and the mix; tune the share; publish."""
    started = time.monotonic()
    rows, why = _rows(db)
    ladder = dedup_ladder(rows)
    # THE DONOR CENSUS COMES FIRST because it is what makes a cell reachable. A family holding a
    # transplantable rule can be carried onto any lane instrument whether or not the grid already
    # shows load for it, and those zero-load families are whole empty ROWS -- the most orthogonal
    # ground on the board. Reading donors after the grid is what hid them.
    donors = _donors(db)
    grid = (grid_occupancy(rows, mintable=set(donors)) if rows
            else {"available": False, "why": why or UNMEASURED})
    gain = orthogonality_gain(rows)
    mix = tune_mix(gain)
    head = headline()
    intake = intake_split()
    # AIM: transplant the families' own rules onto the empty cells, then ratchet what that filled.
    fill = (fill_empty_cells(grid, budget_s=max(budget_s * 0.5, 30.0), db=db)
            if grid.get("available") else
            {"available": False, "why": f"{UNMEASURED}: no measured grid to aim at"})
    occupancy_ratchet = ratchet_occupancy(fill)
    # THE REPORT IS TRUNCATED, THE WORK IS NOT. The filler above was handed every target; the
    # artifact carries the head of the same list so a consumer pays one bounded file read.
    published = grid.get("targets")
    if isinstance(published, list):
        grid["targets"] = published[:MAX_TARGETS]
    doc: dict[str, Any] = {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "law": ("RAISE THE ORTHOGONALITY-WEIGHTED FIGURE, NOT THE RAW ONE. Nothing here caps, "
                "throttles or drops anything: variants keep their place in an uncapped queue, "
                "the mix moves slots between operator classes, and generation is aimed at "
                "ground the desk does not yet hold."),
        "registry_note": why,
        "headline": head, "dedup_ladder": ladder, "grid": grid,
        "fill": fill, "occupancy_ratchet": occupancy_ratchet,
        "intake": intake,
        "mutation_mix": {**mix, "gain": gain,
                         "consumer": "desks/mt5/research/survivor_distiller.py",
                         "bounds": list(SHARE_BOUNDS)},
        "elapsed_s": round(time.monotonic() - started, 3),
        "budget_s": budget_s,
    }
    measured = [b for b in (head, ladder, grid) if b.get("available")]
    doc["verdict"] = "MEASURED" if len(measured) == 3 else UNMEASURED
    return doc


def write(doc: dict[str, Any], *, report: Path | None = None) -> None:
    out = report or OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str) + "\n", encoding="utf-8")
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from libs.ops.events import emit
        grid = doc.get("grid") or {}
        emit("independence_intake", verdict=doc.get("verdict"),
             occupancy=grid.get("occupancy"), empty_cells=grid.get("empty_cells"),
             mechanism_share=(doc.get("mutation_mix") or {}).get("declared_mechanism_share"),
             orthogonal_per_hour=(doc.get("headline") or {}).get(
                 "orthogonal_cells_to_judge_per_hour"))
    except Exception:                                                    # pragma: no cover
        pass


def render(doc: dict[str, Any]) -> list[str]:
    head = doc.get("headline") or {}
    lad = doc.get("dedup_ladder") or {}
    grid = doc.get("grid") or {}
    lines = [f"INDEPENDENCE INTAKE  {doc.get('verdict')}",
             f"  orthogonal cells/h {head.get('orthogonal_cells_to_judge_per_hour')} of "
             f"{head.get('cells_to_judge_per_hour')} raw  (weight "
             f"{head.get('orthogonality_weight')}, effective rank {head.get('effective_rank')})",
             f"  ladder  raw {lad.get('raw_cells')} -> hashes {lad.get('content_hashes')} -> "
             f"grid {lad.get('grid_cells')} -> mechanisms {lad.get('mechanisms')}",
             f"  grid    {grid.get('occupied_cells')}/{grid.get('nominal_cells')} occupied "
             f"({grid.get('occupancy')}), {grid.get('reachable_empty_cells')} reachable empty "
             f"({grid.get('frontier_empty_cells')} frontier)",
             f"  mix     mechanism share "
             f"{(doc.get('mutation_mix') or {}).get('declared_mechanism_share')}"]
    fill = doc.get("fill") or {}
    if fill.get("available"):
        lines.append(f"  fill    {fill.get('empty_cells_targeted')} empty cells aimed at, "
                     f"{fill.get('cells_created_in_empty_cells')} cells created "
                     f"({fill.get('frontier_cells_created')} frontier); occupancy "
                     f"{fill.get('occupancy_before')} -> {fill.get('occupancy_after')} "
                     f"({fill.get('occupied_cells_before')} -> "
                     f"{fill.get('occupied_cells_after')} cells)")
        orth = fill.get("orthogonality") or {}
        lines.append(f"  rank    fill effective rank {orth.get('effective_rank')} (family) / "
                     f"{orth.get('producer_effective_rank')} (producer) over "
                     f"{orth.get('cells')} cells, {orth.get('families')} families, "
                     f"{orth.get('producers')} producers, {orth.get('symbols')} symbols")
        lines.append(f"  stop    {fill.get('stopped_because')} at "
                     f"{fill.get('seconds_per_cell')}s per cell, "
                     f"{fill.get('targets_available')} targets available")
    intake = doc.get("intake") or {}
    if intake.get("available"):
        lines.append(f"  intake  {intake.get('unseen_mechanisms')} unseen / "
                     f"{intake.get('variants')} variants, {intake.get('slots_freed')} judge "
                     f"slots freed")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Independence at intake: order, mutate, spread")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=240.0)
    args = ap.parse_args(argv)
    doc = run(budget_s=float(args.budget_s))
    write(doc)
    for line in render(doc):
        print(line)
    return 0


if __name__ == "__main__":                                               # pragma: no cover
    raise SystemExit(main())
