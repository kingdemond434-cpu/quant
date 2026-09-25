"""THE META-CONTROLLER'S PRICES SET EVERY LEG'S SECONDS AND THE ORDER THEY RUN IN (Tier-1 B27).

THE GAP, IN THE LEDGER'S OWN WORDS: *"the controller is advisory: the hourly cycle runs every leg
on its own clock regardless of the bandit's prices."* It was true. `meta_controller` ranked nine
kinds of action by dE[log W] per unit of the binding resource and ended its own report with
`"boundary": "NO AUTHORITY"`; `research_bandit` priced six arms; `compute_economics` wrote a
70/20/10 tier split into `data/compute_policy.json`. Three price systems, and the hourly cycle
read exactly one number from one of them, for two legs (`alpha_evolution`, `deepen`), through
`research_budget.budget_s`. Every other leg ran on a constant in `LEG_BUDGET_SEC`.

WHAT THIS IS. One place that answers two questions for every leg, every hour:

    applied_budget(leg, base) -> (seconds, record)   how long this leg may run
    order(names)              -> names               which legs run first

and writes the whole plan, planned against applied, to `reports/CYCLE_PRICING.json`.

TWO-SIDED, BECAUSE A PRICE THAT ONLY CUTS IS A BRAKE (GROWTH_GOVERNANCE Rule 1 and the
principal's never-reduce-aggressiveness order). Three properties hold by construction and are
pinned by tests:

  1. WINNERS GET MORE. A leg the board prices above the median is multiplied UP, to `CEIL`.
  2. EVERY LEG KEEPS A SCOUT FLOOR. No leg is ever cut below `FLOOR` x its base, and no leg is
     ever cut below `SCOUT_MIN_S` seconds. A leg priced last still runs; it must, because the
     price is an estimate made from the desk's own past and the desk has been wrong about which
     leg was worthless before (L1.25: failure to discover is never evidence there is nothing).
  3. NEVER A GLOBAL REDUCTION. After clipping, the whole plan is rescaled so the TOTAL seconds
     allocated is never less than the total the legs would have had unpriced. The controller
     moves compute BETWEEN legs; it never quietly hands the hour back.

WHERE THE PRICE COMES FROM, in order, and every leg records which one answered:

    meta_controller   reports/META_CONTROLLER.json boards.delta_elog -> the best dE[log W] per
                      day among the actions of the kind this leg executes (`KIND_LEGS`), which
                      is the desk's own estimate of what an hour spent here is worth
    research_bandit   reports/RESEARCH_BANDIT.json shares -> the arms a leg serves against an
                      equal-share baseline (`research_budget.LEG_ARMS`)
    compute_policy    data/compute_policy.json tier_factors -> the exploitation / exploration /
                      frontier split, mapped onto the leg through its strategy layer. READ, never
                      written here: `compute_economics.py` owns that file.
    unpriced          the MEDIAN price, never zero. A leg nothing priced is an unmeasured leg,
                      and UNMEASURED is not a verdict of worthless (L1.28a).

ORDER IS PRICE-DESCENDING WITH A SCOUT ROTATION. A leg whose last compute-ledger run is older
than `SCOUT_STALE_H` sorts FIRST regardless of price -- otherwise a leg priced low once is priced
low forever, because it never runs to generate the evidence that would re-price it. That is the
bandit's own exploration term, expressed in the only currency the cycle has: position in the
queue when the hour runs short.

    python desks/mt5/research/cycle_pricing.py --once --budget-s 60
"""
from __future__ import annotations

import argparse
import contextlib
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

R = DESK / "reports"
META = R / "META_CONTROLLER.json"
BANDIT = R / "RESEARCH_BANDIT.json"
POLICY = DESK / "data" / "compute_policy.json"
LEDGER = DESK / "data" / "compute_ledger.jsonl"
OUT = R / "CYCLE_PRICING.json"

#: THE SCOUT FLOOR AND THE WINNER'S CEILING. `FLOOR` is the fraction of its base budget the
#: lowest-priced leg still gets; `CEIL` the multiple the best-priced leg may reach. Both are
#: bounds on the RATIO, so the plan is a reallocation and not a resize.
FLOOR, CEIL = 0.60, 2.00
#: No leg is cut below this many seconds whatever the ratio says: below about a minute a
#: subprocess leg spends its whole budget starting an interpreter and reading its inputs, so a
#: smaller number is not a smaller budget, it is a guaranteed timeout with nothing written.
SCOUT_MIN_S = 60
#: A leg that has not run in this long sorts to the FRONT of the hour whatever it is priced at.
SCOUT_STALE_H = 6.0
#: The plan is recomputed at most this often; inside the window every caller reads the same one,
#: so all fifty-odd legs of one pass are priced against one board rather than a drifting one.
PLAN_TTL_S = 45 * 60

