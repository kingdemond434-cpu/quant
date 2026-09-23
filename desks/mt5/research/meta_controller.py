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

AUTHORITY OVER RESEARCH COMPUTE, AND OVER NOTHING ELSE (Tier-1 B27, 2026-09-22). This board used
to end "NOTHING HERE HAS AUTHORITY", and the ledger's gap for item 27 said the same thing back:
*the controller is advisory; the hourly cycle runs every leg on its own clock regardless.* It
does not any more. `research/cycle_pricing.py` turns the dE[log W] board below into every hourly
leg's SECONDS and the ORDER the legs run in -- two-sided (a well-priced leg is multiplied up to
2x), with a scout floor under every leg and a total that can never fall below the unpriced one,
recorded planned-against-applied in `reports/CYCLE_PRICING.json`.

The allocator remains the only thing that sizes a position and the gauntlet the only thing that
certifies. A second mechanism with an opinion about CAPITAL is exactly the failure this desk has
a law about; an hour of research compute is not capital, and leaving it unallocated was the
failure this item was raised for.

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
#: The anytime-valid science controller: the QD archive's empty high-value cells and the
#: campaign continuation decisions (research_genome consumed here, U19).
SCIENCE = R / "SCIENCE_CONTROLLER.json"
OUT = R / "META_CONTROLLER.json"
#: The meta-evolution layer's curriculum and the missed-trade archaeologist's frozen
#: dataset requests: two more sources of the SAME action kinds, priced in the same market.
EVOLUTION = R / "RESEARCH_EVOLUTION.json"
MISSED = R / "MISSED_TRADES.json"

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

    # 1, AGAIN, FROM THE CURRICULUM (LAWS 5m). The meta-evolution layer mints a research
    # question wherever its archive has never been -- a descriptor cell no variant occupies,
    # joined to a coverage hole. An unlit cell's information gain is the uniform Beta's, the
    # same reading `investigate_anomaly` gives zero observations: maximum uncertainty, no
    # probability claimed.
    ev = _read(EVOLUTION)
    for q in (ev.get("curriculum") or [])[:40]:
        if not isinstance(q, dict):
            continue
        cell: dict[str, Any] = q["cell"] if isinstance(q.get("cell"), dict) else {}
        acts.append({
            "kind": "new_hypothesis",
            "target": "curriculum:" + "|".join(str(cell.get(k) or "?") for k in
                                               ("search_family", "data_family", "region",
                                                "horizon")),
            "why": str(q.get("question") or "")[:200],
            "info_gain_nats": float(_beta_gain(0.0, 0.0)),
            "p_success": None, "source": "research_evolution",
        })

    # 3, AGAIN, FROM THE ARCHAEOLOGIST. A frozen `dataset_request` names the input that was
    # absent at a decision that lost; its value is credited only by evidence after `frozen_at`,
    # which the desk has not observed yet -- UNMEASURED, ranked on the board that needs no price.
    mt = _read(MISSED)
    for h in (mt.get("hypotheses") or [])[:40]:
        if not isinstance(h, dict) or h.get("kind") != "dataset_request":
            continue
        acts.append({
            "kind": "acquire_dataset", "target": h.get("hypothesis_id"),
            "why": str(h.get("statement") or "")[:200],
            "info_gain_nats": None, "value_status": "UNMEASURED",
            "value_why": ("frozen at " + str(h.get("frozen_at")) + "; credit only from "
                          "evidence stamped after that, none observed yet"),
            "p_success": None, "source": "missed_trade_archaeologist",
        })

    # 10. THE SCIENCE CONTROLLER'S VERDICTS (U19; research_genome consumed). Its QD archive names
    # the EMPTY cells one axis from the strongest elites -- a new hypothesis each, valued at the
    # neighbours' mean quality times the empty-cell bonus; its anytime-valid campaign decisions
    # name the families to deepen (STOP_DISCOVERED) and the futile ones whose queued launches
    # are compute freed (STOP_FUTILE). Guarded: an absent report contributes nothing and says so.
    acts.extend(_science_actions(_read(SCIENCE)))
    return acts


