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
#: How many empty grid cells are published as targets. The generators read the head of the list;
#: the count and the occupancy are the measurement, the list is the instruction.
MAX_TARGETS = 400
#: Rows read from the registry for the ladder. The ladder is a count of DISTINCT keys, which
#: saturates long before this; the bound keeps the scan off an 8 GB box's memory.
MAX_ROWS = 400_000

#: How many empty cells one PASS transplants a rule onto. Not a ceiling on the grid and not a cap
#: on any producer: the ranked list is re-derived every hour and a cell that fills leaves it, so
#: the next pass continues down the same list. It bounds one hour's registry writes, nothing else.
MAX_FILLS_PER_PASS = 400
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


def grid_occupancy(rows: list[tuple[str, str, str, str, str]]) -> dict[str, Any]:
    """The family x instrument x horizon grid: how much of it is occupied, and what is empty.

    The occupied set is the registry's own, so a cell counts as held the moment one candidate
    sits on it. The empty set is ranked by how much of its OWN row and column is already
    working: an empty cell whose family and whose symbol are both already productive is reachable
    today, and an empty cell on an axis nothing has ever touched is a family module question, not
    a generation target. Both are published; only the first is aimed at.
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
    targets: list[dict[str, Any]] = []
    for fam in families:
        if not fam_load.get(fam):
            continue                       # a family nothing has ever minted is a wiring gap
        for sym in instruments:
            if not sym_load.get(sym):
                continue
            for hor in horizons:
                if hor == "unknown":
                    continue               # UNKNOWN is a verdict on a cell, not a cell to fill
                cell = f"{fam}|{sym}|{hor}"
                if cell in in_grid:
                    continue
                targets.append({"cell": cell, "family": fam, "symbol": sym, "horizon": hor,
                                "family_load": fam_load[fam], "symbol_load": sym_load[sym]})
    targets.sort(key=lambda t: (-min(int(t["family_load"]), int(t["symbol_load"])), t["cell"]))
    return {
        "available": True, "why": why,
        "axes": {"instruments": len(instruments), "families": len(families),
                 "horizons": len(horizons)},
        "nominal_cells": nominal, "occupied_cells": len(in_grid),
        "occupied_anywhere": len(occupied),
        "occupancy": round(len(in_grid) / nominal, 6) if nominal else None,
        "empty_cells": nominal - len(in_grid),
        "reachable_empty_cells": len(targets),
        "families_never_minted": sorted(f for f in families if not fam_load.get(f))[:40],
        "instruments_never_minted": sorted(s for s in instruments if not sym_load.get(s))[:40],
        "targets": targets[:MAX_TARGETS],
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
    recent candidate rather than an arbitrary one. A family with no params has no donor and is
    simply not transplanted -- there is nothing to move.
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
            "lower(coalesce(nullif(horizon,''),'?')), params_json, mechanism, max(seq) "
            "from research_candidates "
            "where params_json is not null and params_json not in ('', '{}') "
            "and family is not null and family != '' group by 1")
        out: dict[str, dict[str, Any]] = {}
        for key, fam, sym, hor, params, mech, _seq in cur:
            try:
                parsed = json.loads(params)
            except (TypeError, ValueError):
                continue
            if isinstance(parsed, dict) and parsed:
                out[str(key)] = {"family": str(fam), "symbol": str(sym), "horizon": str(hor),
                                 "params": parsed, "mechanism": str(mech or "")}
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
    count and creates nothing, so a re-run cannot inflate the count. `MAX_FILLS_PER_PASS` is the
    size of a PASS, not a ceiling on the grid -- the ranked list is re-derived every hour and the
    cells filled leave it, so the next pass continues down the same list.
    """
    started = time.monotonic()
    targets = [t for t in (grid.get("targets") or []) if isinstance(t, dict)]
    if not targets:
        return {"available": False,
                "why": f"{UNMEASURED}: no reachable empty cell to aim at this pass"}
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from libs.moat.registry import enqueue_candidate
    except Exception as exc:                                             # pragma: no cover
        return {"available": False,
                "why": f"{UNMEASURED}: registry door unimportable ({type(exc).__name__})"}
    donors = _donors(db)
    case = _symbol_case()
    occupied_before = int(grid.get("occupied_cells") or 0)
    nominal = int(grid.get("nominal_cells") or 0)
    created: set[str] = set()
    targeted = existing = failed = 0
    by_operator: Counter[str] = Counter()
    for t in targets[:MAX_FILLS_PER_PASS]:
        if time.monotonic() - started > budget_s:
            break
        donor = donors.get(str(t.get("family") or ""))
        if not donor:
            continue
        sym = case.get(str(t.get("symbol") or ""), str(t.get("symbol") or "").upper())
        hor = str(t.get("horizon") or "")
        op = "cross_instrument" if sym.lower() != donor["symbol"].lower() else "cross_horizon"
        targeted += 1
        try:
            _id, made = enqueue_candidate(
                family=donor["family"], symbol=sym, params=donor["params"],
                origin=SOURCE, generator=SOURCE, horizon=hor,
                mechanism=(f"{donor['mechanism'] or donor['family']} carried to {sym} at {hor} "
                           f"(mutation: {op})"))
        except Exception:                                                # pragma: no cover
            failed += 1
            continue
        by_operator[op] += 1
        if made:
            created.add(str(t.get("cell") or f"{t.get('family')}|{sym.lower()}|{hor}"))
        else:
            existing += 1
    after = occupied_before + len(created)
    return {
        "available": True,
        "law": ("AIM, NOT RESTRICTION: every cell is minted through the one registry door, which "
                "de-duplicates on content hash. Nothing is capped, dropped or slowed"),
        "empty_cells_targeted": targeted,
        "cells_created_in_empty_cells": len(created),
        "already_present": existing, "failed": failed,
        "by_operator": dict(by_operator),
        "occupied_cells_before": occupied_before, "occupied_cells_after": after,
        "occupancy_before": round(occupied_before / nominal, 6) if nominal else None,
        "occupancy_after": round(after / nominal, 6) if nominal else None,
        "newly_occupied_cells": len(created),
        "reachable_empty_after": max(int(grid.get("reachable_empty_cells") or 0) - len(created), 0),
        "elapsed_s": round(time.monotonic() - started, 3),
    }


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
    grid = grid_occupancy(rows) if rows else {"available": False, "why": why or UNMEASURED}
    gain = orthogonality_gain(rows)
    mix = tune_mix(gain)
    head = headline()
    intake = intake_split()
    # AIM: transplant the families' own rules onto the empty cells, then ratchet what that filled.
    fill = (fill_empty_cells(grid, budget_s=max(budget_s * 0.5, 30.0), db=db)
            if grid.get("available") else
            {"available": False, "why": f"{UNMEASURED}: no measured grid to aim at"})
    occupancy_ratchet = ratchet_occupancy(fill)
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
             f"({grid.get('occupancy')}), {grid.get('reachable_empty_cells')} reachable empty",
             f"  mix     mechanism share "
             f"{(doc.get('mutation_mix') or {}).get('declared_mechanism_share')}"]
    fill = doc.get("fill") or {}
    if fill.get("available"):
        lines.append(f"  fill    {fill.get('empty_cells_targeted')} empty cells aimed at, "
                     f"{fill.get('cells_created_in_empty_cells')} cells created; occupancy "
                     f"{fill.get('occupancy_before')} -> {fill.get('occupancy_after')} "
                     f"({fill.get('occupied_cells_before')} -> "
                     f"{fill.get('occupied_cells_after')} cells)")
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