_PLAN: dict[str, Any] | None = None
_PLAN_AT = 0.0


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _kind_legs() -> dict[str, tuple[str, ...]]:
    """`meta_controller.KIND_LEGS` -- which leg executes each ranked kind of action. Imported
    rather than restated: two copies of this map would drift, and the epoch measurement in
    `meta_controller` reads the same one."""
    try:
        import meta_controller  # type: ignore[import-not-found]
        km = getattr(meta_controller, "KIND_LEGS", None)
        if isinstance(km, dict):
            return {str(k): tuple(str(x) for x in v) for k, v in km.items()}
    except Exception:
        pass
    return {}


def _leg_layer() -> dict[str, str]:
    try:
        from libs.research.layers import LEG_LAYER
        return dict(LEG_LAYER)
    except Exception:
        return {}


#: Which compute TIER a strategy layer's work belongs to, so `compute_policy`'s 70/20/10 split
#: can reach a leg at all. Information and meta work is where the unknown-unknowns live
#: (exploration); the layers that price, time and size a known edge are exploitation.
LAYER_TIER: dict[str, str] = {
    "information": "exploration",
    "meta": "frontier",
    "prediction": "exploitation",
    "timing": "exploitation",
    "sizing": "exploitation",
    "portfolio": "exploitation",
    "execution": "exploitation",
    "exit": "exploitation",
}


def _meta_prices() -> tuple[dict[str, float], str]:
    """{leg: dE[log W] per day} from the controller's own board, and why it is empty."""
    doc = _read(META)
    board = ((doc.get("boards") or {}).get("delta_elog") or {})
    rows = board.get("rows") if isinstance(board.get("rows"), list) else []
    if not rows:
        return {}, (f"META_CONTROLLER.json delta_elog board is "
                    f"{board.get('status') or 'absent'}: {str(board.get('why'))[:90]}")
    best: dict[str, float] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        kind = str(r.get("kind") or "")
        v = r.get("delta_elog_per_day")
        if not kind or not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        best[kind] = max(best.get(kind, float("-inf")), float(v))
    out: dict[str, float] = {}
    for kind, legs in _kind_legs().items():
        if kind not in best:
            continue
        for leg in legs:
            out[leg] = max(out.get(leg, float("-inf")), best[kind])
    return out, "" if out else "the board ranked no kind this cycle's legs execute"


def _bandit_prices() -> dict[str, float]:
    """{leg: share of its arms / equal-share baseline} for the legs `research_budget` maps."""
    shares = _read(BANDIT).get("shares")
    if not isinstance(shares, dict) or not shares:
        return {}
    try:
        from research_budget import LEG_ARMS  # type: ignore[import-not-found]
    except Exception:
        return {}
    out: dict[str, float] = {}
    for leg, arms in LEG_ARMS.items():
        vals = [float(shares[a]) for a in arms
                if isinstance(shares.get(a), (int, float)) and not isinstance(shares[a], bool)]
        if not vals or len(vals) != len(arms):
            continue
        baseline = len(arms) / max(1, len(shares))
        out[leg] = (sum(vals) / baseline) if baseline > 0 else 1.0
    return out


def _policy_factors() -> tuple[dict[str, float], bool]:
    """{leg: tier factor} from `data/compute_policy.json`, and whether the policy is APPLIED.

    Read-only: `compute_economics.py` is the writer, and a second writer on one file is the
    defect this desk has paid for more than once."""
    doc = _read(POLICY)
    tf = doc.get("tier_factors") if isinstance(doc.get("tier_factors"), dict) else {}
    if not tf:
        return {}, False
    layers = _leg_layer()
    out: dict[str, float] = {}
    for leg, layer in layers.items():
        tier = LAYER_TIER.get(layer)
        v = tf.get(tier) if tier else None
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
            out[leg] = float(v)
    return out, bool(doc.get("applied"))


