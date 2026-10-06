#!/usr/bin/env python3
"""SEED THE FAMILIES ABSORBED FROM THE ELITEQUANT AND THUQUANT LISTS, SCREENED, AND SAY WHAT LANDED.

    python desks/mt5/research/elitequant_breadth.py --once --budget-s 600
    python desks/mt5/research/elitequant_breadth.py --once --dry-run   # measure only

WHY. `mt5desk/families_elitequant.py` adds five price-only mechanisms the desk could not express
(fractional-difference level reversion, the Corwin-Schultz spread shock, backward sup-ADF
bubbles, Carver's accel and skew rules), and `mt5desk/families_cn_cta.py` adds the Chinese futures
CTA canon (Dual Thrust, R-Breaker, Sky Garden, King Keltner), whose MT5 analogues are walked
first. A registered family nobody seeds is IDLE (III.16), so
this organ puts every hypothesis-lane symbol x PARAM_GRID cell in front of the ten gates.

WHAT A PASS DOES, in order:
  1. Walk every symbol in the broker registry that `universe_policy.may_hypothesise` admits and
     whose H1 bars are in the store (the registry decides, never a symbol list).
  2. Run each family x grid cell on the symbol's bars and SCREEN it with
     `proposer_common.screen`: forward return at the family's own TTL, non-overlapping, net of the
     desk's corrected round trip. A cell measured today is not re-measured today.
  3. Donate every cell that clears cost on at least MIN_TRADES independent trades through
     `proposer_common.donate` -- the two-lane filter, point-in-time stamp, preregistration and
     registry, the same door every miner uses -- into `data/intelligence/elitequant_breadth/`,
     which `miner_candidate_compiler` compiles as EXACT_RECIPE. Each row carries its mechanism's
     culture provenance (`families_elitequant.CULTURE`, the `cell_culture` schema, declared).
  4. Write `reports/ELITEQUANT_BREADTH.json`: per family, cells measured / donated / held back
     with the reason, the screen's t distribution against the null's expected tails, and the
     sweep-deflated best cell -- the measured contract this subsystem answers to.

THE SCREEN IS NOT THE GAUNTLET and the donation threshold is COST, not significance: the ten
gates are the only judge. Cells that cannot pay their own round trip even before deflation are
held back and counted, because each donated cell is a trial the shared deflation charges every
FX and metals cell for. ADDITIVE ONLY: nothing here caps, reorders or slows another miner.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
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

from mt5desk import families_cn_cta as cn  # noqa: E402
from mt5desk import families_elitequant as eq  # noqa: E402
from mt5desk import families_quantguild as qg  # noqa: E402
from mt5desk import families_quanttrading as qt  # noqa: E402

#: Every family absorbed from the two curated lists, with its grid and declared culture:
#: EliteQuant (Western canon), thuquant/awesome-quant (the CN futures CTA canon) and
#: je-suis-tm/quant-trading (retail chart patterns and the Oil Money commodity-FX residual).
FAMILIES = {**eq.ELITEQUANT_FAMILIES, **cn.CN_CTA_FAMILIES, **qt.QUANTTRADING_FAMILIES,
            **qg.QUANTGUILD_FAMILIES}
PARAM_GRID = {**eq.PARAM_GRID, **cn.PARAM_GRID, **qt.PARAM_GRID, **qg.PARAM_GRID}
CULTURE = {**eq.CULTURE, **cn.CULTURE, **qt.CULTURE, **qg.CULTURE}
#: Where each family came from, for the donated row's provenance.
ORIGIN = {**dict.fromkeys(eq.ELITEQUANT_FAMILIES, "github.com/EliteQuant/EliteQuant (Apache-2.0)"),
          **dict.fromkeys(cn.CN_CTA_FAMILIES, "github.com/thuquant/awesome-quant (MIT)"),
          **dict.fromkeys(qt.QUANTTRADING_FAMILIES,
                          "github.com/je-suis-tm/quant-trading (Apache-2.0)"),
          # No licence upstream: the two rules are re-derived from the lectures, nothing copied.
          **dict.fromkeys(qg.QUANTGUILD_FAMILIES,
                          "github.com/romanmichaelpaolucci/Quant-Guild-Library (no licence; "
                          "rewritten)")}
#: The registry id each family's cells are credited to (`origin_source_id` on the donated row):
#: the donor repository, rostered in data/source_rosters/elitequant_breadth_origins.json (the
#: Quant Guild Library is a federation seed row that names this organ in `fetched_by`).
SOURCE_ID = {fam: "github:" + ORIGIN[fam].split(" ")[0].removeprefix("github.com/")
             for fam in FAMILIES}
#: Families that read their own second leg keyed by the cell's `symbol` parameter.
SYMBOL_KEYED = frozenset({"commodity_fx_residual"})

SOURCE = "elitequant_breadth"
OUT = BASE / "reports" / "ELITEQUANT_BREADTH.json"
STATE = BASE / "data" / "elitequant_breadth_state.json"
UNMEASURED = "UNMEASURED"
#: Independent trades a cell needs before its screen mean is a number (proposer_common's floor).
MIN_TRADES = 30
#: Shortest H1 history worth screening: the slowest family needs ~370 trading days of warm-up.
MIN_BARS = 5_000


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def identity(symbol: str, family: str, params: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps({"s": symbol, "f": family, "p": params}, sort_keys=True,
                                     default=str).encode()).hexdigest()[:20]


def grid(family: str) -> list[dict[str, Any]]:
    spec = PARAM_GRID.get(family) or {}
    keys = sorted(spec)
    return [dict(zip(keys, combo, strict=True))
            for combo in itertools.product(*(spec[k] for k in keys))]


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _load_state() -> dict[str, Any]:
    doc = _read(STATE)
    return doc if isinstance(doc, dict) and isinstance(doc.get("cells"), dict) else {"cells": {}}


def _save_state(state: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True), "utf-8")
    tmp.replace(STATE)


def symbols() -> list[str]:
    """Hypothesis-lane symbols from the broker registry, in registry order."""
    from research import proposer_common as pc
    from research import universe_policy as up
    syms = [s for s in pc.universe_meta() if up.may_hypothesise(s)]
    # The CN analogues first, so the CN-crowd families reach the gauntlet on the first pass.
    first = [s for s in syms if s.upper() in {a.upper() for a in cn.CN_ANALOGUES}]
    return first + [s for s in syms if s not in first]


def _mechanism(family: str, symbol: str) -> str:
    fn = FAMILIES[family]
    doc = (fn.__doc__ or family.replace("_", " ")).strip().splitlines()[0]
    src = ORIGIN[family].split(" ")[0].removeprefix("github.com/")
    return (f"{family} on {symbol}: {doc} Absorbed from {src} "
            f"({fn.__module__}); fails when {CULTURE[family]['failure_mode_hypothesis']}")


def _null_tails(ts: list[float]) -> dict[str, Any]:
    """The screen's t tails against what a null of the same size would print (|t| > 2: ~2.3% a
    side). An excess is the only family-level evidence a screen can give; parity is UNPROVEN."""
    n = len(ts)
    if not n:
        return {"n": 0}
    up_ = sum(t > 2.0 for t in ts)
    dn = sum(t < -2.0 for t in ts)
    return {"n": n, "t_gt_2": up_, "t_lt_minus_2": dn,
            "null_expected_each_side": round(0.0228 * n, 1),
            "mean_t": round(sum(ts) / n, 3)}


def seed(*, budget_s: float = 600.0, dry_run: bool = False,
         only: list[str] | None = None) -> dict[str, Any]:
    """Screen the grid and donate every cell that clears cost. Never raises out of one cell."""
    from research import proposer_common as pc
    from research.multiplicity import deflate_t

    started = time.monotonic()
    today = datetime.now(tz=UTC).date().isoformat()
    try:
        syms = [s for s in symbols() if not only or s in only]
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"universe unreadable: {type(exc).__name__}"}
    meta = pc.universe_meta()
    state = _load_state()
    cells: dict[str, Any] = state["cells"]
    by_family: dict[str, Counter] = {f: Counter() for f in FAMILIES}
    cands: list[dict[str, Any]] = []
    no_bars: list[str] = []
    errors: Counter = Counter()
    stopped = "grid exhausted"
    for sym in syms:
        if time.monotonic() - started > budget_s:
            stopped = f"time budget {budget_s:g}s reached; resumes next pass"
            break
        plan = [(f, {**p, "symbol": sym} if f in SYMBOL_KEYED else p)
                for f in FAMILIES for p in grid(f)]
        stale = any((cells.get(identity(sym, f, p)) or {}).get("day") != today for f, p in plan)
        d = pc.bars(sym) if stale else None
        if stale and (d is None or len(d) < MIN_BARS):
            no_bars.append(sym)
            continue
        cost = pc.cost_frac(sym, meta, d["close"]) if d is not None else None
        for fam, params in plan:
            ident = identity(sym, fam, params)
            prior = cells.get(ident) or {}
            by_family[fam]["grid"] += 1
            if prior.get("day") != today:
                if cost is None:
                    by_family[fam]["held_back_no_cost_model"] += 1
                    continue
                try:
                    r = pc.screen(d, FAMILIES[fam](d, **params), cost) or {}
                except Exception as exc:
                    errors[f"{fam}: {type(exc).__name__}"] += 1
                    continue
                prior = {**prior, "day": today, "family": fam, "symbol": sym, "params": params,
                         "t_gross": r.get("t_gross"), "n_independent": r.get("n_independent"),
                         "clears_cost": bool(r.get("clears_cost"))}
                cells[ident] = prior
                by_family[fam]["measured_this_pass"] += 1
            n_ind = int(prior.get("n_independent") or 0)
            if n_ind < MIN_TRADES:
                by_family[fam]["held_back_under_min_trades"] += 1
            elif not prior.get("clears_cost"):
                by_family[fam]["held_back_under_cost"] += 1
            else:
                by_family[fam]["clears_screen"] += 1
                if not prior.get("donated_at"):
                    cands.append({"ident": ident, **prior})

    donation: dict[str, Any] = {"status": "DRY_RUN" if dry_run else "NOTHING_NEW"}
    if cands and not dry_run:
        rows = []
        for c in cands:
            row = pc.candidate(
                SOURCE, c["symbol"], c["family"], dict(c["params"]),
                _mechanism(c["family"], c["symbol"]), f"{c['symbol']} {c['family']}",
                {"screen_t_gross": c.get("t_gross"), "n_independent": c.get("n_independent"),
                 "origin": ORIGIN[c["family"]]})
            culture = dict(CULTURE[c["family"]])
            row.update(culture)
            row["origin_source_id"] = SOURCE_ID[c["family"]]
            row.setdefault("provenance", {})["source_id"] = SOURCE_ID[c["family"]]
            row["culture_derivation"] = dict.fromkeys(culture, "declared")
            rows.append(row)
        measured = sum(int(v["measured_this_pass"]) for v in by_family.values())
        path = pc.donate(SOURCE, rows, measured or len(rows))
        counts = pc.donation_counts()
        donation = {"status": "DONATED" if path else "REFUSED_AT_DOOR",
                    "path": str(path) if path else None, "n": int(counts.get("donated") or 0),
                    "refused_wrong_lane": counts.get("refused_wrong_lane"),
                    "registry_error": counts.get("registry_error")}
        if path:
            at = _now()
            for c in cands:
                cells[c["ident"]]["donated_at"] = at
                by_family[c["family"]]["donated_this_pass"] += 1
    if not dry_run:
        _save_state(state)

    contract: dict[str, Any] = {}
    n_all = sum(1 for v in cells.values() if v.get("t_gross") is not None)
    for fam in FAMILIES:
        rows_f = [v for v in cells.values() if v.get("family") == fam
                  and isinstance(v.get("t_gross"), (int, float)) and math.isfinite(v["t_gross"])]
        best = max(rows_f, key=lambda v: float(v["t_gross"]), default=None)
        contract[fam] = {
            "screen_tails": _null_tails([float(v["t_gross"]) for v in rows_f]),
            "best": None if best is None else {
                "symbol": best["symbol"], "params": best["params"],
                "t_gross": best["t_gross"],
                "t_deflated_all_cells": round(deflate_t(float(best["t_gross"]), n_all), 3)},
            "donated_total": sum(1 for v in rows_f if v.get("donated_at")),
            "culture": CULTURE[fam],
        }
    return {
        "status": "OK", "dry_run": bool(dry_run), "stopped_because": stopped,
        "elapsed_s": round(time.monotonic() - started, 2), "symbols_seen": len(syms),
        "symbols_without_bars": sorted(set(no_bars)), "min_trades": MIN_TRADES,
        "cells_by_family": {k: dict(v) for k, v in by_family.items()},
        "candidates_this_pass": len(cands), "donation": donation, "errors": dict(errors),
        "contract": contract,
        "contract_rule": ("each family earns its place by the ten gates' verdicts on its donated "
                          "cells; the screen tails say only whether the family prints more |t|>2 "
                          "than a null of its size would"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--symbols", nargs="*")
    a = ap.parse_args(argv)
    rep = {"generated_at": _now(), "source": SOURCE,
           **seed(budget_s=a.budget_s, dry_run=a.dry_run, only=a.symbols)}
    if not a.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".tmp")
        tmp.write_text(json.dumps(rep, indent=1, sort_keys=True, default=str), "utf-8")
        tmp.replace(OUT)
    print(f"elitequant_breadth: {rep.get('status')} symbols={rep.get('symbols_seen')} "
          f"candidates={rep.get('candidates_this_pass')} "
          f"donation={(rep.get('donation') or {}).get('status')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
