"""Per-account limit optimality: the book's risk setting now against the growth-optimal one (idea 737).

    "live risk limits and order permissions are set autonomously to whatever maximises growth,
     within each prop firm's own rules, with every change logged and reversible"
                                                            -- the principal, 2026-11-14 03:29Z

Before any setting is moved by a machine, the evidence for the move has to exist. This leg is that
evidence, one row per account per pass:

  current         the book's total risk the solve deploys now (sum of per-sleeve risk fractions of
                  the initial balance) and its breach probability on the independent sample;
  growth_optimal  the point on the solver's own frontier (the chosen mix scaled 0.25..3) with the
                  highest objective whose breach probability stays inside the survival margin
                  (kelly_survival.BOOK_MARGIN, never above EPS_DEATH);
  delta           objective(optimal) - objective(current), with the objective named: a challenge
                  phase scores J = speed x pass (prop_challenge_allocator), a funded account scores
                  ruin-counted E[log W] per day;
  unconstrained   the solver's no-margin optimum and what the margin costs (`missed_score`).

THE FIRM'S LIMITS ARE NOT KNOBS. FTMO 5% daily / 10% max and E8 2.5% daily / 10% static floor are
published as `firm_limits` and enter only as ruin inside the simulation. The only knobs are our
book's total-risk scale and the survival margin.

NO RE-SIMULATION FOR FTMO: reports/FTMO_ALLOCATOR.json (MT5-FTMO-Allocator, hourly) already carries
total_risk, validation and the frontier. E8 has no solve on any clock, so this leg runs the same
machinery (`prop_challenge_allocator.solve("e8")`, rules RULES["e8"]) at E8_PATHS paths, cached
for E8_MAX_AGE_S, writing reports/E8_ALLOCATOR_SOLVE.json. That call never applies a book.

REPORT ONLY. reports/LIMIT_OPTIMALITY.json, report_only true, consumer null. Nothing reads it to
size. An absent or failed solve reads UNMEASURED, never a zero.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "LIMIT_OPTIMALITY.json"
FTMO_SOLVE = BASE / "reports" / "FTMO_ALLOCATOR.json"
E8_SOLVE = BASE / "reports" / "E8_ALLOCATOR_SOLVE.json"
#: An hourly reader of an hourly artifact: older than this is STALE, still reported.
MAX_AGE_S = 3 * 3600
#: The E8 solve is run here; at a reduced path count and cached, so the leg stays in minutes.
E8_PATHS = 400
E8_MAX_AGE_S = 6 * 3600
INTENDED_CONSUMER = "autonomous limit setter (principal 2026-11-14 03:29Z), not built"


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _age_s(doc: dict[str, Any], now: datetime) -> float | None:
    try:
        t = datetime.fromisoformat(str(doc["generated_at"]))
    except (KeyError, ValueError, TypeError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return (now - t).total_seconds()


def _margin() -> float | None:
    try:
        import kelly_survival as ks
        return float(ks.BOOK_MARGIN)
    except Exception:                                          # pragma: no cover - import guard
        return None


def phase_row(block: dict[str, Any], margin: float | None, phase: str) -> dict[str, Any]:
    """Current vs growth-optimal for one phase block of a prop solve."""
    val = block.get("validation") or {}
    cur_risk = block.get("total_risk")
    objective = "elog_per_day" if phase == "funded" else "J_speed_x_pass"
    row: dict[str, Any] = {
        "phase": phase, "objective": objective, "solve_status": block.get("status"),
        "current": {"total_risk": cur_risk, "score": val.get("score"),
                    "p_breach": val.get("risk")},
        "unconstrained": {k: (block.get("unconstrained") or {}).get(k)
                          for k in ("score", "missed_score")},
    }
    front = block.get("frontier")
    if not front:
        row["growth_optimal"] = None
        row["delta"] = None
        row["verdict"] = ("UNMEASURED: the solve publishes no frontier for this phase"
                          if phase != "funded" else
                          "UNMEASURED: no frontier for a funded block; the solve's own margin "
                          "optimum is the current row")
        return row
    if margin is None:
        row["growth_optimal"] = None
        row["delta"] = None
        row["verdict"] = "UNMEASURED: survival margin unreadable"
        return row
    ok = [p for p in front if p.get("worst_p_fail") is not None
          and p["worst_p_fail"] <= margin and p.get("J_mix") is not None]
    base = next((p for p in front if p.get("scale") == 1.0), None)
    if not ok or base is None or base.get("J_mix") is None:
        row["growth_optimal"] = None
        row["delta"] = None
        row["verdict"] = ("NO_SURVIVING_SCALE: every frontier point breaches the margin"
                          if not ok else "UNMEASURED: no scale-1 point on the frontier")
        return row
    best = max(ok, key=lambda p: (p["J_mix"], -p["worst_p_fail"]))
    d = round(float(best["J_mix"]) - float(base["J_mix"]), 5)
    row["growth_optimal"] = {"scale": best["scale"], "total_risk": best["total_risk"],
                             "score": best["J_mix"], "p_breach": best["worst_p_fail"]}
    row["frontier_scale_1"] = {"total_risk": base["total_risk"], "score": base["J_mix"],
                               "p_breach": base["worst_p_fail"]}
    row["delta"] = d
    s = best["scale"]
    row["verdict"] = ("AT_OPTIMUM" if s == 1.0 else
                      "SIZE_UP_SUPPORTED" if s > 1.0 else "SIZE_DOWN_SUPPORTED")
    # A size-down that only trims breach probability while the objective falls is never a
    # recommendation (Rule 1): best is chosen on the objective, so s < 1 here means J is higher.
    return row


def account_row(name: str, doc: Any, now: datetime, margin: float | None,
                firm: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {"account": name, "firm_limits": firm, "survival_margin": margin}
    if not isinstance(doc, dict):
        row["status"] = "UNMEASURED: no solve artifact"
        return row
    age = _age_s(doc, now)
    row["solve_generated_at"] = doc.get("generated_at")
    row["solve_age_s"] = None if age is None else round(age)
    acct = doc.get("account") or {}
    row["account_state"] = {k: acct.get(k) for k in ("phase", "status", "balance_x_initial",
                                                    "to_daily_limit", "to_max_loss")}
    phase = acct.get("phase")
    block = (doc.get("phases") or {}).get(phase) if phase else None
    if not isinstance(block, dict):
        row["status"] = f"UNMEASURED: solve status {doc.get('status')!r}, no block for the phase"
        return row
    row.update(phase_row(block, margin, str(phase)))
    row["deployable"] = doc.get("deployable")
    row["status"] = ("STALE" if age is None or age > MAX_AGE_S else "OK")
    return row


def _firm(venue: str) -> dict[str, Any]:
    try:
        import prop_challenge_allocator as pca
        r = pca.RULES[venue]
        return {"rules": r.name, "daily_loss": r.daily_loss, "max_loss": r.max_loss,
                "profit_cap": r.profit_cap, "source": r.source}
    except Exception as exc:                                   # pragma: no cover - import guard
        return {"unreadable": type(exc).__name__}


def e8_solve(now: datetime, *, run: bool = True) -> Any:
    """The cached E8 solve; re-run when older than E8_MAX_AGE_S. Never applies a book."""
    doc = _read(E8_SOLVE)
    age = _age_s(doc, now) if isinstance(doc, dict) else None
    if not run or (age is not None and age <= E8_MAX_AGE_S):
        return doc
    try:
        import prop_challenge_allocator as pca
        fresh = pca.solve("e8", n_paths=E8_PATHS, gap_requests=False)
        fresh["paths"] = E8_PATHS
        fresh["report_only"] = True
        fresh["note"] = "run by limit_optimality for the E8 row; no book is applied from it"
        _write(E8_SOLVE, fresh)
        return fresh
    except Exception as exc:
        return {"generated_at": now.isoformat(timespec="seconds"),
                "status": f"SOLVE_FAILED: {type(exc).__name__}"}


def build(now: datetime | None = None, *, run_e8: bool = True) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    margin = _margin()
    rows = [account_row("ftmo", _read(FTMO_SOLVE), now, margin, _firm("ftmo")),
            account_row("e8", e8_solve(now, run=run_e8), now, margin, _firm("e8"))]
    rows.append({"account": "fusion", "status": "NOT_A_PROP_ACCOUNT",
                 "why": "no firm limit; the growth book's heat is the allocator's survival bar "
                        "(reports/pf_allocation.json kelly_fraction)"})
    measured = [r for r in rows if r.get("status") in ("OK", "STALE")]
    return {"generated_at": now.isoformat(timespec="seconds"),
            "report_only": True, "consumer": None, "intended_consumer": INTENDED_CONSUMER,
            "knobs": "book total-risk scale and the survival margin only; firm limits are fixed",
            "status": "OK" if measured else "UNMEASURED",
            "n_measured": len(measured),
            "accounts": rows,
            "summary": {r["account"]: r.get("verdict") or r.get("status") for r in rows}}


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=float), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="per-account limit optimality (idea 737)")
    ap.add_argument("--no-e8-solve", action="store_true", help="read the cached E8 solve only")
    a = ap.parse_args(argv)
    doc = build(run_e8=not a.no_e8_solve)
    _write(OUT, doc)
    print(f"limit_optimality: {doc['status']} {doc['summary']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
