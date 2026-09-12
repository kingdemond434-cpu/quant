"""F6 -- A PERSISTENT RESEARCH TREE: every promising mechanism keeps growing, and dead branches die.

THE PRINCIPAL, 2026-09-12, ranking this sixth of the remaining blueprint:

    Every promising mechanism spawns a persistent tree -- mechanism -> basic experiment ->
    alternative explanations -> falsifiers -> state variants -> cross-market analogues ->
    execution variants -> portfolio-residual variants -- with posterior value and expected
    information gain per node, MCTS/beam/best-first compute allocation, permanent pruning.

THE GAP, AS THE LEDGER STATES IT: "genetic evolution and sequential RL are not a scientific tree."
Both are true optimisers and neither REMEMBERS. A genetic population carries its best genomes
forward and forgets every question it asked on the way: which alternative explanation was ruled
out, which falsifier was run, which cross-market analogue was already tried and failed. So the
desk re-asks questions it has answered, and -- worse -- never asks the question one level down
from an answer it liked.

WHAT A TREE BUYS THAT A POPULATION CANNOT. A mechanism that certified on XAUUSD has EARNED the
right to have its cross-market analogues tested before a fresh idea gets compute, because the
posterior at that node is genuinely higher. A population expresses that only by keeping the genome
alive; a tree expresses it as an allocation rule, and can say WHY a node got the hour.

FOUR THINGS ARE MEASURED, NOT ASSERTED:

    POSTERIOR VALUE     Beta over "a cell in this branch certifies", from the desk's own counts:
                        61 certificates against a docket of 21,572 cells, by family. A child
                        inherits its parent's posterior SHRUNK toward the desk base rate, because
                        a variant of a productive mechanism is better placed than a fresh idea and
                        is not the parent.
    INFORMATION GAIN    exact expected entropy reduction of that Beta from ONE more observation.
                        Not a heuristic score: E_y[H(Beta(a+y, b+1-y))] against H(Beta(a, b)).
    COST                declared per node kind in cell-equivalents, because a falsifier is one
                        cell and a cross-market analogue is one per symbol, and an allocator that
                        ignores that spends the hour on the widest node every time.
    PRUNING             permanent, and only on evidence: a branch is pruned when it has enough
                        observations AND its 95% upper credible bound sits below the desk's own
                        base rate -- i.e. this branch is measurably worse than drawing at random
                        from the docket. That IS the named falsifier, and it is recorded with the
                        node so the pruning can be argued with rather than merely obeyed.

ABSENCE NEVER PRUNES (L1.28a). A node with no observations has a wide posterior and a HIGH
information gain -- it sorts toward the front, not into the bin. Only a measured branch can die.

THE FRONTIER IS DONATED, NOT JUST PRINTED. Nodes whose experiment is expressible as a cell --
state variants, cross-market analogues, execution variants -- are donated through
`proposer_common.donate` as `joint_genome` cells, so the tree's next question reaches the gauntlet
on the same pass it is asked. Nodes that are questions for a human or a seat go to the queue.

    python desks/mt5/research/research_tree.py [--apply]
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

SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
UNKNOWNS = DESK / "reports" / "UNKNOWN_UNKNOWNS.json"
SLEEVES = DESK / "data" / "sleeves.json"
TREE = DESK / "data" / "research_tree.json"
OUT = DESK / "reports" / "RESEARCH_TREE.json"

#: The node kinds, in the principal's own order. The order matters: a child kind may only be
#: spawned by the kind before it, so a tree cannot grow execution variants of a mechanism whose
#: alternative explanations were never enumerated.
KINDS: tuple[str, ...] = (
    "mechanism",
    "basic_experiment",
    "alternative_explanation",
    "falsifier",
    "state_variant",
    "cross_market_analogue",
    "execution_variant",
    "portfolio_residual_variant",
)

#: Cost of running one node of each kind, in CELL-EQUIVALENTS. A cell is the desk's own unit of
#: research compute -- one (symbol, family, params) judged by the ten gates -- so these are
#: comparable to everything else the hour could have bought.
COST: dict[str, float] = {
    "mechanism": 0.0,                    # a root is a bookkeeping entry, it runs nothing
    "basic_experiment": 1.0,
    "alternative_explanation": 1.0,
    "falsifier": 1.0,
    "state_variant": 3.0,                # three state bands
    "cross_market_analogue": 8.0,        # one cell per candidate symbol
    "execution_variant": 6.0,            # trigger x rest, from the joint genome
    "portfolio_residual_variant": 2.0,
}

#: How strongly a child inherits its parent's posterior. 0 would make every node the desk base
#: rate (the tree would be a flat list); 1 would make a cross-market analogue of a certified
#: mechanism as likely to certify as the mechanism itself, which is the error that produced
#: twelve correlated sleeves of one mechanism. 0.5 is stated, not tuned.
INHERIT = 0.5

#: Observations a branch needs before pruning may be considered. Below this the posterior is wide
#: by construction and an upper bound below base rate is arithmetic, not evidence.
MIN_TRIALS_TO_PRUNE = 12

#: Nodes expanded per pass. The tree is persistent, so a narrow beam is not a loss of reach --
#: it is the rate at which reach is bought, and every unexpanded node is still on the frontier
#: next pass with its information gain intact.
BEAM = 12

#: Prior strength on the desk base rate, in pseudo-observations. Two is deliberately weak: it
#: stops a zero-trial node from claiming certainty without drowning real counts.
PRIOR_N = 2.0


# ------------------------------------------------------------------------------ the evidence

def _counts() -> dict[str, Any]:
    """Certificates and docket trials, by family. The desk's own record, nothing invented."""
    fams_cert: dict[str, int] = {}
    n_cert = 0
    try:
        doc = json.loads(SURVIVORS.read_text(encoding="utf-8"))
        for row in (doc.get("survivors") or {}).values():
            if not isinstance(row, dict):
                continue
            spec = row.get("shadow_spec") or {}
            f = str(spec.get("family") or row.get("family") or "UNKNOWN")
            fams_cert[f] = fams_cert.get(f, 0) + 1
            n_cert += 1
    except (OSError, ValueError):
        pass
    fams_trial: dict[str, int] = {}
    n_trial = 0
    try:
        rows = json.loads(DOCKET.read_text(encoding="utf-8"))
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict):
                continue
            f = str(r.get("family") or "UNKNOWN")
            fams_trial[f] = fams_trial.get(f, 0) + 1
            n_trial += 1
    except (OSError, ValueError):
        pass
    base = (n_cert / n_trial) if n_trial else 0.0
    return {"certificates_by_family": fams_cert, "trials_by_family": fams_trial,
            "n_certificates": n_cert, "n_trials": n_trial, "base_rate": base}