def _last_run_h() -> dict[str, float]:
    """Hours since each leg's last compute-ledger row. Absent legs are infinitely stale, which
    is what puts a never-run leg at the FRONT of the scout rotation rather than the back."""
    out: dict[str, float] = {}
    now = datetime.now(tz=UTC)
    try:
        lines = LEDGER.read_text(encoding="utf-8", errors="replace").splitlines()[-6000:]
    except OSError:
        return out
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        name, at = str(r.get("run") or ""), str(r.get("at") or "")
        if not name or not at:
            continue
        try:
            t = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except ValueError:
            continue
        h = (now - t).total_seconds() / 3600.0
        out[name] = min(out.get(name, h), h)
    return out


def _rank01(values: dict[str, float]) -> dict[str, float]:
    """Prices mapped to [0, 1] by RANK, not by magnitude.

    dE[log W] per day, a bandit share ratio and a tier factor are three different units on three
    different scales, and one outlier in any of them would otherwise swamp the blend. A rank is
    the one transform under which they are comparable and under which a single enormous number
    cannot take the hour.

    TIES SHARE A RANK, and getting that wrong is not cosmetic. `compute_policy` publishes every
    tier factor at 1.0 until it has measured survivors per hour; with strict ranks those 256
    IDENTICAL prices fanned out across the whole [0,1] range and the plan handed one leg 2.0x and
    another 0.6x on no evidence whatsoever. Averaged ranks make an unmeasured policy read as what
    it is: every leg at the median, every factor 1.0x, nothing moved."""
    if not values:
        return {}
    order = sorted(values, key=lambda k: values[k])
    n = len(order)
    if n == 1:
        return {order[0]: 0.5}
    out: dict[str, float] = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        mid = (i + j) / 2.0 / (n - 1)
        for k in order[i:j + 1]:
            out[k] = mid
        i = j + 1
    return out


def _evig_prices() -> tuple[dict[str, float], str]:
    """The unified EVIG acquisition's per-leg factors (Tier-1 B11), or an empty map and why.

    ONE-SIDED AT THE SOURCE AND HERE. `evig_acquisition` publishes factors >= 1.0; this converts
    them to a price by rank, so a leg the frontier says nothing about contributes nothing rather
    than a zero -- the same rule the other three sources follow."""
    try:
        from evig_acquisition import leg_factors
        return leg_factors()
    except Exception as exc:
        return {}, f"evig_acquisition unavailable ({type(exc).__name__}: {exc})"


