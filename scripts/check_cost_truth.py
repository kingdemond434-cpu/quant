#!/usr/bin/env python3
"""COST-TRUTH FENCE (L1.5 / L1.28a / GROWTH GOVERNANCE Rule 1) -- is the desk charging itself
more than its broker charges it?

THE DIRECTION WITH NO ALARM. A cell that is UNDERCHARGED manufactures a survivor and every gate
on this desk exists to catch it. A cell that is OVERCHARGED dies in the gauntlet, is never
mentioned again, and leaves no artifact anywhere that says "a real edge was killed by a cost it
would never have paid". `desks/mt5/research/cost_truth.py` measures the three readings -- what
the model CHARGES, what the broker QUOTES on this account, what the desk has actually PAID --
and this fence is what stops that measurement from becoming a report nobody reads.

WHAT IT FOUND ON THE FIRST RUN (2026-09-23, account 495044, 433 deals, 31 days of M1):
GBPCHF is charged 165.0 points against a book whose own tape quotes a median 0.0 and a p90 of
1.0; CADCHF 98.0 against 0.0/1.0; AUDCHF 110.5 against 0.0/3.0; XAUUSD 14.5 against 5.0 at the
desk's own fill minutes. Commission -- a median 98% of the charged cost on this account -- is
charged at 5.625x (a 5x regime-multiplier misuse in the spine's ratio, and a 1.125x rate).

THE RATCHET IS THE POINT. The defects above live in files this fence's author does not own (the
registry scalar, the spine's ratio, the money-path constant), so failing the tree on day one
would only get the fence disabled -- which is how enforcement dies. Instead the known debt is
DECLARED in `desks/mt5/data/cost_truth_ratchet.json` and may only SHRINK: a NEW overcharged
symbol fails, a RISING commission overcharge fails, and a debt that falls rewrites the
declaration so it can never drift back up.

  OK           (exit 0) -- nothing charged above tolerance outside the declaration.
  UNMEASURED   (exit 0) -- no artifact on this box (no terminal here). A real answer, not a pass
                           by silence: the reason is printed and the ratchet is untouched.
  OVERCHARGED  (exit 2) -- a symbol is charged more than OVERCHARGE_TOL x what the broker quotes
                           or the desk paid, and it is not in the declaration.
  RATCHET-UP   (exit 2) -- the declared debt grew.
  STALE        (exit 2) -- the artifact is older than its own declared cadence allows.

Run: python scripts/check_cost_truth.py [--json] [--ratchet PATH] [--report PATH]
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "desks" / "mt5" / "reports" / "COST_TRUTH.json"
SURFACE = ROOT / "desks" / "mt5" / "reports" / "EXECUTION_COST_SURFACE.json"
RATCHET = ROOT / "desks" / "mt5" / "data" / "cost_truth_ratchet.json"

OK, UNMEASURED, OVERCHARGED, RATCHET_UP, STALE = (
    "OK", "UNMEASURED", "OVERCHARGED", "RATCHET-UP", "STALE")
#: Mirrors `cost_truth.OVERCHARGE_TOL`. The artifact publishes its own tolerance and that one
#: wins when present, so the two can never drift apart silently.
DEFAULT_TOL = 1.5
#: Mirrors `cost_truth.STALE_AFTER_S`; the artifact's own value wins when present.
DEFAULT_STALE_S = 4 * 3600


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _f(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def age_s(stamp: Any) -> float | None:
    try:
        when = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return (datetime.now(tz=UTC) - when).total_seconds()


def overcharged_symbols(rep: dict[str, Any], tol: float) -> list[dict[str, Any]]:
    """Every symbol charged above `tol` times what the venue quotes at the desk's own fills.

    A symbol with no terminal reading is not listed: UNMEASURED is a verdict here too, and a
    fence that counted absence as a defect would fail on every box without a terminal.
    """
    out: list[dict[str, Any]] = []
    for row in rep.get("symbols") or []:
        cmp_ = row.get("compare") or {}
        ratio = _f(cmp_.get("spread_charged_over_quoted"))
        if cmp_.get("verdict") == OVERCHARGED and ratio is None:
            # charged against a venue quoting zero everywhere: an infinite ratio, still a defect
            out.append({"symbol": row.get("symbol"), "ratio": None,
                        "charged_pts": cmp_.get("charged_pts"),
                        "reference_pts": cmp_.get("reference_pts"),
                        "why": cmp_.get("why") or "charged against a zero-quoting book"})
        elif ratio is not None and ratio > tol:
            out.append({"symbol": row.get("symbol"), "ratio": round(ratio, 4),
                        "charged_pts": cmp_.get("charged_pts"),
                        "reference_pts": cmp_.get("reference_pts"),
                        "why": f"charged {cmp_.get('charged_pts')} pts against "
                               f"{cmp_.get('reference_pts')} quoted ({cmp_.get('reference_basis')})"})
    out.sort(key=lambda r: -(r["ratio"] or float("inf")))
    return out


def judge(rep: Any, ratchet: Any, surface: Any) -> dict[str, Any]:
    """The verdict, with every number it rests on."""
    if not isinstance(rep, dict) or not rep.get("symbols"):
        return {"verdict": UNMEASURED, "exit": 0,
                "why": (f"no {REPORT.relative_to(ROOT).as_posix()} on this box: the cost-truth "
                        "organ needs the terminal, so absence here is a real answer and not a "
                        "pass by silence")}
    tol = _f(rep.get("overcharge_tolerance")) or DEFAULT_TOL
    stale_s = _f(rep.get("stale_after_s")) or DEFAULT_STALE_S
    declared = ratchet if isinstance(ratchet, dict) else {}
    declared_syms = {str(s) for s in (declared.get("overcharged_symbols") or [])}
    declared_comm = _f(declared.get("commission_total_overcharge"))

    found = overcharged_symbols(rep, tol)
    found_syms = {str(r["symbol"]) for r in found}
    new = sorted(found_syms - declared_syms)
    gone = sorted(declared_syms - found_syms)
    comm = _f((rep.get("commission") or {}).get("total_overcharge"))

    out: dict[str, Any] = {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "artifact_at": rep.get("at"), "tolerance": tol,
        "n_symbols": rep.get("n_symbols"), "n_overcharged": len(found),
        "overcharged": found[:40], "new_since_declaration": new, "cleared": gone,
        "commission_total_overcharge": comm,
        "commission_declared": declared_comm,
        "terminal_status": rep.get("terminal_status"),
        "surface_cells": (surface or {}).get("n_cells") if isinstance(surface, dict) else None,
    }
    age = age_s(rep.get("at"))
    out["age_s"] = None if age is None else round(age, 1)
    if age is not None and age > stale_s:
        out["verdict"], out["exit"] = STALE, 2
        out["why"] = (f"COST_TRUTH.json is {round(age / 3600, 1)}h old against a declared "
                      f"cadence of {round(stale_s / 3600, 1)}h: the desk is refusing candidates "
                      "on a cost reading older than its own clock")
        return out
    if new:
        out["verdict"], out["exit"] = OVERCHARGED, 2
        out["why"] = (f"{len(new)} symbol(s) charged above {tol}x what the broker quotes and not "
                      f"in the declaration: {', '.join(new[:8])}. Either correct the charge or "
                      "declare it with an owner -- an overcharged symbol kills real edge and "
                      "leaves no other trace")
        return out
    if comm is not None and declared_comm is not None and comm > declared_comm + 1e-9:
        out["verdict"], out["exit"] = RATCHET_UP, 2
        out["why"] = (f"the commission overcharge rose from {declared_comm}x to {comm}x; "
                      "commission is the dominant term of every refusal on this account")
        return out
    out["verdict"], out["exit"] = OK, 0
    out["why"] = (f"{len(found)} overcharged symbol(s), all declared; commission overcharge "
                  f"{comm}x at or under the declared {declared_comm}x")
    return out


def rewrite_ratchet(path: Path, verdict: dict[str, Any], declared: Any) -> bool:
    """Lower the declaration when the debt shrinks. It is never raised here -- a growing debt is
    the failure, and a fence that quietly re-declared it would be a fence that agrees."""
    if verdict.get("verdict") not in (OK,):
        return False
    old = declared if isinstance(declared, dict) else {}
    syms = sorted({str(r["symbol"]) for r in verdict.get("overcharged") or []})
    comm = _f(verdict.get("commission_total_overcharge"))
    old_syms = sorted({str(s) for s in (old.get("overcharged_symbols") or [])})
    old_comm = _f(old.get("commission_total_overcharge"))
    if syms == old_syms and (comm is None or old_comm is None or comm >= old_comm - 1e-9):
        return False
    doc = {"at": verdict["at"], "overcharged_symbols": syms,
           "commission_total_overcharge": comm if comm is not None else old_comm,
           "n_overcharged": len(syms),
           "rule": ("DECLARED DEBT, and it may only shrink. A new overcharged symbol or a "
                    "rising commission overcharge fails scripts/check_cost_truth.py; a debt "
                    "that falls rewrites this file so it can never drift back up."),
           "owners": old.get("owners") or {
               "median_spread_pts": "the registry writer (fetch_universe / expand_universe): "
                                    "the scalar is collapsed from a spliced tape",
               "commission_ratio": "net_edge_spine.commission_term -- divide out the RAW regime",
               "commission_rate": "libs/portfolio/fusion_cost.COMMISSION_PER_LOT_PER_SIDE"}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", "utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report", type=Path, default=REPORT)
    ap.add_argument("--surface", type=Path, default=SURFACE)
    ap.add_argument("--ratchet", type=Path, default=RATCHET)
    args = ap.parse_args(argv)

    rep = _json(args.report)
    declared = _json(args.ratchet)
    verdict = judge(rep, declared, _json(args.surface))
    if rewrite_ratchet(args.ratchet, verdict, declared):
        verdict["ratchet_lowered"] = True

    if args.json:
        print(json.dumps(verdict, indent=1, sort_keys=True))
    else:
        print(f"check_cost_truth: {verdict['verdict']} -- {verdict['why']}")
        for row in (verdict.get("overcharged") or [])[:8]:
            print(f"  {row['symbol']:9s} charged {row['charged_pts']} vs quoted "
                  f"{row['reference_pts']} ({row['ratio']}x)")
    return int(verdict["exit"])


if __name__ == "__main__":
    raise SystemExit(main())