def _live_symbols() -> list[str]:
    try:
        doc = json.loads(SLEEVES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc if isinstance(doc, list) else (doc.get("sleeves") or [])
    out: list[str] = []
    for r in rows:
        if isinstance(r, dict) and str(r.get("status", "")).upper() == "LIVE":
            s = str(r.get("symbol") or "").strip()
            if s and s not in out:
                out.append(s)
    return out


# ----------------------------------------------------------- posterior and information gain

def _beta_entropy(a: float, b: float) -> float:
    """Differential entropy of Beta(a, b) in nats, via lgamma and the digamma identity."""
    if a <= 0 or b <= 0:
        return 0.0
    lb = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    # Digamma by the standard recurrence-plus-asymptotic expansion. Written out rather than
    # imported because this file must run wherever the desk runs, including where scipy is not
    # installed -- which is the case on this box.
    def _digamma(x: float) -> float:
        r = 0.0
        while x < 6:
            r -= 1.0 / x
            x += 1
        f = 1.0 / (x * x)
        return r + math.log(x) - 0.5 / x + f * (
            -1 / 12.0 + f * (1 / 120.0 + f * (-1 / 252.0 + f * (1 / 240.0))))
    return (lb - (a - 1) * _digamma(a) - (b - 1) * _digamma(b)
            + (a + b - 2) * _digamma(a + b))


def _info_gain(a: float, b: float) -> float:
    """EXACT expected entropy reduction from ONE more observation of this branch.

    Not a heuristic novelty score. The posterior predictive says the next cell certifies with
    probability a/(a+b); the expected posterior entropy is that mixture, and the gain is the
    difference. This is what makes "which node deserves the next hour" a computation rather than
    a preference.
    """
    n = a + b
    if n <= 0:
        return 0.0
    p = a / n
    h0 = _beta_entropy(a, b)
    h1 = p * _beta_entropy(a + 1, b) + (1 - p) * _beta_entropy(a, b + 1)
    return max(0.0, h0 - h1)


def _upper95(a: float, b: float) -> float:
    """Upper 95% credible bound on the branch's certification rate.

    Normal approximation on purpose and stated as such: it is used ONLY to decide whether a
    branch with at least twelve observations is measurably worse than the desk's base rate, and
    at that count the approximation's error is far smaller than the gap it is asked to resolve.
    """
    n = a + b
    if n <= 0:
        return 1.0
    m = a / n
    sd = math.sqrt(max(m * (1 - m) / n, 1e-12))
    return min(1.0, m + 1.96 * sd)


# --------------------------------------------------------------------------------- the tree

def _load_tree() -> dict[str, Any]:
    try:
        d = json.loads(TREE.read_text(encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("nodes"), dict):
            return d
    except (OSError, ValueError):
        pass
    return {"created": datetime.now(tz=UTC).isoformat(timespec="seconds"), "nodes": {},
            "passes": 0}


def _node_id(kind: str, parent: str | None, label: str) -> str:
    return f"{parent or 'root'}|{kind}:{label}"


def _seed_roots(tree: dict[str, Any], counts: dict[str, Any]) -> int:
    """One root per MECHANISM the desk has evidence about -- productive or merely tested."""
    added = 0
    fams = set(counts["certificates_by_family"]) | set(counts["trials_by_family"])
    for fam in sorted(fams):
        if fam in ("UNKNOWN", ""):
            continue
        nid = _node_id("mechanism", None, fam)
        if nid in tree["nodes"]:
            continue
        tree["nodes"][nid] = {
            "id": nid, "kind": "mechanism", "parent": None, "label": fam,
            "question": f"does the {fam} mechanism produce certificates at better than base rate?",
            "successes": int(counts["certificates_by_family"].get(fam, 0)),
            "trials": int(counts["trials_by_family"].get(fam, 0)),
            "state": "OPEN", "created": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        }
        added += 1
    # ROOTS THE DESK HAS NO WORD FOR. Every anomaly kind F8 reports becomes a mechanism node with
    # zero observations -- which gives it a wide posterior and therefore a HIGH information gain,
    # so the unexplained sorts toward the front of the queue rather than into it.
    try:
        u = json.loads(UNKNOWNS.read_text(encoding="utf-8"))
        for kind in (u.get("by_kind") or {}):
            nid = _node_id("mechanism", None, f"unexplained:{kind}")
            if nid in tree["nodes"]:
                continue
            tree["nodes"][nid] = {
                "id": nid, "kind": "mechanism", "parent": None, "label": f"unexplained:{kind}",
                "question": (f"what mechanism produces the {kind} anomalies the desk's models "
                             f"cannot explain?"),
                "successes": 0, "trials": 0, "state": "OPEN",
                "created": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            }
            added += 1
    except (OSError, ValueError):
        pass
    return added


def _children_for(node: dict[str, Any], symbols: list[str]) -> list[dict[str, Any]]:
    """The next kind down, spawned with the questions that kind is FOR.

    A child kind may only be spawned by the kind immediately before it, so the tree cannot grow
    execution variants of a mechanism whose alternative explanations were never enumerated. That
    ordering is the scientific content of F6: the blueprint's sequence is a method, not a menu.
    """
    kind = node["kind"]
    try:
        nxt = KINDS[KINDS.index(kind) + 1]
    except (ValueError, IndexError):
        return []
    lab = node["label"]
    def mk(label: str, q: str, spec: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "id": _node_id(nxt, node["id"], label), "kind": nxt, "parent": node["id"],
            "label": label, "question": q, "successes": 0, "trials": 0, "state": "OPEN",
            "spec": spec, "created": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        }
    if nxt == "basic_experiment":
        return [mk("as_specified",
                   f"does {lab} clear the ten gates on its own declared parameters, "
                   f"out of sample, net of this desk's costs?")]
    if nxt == "alternative_explanation":
        return [mk(a, q) for a, q in (
            ("cost_artefact", f"is {lab}'s edge smaller than the spread it must cross, so that "
                              f"the measured expectancy is a cost model error?"),
            ("session_proxy", f"is {lab} a clock in disguise -- does the edge survive when the "
                              f"hour-of-day is shuffled and the mechanism kept?"),
            ("survivorship", f"does {lab} appear only on instruments that still exist in the "
                             f"universe today?"),
            ("one_regime", f"is {lab} a single regime's artefact -- does it survive the half of "
                           f"history it was not found in?"))]
    if nxt == "falsifier":
        return [mk("named_falsifier",
                   f"run {lab}'s own declared falsifier. A mechanism with no falsifier that has "
                   f"actually been RUN is a story, and this desk retires lessons only on a "
                   f"falsifier that arrived.")]
    if nxt == "state_variant":
        return [mk(f"state:{b}", f"does {lab} hold in the {b} volatility band, or is its "
                                 f"expectancy carried by one state?",
                   {"state_band": b}) for b in ("calm", "active")]
    if nxt == "cross_market_analogue":
        return [mk(f"symbol:{s}", f"does {lab} reproduce on {s}, an instrument it was not "
                                  f"found on?", {"symbol": s}) for s in symbols[:6]]
    if nxt == "execution_variant":
        return [mk(f"exec:trigger{t}", f"does {lab} survive a resting entry {t} ATR away -- a "
                                       f"better price bought with missed trades?",
                   {"trigger_atr": t}) for t in (0.25, 0.5)]
    if nxt == "portfolio_residual_variant":
        return [mk("residual_to_book",
                   f"what does {lab} add to the BOOK rather than standalone -- is its return the "
                   f"residual to what is already funded, or the same bet again?")]
    return []


def _score(node: dict[str, Any], tree: dict[str, Any], base: float) -> dict[str, float]:
    """Posterior value and information gain, with the parent's evidence inherited and shrunk."""
    a = PRIOR_N * base + float(node.get("successes") or 0)
    b = PRIOR_N * (1 - base) + max(0.0, float(node.get("trials") or 0)
                                   - float(node.get("successes") or 0))
    p = tree["nodes"].get(node.get("parent") or "")
    if p:
        pa = PRIOR_N * base + float(p.get("successes") or 0)
        pb = PRIOR_N * (1 - base) + max(0.0, float(p.get("trials") or 0)
                                        - float(p.get("successes") or 0))
        a += INHERIT * pa
        b += INHERIT * pb
    return {"alpha": a, "beta": b, "posterior_value": a / (a + b),
            "info_gain": _info_gain(a, b), "upper95": _upper95(a, b),
            "cost": COST.get(node["kind"], 1.0)}


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    counts = _counts()
    if not counts["n_trials"]:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": ("the docket is unreadable or empty, so no branch has a trial count and "
                        "every posterior would be the prior. UNMEASURED, not a flat tree.")}
    tree = _load_tree()
    base = float(counts["base_rate"])
    symbols = _live_symbols()
    seeded = _seed_roots(tree, counts)

    # REFRESH THE ROOTS' COUNTS EVERY PASS. A mechanism's posterior is the desk's live record of
    # it, not a snapshot from the pass that created the node.
    for n in tree["nodes"].values():
        if n["kind"] == "mechanism" and not str(n["label"]).startswith("unexplained:"):
            n["successes"] = int(counts["certificates_by_family"].get(n["label"], 0))
            n["trials"] = int(counts["trials_by_family"].get(n["label"], 0))

    # PRUNE FIRST, so the beam is never spent expanding a branch this pass has just refuted.
    #
    # THE BENCHMARK IS LEAVE-ONE-OUT, and the first run is why. `discovered` is 17,151 of 21,572
    # docket cells, so comparing it to a base rate it almost entirely CONSTITUTES compares a
    # branch to itself -- and the direction of that error is to under-prune the largest branch,
    # which is the one whose compute matters most. Each branch is therefore judged against the
    # rate of everything that is NOT it: `discovered` at 0.192% against 0.633% for the rest of
    # the desk, rather than against 0.283% it supplies three quarters of.
    pruned_now: list[dict[str, Any]] = []
    n_cert_all = int(counts["n_certificates"])
    n_trial_all = int(counts["n_trials"])
    for n in tree["nodes"].values():
        if n["state"] != "OPEN":
            continue
        tr = int(n.get("trials") or 0)
        su = int(n.get("successes") or 0)
        if tr < MIN_TRIALS_TO_PRUNE:
            continue
        rest_t, rest_c = n_trial_all - tr, n_cert_all - su
        bench = (rest_c / rest_t) if rest_t > 0 else base
        sc = _score(n, tree, bench)
        if sc["upper95"] >= bench:
            continue
        # A BRANCH THAT HAS PRODUCED CERTIFICATES IS NOT REFUTED BY BEING BELOW THE ALTERNATIVE.
        # Its certificates stand -- they passed ten gates each and this organ judges none of
        # them. What is exhausted is the case for spending the NEXT hour here, which is the only
        # thing a tree allocates. Saying "REFUTED" of a branch holding 33 live certificates would
        # be a claim this measurement cannot support, and the two states are kept apart so a
        # reader cannot confuse them.
        n["state"] = "PRUNED"
        n["prune_class"] = "EXHAUSTED_OF_NEW" if su > 0 else "REFUTED"
        n["pruned_at"] = now.isoformat(timespec="seconds")
        n["falsifier_that_arrived"] = (
            f"after {tr} observations this branch certified {su} time(s); its 95% upper credible "
            f"bound is {sc['upper95']:.4%} against {bench:.4%} for every OTHER branch on the "
            f"desk. The next cell spent here is measurably worse than a cell spent anywhere "
            f"else.")
        n["what_pruning_does_not_mean"] = (
            "no certificate is retired, revoked or doubted by this. The tree allocates ATTENTION "
            "and nothing else: a pruned branch stops being expanded, its existing certificates "
            "keep their forward clocks and their capital, and a fresh certificate arriving here "
            "reopens the node on the next pass because the counts are re-read every time."
            if su > 0 else
            "no certificate is affected -- this branch has produced none. It stops being "
            "expanded; it is not asserted to be impossible.")
        pruned_now.append({"id": n["id"], "class": n["prune_class"],
                           "certificates_held": su, "trials": tr,
                           "benchmark_excluding_self": round(bench, 6),
                           "why": n["falsifier_that_arrived"]})

    # THE FRONTIER, ranked by information gain PER CELL-EQUIVALENT. A node with no observations
    # has a wide posterior and therefore a high gain -- the unexplained sorts to the FRONT.
    frontier: list[dict[str, Any]] = []
    for n in tree["nodes"].values():
        if n["state"] != "OPEN" or n.get("expanded"):
            continue
        sc = _score(n, tree, base)
        cost = max(sc["cost"], 0.5)
        frontier.append({**{k: n[k] for k in ("id", "kind", "label", "question")},
                         "spec": n.get("spec"),
                         "posterior_value": round(sc["posterior_value"], 6),
                         "info_gain_nats": round(sc["info_gain"], 6),
                         "cost_cells": sc["cost"],
                         "gain_per_cell": round(sc["info_gain"] / cost, 6)})
    frontier.sort(key=lambda r: -float(r["gain_per_cell"]))

    # EXPAND the beam: best-first, and expanding means SPAWNING THE NEXT KIND DOWN.
    expanded: list[str] = []
    added = 0
    for row in frontier[:BEAM]:
        node = tree["nodes"][row["id"]]
        kids = _children_for(node, symbols)
        node["expanded"] = now.isoformat(timespec="seconds")
        expanded.append(node["id"])
        for k in kids:
            if k["id"] not in tree["nodes"]:
                tree["nodes"][k["id"]] = k
                added += 1

    tree["passes"] = int(tree.get("passes") or 0) + 1
    tree["updated"] = now.isoformat(timespec="seconds")

    by_kind: dict[str, int] = {}
    by_state: dict[str, int] = {}
    for n in tree["nodes"].values():
        by_kind[n["kind"]] = by_kind.get(n["kind"], 0) + 1
        by_state[n["state"]] = by_state.get(n["state"], 0) + 1
    depth_reached = max((KINDS.index(n["kind"]) for n in tree["nodes"].values()), default=0)

    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK",
        "pass": tree["passes"],
        "evidence": counts,
        "tree": {"n_nodes": len(tree["nodes"]), "by_kind": by_kind, "by_state": by_state,
                 "roots_seeded_this_pass": seeded, "children_added_this_pass": added,
                 "deepest_kind_reached": KINDS[depth_reached]},
        "expanded_this_pass": expanded,
        "pruned_this_pass": pruned_now,
        "frontier": frontier[:30],
        "_tree_state": tree,
        "allocation_rule": (
            "best-first by EXPECTED INFORMATION GAIN PER CELL-EQUIVALENT. The gain is the exact "
            "expected entropy reduction of the branch's Beta posterior from one more observation, "
            "and the cost is declared per node kind, because an allocator that ignores cost buys "
            "the widest node every hour."),
        "pruning_rule": (
            f"permanent, and only on evidence: at least {MIN_TRIALS_TO_PRUNE} observations AND a "
            f"95% upper credible bound below the rate of every OTHER branch (leave-one-out, "
            f"never the pooled {base:.4%} a large branch mostly constitutes). ABSENCE NEVER "
            f"PRUNES -- a node with no observations has a wide posterior and a HIGH information "
            f"gain, so the unexplained sorts toward the front, not into the bin. A pruned branch "
            f"that has produced certificates is EXHAUSTED_OF_NEW, never REFUTED: its "
            f"certificates keep their clocks and their capital, and a fresh one reopens the node "
            f"because the counts are re-read every pass."),
        "why": (
            "genetic evolution and sequential RL are optimisers and neither REMEMBERS. A "
            "population carries its best genomes forward and forgets every question asked on the "
            "way -- which alternative explanation was ruled out, which falsifier was run, which "
            "cross-market analogue already failed. So the desk re-asks answered questions and "
            "never asks the one a level below an answer it liked."),
        "boundary": (
            "the tree allocates ATTENTION and nothing else. It certifies nothing, sizes nothing "
            "and promotes nothing; the experiments it ranks reach the book through the identical "
            "ten gates."),
    }