def build_plan(bases: dict[str, int] | None = None) -> dict[str, Any]:
    """The hour's plan: a price, a factor and a planned budget for every leg with a base."""
    if bases is None:
        bases = _bases()
    meta, meta_why = _meta_prices()
    bandit = _bandit_prices()
    policy, policy_applied = _policy_factors()
    stale = _last_run_h()

    m01, b01, p01 = _rank01(meta), _rank01(bandit), _rank01(policy)
    # THE BLEND, AND THE WEIGHTS ARE NOT ARBITRARY. The meta controller is the only source that
    # speaks in the objective's own units (log-wealth per day), so it leads; the bandit prices
    # the arms a leg feeds, which is one step removed; the tier split is a prior over kinds of
    # work and is the weakest claim of the three. A source that has nothing to say about a leg
    # contributes nothing rather than a zero, and the weights of the sources that DID speak are
    # renormalised -- otherwise "no opinion" would read as "priced lowest".
    # THE FRONTIER JOINS THE PRICE STACK (Tier-1 B11, 2026-09-23). `evig_acquisition` ranks the
    # bandit's ARMS, the docket's CELLS, the research tree's NODES and the frontier map's
    # REGIONS on one percentile scale and hands back a per-leg factor. Until it existed the
    # frontier ranked cells nobody could fund: three rankings in three currencies, none of which
    # reached a budget. Its weight sits below the meta controller's (which speaks in the
    # objective's own units) and beside the bandit's, because a percentile across families is a
    # weaker claim than log-wealth per day and a stronger one than a tier prior.
    evig, evig_why = _evig_prices()
    e01 = _rank01(evig)
    W = {"meta_controller": 0.45, "research_bandit": 0.25, "evig_acquisition": 0.20,
         "compute_policy": 0.10}
    legs: dict[str, dict[str, Any]] = {}
    for leg, base in sorted(bases.items()):
        parts: list[tuple[str, float, float]] = []
        if leg in m01:
            parts.append(("meta_controller", W["meta_controller"], m01[leg]))
        if leg in b01:
            parts.append(("research_bandit", W["research_bandit"], b01[leg]))
        if leg in e01:
            parts.append(("evig_acquisition", W["evig_acquisition"], e01[leg]))
        if leg in p01:
            parts.append(("compute_policy", W["compute_policy"], p01[leg]))
        if parts:
            wsum = sum(w for _s, w, _v in parts)
            score = sum(w * v for _s, w, v in parts) / wsum
            sources = [s for s, _w, _v in parts]
        else:
            score, sources = 0.5, []
        legs[leg] = {"base_s": int(base), "score": round(score, 6), "priced_by": sources,
                     "stale_h": round(stale.get(leg, float("inf")), 2)
                     if leg in stale else None}
    # UNPRICED LEGS SIT AT THE MEDIAN OF THE PRICED ONES, never at zero and never at the bottom.
    priced = [v["score"] for v in legs.values() if v["priced_by"]]
    median = statistics.median(priced) if priced else 0.5
    for v in legs.values():
        if not v["priced_by"]:
            v["score"] = round(median, 6)
            v["priced_by"] = ["unpriced:median"]

    # THE FACTOR: a rank score in [0,1] mapped onto [FLOOR, CEIL]. Two-sided by construction --
    # the top of the range is a 2x increase, the bottom a 0.6x scout floor, and the midpoint is
    # exactly 1.0x only when FLOOR and CEIL are symmetric about it, which they are not, so the
    # map is anchored at the median instead: median score -> 1.0x.
    for v in legs.values():
        s = float(v["score"])
        f = (1.0 + (s - median) / max(1e-9, 1.0 - median) * (CEIL - 1.0)) if s >= median else \
            (FLOOR + (s / max(1e-9, median)) * (1.0 - FLOOR))
        v["factor"] = round(max(FLOOR, min(CEIL, f)), 4)
        v["planned_s"] = max(SCOUT_MIN_S, round(v["base_s"] * v["factor"]))

    # NEVER A GLOBAL REDUCTION. Clipping and the scout minimum can only add; the rescale below
    # exists for the case where they do not, so the hour's total is never handed back.
    total_base = sum(v["base_s"] for v in legs.values())
    total_planned = sum(v["planned_s"] for v in legs.values())
    rescale = 1.0
    if total_planned < total_base and total_planned > 0:
        rescale = total_base / total_planned
        for v in legs.values():
            v["planned_s"] = max(SCOUT_MIN_S, round(v["planned_s"] * rescale))
        total_planned = sum(v["planned_s"] for v in legs.values())

    ordered = order(list(legs), legs)
    for i, leg in enumerate(ordered):
        legs[leg]["rank"] = i
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "sources": {"meta_controller": bool(meta), "meta_why": meta_why,
                    "research_bandit": bool(bandit), "compute_policy": bool(policy),
                    "compute_policy_applied": policy_applied,
                    "evig_acquisition": bool(evig), "evig_why": evig_why},
        "weights": W, "floor": FLOOR, "ceiling": CEIL, "scout_min_s": SCOUT_MIN_S,
        "scout_stale_h": SCOUT_STALE_H,
        "median_score": round(median, 6), "rescale": round(rescale, 4),
        "totals": {"base_s": total_base, "planned_s": total_planned,
                   "never_reduced": total_planned >= total_base},
        "legs": legs, "order": ordered, "applied": {},
        "rule": ("every leg's seconds are its base times a factor derived by RANK from the meta "
                 "controller's dE[log W] board, the bandit's arm shares and the compute policy's "
                 "tier split, clipped to [FLOOR, CEIL] and floored at SCOUT_MIN_S; the hour's "
                 "total is never below the unpriced total; order is price-descending with every "
                 "leg staler than SCOUT_STALE_H pulled to the front"),
    }


