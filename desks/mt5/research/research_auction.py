"""THE RESEARCH AUCTION (Tier-5 mandate 109/110/169-9): departments bid for the next epoch's
compute; winners get budget, losers give it up, and nobody reaches zero.

The desk priced research in one market (`budget_market`, `meta_controller`) and let the bandit's
shares and the resource exchange scale a leg's seconds (`research_budget.budget_s`). What it did
not have was a CLEARING: a place where every department's measured claim on the next hour is
put against every other's, with the portfolio's bounties, the funnel's bottleneck and the
replenishment gap as demand, and the result handed to the budget as one factor per department.

Bids are MEASURED, per department, per epoch (the hour):
    productivity   candidates the department enqueued in the window per compute hour it burned
                   (registry research_candidates by generator/department x compute_ledger hours);
                   a department with hours and no yield bids below par, one with yield and no
                   recorded hours bids par (its cost is UNMEASURED, not zero)
    bounty demand  open PORTFOLIO_BOUNTY rows addressed to the department (x0.25 each, capped)
    bottleneck     BOTTLENECK_LAW.compute_shift for the department (>= 1, the binding one only)
    replenishment  ALPHA_REPLENISHMENT.gap > 0 raises discovery and validate

Clearing is TWO-SIDED and budget-neutral in logs: factor_j = bid_j / geometric-mean(bids), then
clipped to research_budget's own [FLOOR, CEIL] = [0.5, 2.0]. A winner's seconds rise next epoch
and a loser's fall, never below the floor -- the exploration floor is the clip, and it is the
consumer's own number, not one invented here. `research_budget.budget_s` multiplies the factor
of a leg's department in (`_auction_factor`) when RESEARCH_AUCTION.json is younger than 3 h.
Proposals are also written in the meta-controller's action shape so the board can show them.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import math
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

R = BASE / "reports"
OUT = R / "RESEARCH_AUCTION.json"
BOUNTY = R / "PORTFOLIO_BOUNTY.json"
BOTTLENECK = R / "BOTTLENECK_LAW.json"
#: The 24/7 maximiser's demand signal (desks/mt5/research/bottleneck_attack.py). Read here rather
#: than in `bids()` so that function stays pure and injectable; absent until that leg has run,
#: which leaves the auction exactly as it was.
ATTACK = R / "BOTTLENECK_ATTACK.json"
REPLENISH = R / "ALPHA_REPLENISHMENT.json"
FLOOR, CEIL = 0.5, 2.0          # research_budget.FLOOR / CEIL, the consumer's clip
WINDOW_DAYS = 7.0
BOUNTY_WEIGHT = 0.25
BOUNTY_CAP = 1.0
REPLENISH_WEIGHT = 0.5
DEFAULT_DEPARTMENTS = ("japan", "regions", "data", "intel", "discovery", "validate", "macro",
                       "execution", "forward", "meta", "mathlab", "rest")


def _lst(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _dct(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def leg_departments() -> tuple[dict[str, str], tuple[str, ...]]:
    """hourly_cycle's own tables, imported lazily; the auction must not fail without them."""
    try:
        hc = importlib.import_module("hourly_cycle")
        return dict(hc.LEG_DEPARTMENT), tuple(hc.DEPARTMENTS)
    except Exception:
        return {}, DEFAULT_DEPARTMENTS


def hours_by_department(legs: dict[str, str], window_days: float = WINDOW_DAYS) -> dict[str, float]:
    try:
        from libs.ops.compute_ledger import cost_by_run
        cost = cost_by_run(window_days=int(window_days))
    except Exception:
        return {}
    out: dict[str, float] = {}
    for run, row in cost.items():
        dept = legs.get(str(run), "rest")
        out[dept] = out.get(dept, 0.0) + float(row.get("hours") or 0.0)
    return out


def yield_by_department(legs: dict[str, str], now: datetime, conn: Any | None = None,
                        window_days: float = WINDOW_DAYS) -> dict[str, int]:
    """Candidates enqueued per department in the window: the `department` column when set,
    else the generator's department, else `rest`."""
    from libs.moat import registry
    c = conn or registry.connect()
    out: dict[str, int] = {}
    cut = (now - timedelta(days=window_days)).isoformat()
    try:
        for r in c.execute("SELECT department, generator, origin, COUNT(*) AS n FROM "
                           "research_candidates WHERE created_at >= ? GROUP BY department, "
                           "generator, origin", (cut,)):
            dept = str(r["department"] or "") or legs.get(str(r["generator"] or ""), "") \
                or ("intel" if str(r["origin"] or "") in ("EXTERNAL", "MOAT") else "discovery")
            out[dept] = out.get(dept, 0) + int(r["n"])
    finally:
        if conn is None:
            c.close()
    return out