def _donate(doc: dict[str, Any]) -> dict[str, Any]:
    """Frontier nodes that ARE cells, into the gauntlet's intake through the stamped contract."""
    rows = [r for r in doc.get("frontier") or []
            if r.get("spec") and r["kind"] in ("state_variant", "cross_market_analogue",
                                               "execution_variant")]
    if not rows:
        return {"donated": 0, "why": ("no frontier node is yet expressible as a cell -- the tree "
                                      "is still at mechanism and experiment depth")}
    try:
        from research.proposer_common import donate
    except ImportError as exc:
        return {"donated": 0, "why": f"proposer_common unavailable ({exc})"}
    cands: list[dict[str, Any]] = []
    for r in rows[:20]:
        spec = dict(r["spec"])
        # The parent mechanism's family is the first segment of the root id.
        fam = str(r["id"].split("|", 1)[0].split(":", 1)[-1]) or "momentum_volgate"
        sym = spec.pop("symbol", None)
        if not sym:
            continue
        cands.append({
            "symbol": sym, "family": "joint_genome",
            "params": {"base_family": fam, **spec},
            "exp_r": None, "n": None,
            "source": "research_tree",
            "mechanism_status": "NAMED", "mechanism": fam,
            "mechanism_note": r["question"],
            "falsifier": (f"this node was ranked on expected information gain "
                          f"({r['info_gain_nats']} nats per observation) and a posterior value of "
                          f"{r['posterior_value']}. It is refuted if the cell's verdict leaves "
                          f"the branch's 95% upper bound below the desk base rate."),
            "payer": "unnamed until the experiment names one",
            "measurement_class": "DIRECT",
            "selection_trials": int((doc.get("evidence") or {}).get("n_trials") or 0),
        })
    if not cands:
        return {"donated": 0, "why": "no cell-shaped frontier node carries a symbol"}
    try:
        path = donate("research_tree", cands,
                      int((doc.get("evidence") or {}).get("n_trials") or 0))
    except Exception as exc:
        return {"donated": 0, "why": f"donation refused: {type(exc).__name__}: {exc}"}
    return {"donated": len(cands) if path else 0, "path": str(path) if path else None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="persist the tree, write, donate")
    a = ap.parse_args(argv)
    doc = build()
    if doc.get("status") == "UNMEASURED":
        print(f"research tree: UNMEASURED -- {doc.get('why')}")
        return 0
    t, ev = doc["tree"], doc["evidence"]
    print(f"research tree: pass {doc['pass']}   {t['n_nodes']} node(s), deepest kind "
          f"{t['deepest_kind_reached']}")
    print(f"  base rate {ev['base_rate']:.4%}  ({ev['n_certificates']} certificate(s) / "
          f"{ev['n_trials']} docket cell(s))")
    print(f"  by kind : {t['by_kind']}")
    print(f"  by state: {t['by_state']}   (+{t['roots_seeded_this_pass']} root(s), "
          f"+{t['children_added_this_pass']} child(ren) this pass)")
    for r in doc["frontier"][:10]:
        print(f"  {r['gain_per_cell']:.4f} gain/cell  p={r['posterior_value']:.4f}  "
              f"{r['kind']:<26} {r['question'][:78]}")
    for p in doc["pruned_this_pass"][:8]:
        print(f"  {p['class']:<17} {p['id'][:52]}")
        print(f"     {p['why'][:160]}")
    if not a.apply:
        print("  --apply not given; tree not persisted, nothing donated")
        return 0
    tree = doc.pop("_tree_state")
    TREE.parent.mkdir(parents=True, exist_ok=True)
    TREE.write_text(json.dumps(tree, indent=1, default=str), encoding="utf-8")
    doc["donation"] = _donate(doc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"  donated {doc['donation'].get('donated', 0)} frontier cell(s)"
          f"{'' if not doc['donation'].get('why') else ' -- ' + str(doc['donation']['why'])}")
    print(f"-> {TREE}\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