def declare_spec(leg: str, rec: dict[str, Any]) -> None:
    """Write this leg's JOB SPEC where `job_lock` reads it. I3's producer half. Never raises.

    I3'S GAP, IN THE LEDGER'S OWN WORDS: *"a job's spec carries a memory floor but no CPU count,
    no deadline and no EVSI, so no scheduler can rank two competing jobs."* `job_lock.record_spec`
    has accepted all four fields since the row's first half and NOTHING EVER CALLED IT -- the
    declaration existed and no job ever declared. Every leg of the hourly cycle passes through
    `applied_budget`, so this is the one place where all four are known at once:

        mb          the leg's own measured high-water RSS, corrected upward by what it has
                    actually used (`job_lock.measured_need_mb`) -- never a constant, and never
                    sized off a machine (CLAUDE.md: measure the box the code runs on)
        cpu         1, declared rather than assumed: every cycle leg is a single subprocess
        deadline_s  the seconds this leg was actually granted this hour, which is exactly how
                    long it may hold the box before pre-empting it is worth considering
        evsi        the board's dE[log W] price for this leg -- what the desk expects to LEARN
                    from the hour, which is the field a scheduler must rank on

    It declares; it admits nothing and refuses nothing.
    """
    try:
        from research.job_lock import measured_need_mb, record_spec
    except Exception:                                          # pragma: no cover - import env
        try:
            from job_lock import (  # type: ignore[import-not-found,no-redef]
                measured_need_mb,
                record_spec,
            )
        except Exception:
            return
    try:
        base_mb = int(rec.get("base_mb") or 0) or 256
        need, _why = measured_need_mb(str(leg), base_mb)
        score = rec.get("score")
        record_spec(str(leg), mb=int(need), cpu=1,
                    deadline_s=float(rec.get("applied_s") or rec.get("base_s") or 0.0) or None,
                    evsi=float(score) if isinstance(score, (int, float)) else None)
    except Exception:                                          # a declaration never costs a leg
        return


def order(names: list[str], legs: dict[str, dict[str, Any]] | None = None) -> list[str]:
    """`names` in the order this hour should run them: scouts first, then price-descending.

    I3's CONSUMER. Two legs the board prices identically -- which is common, because most legs
    are priced by the same tier factor -- were separated by their own SPELLING. They are now
    separated by what they DECLARED: `job_lock.admission_order` ranks by EVSI, then by the
    shorter deadline, then by the smaller memory need. That is the "no scheduler can rank two
    competing jobs" half of I3, cashed. It re-orders and refuses nothing: every named leg is
    still returned, and the scout tier (a leg unrun for six hours) still outranks every price.
    """
    table = legs if legs is not None else plan().get("legs", {})
    declared: dict[str, int] = {}
    try:
        from research.job_lock import admission_order
    except Exception:                                          # pragma: no cover - import env
        admission_order = None                                 # type: ignore[assignment]
    if admission_order is not None:
        with contextlib.suppress(Exception):
            declared = {n: i for i, (n, _spec) in enumerate(admission_order(names))}

    def key(n: str) -> tuple[int, float, int, str]:
        row = table.get(n) or {}
        st = row.get("stale_h")
        scout = 0 if (st is None or float(st) >= SCOUT_STALE_H) else 1
        return (scout, -float(row.get("score") or 0.0), declared.get(n, len(names)), n)

    return sorted(names, key=key)


def _bases() -> dict[str, int]:
    """Every leg the cycle knows and its unpriced budget, from `hourly_cycle.LEG_BUDGET_SEC`
    plus its default. Imported so this file never restates the cycle's constants."""
    out: dict[str, int] = {}
    try:
        import hourly_cycle as hc  # type: ignore[import-not-found]
        default = int(getattr(hc, "SEARCH_BUDGET_SEC", 720))
        out.update({str(k): int(v) for k, v in getattr(hc, "LEG_BUDGET_SEC", {}).items()})
        for leg in _leg_layer():
            out.setdefault(leg, default)
    except Exception:
        for leg in _leg_layer():
            out.setdefault(leg, 720)
    return out


def plan(*, force: bool = False) -> dict[str, Any]:
    """This hour's plan, built at most once per `PLAN_TTL_S` so every leg is priced alike."""
    global _PLAN, _PLAN_AT
    if force or _PLAN is None or (time.monotonic() - _PLAN_AT) > PLAN_TTL_S:
        _PLAN = build_plan()
        _PLAN_AT = time.monotonic()
        _write(_PLAN)
    return _PLAN


