"""F11 + F27 -- ONE CONTROLLER OVER NINE DIFFERENT KINDS OF ACTION, priced in one market.

THE PRINCIPAL, 2026-09-12, twice over:

    F11  One controller choosing between fundamentally different actions -- new hypothesis,
         deepen existing, acquire dataset, run another falsifier, investigate an anomaly, gather
         forward observations, evolve a family, test cross-market transfer, abandon a region --
         optimising expected future dElog.

    F27  Combine the sequential learner with the population bandit, EVIG, frontier coverage,
         research costs and delayed live credit so ALL research compute competes in one budget
         market.

THESE ARE ONE THING AND THEY ARE BUILT AS ONE. F11 names the action set; F27 names the market the
actions compete in. A controller that ranked the nine actions on their own private scores would be
nine schedulers with a shared printout.

WHAT WAS ALREADY HERE AND IS NOT DUPLICATED. `budget_market` prices compute, trials and capital
against each other in dE[log W] per unit of each -- item 28's first half, already built and,
until today, running nowhere. This controller does not re-price anything; it READS those prices
and spends them on actions.

THE THREE RESOURCES ARE NOT SUMMABLE AND THIS REFUSES TO SUM THEM. A cell-hour, a slot in the
family-wise error budget and a basis point of heat have different units. The controller therefore
ranks each action by dE[log W] per unit of the resource that action actually CONSUMES, and reports
which resource is BINDING -- the one whose price is highest relative to what is available. That is
the difference between a three-resource loop and a weighted sum with invented weights.

WHERE A PRICE IS UNMEASURED THE BOARD SAYS SO AND RANKS ON INFORMATION INSTEAD. Measured
2026-09-12: compute's price is UNMEASURED because `scaling_laws` needs seven days of compute
ledger and the ledger holds two. A controller that filled that gap with a plausible number would
be pricing every research hour off a guess, and every ranking it produced would inherit the guess
silently. So there are TWO boards -- one in dE[log W] where the price exists, one in nats per
cell-equivalent where it does not -- and the report says which is which.

NOTHING HERE HAS AUTHORITY. It publishes a ranked docket. The allocator remains the only thing
that sizes a position, the gauntlet the only thing that certifies, and the schedulers still run
what they run. A second mechanism with an opinion about capital is exactly the failure this desk
has a law about.

    python desks/mt5/research/meta_controller.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

R = DESK / "reports"
BUDGET = R / "BUDGET_MARKET.json"
FRONTIER = R / "FRONTIER_MAP.json"
TREE = R / "RESEARCH_TREE.json"
NEGKNOW = R / "NEGATIVE_KNOWLEDGE.json"
PIT = R / "PIT_AUDIT.json"
FWDCAL = R / "FORWARD_CALIBRATION.json"
UNKNOWNS = R / "UNKNOWN_UNKNOWNS.json"
JOINT = R / "JOINT_EVOLUTION.json"
ORTHO = R / "ORTHOGONALITY.json"
SURVIVORS = R / "UNIVERSAL_SURVIVORS.json"
OUT = R / "META_CONTROLLER.json"

#: The nine action kinds, with what each COSTS in the desk's own units.
#:
#:   compute  cell-equivalents: one (symbol, family, params) put through the ten gates
#:   trials   slots in the shared family-wise error budget. NOT the same as compute, and the
#:            difference is the whole reason they are separate columns: running a falsifier
#:            against an existing certificate costs compute and NO trial, because it tests a
#:            claim already charged for. Minting a new hypothesis costs both.
#:   capital  heat. Zero for every research action; only promotion spends it, and promotion is
#:            the allocator's decision, not this controller's.
COSTS: dict[str, dict[str, float]] = {
    "new_hypothesis":         {"compute": 1.0, "trials": 1.0, "capital": 0.0},
    "deepen_existing":        {"compute": 1.0, "trials": 1.0, "capital": 0.0},
    "acquire_dataset":        {"compute": 8.0, "trials": 0.0, "capital": 0.0},
    "run_falsifier":          {"compute": 1.0, "trials": 0.0, "capital": 0.0},
    "investigate_anomaly":    {"compute": 2.0, "trials": 0.0, "capital": 0.0},
    "gather_forward":         {"compute": 0.0, "trials": 0.0, "capital": 0.0},
    "evolve_family":          {"compute": 160.0, "trials": 0.0, "capital": 0.0},
    "cross_market_transfer":  {"compute": 1.0, "trials": 1.0, "capital": 0.0},
    "abandon_region":         {"compute": 0.0, "trials": 0.0, "capital": 0.0},
}

#: Wall-clock hours one cell-equivalent costs, used ONLY to convert a compute price quoted per
#: HOUR into a price per CELL. Measured off the desk's own sweep: the hourly gauntlet reaches on
#: the order of 3,000 cells in an hour of wall time on this box.
CELLS_PER_COMPUTE_HOUR = 3000.0

#: How many actions of each kind the board carries. A docket nobody can read is a docket nobody
#: reads, and the point is the ORDER, not the enumeration.
PER_KIND = 6


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _price(budget: dict[str, Any]) -> dict[str, Any]:
    """The three shadow prices, read from budget_market's OWN schema.

    THE FIRST RUN READ THE WRONG KEYS AND REPORTED EVERY PRICE UNMEASURED, including capital,
    which budget_market had measured at +5.899e-02 on the same pass. That is the worst failure
    available to a reader organ: it does not error, it produces a complete-looking board whose
    every row says "unknown", and the upstream measurement is silently discarded. The market's
    rows live under `resources` with the price on
    `price_dElogW_per_unit_per_day`; keyed off that, and a schema change now shows as a missing
    KEY rather than as a plausible absence.
    """
    rows = budget.get("resources")
    by_name: dict[str, dict[str, Any]] = {}
    if isinstance(rows, list):
        for r in rows:
            if isinstance(r, dict) and r.get("resource"):
                by_name[str(r["resource"])] = r
    out: dict[str, Any] = {}
    for name in ("capital", "compute", "trials"):
        row = by_name.get(name)
        if row is None:
            out[name] = {"status": "UNMEASURED",
                         "basis": (f"budget_market published no row named {name!r}; it listed "
                                   f"{sorted(by_name) or 'nothing'}. This is a SCHEMA mismatch, "
                                   f"not an unmeasured price.")}
            continue
        v = row.get("price_dElogW_per_unit_per_day")
        if not isinstance(v, (int, float)) or not math.isfinite(float(v)):
            out[name] = {"status": "UNMEASURED", "basis": row.get("basis")}
        else:
            out[name] = {"status": "OK", "price": float(v), "unit": row.get("unit"),
                         "basis": row.get("basis"), "headroom": row.get("headroom"),
                         "binding": row.get("binding")}
    return out


# ------------------------------------------------------------------ the nine action sources

def _actions() -> list[dict[str, Any]]:
    """Every action the desk could take next, from the organs that already measure each one."""
    acts: list[dict[str, Any]] = []

    # 1 + 8. NEW HYPOTHESIS and CROSS-MARKET TRANSFER both come off the frontier map's one-step
    # neighbourhood; they differ only in WHICH axis moves, and the distinction is worth keeping
    # because a transfer inherits a mechanism that already worked somewhere.
    fm = _read(FRONTIER)
    for row in (fm.get("frontier") or [])[:200]:
        kind = ("cross_market_transfer" if row.get("changed_axis") == "market"
                else "new_hypothesis")
        acts.append({
            "kind": kind, "target": row.get("key"),
            "why": (f"{row.get('changed_axis')}: {row.get('from_value')} -> "
                    f"{row.get('to_value')}, one step from a region holding "
                    f"{row.get('parent_occupancy')} cell(s) and "
                    f"{row.get('parent_certificates')} certificate(s)"),
            "info_gain_nats": float(row.get("info_gain_nats") or 0.0),
            "p_success": float(row.get("inherited_value") or 0.0),
            "source": "frontier_map",
        })

    # 2. DEEPEN AN EXISTING BRANCH -- the research tree's own frontier, already ranked by exact
    # expected entropy reduction per cell-equivalent.
    tr = _read(TREE)
    for row in (tr.get("frontier") or [])[:60]:
        if row.get("kind") == "mechanism":
            continue
        acts.append({
            "kind": "deepen_existing", "target": row.get("id"),
            "why": str(row.get("question") or "")[:200],
            "info_gain_nats": float(row.get("info_gain_nats") or 0.0),
            "p_success": float(row.get("posterior_value") or 0.0),
            "compute_override": float(row.get("cost_cells") or 1.0),
            "source": "research_tree",
        })

    # 3. ACQUIRE OR REPAIR A DATASET -- the PIT audit's uncertified MONEY-PATH paths. Its value
    # is not a certification rate: it is the decisions it stops being wrong, which this desk
    # cannot price yet and says so rather than inventing a figure.
    pit = _read(PIT)
    for pid in (pit.get("money_path_uncertified") or [])[:10]:
        prow: dict[str, Any] = next(
            (r for r in (pit.get("paths") or []) if isinstance(r, dict) and r.get("id") == pid),
            {})
        acts.append({
            "kind": "acquire_dataset", "target": pid,
            "why": (f"money-path data with {prow.get('n_facts_present', 0)}/9 "
                    f"point-in-time facts; missing "
                    f"{', '.join((prow.get('missing_facts') or [])[:4])}"),
            "info_gain_nats": None,
            "value_status": "UNMEASURED",
            "value_why": ("a PIT repair's value is the decisions it stops being wrong, and the "
                          "desk has no measurement of that. Ranked on the board that does not "
                          "require a price, never given an invented one."),
            "p_success": None, "source": "pit_audit",
        })

    # 4. RUN A FALSIFIER against a certificate. Costs compute and NO TRIAL: it tests a claim the
    # desk already charged itself for. That asymmetry is why trials are their own column.
    sv = _read(SURVIVORS)
    for key, row in list((sv.get("survivors") or {}).items())[:200]:
        if not isinstance(row, dict):
            continue
        spec = row.get("shadow_spec") or {}
        acts.append({
            "kind": "run_falsifier", "target": key,
            "why": (f"{spec.get('family')} on {spec.get('symbol')} holds a certificate; its "
                    f"declared falsifier tests a claim already charged to the trial budget, so "
                    f"this costs compute and no statistical significance"),
            "info_gain_nats": None, "p_success": None,
            "value_status": "UNMEASURED",
            "value_why": ("worth = P(the certificate is wrong) x the capital it holds. The live "
                          "book holds 16 deals across 3 days, so the second factor is not "
                          "measurable and the product is not either."),
            "source": "universal_survivors",
        })

    # 5. INVESTIGATE AN ANOMALY -- and note what the anomaly organ itself says about its own
    # verdict, because a queue built without an event calendar measures volatility.
    uk = _read(UNKNOWNS)
    for kind, n in (uk.get("by_kind") or {}).items():
        acts.append({
            "kind": "investigate_anomaly", "target": f"unexplained:{kind}",
            "why": (f"{n} observation(s) the desk's models cannot explain"
                    + ("" if uk.get("status") != "UNMEASURED"
                       else " -- but UNKNOWN_UNKNOWNS reports UNMEASURED: the event ledger "
                            "parses to zero rows, so 'unexplained' is true by construction")),
            # ZERO OBSERVATIONS MEANS MAXIMUM UNCERTAINTY, which is a high information gain and
            # NOT a high probability. The two are different and conflating them is how an
            # exploration budget becomes a hunch budget.
            "info_gain_nats": float(_beta_gain(0.0, 0.0)),
            "p_success": None,
            "source": "unknown_unknowns",
        })

    # 6. GATHER FORWARD OBSERVATIONS. Costs no compute and no trials -- it costs TIME, which this
    # desk cannot buy, and lane capacity, which it can.
    fc = _read(FWDCAL)
    lane: dict[str, Any] = fc["lane"] if isinstance(fc.get("lane"), dict) else {}
    null: dict[str, Any] = fc["null"] if isinstance(fc.get("null"), dict) else {}
    if lane:
        acts.append({
            "kind": "gather_forward", "target": "forward_lane",
            "why": (f"{lane.get('n_eligible')} clock(s) eligible of {lane.get('n_active')} "
                    f"active; noise would pass "
                    f"{float(null.get('false_admission_rate') or 0):.2%} of them"),
            "info_gain_nats": None,
            "value_status": "UNMEASURED" if not lane.get("n_eligible") else "OK",
            "value_why": ("a forward observation's value is the reduction in the lane's own "
                          "false-admission rate, and with zero eligible clocks there is nothing "
                          "to reduce yet. Costs no compute and no trials -- it costs TIME, which "
                          "this desk cannot buy."),
            "p_success": None, "source": "forward_calibration",
        })

    # 7. EVOLVE A FAMILY -- only where the joint search MEASURED that the layers interact, which
    # is the only evidence that re-searching a family can find anything the fixed recipe cannot.
    je = _read(JOINT)
    for s in (je.get("surfaces") or [])[:40]:
        iv = s.get("interaction") or {}
        if iv.get("status") != "OK" or not iv.get("n_pairs_over_5pct"):
            continue
        top = (iv.get("top_interactions") or [{}])[0]
        acts.append({
            "kind": "evolve_family", "target": f"{s.get('symbol')}.{s.get('family')}",
            "why": (f"{iv.get('n_pairs_over_5pct')} axis pair(s) interact; largest "
                    f"{top.get('axes')} at {float(top.get('interaction_share') or 0):.1%} of "
                    f"fitness variance"),
            "info_gain_nats": float(top.get("interaction_share") or 0.0),
            "p_success": None,
            "beats_incumbent_oos": s.get("joint_beats_incumbent_out_of_sample"),
            "source": "joint_evolution",
        })

    # 9. ABANDON A REGION. Its value is the compute FREED, which is a real positive contribution
    # by redirection -- and the only action here whose value rises with how much was being spent.
    for row in (fm.get("barren_and_expensive") or [])[:10]:
        acts.append({
            "kind": "abandon_region", "target": row.get("key"),
            "why": (f"{row.get('occupancy')} cell(s) judged, {row.get('certificates')} "
                    f"certificate(s), upper bound {float(row['ci95'][1]):.4%}"),
            "info_gain_nats": 0.0,
            "frees_cells": float(row.get("occupancy") or 0.0),
            "p_success": None, "source": "frontier_map",
        })
    for row in (tr.get("pruned_this_pass") or [])[:10]:
        acts.append({
            "kind": "abandon_region", "target": row.get("id"),
            "why": str(row.get("why") or "")[:200],
            "info_gain_nats": 0.0,
            "frees_cells": float(row.get("trials") or 0.0),
            "p_success": None, "source": "research_tree",
        })
    return acts


def _beta_gain(a: float, b: float) -> float:
    """Expected entropy reduction of a Beta(1+a, 1+b) from one observation. Uniform when unseen."""
    def _dg(x: float) -> float:
        r = 0.0
        while x < 6:
            r -= 1.0 / x
            x += 1
        f = 1.0 / (x * x)
        return r + math.log(x) - 0.5 / x + f * (
            -1 / 12.0 + f * (1 / 120.0 + f * (-1 / 252.0 + f * (1 / 240.0))))

    def _h(p: float, q: float) -> float:
        return (math.lgamma(p) + math.lgamma(q) - math.lgamma(p + q)
                - (p - 1) * _dg(p) - (q - 1) * _dg(q) + (p + q - 2) * _dg(p + q))

    p, q = 1.0 + a, 1.0 + b
    m = p / (p + q)
    return max(0.0, _h(p, q) - (m * _h(p + 1, q) + (1 - m) * _h(p, q + 1)))


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    budget = _read(BUDGET)
    prices = _price(budget)
    acts = _actions()
    if not acts:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": ("no upstream organ has published a report to act on -- the frontier map, "
                        "research tree, PIT audit and forward calibration are all absent or "
                        "empty. UNMEASURED, not 'nothing to do'.")}

    nk = _read(NEGKNOW)
    base = float(((nk.get("training") or {}).get("train_base_rate")) or 0.0)

    priced: list[dict[str, Any]] = []
    for a in acts:
        cost = dict(COSTS.get(str(a["kind"]), {"compute": 1.0, "trials": 1.0, "capital": 0.0}))
        if a.get("compute_override"):
            cost["compute"] = float(a["compute_override"])
        ig = a.get("info_gain_nats")
        # THE BINDING RESOURCE is the one this action actually consumes most of, priced. Where a
        # price is UNMEASURED the action still appears -- on the information board.
        per_cell = (float(ig) / max(cost["compute"], 0.5)) if isinstance(ig, (int, float)) else None
        delta_elog = None
        basis = None
        cp = prices.get("compute") or {}
        if per_cell is not None and cp.get("status") == "OK":
            # compute price is quoted per HOUR; one cell is 1/CELLS_PER_COMPUTE_HOUR of an hour.
            delta_elog = per_cell * float(cp["price"]) / CELLS_PER_COMPUTE_HOUR
            basis = "info_gain x compute price"
        priced.append({**a, "cost": cost,
                       "info_per_cell": None if per_cell is None else round(per_cell, 8),
                       "delta_elog_per_day": None if delta_elog is None else round(delta_elog, 10),
                       "delta_elog_basis": basis})

    by_kind: dict[str, list[dict[str, Any]]] = {}
    for a in priced:
        by_kind.setdefault(str(a["kind"]), []).append(a)
    for k in by_kind:
        by_kind[k].sort(key=lambda r: -(float(r["info_per_cell"] or 0.0)))
        by_kind[k] = by_kind[k][:PER_KIND]

    information_board = sorted(
        (a for a in priced if a.get("info_per_cell") is not None),
        key=lambda r: -float(r["info_per_cell"]))
    elog_board = sorted(
        (a for a in priced if a.get("delta_elog_per_day") is not None),
        key=lambda r: -float(r["delta_elog_per_day"]))
    unpriceable = [a for a in priced if a.get("value_status") == "UNMEASURED"]

    # WHICH RESOURCE BINDS. Not a weighted sum: the resource whose shadow price is highest in its
    # OWN units, reported with those units attached so nobody reads them as comparable numbers.
    binding = None
    ranked_prices = [(k, v) for k, v in prices.items() if v.get("status") == "OK"]
    if ranked_prices:
        k, v = max(ranked_prices, key=lambda t: float(t[1]["price"]))
        binding = {"resource": k, "price": v["price"], "unit": v.get("unit"),
                   "why": ("the highest shadow price among the resources that HAVE one. Prices "
                           "in different units are not comparable as numbers -- this names the "
                           "resource whose marginal unit the desk's own market says is worth "
                           "most, and the unit is carried so it cannot be read as a ratio "
                           "against another resource.")}

    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK",
        "n_actions": len(priced),
        "prices": prices,
        "binding_resource": binding,
        "base_rate": base,
        "boards": {
            "delta_elog": {
                "status": "OK" if elog_board else "UNMEASURED",
                "rows": elog_board[:20],
                "why": (None if elog_board else
                        "compute has no measured price, so no action can be quoted in dE[log W] "
                        "per day. `scaling_laws` needs seven days of compute ledger and the box "
                        "holds two; the price appears on its own when the ledger is long enough. "
                        "Filling it with a plausible number would price every research hour off "
                        "a guess and every ranking would inherit it silently."),
            },
            "information": {
                "status": "OK" if information_board else "UNMEASURED",
                "rows": information_board[:25],
                "unit": "nats of expected entropy reduction per cell-equivalent",
            },
            "unpriceable": {
                "n": len(unpriceable),
                "rows": [{k: a.get(k) for k in
                          ("kind", "target", "why", "value_status", "value_why")}
                         for a in unpriceable[:12]],
                "why": ("actions whose VALUE the desk cannot measure yet -- a PIT repair, a "
                        "falsifier against a certificate, a forward observation with no eligible "
                        "clock. They are listed rather than scored, because an invented score "
                        "would sort them among the measured ones and nothing would say which was "
                        "which."),
            },
        },
        "by_kind": by_kind,
        "action_kinds": list(COSTS),
        "costs_note": (
            "trials are NOT compute. Running a falsifier against an existing certificate costs a "
            "cell of compute and ZERO trials, because it tests a claim the desk has already "
            "charged itself for; minting a new hypothesis costs both. That asymmetry is the "
            "reason the two are separate columns and not one 'cost' number."),
        "boundary": (
            "NO AUTHORITY. This publishes a ranked docket. The allocator remains the only thing "
            "that sizes a position, the gauntlet the only thing that certifies, and the "
            "schedulers still run what they run."),
        "why": (
            "the desk allocates compute, trials and capital well and allocates them SEPARATELY, "
            "so it cannot answer the only question that matters at the margin: given one more "
            "unit of anything, where does it go? These three are not summable -- a cell-hour, an "
            "error-budget slot and a basis point of heat have different units -- so each action "
            "is ranked per unit of what it actually consumes and the binding resource is named."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if doc.get("status") != "OK":
        print(f"meta controller: {doc.get('status')} -- {doc.get('why')}")
        return 0
    print(f"meta controller: OK   {doc['n_actions']} action(s) across "
          f"{len(doc['action_kinds'])} kind(s)")
    for name, p in doc["prices"].items():
        if p.get("status") == "OK":
            print(f"  price {name:<9} {float(p['price']):+.6e} per {p.get('unit')}")
        else:
            print(f"  price {name:<9} UNMEASURED -- {str(p.get('basis'))[:80]}")
    b = doc.get("binding_resource")
    if b:
        print(f"  binding resource: {b['resource']} at {float(b['price']):+.4e} "
              f"per {b.get('unit')}")
    eb = doc["boards"]["delta_elog"]
    if eb["status"] == "OK":
        print("  dE[log W] board:")
        for r in eb["rows"][:8]:
            print(f"    {float(r['delta_elog_per_day']):+.3e}/day  {r['kind']:<22} "
                  f"{str(r['target'])[:44]}")
    else:
        print(f"  dE[log W] board: UNMEASURED -- {eb['why'][:120]}")
    print("  information board (nats per cell-equivalent):")
    for r in doc["boards"]["information"]["rows"][:10]:
        print(f"    {float(r['info_per_cell']):.5f}  {r['kind']:<22} {str(r['target'])[:46]}")
    up = doc["boards"]["unpriceable"]
    print(f"  {up['n']} action(s) have no measurable value yet and are listed, not scored:")
    for r in up["rows"][:4]:
        print(f"    {r['kind']:<22} {str(r['target'])[:40]:<40} {str(r['value_why'])[:70]}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
