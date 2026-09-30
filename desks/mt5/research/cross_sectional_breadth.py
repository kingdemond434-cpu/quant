#!/usr/bin/env python3
"""SEED THE CROSS-SECTIONAL CLASS BOOKS INTO THE DOCKET, AND SAY WHERE THEY LANDED.

    python desks/mt5/research/cross_sectional_breadth.py --once --budget-s 900
    python desks/mt5/research/cross_sectional_breadth.py --once --dry-run  # measure only

WHY. Measured on the trading box 2026-09-30: 837 certificates and k_eff 2.53, 9 of 15 alpha
clusters occupied. Tier-1 books get their hundreds of independent bets from CROSS-SECTIONAL
books, and the desk's one cross-sectional family could never be judged -- it takes its peers as
an argument the sealed gauntlet does not supply (see `mt5desk/families_cross_sectional.py`). The
six families in that module load their own class panel, so a cell is just (symbol, family,
params) and reaches the ten gates through the one intake every miner uses.

WHAT A PASS DOES, in order:
  1. Walk every hypothesis-lane symbol that has a peer class (`universe_policy.peer_class`, the
     broker registry, never a symbol list) and whose H1 bars are in the store.
  2. For every family x param-grid cell on it (`families_cross_sectional.PARAM_GRID`), run the
     family on the symbol's own bars and COUNT how it fires: distinct signal days, and a LOWER
     BOUND on distinct trade-entry days (signals walked one position at a time, each held to its
     full time exit -- an earlier stop only adds trades). The sealed gauntlet drops any cell whose
     daily series has fewer than 60 days; a cell under SEED_FLOOR here is HELD BACK and counted,
     never donated to come back UNKNOWN.
  3. Donate the cells that clear it through `proposer_common.donate` -- the two-lane filter, the
     point-in-time stamp, the preregistration and the registry's `enqueue_candidate`, i.e. the
     same door every miner uses -- into `data/intelligence/cross_sectional_breadth/`, which
     `miner_candidate_compiler` compiles as EXACT_RECIPE into the docket the gauntlet judges.
  4. Write `reports/CROSS_SECTIONAL_BREADTH.json`: the families, the cluster and census class
     each is built to fill and whether that target is EMPTY right now, cells seeded / held back
     per family and class, and the verdicts and certificates they have earned per cluster.

ADDITIVE ONLY. Nothing here caps, reorders or slows any other miner; it adds cells. A cell is
measured at most once per day (the state file carries the day), so a pass that runs out of budget
resumes where it stopped on the next hour instead of restarting the same prefix.

UNMEASURED IS AN ANSWER (L1.28a). An absent breadth artifact, ledger or canon makes the field it
feeds UNMEASURED with the reason; it never reads as zero.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd  # noqa: E402
from mt5desk import families_cross_sectional as xs  # noqa: E402

SOURCE = "cross_sectional_breadth"
OUT = BASE / "reports" / "CROSS_SECTIONAL_BREADTH.json"
STATE = BASE / "data" / "cross_sectional_breadth_state.json"
BREADTH = BASE / "reports" / "EFFECTIVE_BREADTH.json"
BREADTH_LEDGER = ROOT / "web" / "breadth_ledger.json"
CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
VERDICTS = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
UNMEASURED = "UNMEASURED"

#: The sealed gauntlet's own floor: a daily series under 60 days is dropped before any gate.
FIRE_FLOOR = 60
#: What a cell must clear HERE. Ten percent above the gauntlet's floor, because the gauntlet trims
#: a partial last day and the cost model can refuse an entry the count above assumed.
SEED_FLOOR = 66
#: Bytes of the verdict ledger's tail read per pass. The newest verdicts are at the end.
VERDICT_TAIL_BYTES = 64 * 1024 * 1024


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def identity(symbol: str, family: str, params: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps({"s": symbol, "f": family, "p": params}, sort_keys=True,
                                     default=str).encode()).hexdigest()[:20]


def grid(family: str) -> list[dict[str, Any]]:
    spec = xs.PARAM_GRID.get(family) or {}
    keys = sorted(spec)
    return [dict(zip(keys, combo, strict=True))
            for combo in itertools.product(*(spec[k] for k in keys))]


def firing(sigs: list, d: pd.DataFrame) -> dict[str, int]:
    """Distinct signal days, and a LOWER BOUND on distinct trade-entry days.

    The engine holds one position at a time and enters at the bar after the signal. Walking the
    signals with each trade held to its full time exit gives the FEWEST trades the engine can
    take; a stop or target hit earlier frees the book sooner and can only add trades. Signals are
    at most one per decision day, so trades are on distinct days.
    """
    if not sigs:
        return {"signal_days": 0, "trade_days_lb": 0}
    idx = d.index
    days = {pd.Timestamp(s.time).date() for s in sigs}
    free_from = -1
    trades = 0
    for s in sorted(sigs, key=lambda s: pd.Timestamp(s.time)):
        p = int(idx.searchsorted(pd.Timestamp(s.time)))
        if p <= free_from or p + 1 >= len(idx):
            continue
        trades += 1
        free_from = p + 1 + int(s.ttl_bars)
    return {"signal_days": len(days), "trade_days_lb": trades}


def _bars(symbol: str) -> pd.DataFrame | None:
    path = xs.UNIVERSE_DIR / f"{symbol}_H1.parquet"
    if not path.exists():
        return None
    try:
        return xs._h1(pd.read_parquet(path))
    except Exception:
        return None


def _load_state() -> dict[str, Any]:
    doc = _read(STATE)
    return doc if isinstance(doc, dict) and isinstance(doc.get("cells"), dict) else {"cells": {}}


def _save_state(state: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True), "utf-8")
    tmp.replace(STATE)


def _mechanism(family: str, symbol: str, klass: str) -> str:
    t = xs.TARGETS.get(family, {})
    return (f"{family} on {symbol} ranked within its {klass} class: {t.get('prior', '')}. "
            f"Built for the {t.get('cluster', '?')} alpha cluster; one market-neutral leg of a "
            "class book, long the top of the class and short the bottom")


def seed(*, budget_s: float = 900.0, dry_run: bool = False,
         symbols: list[str] | None = None) -> dict[str, Any]:
    """Measure firing on the grid and donate every cell that clears SEED_FLOOR. Never raises
    out of a single cell: a family that errors on one symbol is counted and the pass goes on."""
    started = time.monotonic()
    today = datetime.now(tz=UTC).date().isoformat()
    try:
        classes = xs._policy().peer_classes()
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"peer classes unreadable: {type(exc).__name__}"}
    state = _load_state()
    cells_state: dict[str, Any] = state["cells"]
    cands: list[dict[str, Any]] = []
    by_family: dict[str, Counter] = {f: Counter() for f in xs.CROSS_SECTIONAL_FAMILIES}
    by_class: dict[str, Counter] = {}
    no_bars: list[str] = []
    errors: Counter = Counter()
    stopped = "grid exhausted"
    for klass, members in sorted(classes.items()):
        row = by_class.setdefault(klass, Counter())
        row["members_in_registry"] = len(members)
        for sym in members:
            if symbols and sym not in symbols:
                continue
            if time.monotonic() - started > budget_s:
                stopped = f"time budget {budget_s:g}s reached; resumes next pass"
                break
            plan = [(fam, fn, {"symbol": sym, **params})
                    for fam, fn in xs.CROSS_SECTIONAL_FAMILIES.items() for params in grid(fam)]
            stale = any((cells_state.get(identity(sym, f, c)) or {}).get("day") != today
                        for f, _fn, c in plan)
            d = _bars(sym) if stale else None
            if stale and d is None:
                no_bars.append(sym)
                row["members_without_bars"] += 1
                continue
            for fam, fn, call in plan:
                ident = identity(sym, fam, call)
                prior = cells_state.get(ident) or {}
                by_family[fam]["grid"] += 1
                row["grid"] += 1
                if prior.get("day") != today:
                    try:
                        got = firing(list(fn(d, **call) or []), d)
                    except Exception as exc:
                        errors[f"{fam}: {type(exc).__name__}"] += 1
                        continue
                    prior = {**prior, **got, "day": today, "family": fam, "symbol": sym,
                             "klass": klass, "params": call}
                    cells_state[ident] = prior
                    by_family[fam]["measured_this_pass"] += 1
                ok = int(prior.get("trade_days_lb") or 0) >= SEED_FLOOR
                by_family[fam]["clears_floor" if ok else "held_back_under_floor"] += 1
                row["clears_floor" if ok else "held_back_under_floor"] += 1
                if ok and not prior.get("donated_at"):
                    cands.append({"ident": ident, "symbol": sym, "family": fam,
                                  "params": call, "klass": klass,
                                  "firing": {k: prior.get(k) for k in
                                             ("signal_days", "trade_days_lb")}})
        else:
            continue
        break

    donated = 0
    donation: dict[str, Any] = {"status": "DRY_RUN" if dry_run else "NOTHING_NEW"}
    if cands and not dry_run:
        from research import proposer_common as pc
        rows = [pc.candidate(
            SOURCE, c["symbol"], c["family"], c["params"],
            _mechanism(c["family"], c["symbol"], c["klass"]),
            f"{c['symbol']} {c['family']} (class {c['klass']})",
            {"firing": c["firing"], "seed_floor": SEED_FLOOR, "gauntlet_floor": FIRE_FLOOR,
             "target_cluster": xs.TARGETS.get(c["family"], {}).get("cluster"),
             "peer_class": c["klass"]}) for c in cands]
        path = pc.donate(SOURCE, rows, sum(int(v["measured_this_pass"])
                                           for v in by_family.values()) or len(rows))
        counts = pc.donation_counts()
        donated = int(counts.get("donated") or 0)
        donation = {"status": "DONATED" if path else "REFUSED_AT_DOOR",
                    "path": str(path) if path else None,
                    "refused_wrong_lane": counts.get("refused_wrong_lane"),
                    "refused_unstamped": counts.get("refused_unstamped"),
                    "registry_error": counts.get("registry_error")}
        if path:
            at = _now()
            for c in cands:
                cells_state[c["ident"]]["donated_at"] = at
                by_family[c["family"]]["seeded_this_pass"] += 1
    if not dry_run:
        _save_state(state)
    seeded_total = Counter(str(v.get("family")) for v in cells_state.values()
                           if v.get("donated_at"))
    seeded_by_class = Counter(str(v.get("klass")) for v in cells_state.values()
                              if v.get("donated_at"))
    for fam, cnt in by_family.items():
        cnt["seeded_total"] = seeded_total.get(fam, 0)
    for klass, cnt in by_class.items():
        cnt["seeded_total"] = seeded_by_class.get(klass, 0)
    measured = [v for v in cells_state.values() if v.get("day")]
    return {
        "status": "OK", "dry_run": bool(dry_run), "stopped_because": stopped,
        "elapsed_s": round(time.monotonic() - started, 2),
        "seed_floor_trade_days": SEED_FLOOR, "gauntlet_floor_days": FIRE_FLOOR,
        "cells_by_family": {k: dict(v) for k, v in by_family.items()},
        "cells_by_class": {k: dict(v) for k, v in sorted(by_class.items())},
        "candidates_this_pass": len(cands), "donated_this_pass": donated,
        "donation": donation,
        "symbols_without_bars": sorted(set(no_bars)),
        "errors": dict(errors),
        "firing_of_seeded": _firing_summary([v for v in measured if v.get("donated_at")]),
        "firing_of_clearing": _firing_summary(
            [v for v in measured if int(v.get("trade_days_lb") or 0) >= SEED_FLOOR]),
        "firing_of_held_back": _firing_summary(
            [v for v in measured if int(v.get("trade_days_lb") or 0) < SEED_FLOOR]),
    }


def _firing_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    td = sorted(int(r.get("trade_days_lb") or 0) for r in rows)
    sd = sorted(int(r.get("signal_days") or 0) for r in rows)
    return {"n": len(rows), "trade_days_lb_min": td[0], "trade_days_lb_median": td[len(td) // 2],
            "signal_days_min": sd[0], "signal_days_median": sd[len(sd) // 2]}


# ------------------------------------------------------------------------------ the report ---
def _cluster_occupancy() -> dict[str, Any]:
    doc = _read(BREADTH)
    if not isinstance(doc, dict) or not isinstance(doc.get("clusters"), dict):
        return {"status": UNMEASURED, "why": f"{BREADTH.name} absent or has no clusters block"}
    from libs.research.alpha_clusters import CLUSTERS
    occ = set(doc["clusters"].get("occupied_either") or [])
    return {"status": "MEASURED", "occupied": sorted(occ),
            "empty": [c.key for c in CLUSTERS if c.key not in occ],
            "measured_at": doc.get("generated_at") or doc.get("at")}


def _vacant_classes() -> dict[str, Any]:
    doc = _read(BREADTH_LEDGER)
    if not isinstance(doc, dict) or "vacant_high_orthogonality_classes" not in doc:
        return {"status": UNMEASURED, "why": f"{BREADTH_LEDGER} absent or unreadable"}
    return {"status": "MEASURED", "updated": doc.get("updated"),
            "vacant": [str(v.get("class")) for v in doc["vacant_high_orthogonality_classes"]
                       if isinstance(v, dict)]}


def _verdicts() -> dict[str, Any]:
    """Verdicts the sealed gauntlet recorded on these families, by family and terminal gate."""
    fams = set(xs.CROSS_SECTIONAL_FAMILIES)
    try:
        size = VERDICTS.stat().st_size
        with VERDICTS.open("rb") as fh:
            if size > VERDICT_TAIL_BYTES:
                fh.seek(size - VERDICT_TAIL_BYTES)
                fh.readline()
            blob = fh.read()
    except OSError as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__} reading {VERDICTS.name}"}
    out: dict[str, Counter] = {}
    for line in blob.splitlines():
        if not line.strip() or b"class_" not in line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        fam = str(row.get("family") or "")
        if fam in fams:
            out.setdefault(fam, Counter())[str(row.get("terminal_gate") or "?")] += 1
    if not out:
        return {"status": UNMEASURED, "why": ("the gauntlet has recorded no verdict on any "
                                              "cross-sectional class cell yet")}
    return {"status": "MEASURED", "by_family": {k: dict(v) for k, v in out.items()}}


def _certificates(verdicts: dict[str, Any]) -> dict[str, Any]:
    """Certificates in the canon on these families, per target cluster.

    UNMEASURED, NOT ZERO, until the gauntlet has judged at least one of these cells: a canon
    with none of them in it before any verdict is a statement about the queue, not the edge."""
    if verdicts.get("status") != "MEASURED":
        return {"status": UNMEASURED,
                "why": f"no verdict on these families yet ({verdicts.get('why')})"}
    doc = _read(CANON)
    if not isinstance(doc, dict) or not isinstance(doc.get("survivors"), dict):
        return {"status": UNMEASURED, "why": f"{CANON.name} absent or unreadable"}
    by_cluster: Counter = Counter()
    by_family: Counter = Counter()
    symbols: dict[str, set[str]] = {}
    for key, cert in doc["survivors"].items():
        if not isinstance(cert, dict):
            continue
        fam = str((cert.get("shadow_spec") or {}).get("family") or cert.get("family") or "")
        if not fam:
            fam = next((f for f in xs.CROSS_SECTIONAL_FAMILIES if f in str(key)), "")
        if fam not in xs.CROSS_SECTIONAL_FAMILIES:
            continue
        cl = xs.TARGETS[fam]["cluster"]
        by_cluster[cl] += 1
        by_family[fam] += 1
        symbols.setdefault(cl, set()).add(str(cert.get("sym") or ""))
    return {"status": "MEASURED", "by_cluster": dict(by_cluster), "by_family": dict(by_family),
            "symbols_by_cluster": {k: sorted(v) for k, v in symbols.items()},
            "total": int(sum(by_cluster.values()))}


def _families(occupancy: dict[str, Any], vacant: dict[str, Any]) -> list[dict[str, Any]]:
    from libs.research.alpha_clusters import classify_family
    from libs.research.mechanism_census import CONSTRUCTION_CLASS
    from libs.validation.family_multiplicity import family_of
    rows = []
    for fam in xs.CROSS_SECTIONAL_FAMILIES:
        target = xs.TARGETS[fam]["cluster"]
        census = family_of(fam)
        census_class = CONSTRUCTION_CLASS.get(fam)
        rows.append({
            "family": fam, "prior": xs.TARGETS[fam]["prior"],
            "target_cluster": target, "classified_cluster": classify_family(fam),
            "target_cluster_empty_now": (target in occupancy.get("empty", [])
                                         if occupancy.get("status") == "MEASURED"
                                         else UNMEASURED),
            "census_class": census_class, "multiplicity_family": census,
            "census_class_vacant_now": (census_class in vacant.get("vacant", [])
                                        if vacant.get("status") == "MEASURED" else UNMEASURED),
            "grid_per_symbol": len(grid(fam)), "param_grid": xs.PARAM_GRID[fam],
            "registered_in": "mt5desk.families_orthogonal.ORTHOGONAL_FAMILIES",
        })
    return rows


def report(seeded: dict[str, Any]) -> dict[str, Any]:
    occupancy = _cluster_occupancy()
    vacant = _vacant_classes()
    verdicts = _verdicts()
    try:
        classes = xs._policy().peer_classes()
    except Exception:
        classes = {}
    return {
        "at": _now(), "organ": "desks/mt5/research/cross_sectional_breadth.py",
        "rule": ("each cell is one market-neutral LEG of a within-class rank book; a cell is "
                 f"donated only when its lower-bound trade days clear {SEED_FLOOR} (the sealed "
                 f"gauntlet drops a series under {FIRE_FLOOR} days as UNKNOWN). Additive: no "
                 "other miner is capped, reordered or slowed"),
        "families": _families(occupancy, vacant),
        "peer_classes": {k: {"members": len(v),
                             "rankable": len(v) >= xs.MIN_MEMBERS} for k, v in classes.items()},
        "cluster_occupancy_now": occupancy,
        "vacant_census_classes_now": vacant,
        "seeding": seeded,
        "verdicts": verdicts,
        "certificates": _certificates(verdicts),
        "consumer": ("data/intelligence/cross_sectional_breadth/ -> "
                     "research/miner_candidate_compiler.py (EXACT_RECIPE) -> the docket -> "
                     "scripts/external_gauntlet.py build_cell (sealed; resolves the family via "
                     "families_orthogonal.ORTHOGONAL_FAMILIES)"),
    }


def run(*, budget_s: float = 900.0, dry_run: bool = False,
        symbols: list[str] | None = None, out: Path | None = None) -> dict[str, Any]:
    seeded = seed(budget_s=budget_s, dry_run=dry_run, symbols=symbols)
    doc = report(seeded)
    target = out or OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true", help="one pass (the scheduled form)")
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--dry-run", action="store_true", help="measure and report, donate nothing")
    ap.add_argument("--symbols", nargs="*", default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    doc = run(budget_s=args.budget_s, dry_run=args.dry_run, symbols=args.symbols, out=args.out)
    s = doc["seeding"]
    print(f"cross_sectional_breadth: {s.get('status')} candidates={s.get('candidates_this_pass')} "
          f"donated={s.get('donated_this_pass')} stopped={s.get('stopped_because')!r} "
          f"elapsed={s.get('elapsed_s')}s -> {args.out or OUT}")
    for fam, c in (s.get("cells_by_family") or {}).items():
        print(f"  {fam:32} grid={c.get('grid', 0):5} clears={c.get('clears_floor', 0):5} "
              f"held_back={c.get('held_back_under_floor', 0):5} "
              f"seeded_total={c.get('seeded_total', 0):5}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