def _anytime_p(cont: dict[str, Any], fam: dict[str, Any]) -> float:
    """The anytime-valid p-value of a DISCOVERED family, from whichever key carries it.

    THE DEFECT THIS CLOSES (2026-09-23). `science_controller.continuation_of` publishes
    `anytime_p_discovery` and `anytime_p_futility`; the family row above it publishes
    `anytime_p` from the indicator e-value. This function read `continuation["anytime_p"]`,
    which NEITHER produces -- so every real STOP_DISCOVERED action was ranked at
    `p_success = 1 - 1.0 = 0.0`, i.e. the meta-controller scored an anytime-valid discovery as
    having no chance of success and sorted it below every speculative empty cell. The unit test
    did not catch it because its fixture was written by hand with the key the consumer wanted
    rather than the key the producer emits; `test_science_controller_contract.py` now builds the
    row from `continuation_of` itself, which is the only shape that can go stale silently.

    Order: the continuation's own discovery p-value, then the family's e-value p-value, then the
    legacy flat key. An unreadable one is 1.0, which scores the action at zero rather than
    inventing confidence.
    """
    for src, key in ((cont, "anytime_p_discovery"), (fam, "anytime_p"), (cont, "anytime_p")):
        val = src.get(key)
        if isinstance(val, (int, float)):
            return max(0.0, min(1.0, float(val)))
    return 1.0


def _science_actions(science: dict[str, Any]) -> list[dict[str, Any]]:
    """Actions read off SCIENCE_CONTROLLER.json; empty when the report is absent or malformed."""
    out: list[dict[str, Any]] = []
    if not isinstance(science, dict) or not science:
        return out
    for row in (science.get("empty_high_value_cells") or [])[:PER_KIND * 2]:
        if not isinstance(row, dict) or not row.get("cell"):
            continue
        out.append({
            "kind": "new_hypothesis", "target": f"archive:{row['cell']}",
            "why": (f"an EMPTY quality-diversity cell one axis from {row.get('neighbours', 0)} "
                    f"populated neighbour(s), valued {float(row.get('value') or 0.0):.4f} with "
                    f"the empty-cell bonus"),
            "info_gain_nats": float(_beta_gain(0.0, 0.0)),
            "p_success": float(row.get("value") or 0.0), "source": "science_controller",
        })
    fams = science.get("families")
    top = (fams.get("top") or []) if isinstance(fams, dict) else []
    for fam in top:
        if not isinstance(fam, dict):
            continue
        cont: dict[str, Any] = (fam["continuation"]
                                if isinstance(fam.get("continuation"), dict) else {})
        decision = str(cont.get("decision") or "")
        fid = str(fam.get("family_id") or "")
        if not fid or not decision:
            continue
        passes = float(fam.get("passes_at_gate") or 0.0)
        judged = float(fam.get("judged") or 0.0)
        if decision == "STOP_DISCOVERED":
            out.append({
                "kind": "deepen_existing", "target": f"family:{fid}",
                "why": f"anytime-valid DISCOVERY: {cont.get('why', '')}"[:200],
                "info_gain_nats": float(_beta_gain(passes, max(0.0, judged - passes))),
                "p_success": max(0.0, 1.0 - _anytime_p(cont, fam)),
                "compute_override": 1.0, "source": "science_controller",
            })
        elif decision == "STOP_FUTILE" and int(fam.get("queued") or 0) > 0:
            out.append({
                "kind": "abandon_region", "target": f"family:{fid}",
                "why": f"anytime-valid FUTILE: {cont.get('why', '')}"[:200],
                "info_gain_nats": 0.0,
                "frees_cells": float(fam.get("queued") or 0.0),
                "p_success": None, "source": "science_controller",
            })
    return out


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


#: Which hourly leg executes each kind of action the board ranks. An epoch is complete when
#: every ranked kind's leg has a compute-ledger run newer than the previous board.
KIND_LEGS: dict[str, tuple[str, ...]] = {
    "new_hypothesis": ("breadth_sweep", "compile_candidates", "alpha_evolution"),
    "deepen_existing": ("deepen",),
    "acquire_dataset": ("source_fixer", "exogenous_search", "asia_collector"),
    "run_falsifier": ("falsifier_run", "adversaries"),
    "investigate_anomaly": ("weak_signals", "residual_factors"),
    "gather_forward": ("forward_reconcile", "heal_clocks", "enrol_clocks"),
    "evolve_family": ("alpha_evolution",),
    "cross_market_transfer": ("session_chart_expansion", "futures_lead_lag"),
    "abandon_region": ("queue_compact", "requeue_unrunnable"),
}