def applied_budget(leg: str, base: float) -> tuple[int, dict[str, Any]]:
    """(seconds, record) for `leg`. The base on any failure -- the cycle never stalls on a price.

    The record lands in CYCLE_PRICING.json under `applied`, which is what makes the artifact a
    PLANNED-versus-APPLIED measurement rather than a plan nobody checked."""
    base_i = max(1, int(base))
    try:
        p = plan()
        row = dict(p.get("legs", {}).get(leg) or {})
        if not row:
            rec = {"leg": leg, "base_s": base_i, "applied_s": base_i, "factor": 1.0,
                   "applied": False, "why": "leg carries no price this hour; base budget"}
        else:
            factor = float(row.get("factor") or 1.0)
            applied = max(SCOUT_MIN_S, round(base_i * factor))
            rec = {"leg": leg, "base_s": base_i, "planned_s": int(row.get("planned_s") or applied),
                   "applied_s": applied, "factor": round(factor, 4),
                   "score": row.get("score"), "priced_by": row.get("priced_by"),
                   "rank": row.get("rank"), "applied": True,
                   "why": (f"rank score {row.get('score')} vs median {p.get('median_score')} "
                           f"-> x{factor:.2f} (priced by {', '.join(row.get('priced_by') or [])})")}
        rec["at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
        record(rec)
        out_s = rec["applied_s"]
        declare_spec(leg, rec)
        return (int(out_s) if isinstance(out_s, (int, float)) else base_i), rec
    except Exception as exc:                                   # never stall a leg on a price
        return base_i, {"leg": leg, "base_s": base_i, "applied_s": base_i, "factor": 1.0,
                        "applied": False,
                        "why": f"cycle_pricing unavailable: {type(exc).__name__}: {exc}"}


def record(rec: dict[str, Any]) -> None:
    """Merge one leg's APPLIED record into the artifact (per leg, latest wins). Never raises."""
    doc = _read(OUT) or {}
    applied = dict(doc["applied"]) if isinstance(doc.get("applied"), dict) else {}
    applied[str(rec.get("leg"))] = rec
    doc["applied"] = applied
    doc["n_applied"] = sum(1 for v in applied.values()
                           if isinstance(v, dict) and v.get("applied"))
    doc["applied_total_s"] = sum(int(v.get("applied_s") or 0) for v in applied.values()
                                 if isinstance(v, dict) and isinstance(v.get("applied_s"), int))
    _write(doc)


def _write(doc: dict[str, Any]) -> None:
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    except OSError:
        pass


def authority(max_age_h: float = 3.0) -> tuple[bool, str]:
    """Was the controller OBEYED this hour? The claim is made by the organ that spent, never by
    the one that priced -- the same rule `research_budget.authority` follows, for the same
    reason: a price nobody acted on is a report, and the attestation must be able to tell."""
    doc = _read(OUT)
    applied = doc.get("applied") if isinstance(doc.get("applied"), dict) else {}
    if not applied:
        return False, "no leg has asked cycle_pricing for its budget"
    try:
        age_h = (time.time() - OUT.stat().st_mtime) / 3600.0
    except OSError:
        return False, "CYCLE_PRICING.json unreadable"
    if age_h > max_age_h:
        return False, f"CYCLE_PRICING.json is {age_h:.1f}h old"
    moved = [k for k, v in applied.items()
             if isinstance(v, dict) and v.get("applied")
             and abs(float(v.get("factor") or 1.0) - 1.0) > 1e-6]
    if not moved:
        return False, "every leg ran on its base budget (no price moved a leg's seconds)"
    return True, (f"{len(moved)} leg(s) spent by the controller's prices this hour "
                  f"({', '.join(sorted(moved)[:6])})")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="build one plan and exit (the leg shape)")
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.parse_args(argv)
    p = build_plan()
    _PLAN_SET(p)
    _write({**p, **{k: v for k, v in (_read(OUT) or {}).items()
                    if k in ("applied", "n_applied", "applied_total_s")}})
    t = p["totals"]
    print(f"cycle pricing: {len(p['legs'])} leg(s) priced; base {t['base_s']}s -> planned "
          f"{t['planned_s']}s (never_reduced={t['never_reduced']}, rescale x{p['rescale']})")
    src = p["sources"]
    print(f"  sources: meta_controller={src['meta_controller']} bandit={src['research_bandit']} "
          f"compute_policy={src['compute_policy']}"
          + (f" -- {src['meta_why'][:100]}" if src.get("meta_why") else ""))
    top = p["order"][:6]
    for leg in top:
        v = p["legs"][leg]
        print(f"    {leg:<28} x{v['factor']:<5} {v['base_s']:>5}s -> {v['planned_s']:>5}s  "
              f"({', '.join(v['priced_by'])})")
    ok, why = authority()
    print(f"  authoritative: {ok} -- {why[:120]}")
    print(f"written: {OUT}")
    return 0


def _PLAN_SET(p: dict[str, Any]) -> None:
    global _PLAN, _PLAN_AT
    _PLAN, _PLAN_AT = p, time.monotonic()


if __name__ == "__main__":
    raise SystemExit(main())
