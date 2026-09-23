"""B11 -- ONE ACQUISITION FUNCTION OVER EVERY RESEARCH RESOURCE, and it sets the hour's seconds.

THE BLUEPRINT ITEM: "one EVIG acquisition function for every research resource". THE GAP, in the
ledger's words: "the bandit prices arms and the frontier ranks cells, separately; neither
schedules compute".

Half of that sentence stopped being true on 2026-09-16: `research_budget` and `cycle_pricing` let
the bandit's arm shares set a leg's seconds and the order the legs run in, and the closed-loop
attestation reads `evig_controller_authoritative` from the organ that OBEYED. The half that is
still true is the FRONTIER: the CEO docket ranks cells, the research tree ranks nodes by expected
information gain, the frontier map ranks regions -- three rankings in three currencies, none of
which reaches a budget. A cell nobody can fund is a preference, not a decision.

THIS IS THE JOIN. Every research resource the desk can spend an hour on is priced here:

    ARM       `RESEARCH_BANDIT.json`.arms -- worth x P(survivor) / cost, the bandit's own score
    CELL      `CEO_DOCKET.json`.proposals -- the docket's rank, now carrying the proposing
              scientist's live marginal E[log W] (B7)
    NODE      `RESEARCH_TREE.json`.frontier -- expected information gain in nats x posterior
              value, per node
    REGION    `FRONTIER_MAP.json` -- occupancy and expected value per unexplored region

RANK, NOT AN INVENTED EXCHANGE RATE. Nats of expected information and log-wealth per day are not
the same unit, and the desk has never measured the conversion between them. Pretending otherwise
-- multiplying nats by a constant chosen to make the arithmetic work -- would put a made-up
number at the centre of every compute decision. So each family is ranked WITHIN itself and the
families are merged on their percentile, exactly as `cycle_pricing` already merges three price
sources. The assumption that remains is stated rather than hidden: that the best cell and the
best arm are worth comparable hours, which is the weakest claim that still lets one budget cover
both.

UPWARD ONLY. The factor this publishes is >= 1.0 by construction. `cycle_pricing` is already
two-sided and protects the hour's total; a second source that could also cut would be a second
brake, and this desk's standing order is that nothing reduces its aggressiveness by fiat. What
this can do is move MORE of the hour to the legs the frontier says are worth it.

    python desks/mt5/research/evig_acquisition.py [--once] [--budget-s N]
        -> desks/mt5/reports/EVIG_ACQUISITION.json
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
R = DESK / "reports"
OUT = R / "EVIG_ACQUISITION.json"
BANDIT = R / "RESEARCH_BANDIT.json"
DOCKET = R / "CEO_DOCKET.json"
TREE = R / "RESEARCH_TREE.json"
MAP = R / "FRONTIER_MAP.json"

#: The legs each resource family's work is actually done by. Arms resolve through the bandit's
#: own ARM_RUNS; these are the families the bandit does not name.
CELL_LEGS = ("external_gauntlet", "backtest", "sweep", "compile")
NODE_LEGS = ("research_tree", "deepen")
REGION_LEGS = ("frontier", "breadth_sweep")
#: The most a leg's seconds may be multiplied by this source. One-sided: the floor is 1.0.
MAX_FACTOR = 1.6
#: Cost units for a docket proposal's declared cost, used only to rank cells against each other.
COST_UNITS = {"low": 1.0, "medium": 3.0, "high": 8.0}


def _read(p: Path) -> dict[str, Any]:
    try:
        doc = json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _rank01(values: dict[str, float]) -> dict[str, float]:
    """Percentile of each value within its own family. One member ranks 1.0 -- it is the best
    thing its family has, which is exactly what the caller asked."""
    if not values:
        return {}
    order = sorted(values, key=lambda k: float(values[k]))
    n = len(order)
    return {k: (1.0 if n == 1 else i / (n - 1)) for i, k in enumerate(order)}


def _arms() -> tuple[dict[str, float], dict[str, Any]]:
    doc = _read(BANDIT)
    arms = doc.get("arms") if isinstance(doc.get("arms"), dict) else {}
    out: dict[str, float] = {}
    for name, row in arms.items():
        if not isinstance(row, dict):
            continue
        try:
            worth, p, cost = (float(row.get("worth") or 0.0),
                              float(row.get("p_survivor") or 0.0),
                              float(row.get("cost") or 0.0))
        except (TypeError, ValueError):
            continue
        if cost <= 0:
            continue
        out[str(name)] = worth * p / cost
    return out, {"n": len(out), "source": "RESEARCH_BANDIT.json arms (worth x p_survivor / cost)",
                 "realised_credit": (doc.get("realised_credit") or {}).get("basis")
                 if isinstance(doc.get("realised_credit"), dict) else None}


def _cells() -> tuple[dict[str, float], dict[str, Any]]:
    doc = _read(DOCKET)
    props = doc.get("proposals") if isinstance(doc.get("proposals"), list) else []
    out: dict[str, float] = {}
    for p in props:
        if not isinstance(p, dict):
            continue
        cost = COST_UNITS.get(str(p.get("cost") or "medium"), 3.0)
        live = p.get("scientist_live_score")
        # A proposal with a live-scored proposer is worth what that proposer's work has earned;
        # one without is worth the docket's own ordering, which is a rank and not a growth rate.
        value = (float(live) if isinstance(live, (int, float)) and float(live) > 0 else
                 1.0 / (1.0 + float(p.get("rank") or 99)))
        out[str(p.get("id") or p.get("title") or len(out))] = value / cost
    return out, {"n": len(out), "at": doc.get("at"),
                 "source": "CEO_DOCKET.json proposals (live scientist score / declared cost)",
                 "authoritative": doc.get("authoritative")}


def _nodes() -> tuple[dict[str, float], dict[str, Any]]:
    doc = _read(TREE)
    rows = doc.get("frontier") if isinstance(doc.get("frontier"), list) else []
    out: dict[str, float] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            gain = float(r.get("info_gain_nats") or 0.0)
            post = float(r.get("posterior_value") or 0.0)
        except (TypeError, ValueError):
            continue
        out[str(r.get("id") or len(out))] = gain * max(0.0, post)
    return out, {"n": len(out), "at": doc.get("at"),
                 "source": "RESEARCH_TREE.json frontier (info gain nats x posterior value)"}


def _regions() -> tuple[dict[str, float], dict[str, Any]]:
    doc = _read(MAP)
    regions = doc.get("regions") if isinstance(doc.get("regions"), (dict, list)) else {}
    rows = regions.values() if isinstance(regions, dict) else regions
    out: dict[str, float] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            ev = float(r.get("expected_value") or r.get("value") or 0.0)
            occ = float(r.get("occupancy") or 0.0)
        except (TypeError, ValueError):
            continue
        # An EMPTY region with value is the point of a frontier map: value x (1 - occupancy).
        out[str(r.get("id") or r.get("key") or len(out))] = ev * max(0.0, 1.0 - occ)
    return out, {"n": len(out), "at": doc.get("at"),
                 "source": "FRONTIER_MAP.json regions (expected value x unoccupied share)"}


def _arm_legs(arm: str) -> tuple[str, ...]:
    try:
        from libs.research.bandit import ARM_RUNS
        return tuple(ARM_RUNS.get(arm, ()))
    except Exception:
        return ()


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    families = {"arm": _arms(), "cell": _cells(), "node": _nodes(), "region": _regions()}
    ranked: list[dict[str, Any]] = []
    leg_score: dict[str, list[float]] = {}
    for fam, (values, meta) in families.items():
        r01 = _rank01(values)
        for key, raw in values.items():
            pct = r01.get(key, 0.0)
            legs = (_arm_legs(key) if fam == "arm" else
                    CELL_LEGS if fam == "cell" else
                    NODE_LEGS if fam == "node" else REGION_LEGS)
            ranked.append({"family": fam, "resource": key, "evig": round(float(raw), 9),
                           "percentile": round(pct, 4), "legs": list(legs),
                           "basis": meta.get("source")})
            for leg in legs:
                leg_score.setdefault(leg, []).append(pct)
    ranked.sort(key=lambda r: (-float(r["percentile"]), r["family"], str(r["resource"])))

    # THE FACTOR: a leg's mean percentile across every resource it serves, mapped onto
    # [1.0, MAX_FACTOR]. One-sided by construction -- see the module docstring.
    factors = {leg: round(1.0 + (sum(v) / len(v)) * (MAX_FACTOR - 1.0), 4)
               for leg, v in leg_score.items() if v}
    measured = {f: m for f, (_v, m) in families.items()}
    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK" if ranked else "UNMEASURED",
        "n_resources": len(ranked), "n_families": sum(1 for _f, (v, _m) in families.items() if v),
        "families": measured,
        "ranked": ranked[:60],
        "leg_factor": factors,
        "max_factor": MAX_FACTOR,
        "unification": (
            "each family is ranked WITHIN itself and merged on percentile. Nats of expected "
            "information and log-wealth per day are different units and this desk has never "
            "measured the conversion; inventing one would put a made-up constant at the centre "
            "of every compute decision. The assumption that remains is stated: that the best "
            "cell and the best arm deserve comparable hours."),
        "one_sided": ("the factor is >= 1.0 always. `cycle_pricing` is already two-sided and "
                      "protects the hour's total; a second source that could also cut would be "
                      "a second brake, and nothing on this desk reduces its own aggressiveness "
                      "by fiat (principal, 2026-09-08)."),
        "consumers": ["desks/mt5/research/cycle_pricing.py::build_plan (fourth price source, "
                      "which sets every leg's seconds and the order they run in)"],
    }


def leg_factors(max_age_h: float = 6.0) -> tuple[dict[str, float], str]:
    """Consumer helper: the per-leg multipliers, or an empty map with the reason."""
    import time as _time
    try:
        age_h = (_time.time() - OUT.stat().st_mtime) / 3600.0
    except OSError:
        return {}, "no EVIG_ACQUISITION.json: the frontier prices nothing this hour"
    if age_h > max_age_h:
        return {}, f"EVIG_ACQUISITION.json is {age_h:.1f}h old"
    doc = _read(OUT)
    f = doc.get("leg_factor") if isinstance(doc.get("leg_factor"), dict) else {}
    if not f:
        return {}, "EVIG_ACQUISITION.json carries no leg factors"
    return ({str(k): float(v) for k, v in f.items()},
            f"{len(f)} leg(s) priced by {doc.get('n_resources')} resource(s) across "
            f"{doc.get('n_families')} families, {age_h:.1f}h old")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.parse_args(argv)
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"evig acquisition: {doc['status']}  {doc['n_resources']} resource(s) across "
          f"{doc['n_families']} family(ies)")
    for r in doc["ranked"][:8]:
        print(f"  {r['family']:<7} {str(r['resource'])[:34]:<34} pct={r['percentile']:<6} "
              f"legs={','.join(r['legs'][:3])}")
    print(f"  leg factors: {doc['leg_factor']}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