def _attach_priors(actions: list[dict[str, Any]]) -> None:
    """Stamp each action with the posterior for the organ that proposed it (and its family).

    `libs.research.research_priors` is the desk's record of what every COMPLETED experiment
    taught: P(source yields value), P(family works), P(operator works). An absent prior store is
    UNMEASURED and leaves every action exactly as it was -- a controller that could not read the
    priors must not silently re-weight anything.
    """
    try:
        from libs.research import research_priors as rp
        state = rp.load()
    except Exception as exc:
        for a in actions:
            a["prior_status"] = f"UNMEASURED: {type(exc).__name__}"
        return
    for a in actions:
        src = str(a.get("source") or "")
        fam = str(a.get("family") or "")
        ps = rp.prior_for("source", src, state=state) if src else None
        pf = rp.prior_for("family", fam, state=state) if fam else None
        means = [p.mean for p in (ps, pf) if p is not None]
        mean = sum(means) / len(means) if means else rp.PRIOR_A / (rp.PRIOR_A + rp.PRIOR_B)
        a["prior_mean"] = round(mean, 6)
        a["prior_status"] = "POSTERIOR" if any(
            p is not None and p.status == "POSTERIOR" for p in (ps, pf)) else "PRIOR"
        ig = a.get("info_per_cell")
        if isinstance(ig, (int, float)):
            # TWO-SIDED by construction: the factor is 2 x mean, so a source measured better than
            # even RAISES the action above its raw information gain and a source measured worse
            # lowers it. A one-sided shrink would be the timidity the growth law forbids.
            a["prior_adjusted_info_per_cell"] = round(float(ig) * 2.0 * mean, 8)


def _epoch_id(at: datetime) -> str:
    """The immutable id of this controller cycle. Falls back to the timestamp alone when the
    control plane is not importable, because a cycle with no id at all is one that any stale
    report can certify."""
    try:
        sys.path.insert(0, str(ROOT))
        from libs.ops.control_plane.reconciler import epoch_id
        return epoch_id(at)
    except Exception:
        return "E" + at.astimezone(UTC).strftime("%Y%m%dT%H%M%S")