def bids(departments: tuple[str, ...], hours: dict[str, float], yields: dict[str, int],
         bounty: dict[str, Any], bottleneck: dict[str, Any],
         replenish: dict[str, Any]) -> dict[str, dict[str, Any]]:
    total_h = sum(hours.values())
    total_y = sum(yields.values())
    open_b = _lst(bounty.get("bounties"))
    shift = _dct(bottleneck.get("compute_shift"))
    gap = replenish.get("gap")
    gap_pressure = (min(1.0, float(gap) / max(1.0, float(replenish.get("n_live") or 1)))
                    if isinstance(gap, (int, float)) and float(gap) > 0 else 0.0)
    out: dict[str, dict[str, Any]] = {}
    for d in departments:
        h, y = float(hours.get(d, 0.0)), int(yields.get(d, 0))
        if h > 0 and y == 0 and total_y > 0:
            # BEFORE the ratio, deliberately: the ratio would read 0.0 here and clear this
            # department to the consumer's FLOOR on one quiet window. Half par is a demotion
            # a single enqueued row reverses; zero is a department the auction cannot re-fund.
            productivity, prod_basis = 0.5, "hours burned, nothing enqueued in the window"
        elif total_h > 0 and total_y > 0 and h > 0:
            productivity = (y / total_y) / (h / total_h)          # yield share per hour share
            prod_basis = "MEASURED"
        elif y > 0 and h <= 0:
            productivity, prod_basis = 1.0, "cost UNMEASURED (no ledger hours); par"
        else:
            productivity, prod_basis = 1.0, "UNMEASURED; par"
        n_b = len([b for b in open_b if isinstance(b, dict) and d in _lst(b.get("targets"))])
        bounty_bonus = min(BOUNTY_CAP, BOUNTY_WEIGHT * n_b)
        bn = float(shift.get(d, 1.0) or 1.0)
        rep = REPLENISH_WEIGHT * gap_pressure if d in ("discovery", "validate") else 0.0
        bid = max(1e-6, productivity) * (1.0 + bounty_bonus) * bn * (1.0 + rep)
        out[d] = {"bid": round(bid, 4), "productivity": round(productivity, 4),
                  "productivity_basis": prod_basis, "hours": round(h, 3), "yield": y,
                  "bounties_addressed": n_b, "bottleneck_shift": bn,
                  "replenishment_pressure": round(rep, 4)}
    return out