def _epoch(kinds: list[str]) -> dict[str, Any]:
    """Did every ranked kind's owning leg run since the previous board? Read from the ledger."""
    from datetime import datetime as _dt
    prev_at = None
    try:
        prev = json.loads(OUT.read_text(encoding="utf-8-sig"))
        prev_at = _dt.fromisoformat(str(prev.get("at")).replace("Z", "+00:00"))
    except Exception:
        prev_at = None
    ledger = DESK / "data" / "compute_ledger.jsonl"
    ran: dict[str, str] = {}
    try:
        for ln in ledger.read_text(encoding="utf-8", errors="replace").splitlines()[-4000:]:
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            name = str(r.get("run") or r.get("leg") or r.get("name") or "")
            at = str(r.get("at") or r.get("time") or r.get("ended") or "")
            if not name or not at:
                continue
            try:
                t = _dt.fromisoformat(at.replace("Z", "+00:00"))
            except ValueError:
                continue
            if prev_at is None or t > prev_at:
                ran[name] = max(ran.get(name, ""), at)
    except OSError:
        return {"complete": None, "why": "compute ledger unreadable", "since": str(prev_at)}
    served: dict[str, str | None] = {}
    for kind in kinds:
        legs = KIND_LEGS.get(kind, ())
        hit = next((f"{leg} @ {ran[leg]}" for leg in legs if leg in ran), None)
        served[kind] = hit
    missing = [k for k, v in served.items() if v is None]
    return {
        "since": prev_at.isoformat(timespec="seconds") if prev_at else None,
        "complete": (not missing) if kinds else None,
        "served": served,
        "missing": missing,
        "why": ("every ranked kind's owning leg ran since the previous board"
                if kinds and not missing else
                f"{len(missing)} kind(s) had no owning-leg run since the previous board: {missing}"
                if kinds else "no ranked kinds"),
    }


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
    # THE PRIORS ARE CONSUMED HERE (RD-Agent closure item 4, principal 2026-09-22). Every
    # completed experiment moved a Beta posterior on the SOURCE that proposed it and, where the
    # action names one, the FAMILY. Reading them is what makes this a controller that learns
    # rather than a board that re-ranks the same organs forever. It ORDERS, it never vetoes: an
    # unseen source draws the uniform prior (mean 0.5) and therefore still competes, and no
    # action is dropped for a low posterior -- nothing here reduces the desk's aggressiveness.
    _attach_priors(priced)
    for a in priced:
        by_kind.setdefault(str(a["kind"]), []).append(a)
    for k in by_kind:
        by_kind[k].sort(key=lambda r: -(float(r.get("prior_adjusted_info_per_cell")
                                              or r["info_per_cell"] or 0.0)))
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
        # THE EPOCH, MEASURED (2026-09-16): an epoch completes when every kind of action this
        # board ranked was executed by the organ that owns it since the previous board was
        # published -- read from the compute ledger, never assumed from the schedule.
        "epoch": _epoch([k for k, v in by_kind.items() if v]),
        "epoch_complete": _epoch([k for k, v in by_kind.items() if v]).get("complete"),
        # THE EPOCH'S IMMUTABLE ID (principal 2026-09-17, LAWS.md 7). An epoch that is only a
        # boolean cannot stop an earlier pass's report from certifying a later one: every report
        # used to certify THIS cycle must carry THIS id, or be created after it began. Derived
        # from the cycle's own timestamp, so two organs certifying one cycle compute the same id
        # and a later pass necessarily computes a different one.
        "epoch_id": _epoch_id(now),
        "epoch_started_at": now.isoformat(timespec="seconds"),
        "costs_note": (
            "trials are NOT compute. Running a falsifier against an existing certificate costs a "
            "cell of compute and ZERO trials, because it tests a claim the desk has already "
            "charged itself for; minting a new hypothesis costs both. That asymmetry is the "
            "reason the two are separate columns and not one 'cost' number."),
        "boundary": (
            "AUTHORITY OVER RESEARCH COMPUTE ONLY (Tier-1 B27, 2026-09-22). This board's prices "
            "now set every hourly leg's seconds and the order the legs run in, through "
            "`research/cycle_pricing.py` -> `hourly_cycle._priced_budget` -> "
            "reports/CYCLE_PRICING.json, two-sided and with a scout floor under every leg. "
            "NOTHING ELSE CHANGED: the allocator remains the only thing that sizes a position, "
            "the gauntlet the only thing that certifies, and no leg is ever removed from the "
            "hour -- a cheaply-priced leg is delayed and shortened to its floor, never starved."),
        "compute_authority": {
            "consumer": "desks/mt5/research/cycle_pricing.py",
            "artifact": "desks/mt5/reports/CYCLE_PRICING.json",
            "what_it_sets": ["hourly_cycle._producer_impl budget", "hourly_cycle._auto_leg budget",
                             "hourly_cycle.run_auto_legs order"],
        },
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
    # THE BOARD IS PUBLISHED WITH ITS OWN LEASE AND ITS EPOCH (LAWS.md 7). The envelope carries
    # the producer run id and the epoch, so a consumer can prove WHICH pass it read rather than
    # inferring it from two timestamps that happen to be close together; the watermark carries
    # the epoch id, which is the controller's progress metric.
    _publish(doc)
    print(f"-> {OUT}")
    return 0


def _publish(doc: dict[str, Any]) -> None:
    try:
        sys.path.insert(0, str(ROOT))
        from libs.ops.control_plane import watermarks as wm
        from libs.ops.control_plane.lease import write_report
        env = write_report(OUT, doc, "leg:meta_controller", inputs=(), ttl="hourly",
                           epoch_id=str(doc.get("epoch_id") or ""), root=ROOT)
        wm.progress("leg:meta_controller", "epoch_id", str(doc.get("epoch_id") or ""),
                    run_id=str(env.get("producer_run_id")), epoch_id=str(doc.get("epoch_id")))
    except Exception as exc:
        print(f"meta controller: lease/watermark UNAVAILABLE ({type(exc).__name__}: {exc}); "
              f"writing the board unleased", flush=True)
        OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