def clear(bid_rows: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Two-sided: bid over the geometric mean of bids, clipped to the consumer's [FLOOR, CEIL]."""
    vals = [float(r["bid"]) for r in bid_rows.values() if float(r["bid"]) > 0]
    if not vals:
        return dict.fromkeys(bid_rows, 1.0)
    gmean = math.exp(sum(math.log(v) for v in vals) / len(vals))
    return {d: round(max(FLOOR, min(CEIL, float(r["bid"]) / gmean)), 4)
            for d, r in bid_rows.items()}


def build(now: datetime | None = None, conn: Any | None = None,
          bounty: dict[str, Any] | None = None, bottleneck: dict[str, Any] | None = None,
          replenish: dict[str, Any] | None = None, hours: dict[str, float] | None = None,
          yields: dict[str, int] | None = None,
          departments: tuple[str, ...] | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    legs, depts = leg_departments()
    departments = departments or depts
    unmeasured: list[str] = []
    if hours is None:
        hours = hours_by_department(legs)
        if not hours:
            unmeasured.append("compute ledger empty or unreadable: every cost reads UNMEASURED")
    if yields is None:
        try:
            yields = yield_by_department(legs, now, conn)
        except Exception as exc:
            yields = {}
            unmeasured.append(f"registry unavailable: {type(exc).__name__}: {exc}")
    bounty = bounty if bounty is not None else _read(BOUNTY)
    bottleneck = bottleneck if bottleneck is not None else _read(BOTTLENECK)
    # THE BOTTLENECK ATTACKER'S SHIFT, BLENDED IN (principal 2026-09-23). `bottleneck_law` names
    # the binding FUNNEL STAGE from registry counts; `bottleneck_attack` names the binding
    # OPERATIONAL constraint from rates and queues -- conversion debt, judging throughput,
    # enrolment latency and plumbing defects. Both are demand signals for the same auction, so
    # the MAXIMUM per department is taken and never the minimum: a department two organs both
    # call starved is not funded less because one of them is more cautious about it, and neither
    # organ can cut, because both emit factors at or above 1.0 by construction.
    _attack = _read(ATTACK)
    if _attack.get("compute_shift"):
        _merged = dict(_dct(bottleneck.get("compute_shift")))
        for _d, _f in _dct(_attack.get("compute_shift")).items():
            with contextlib.suppress(TypeError, ValueError):
                _merged[_d] = max(float(_merged.get(_d, 1.0) or 1.0), float(_f))
        bottleneck = {**bottleneck, "compute_shift": _merged,
                      "blended_from": ["BOTTLENECK_LAW.json", "BOTTLENECK_ATTACK.json"]}
    replenish = replenish if replenish is not None else _read(REPLENISH)
    for name, d in (("PORTFOLIO_BOUNTY", bounty), ("BOTTLENECK_LAW", bottleneck),
                    ("ALPHA_REPLENISHMENT", replenish)):
        if not d:
            unmeasured.append(f"{name}.json absent: that demand term is 0")
    rows = bids(departments, hours, yields, bounty, bottleneck, replenish)
    factors = clear(rows)
    ranked = sorted(factors.items(), key=lambda kv: -kv[1])
    winners = [d for d, f in ranked if f > 1.0]
    losers = [d for d, f in ranked if f < 1.0]
    epoch = now.strftime("%Y-%m-%dT%H")
    proposals = [{
        "kind": "research_budget_factor", "target": d,
        "why": (f"bid {rows[d]['bid']} (productivity {rows[d]['productivity']} "
                f"[{rows[d]['productivity_basis']}], bounties {rows[d]['bounties_addressed']}, "
                f"bottleneck x{rows[d]['bottleneck_shift']}, replenishment "
                f"+{rows[d]['replenishment_pressure']}) -> x{f} next epoch"),
        "factor": f, "epoch": epoch, "source": "research_auction",
    } for d, f in ranked]
    doc: dict[str, Any] = {
        "at": now.isoformat(timespec="seconds"), "epoch_id": epoch, "window_days": WINDOW_DAYS,
        "departments": list(departments), "bids": rows, "factors": factors,
        "winners": winners, "losers": losers, "clip": [FLOOR, CEIL],
        "proposals": proposals, "unmeasured": unmeasured,
        "consumer": ("research_budget.budget_s (_auction_factor: a leg's seconds x the factor of "
                     "its department while this file is < 3 h old); meta_controller board shape "
                     "under `proposals`; research_dashboard"),
        "rule": ("two-sided: factor = bid / geometric mean of bids, clipped to research_budget's "
                 "own [0.5, 2.0]; a winner's seconds rise next epoch, a loser's fall, none to "
                 "zero; every bid term is measured or reads par with its basis named"),
    }
    doc["headline"] = (f"epoch {epoch}: winners {winners[:4]} losers {losers[:4]}; "
                       f"{len(unmeasured)} unmeasured input(s)")
    return doc


def publish(doc: dict[str, Any], out: Path = OUT) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        from libs.moat import registry
        for p in doc["proposals"]:
            registry.remember("research_auction", p["why"], kind="proposal",
                              memory_key=f"auction:{p['target']}",
                              metrics={"factor": p["factor"], "epoch": p["epoch"]})
        doc["registry_memories"] = len(doc["proposals"])
    except Exception as exc:
        doc["registry"] = f"not written: {type(exc).__name__}: {exc}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", default=True)
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    doc = build()
    doc["elapsed_s"] = round(time.monotonic() - t0, 3)
    doc["budget_s"] = a.budget_s
    publish(doc, a.out)
    print(f"research auction: {doc['headline']}")
    for d, f in sorted(doc["factors"].items(), key=lambda kv: -kv[1]):
        print(f"  {d:<10} x{f:.2f}  bid {doc['bids'][d]['bid']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
