"""The co-evolution machinery: residuals, islands, self-play, synthetic worlds, queues.

This is the half of the RD-Agent closure that makes ONE experiment change the NEXT. The loop is
DATA -> REPRESENTATION -> FACTOR -> MODEL -> RESIDUAL -> NEW HYPOTHESIS, and every arrow in it is
a function here:

* RESIDUAL -> NEW HYPOTHESIS (item 3). `residual_structure` takes what a model got wrong and asks
  the residual series the same questions the desk asks a price series -- by state, session,
  country, macro, participant, asset and horizon -- and `residual_requests` turns every axis that
  answers into a typed request. A residual that is structured by session is a FACTOR request; one
  structured by an axis the desk has no column for is a DATA request; one structured by an axis
  the desk has a column for but no story is a MECHANISM request.
* FAILURE -> DESCENDANT (item 10). A dead cell is never just dead: `descendants_for` reads the
  failure's KIND and emits the descendant that kind implies -- weak IC asks for a representation
  change, state-dependent failure asks for a conditional model, a cost-dead cell asks for
  lower-turnover children, and a misspecification asks for a model-family challenger.
* R x M (item 7). A representation is never declared dead after one learner. `compatibility_matrix`
  publishes the whole grid, and `dead_representations` names only the rows that failed under
  EVERY learner tried -- the rest are UNMEASURED against the learners not yet run.
* ISLANDS (item 15). Populations with different priors and different information subsets evolve
  apart; `migrate` moves only concepts that are strong AND novel on the destination island, so
  migration cannot homogenise the archipelago into one population with extra bookkeeping.
* SELF-PLAY (item 17). Four roles -- proposer, attacker, independent re-implementer, simplifier.
  A candidate must beat the strongest SIMPLER explanation, not only the null: `self_play` rejects
  a candidate whose margin over the simplest alternative does not exceed the complexity it added.
* ACTIVE DESIGN (item 13). When two hypotheses disagree, `design_discriminating_experiment` picks
  the experiment whose expected information gain about WHICH is true is largest, rather than
  running both and paying two trials for one answer.
* SYNTHETIC WORLDS (item 18). `synthetic_world` plants a known structure; `rediscovery_score`
  measures whether a research method finds it. A desk that cannot rediscover a structure it
  planted itself has no standing to claim it found one it did not plant.
* QUEUES (item 14). Seven independent queues. `idle_defect` reports idle capacity with high-value
  work queued AS A DEFECT, which is the only reason the queues are worth keeping separate.

Pure Python by construction (see `libs.research.model_families` for why): no numpy, no pandas, no
sklearn at module scope, so the closure runs on a box where the heavy stack is absent.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from libs.research import model_families as MF

UNMEASURED = "UNMEASURED"

# ----------------------------------------------------------------- item 14: the seven queues
QUEUE_KINDS: tuple[str, ...] = ("data", "factor", "representation", "model", "mechanism",
                                "falsification", "replication")


@dataclass
class Request:
    """One unit of queued research. `kind` routes it; `payload` is what the worker needs."""

    kind: str
    title: str
    why: str
    payload: dict[str, Any] = field(default_factory=dict)
    priority: float = 1.0
    source: str = "coevolution"
    parent: str = ""

    def __post_init__(self) -> None:
        if self.kind not in QUEUE_KINDS:
            raise ValueError(f"unknown queue kind {self.kind!r}; known: {QUEUE_KINDS}")

    @property
    def request_id(self) -> str:
        blob = json.dumps({"k": self.kind, "t": self.title, "p": self.payload},
                          sort_keys=True, default=str)
        return "req_" + hashlib.sha1(blob.encode()).hexdigest()[:12]

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "request_id": self.request_id}


class QueueSet:
    """Seven independent queues. Independent because a starved model queue must be VISIBLE as a
    starved model queue, not hidden inside one pooled backlog that looks busy."""

    def __init__(self) -> None:
        self.queues: dict[str, list[Request]] = {k: [] for k in QUEUE_KINDS}
        self._seen: set[str] = set()

    def push(self, req: Request) -> bool:
        if req.request_id in self._seen:
            return False
        self._seen.add(req.request_id)
        self.queues[req.kind].append(req)
        return True

    def extend(self, reqs: Sequence[Request]) -> int:
        return sum(1 for r in reqs if self.push(r))

    def depth(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.queues.items()}

    def top(self, kind: str, n: int = 5) -> list[Request]:
        return sorted(self.queues[kind], key=lambda r: -r.priority)[:n]

    def all_requests(self) -> list[Request]:
        return [r for k in QUEUE_KINDS for r in self.queues[k]]

    def idle_defect(self, *, free_slots: int, value_floor: float = 1.0) -> dict[str, Any]:
        """Idle capacity with high-value queued work is a DEFECT and is reported as one."""
        waiting = [r for r in self.all_requests() if r.priority >= value_floor]
        starved = sorted({r.kind for r in waiting})
        defect = free_slots > 0 and bool(waiting)
        return {
            "free_slots": int(free_slots), "queued_at_or_above_floor": len(waiting),
            "value_floor": value_floor, "queues_with_work": starved,
            "depth": self.depth(),
            "verdict": "DEFECT" if defect else ("IDLE_AND_EMPTY" if free_slots > 0 else "BUSY"),
            "why": (f"{free_slots} slot(s) idle while {len(waiting)} request(s) at priority "
                    f">= {value_floor} wait in {starved}" if defect else
                    ("no queued work at or above the value floor" if free_slots > 0 else
                     "every slot in use")),
        }


# ----------------------------------------------------------------- item 3: residual research
#: The axes a residual series is interrogated on. A residual with structure on ANY of them is a
#: new research dataset, not noise.
RESIDUAL_AXES: tuple[str, ...] = ("state", "session", "country", "macro", "participant",
                                  "asset", "horizon")
#: |t| above which a bucket's residual mean is called structure rather than sampling noise.
STRUCTURE_T = 2.0
MIN_BUCKET = 12


def residuals(y: Sequence[float], p: Sequence[float]) -> list[float]:
    """The model's error series: realised minus predicted probability."""
    return [float(y[i]) - float(p[i]) for i in range(min(len(y), len(p)))]


def _t_stat(vals: Sequence[float]) -> float:
    n = len(vals)
    if n < 3:
        return 0.0
    m = sum(vals) / n
    v = sum((x - m) ** 2 for x in vals) / (n - 1)
    se = math.sqrt(v / n)
    if se > 0:
        return m / se
    # A BUCKET WITH NO SPREAD IS NOT A BUCKET WITH NO SIGNAL. Zero variance around a non-zero
    # mean is the STRONGEST structure a residual can show -- the model is wrong by the same
    # amount every time -- and returning 0.0 there (the naive guard against dividing by zero)
    # would file the most structured residual the desk can produce as flat.
    return 0.0 if abs(m) < 1e-12 else math.copysign(99.0, m)


def residual_structure(resid: Sequence[float], context: Mapping[str, Sequence[str]],
                       *, min_bucket: int = MIN_BUCKET, t_floor: float = STRUCTURE_T
                       ) -> dict[str, Any]:
    """Per axis: which buckets of the context hold a residual mean that is not zero.

    `context` maps an axis name to one label per residual row. An axis absent from `context` is
    UNMEASURED on this pass -- it is NOT reported as flat, because nobody looked.
    """
    out: dict[str, Any] = {}
    for axis in RESIDUAL_AXES:
        labels = context.get(axis)
        if not labels:
            out[axis] = {"verdict": UNMEASURED,
                         "why": "no label column for this axis on this pass"}
            continue
        buckets: dict[str, list[float]] = {}
        for i, lab in enumerate(labels[:len(resid)]):
            buckets.setdefault(str(lab), []).append(float(resid[i]))
        rows = {}
        for lab, vals in sorted(buckets.items()):
            if len(vals) < min_bucket:
                continue
            t = _t_stat(vals)
            rows[lab] = {"n": len(vals), "mean": round(sum(vals) / len(vals), 6),
                         "t": round(t, 3), "structured": abs(t) >= t_floor}
        hits = sorted((lab for lab, r in rows.items() if r["structured"]),
                      key=lambda lab: -abs(float(rows[lab]["t"])))
        out[axis] = {"verdict": "STRUCTURED" if hits else ("FLAT" if rows else UNMEASURED),
                     "buckets": rows, "structured_levels": hits,
                     "why": "" if rows else f"no bucket reached n>={min_bucket}"}
    return out


#: Which queue an axis's residual structure is addressed to. An axis the desk already has a
#: column for raises a FACTOR request; an axis it does not raises a DATA request; the two the
#: desk can observe but cannot explain raise a MECHANISM request.
_AXIS_QUEUE = {"state": "factor", "session": "factor", "horizon": "representation",
               "country": "data", "macro": "data", "participant": "data",
               "asset": "mechanism"}


def residual_requests(structure: Mapping[str, Any], *, model: str, symbol: str,
                      features: Sequence[str] = (), parent: str = "") -> list[Request]:
    """Every structured axis becomes a typed request. This is the RESIDUAL -> HYPOTHESIS arrow."""
    reqs: list[Request] = []
    for axis, row in structure.items():
        if not isinstance(row, Mapping) or row.get("verdict") != "STRUCTURED":
            continue
        levels = list(row.get("structured_levels") or [])
        buckets = row.get("buckets") or {}
        worst = max((abs(float(buckets[lv]["t"])) for lv in levels), default=0.0)
        reqs.append(Request(
            kind=_AXIS_QUEUE.get(axis, "factor"),
            title=f"{symbol}: {model} residual is structured by {axis} ({', '.join(levels[:3])})",
            why=(f"After {model} on [{', '.join(features) or 'the current feature set'}], the "
                 f"residual mean differs from zero on {axis} levels {levels[:5]} at |t| up to "
                 f"{worst:.2f}. The model is missing whatever separates those levels; the "
                 f"residual series is therefore a new research dataset on the {axis} axis."),
            payload={"axis": axis, "levels": levels, "model": model, "symbol": symbol,
                     "features": list(features), "max_abs_t": round(worst, 3),
                     "buckets": {lv: buckets[lv] for lv in levels[:5]}},
            priority=min(5.0, 1.0 + worst / 2.0), source="residual_research", parent=parent))
    return reqs


# ----------------------------------------------------------------- item 10: failure -> descendant
#: failure kind -> (queue, descendant kind, what the child must change)
FAILURE_RULES: dict[str, tuple[str, str, str]] = {
    "weak_ic": ("representation", "representation_change",
                "the signal is too weak in THIS representation; re-express the same information "
                "(rank, z-score, difference, spectral state) before abandoning it"),
    "state_dependent": ("model", "conditional_model",
                        "the cell works in some states and not others; the child is a model "
                        "CONDITIONED on the state, not an average over it"),
    "cost_dead": ("factor", "lower_turnover_descendant",
                  "gross edge survives and net does not; the child trades the same idea at a "
                  "longer horizon / wider band / fewer rebalances"),
    "misspecified": ("model", "model_family_challenger",
                     "the residual carries the structure the model class cannot represent; the "
                     "child is a DIFFERENT model family on the same features"),
    "no_data": ("data", "data_request",
                "the cell could not be measured for want of an input; the child is the "
                "acquisition of that input, not another fit"),
    "unreplicated": ("replication", "independent_reimplementation",
                     "one implementation is one opinion; the child is an independent rebuild "
                     "of the same claim by a different route"),
}


def classify_failure(result: Mapping[str, Any]) -> str:
    """The failure's KIND, from the numbers the fit already produced.

    Order matters and is the desk's: an unmeasurable cell is `no_data` before anything else, a
    cell whose gross edge is eaten by cost is `cost_dead` before it is called weak, a cell whose
    edge is real in one state is `state_dependent` before it is called misspecified, and only a
    cell whose RESIDUAL is structured is `misspecified` -- otherwise it is simply weak.
    """
    if result.get("verdict") == UNMEASURED or result.get("n") in (None, 0):
        return "no_data"
    gross = result.get("gross_gain", result.get("gain"))
    net = result.get("net_gain")
    if gross is not None and net is not None and float(gross) > 0 and float(net) <= 0:
        return "cost_dead"
    if bool(result.get("state_dependent")) or (
            result.get("best_state_gain") is not None
            and float(result.get("best_state_gain") or 0) > 0 >= float(net or 0)):
        return "state_dependent"
    if bool(result.get("residual_structured")):
        return "misspecified"
    if result.get("replications") == 0 and float(net or 0) > 0:
        return "unreplicated"
    return "weak_ic"


def descendants_for(result: Mapping[str, Any], *, symbol: str = "", parent: str = ""
                    ) -> list[Request]:
    """Every failure emits its descendants. A dead cell that emits nothing is the real defect."""
    kind = classify_failure(result)
    queue, descendant, instruction = FAILURE_RULES[kind]
    label = str(result.get("model") or result.get("family") or "the fit")
    reqs = [Request(
        kind=queue, title=f"{symbol or 'book'}: {descendant} after {label} failed ({kind})",
        why=instruction,
        payload={"failure_kind": kind, "descendant_kind": descendant, "parent_result":
                 {k: result.get(k) for k in ("family", "model", "n", "gain", "net_gain",
                                             "verdict", "features")},
                 "symbol": symbol},
        priority=2.0 if kind in ("cost_dead", "state_dependent") else 1.5,
        source="failure_descendants", parent=parent)]
    # A misspecification also asks to be FALSIFIED by the challenger, so the challenger cannot
    # quietly become the new champion without the comparison being recorded.
    if kind == "misspecified":
        reqs.append(Request(
            kind="falsification",
            title=f"{symbol or 'book'}: falsify {label} against its model-family challenger",
            why=("The challenger must be scored on the SAME folds as the incumbent and beat it "
                 "net of its own larger tax, or the misspecification verdict does not stand."),
            payload={"incumbent": label, "failure_kind": kind, "symbol": symbol},
            priority=1.8, source="failure_descendants", parent=parent))
    return reqs


# ----------------------------------------------------------------- item 7: R x M compatibility
def compatibility_matrix(cells: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The R_k x M_j grid: net gain per (representation, model) cell, plus the honest verdicts.

    A representation is DEAD only when every model tried on it failed; with fewer than
    `min_learners` learners tried it is UNMEASURED, which is why a representation cannot be
    buried by one unlucky learner.
    """
    grid: dict[str, dict[str, Any]] = {}
    for c in cells:
        rep, mod = str(c.get("representation")), str(c.get("model"))
        row = {"net_gain": c.get("net_gain"), "verdict": c.get("verdict"), "n": c.get("n"),
               "backend": c.get("backend"), "heavy_verdict": c.get("heavy_verdict"),
               "best_on": c.get("symbol"), "pooled": 1}
        prior = grid.setdefault(rep, {}).get(mod)
        if prior is None:
            grid[rep][mod] = row
            continue
        # THE SAME (R, M) CELL SEEN ON SEVERAL INSTRUMENTS KEEPS ITS BEST, not its last. Taking
        # the last silently made the whole grid a report on whichever symbol happened to be swept
        # last -- measured 2026-09-22, when six earning cells sat in the winners list while every
        # representation read DEAD because a later instrument's negative cell had overwritten the
        # positive one at the same key.
        row["pooled"] = int(prior.get("pooled") or 1) + 1
        keep = prior if (prior.get("net_gain") is not None
                         and (row["net_gain"] is None
                              or float(prior["net_gain"]) >= float(row["net_gain"]))) else row
        grid[rep][mod] = {**keep, "pooled": row["pooled"]}
    reps = sorted(grid)
    models = sorted({m for row in grid.values() for m in row})
    return {"representations": reps, "models": models, "grid": grid,
            "n_cells": sum(len(r) for r in grid.values()),
            "rule": ("a representation is judged against the WHOLE model row, never one "
                     "learner; an untried (R, M) cell is UNMEASURED, not a zero")}


def dead_representations(matrix: Mapping[str, Any], *, min_learners: int = 2) -> dict[str, Any]:
    out: dict[str, Any] = {}
    grid = matrix.get("grid") or {}
    for rep, row in grid.items():
        tried = [v for v in row.values() if v.get("net_gain") is not None]
        if len(tried) < min_learners:
            out[rep] = {"verdict": UNMEASURED, "learners_tried": len(tried),
                        "why": f"needs {min_learners} learners before a death certificate"}
            continue
        best = max(float(v["net_gain"]) for v in tried)
        out[rep] = {"verdict": "DEAD" if best <= 0 else "ALIVE", "learners_tried": len(tried),
                    "best_net_gain": round(best, 6),
                    "best_model": max((v for v in row.items() if v[1].get("net_gain") is not None),
                                      key=lambda kv: float(kv[1]["net_gain"]))[0]}
    return out


# ----------------------------------------------------------------- item 15: multi-island
@dataclass(frozen=True)
class Island:
    """One population with its OWN prior and its OWN slice of the information."""

    name: str
    #: Model families this island prefers -- its prior over how the world is shaped.
    prior_models: tuple[str, ...]
    #: Feature indices this island may see. Different subsets is what keeps the islands honest:
    #: a concept that survives on two islands survived on two different information sets.
    info_subset: tuple[int, ...]
    seed: int = 0
    note: str = ""


def default_islands(n_features: int, *, seed: int = 0) -> list[Island]:
    """Four islands: a linear prior, a nonlinear prior, a state prior and a sparse prior."""
    rng = random.Random(seed)  # noqa: S311
    idx = list(range(max(1, n_features)))
    def _half(off: int) -> tuple[int, ...]:
        pick = sorted(rng.sample(idx, max(1, int(len(idx) * 0.7)))) if len(idx) > 2 else idx
        return tuple(pick) if off % 2 == 0 else tuple(reversed(pick))
    return [
        Island("linear_prior", ("linear", "sparse", "bayesian"), _half(0), seed + 1,
               "believes the world is additive; sees most features"),
        Island("nonlinear_prior", ("tree", "boosting", "neural"), _half(1), seed + 2,
               "believes in thresholds and interactions"),
        Island("state_prior", ("mixture_of_experts", "state_space", "sequence"), _half(2),
               seed + 3, "believes the edge is conditional on a latent state"),
        Island("sparse_prior", ("sparse", "linear", "graph"), _half(3), seed + 4,
               "believes almost everything is noise"),
    ]


#: A concept migrates only if it is strong: positive net gain AND a margin over the destination's
#: own best. A weak migrant is population homogenisation with extra steps.
MIGRATION_MARGIN = 1e-4


def migrate(results: Mapping[str, Sequence[Mapping[str, Any]]], *,
            margin: float = MIGRATION_MARGIN, max_per_island: int = 1) -> list[dict[str, Any]]:
    """Only strong concepts migrate, and only to islands they actually improve."""
    best_local: dict[str, float] = {}
    for isl, rows in results.items():
        vals = [float(r.get("net_gain") or 0.0) for r in rows if r.get("net_gain") is not None]
        best_local[isl] = max(vals) if vals else float("-inf")
    moves: list[dict[str, Any]] = []
    for src, rows in results.items():
        strong = sorted((r for r in rows
                         if r.get("net_gain") is not None and float(r["net_gain"]) > 0.0),
                        key=lambda r: -float(r["net_gain"]))
        for dst in results:
            if dst == src:
                continue
            taken = 0
            for r in strong:
                if taken >= max_per_island:
                    break
                gain = float(r["net_gain"])
                if gain <= best_local[dst] + margin:
                    continue
                moves.append({"from": src, "to": dst, "concept": r.get("concept") or r.get("model"),
                              "net_gain": round(gain, 6),
                              "destination_best": (None if best_local[dst] == float("-inf")
                                                   else round(best_local[dst], 6)),
                              "why": "strictly stronger than the destination's own best"})
                taken += 1
    return moves


# ----------------------------------------------------------------- item 17: research self-play
#: How much net gain a candidate must add PER unit of extra complexity over the simplest rival.
COMPLEXITY_PRICE = 0.0002


def self_play(candidate: Mapping[str, Any], alternatives: Sequence[Mapping[str, Any]],
              *, complexity_price: float = COMPLEXITY_PRICE) -> dict[str, Any]:
    """Four roles on one claim; a candidate must beat the strongest SIMPLER explanation.

    proposer      - the candidate as submitted.
    attacker      - the candidate's own stability: a fold spread wider than its gain is an attack
                    it did not survive.
    reimplementer - an independently produced row for the same claim; disagreement is fatal.
    simplifier    - the strongest alternative with FEWER parameters. The candidate must clear it
                    by `complexity_price` per extra parameter, so complexity is never free.
    """
    cand_net = float(candidate.get("net_gain") or 0.0)
    cand_k = int(candidate.get("complexity") or len(candidate.get("features") or ()) or 1)
    simpler = [a for a in alternatives
               if int(a.get("complexity") or len(a.get("features") or ()) or 1) < cand_k
               and a.get("net_gain") is not None]
    best_simpler = max(simpler, key=lambda a: float(a["net_gain"])) if simpler else None
    verdicts: list[dict[str, Any]] = []

    if best_simpler is not None:
        rival_net = float(best_simpler["net_gain"])
        dk = cand_k - int(best_simpler.get("complexity")
                          or len(best_simpler.get("features") or ()) or 1)
        required = rival_net + complexity_price * max(1, dk)
        ok = cand_net > required
        verdicts.append({"role": "simplifier", "pass": ok,
                         "rival": best_simpler.get("model") or best_simpler.get("name"),
                         "rival_net_gain": round(rival_net, 6),
                         "required_net_gain": round(required, 6),
                         "why": ("clears the strongest simpler explanation by more than the "
                                 "complexity it added" if ok else
                                 "a SIMPLER explanation is at least as good; the extra "
                                 "structure bought nothing")})
    else:
        verdicts.append({"role": "simplifier", "pass": True, "rival": None,
                         "why": "no strictly simpler alternative was offered on this claim"})

    spread = candidate.get("fold_spread")
    if spread is None:
        verdicts.append({"role": "attacker", "pass": True, "verdict": UNMEASURED,
                         "why": "no fold spread reported; stability is UNMEASURED, not proven"})
    else:
        ok = float(spread) <= max(abs(cand_net), 1e-9) * 4.0
        verdicts.append({"role": "attacker", "pass": ok, "fold_spread": round(float(spread), 6),
                         "why": ("fold-to-fold spread is small against the gain" if ok else
                                 "fold-to-fold spread swamps the gain: the edge is an artefact "
                                 "of one fold")})

    reimpl = candidate.get("reimplementation_net_gain")
    if reimpl is None:
        verdicts.append({"role": "reimplementer", "pass": True, "verdict": UNMEASURED,
                         "why": "no independent re-implementation yet; queued, not credited"})
    else:
        agree = abs(float(reimpl) - cand_net) <= max(0.25 * abs(cand_net), 5e-4)
        verdicts.append({"role": "reimplementer", "pass": agree,
                         "reimplementation_net_gain": round(float(reimpl), 6),
                         "why": ("an independent rebuild lands within a quarter of the claim"
                                 if agree else
                                 "an independent rebuild disagrees with the claim")})

    failed = [v for v in verdicts if not v["pass"]]
    return {"verdict": "REJECTED" if failed else "SURVIVES_SELF_PLAY",
            "rejected_by": [v["role"] for v in failed],
            "candidate_net_gain": round(cand_net, 6), "candidate_complexity": cand_k,
            "roles": verdicts,
            "rule": ("a candidate must beat the strongest SIMPLER explanation by the complexity "
                     "price, survive its own fold spread and agree with an independent rebuild")}


# ----------------------------------------------------------------- item 13: active design
def expected_information_gain(p_true: float, discriminations: Sequence[float]) -> float:
    """Expected bits about WHICH hypothesis is true, for one design.

    `p_true` is the prior that H1 holds; `discriminations` is, per outcome, the probability the
    design produces that outcome under H1 minus under H2 (how differently the two theories
    predict it). A design both theories predict identically yields zero bits no matter how
    precisely it is measured -- which is the whole point of designing rather than running both.
    """
    p = min(1 - 1e-9, max(1e-9, float(p_true)))
    h_prior = -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
    if not discriminations:
        return 0.0
    sep = sum(abs(float(d)) for d in discriminations) / len(discriminations)
    sep = min(1.0, max(0.0, sep))
    # Posterior entropy after an observation that separates the theories by `sep`.
    post = p * (1 - sep) / (p * (1 - sep) + (1 - p) * (1 - sep) + sep * p) if sep < 1 else 1.0
    post = min(1 - 1e-9, max(1e-9, post))
    h_post = -(post * math.log2(post) + (1 - post) * math.log2(1 - post)) * (1.0 - sep)
    return round(max(0.0, h_prior - h_post), 6)


def design_discriminating_experiment(h1: Mapping[str, Any], h2: Mapping[str, Any],
                                     designs: Sequence[Mapping[str, Any]],
                                     *, prior_h1: float = 0.5) -> dict[str, Any]:
    """Run the experiment that tells the two theories apart, not both theories blindly."""
    scored = []
    for d in designs:
        eig = expected_information_gain(prior_h1, list(d.get("discriminations") or ()))
        cost = max(1e-6, float(d.get("cost_s") or 1.0))
        scored.append({**{k: d.get(k) for k in ("name", "cost_s", "discriminations")},
                       "expected_bits": eig, "bits_per_second": round(eig / cost, 6)})
    scored.sort(key=lambda r: -float(r["bits_per_second"] or 0.0))
    chosen = scored[0] if scored else None
    return {"h1": h1.get("name"), "h2": h2.get("name"), "prior_h1": prior_h1,
            "designs": scored, "chosen": chosen,
            "saved_trials": max(0, len(scored) - 1),
            "rule": ("choose argmax expected bits about WHICH theory is true per second; a "
                     "design both theories predict identically is worth zero bits")}


# ----------------------------------------------------------------- item 18: synthetic worlds
#: The structures the desk plants in synthetic data. Each names the mechanism it hides, so a
#: rediscovery score is per STRUCTURE as well as per method.
WORLD_KINDS: tuple[str, ...] = ("linear", "interaction", "threshold", "state_dependent",
                                "lagged", "null")


def synthetic_world(kind: str = "linear", *, n: int = 600, p: int = 5, seed: int = 0,
                    noise: float = 0.6) -> dict[str, Any]:
    """Data with a KNOWN hidden structure. `null` plants nothing -- the control that catches a
    method which "rediscovers" structure in noise."""
    if kind not in WORLD_KINDS:
        raise ValueError(f"unknown world {kind!r}; known: {WORLD_KINDS}")
    rng = random.Random(seed)  # noqa: S311
    x = [[rng.gauss(0.0, 1.0) for _ in range(p)] for _ in range(n)]
    y: list[float] = []
    for i, r in enumerate(x):
        if kind == "linear":
            s = 1.2 * r[0] - 0.8 * r[1]
        elif kind == "interaction":
            s = 1.6 * r[0] * r[1]
        elif kind == "threshold":
            s = 1.6 if r[0] > 0.5 else -1.6 * (1.0 if r[0] < -0.5 else 0.0)
        elif kind == "state_dependent":
            s = (1.6 * r[0]) if r[2] > 0 else (-1.6 * r[0])
        elif kind == "lagged":
            s = 1.4 * x[i - 2][0] if i >= 2 else 0.0
        else:
            s = 0.0
        y.append(1.0 if s + rng.gauss(0.0, noise) > 0 else 0.0)
    hidden = {"linear": [0, 1], "interaction": [0, 1], "threshold": [0],
              "state_dependent": [0, 2], "lagged": [0], "null": []}[kind]
    return {"kind": kind, "x": x, "y": y, "hidden_features": hidden, "n": n, "p": p,
            "seed": seed, "noise": noise,
            "mechanism": {"linear": "additive in two features",
                          "interaction": "product of two features",
                          "threshold": "a step in one feature",
                          "state_dependent": "one feature's sign flips with a second",
                          "lagged": "a feature two rows back",
                          "null": "nothing -- the control"}[kind]}


def rediscovery_score(methods: Sequence[str] = MF.ORDER, *, kinds: Sequence[str] = WORLD_KINDS,
                      n: int = 400, seed: int = 0, allow_heavy: bool = True,
                      min_rows: int = 120) -> dict[str, Any]:
    """Can each research method rediscover a structure the desk planted itself? (item 18)

    A hit is a positive net gain on a world that HAS structure; on the `null` world a positive
    verdict is a FALSE POSITIVE and is scored against the method. The published score is
    hits / worlds-with-structure, with the false-positive count beside it -- never folded into
    one number, because a method that fires on everything would look perfect if it were.
    """
    per_method: dict[str, Any] = {}
    worlds = {k: synthetic_world(k, n=n, seed=seed + i) for i, k in enumerate(kinds)}
    structured = [k for k in kinds if k != "null"]
    for m in methods:
        rows: dict[str, Any] = {}
        hits, false_pos = 0, 0
        for k, w in worlds.items():
            r = MF.walk_forward(m, w["x"], w["y"], allow_heavy=allow_heavy, min_rows=min_rows)
            found = r.get("verdict") == MF.POSITIVE
            rows[k] = {"net_gain": r.get("net_gain"), "verdict": r.get("verdict"),
                       "found": found, "hidden": w["hidden_features"]}
            if k == "null":
                false_pos += int(found)
            else:
                hits += int(found)
        per_method[m] = {
            "worlds": rows, "hits": hits, "of": len(structured),
            "false_positives": false_pos,
            "score": round(hits / len(structured), 4) if structured else None,
            "heavy_verdict": MF.availability()[m]["heavy_verdict"]}
    best = max(per_method, key=lambda m: (per_method[m]["score"] or 0.0,
                                          -per_method[m]["false_positives"])) \
        if per_method else None
    return {"per_method": per_method, "worlds": list(kinds), "n_rows": n, "seed": seed,
            "best_method": best,
            "desk_score": round(sum((per_method[m]["score"] or 0.0) for m in per_method)
                                / max(1, len(per_method)), 4),
            "rule": ("score = structured worlds rediscovered / structured worlds planted; a "
                     "positive verdict on the null world is a false positive and is published "
                     "beside the score, never netted into it")}


# ----------------------------------------------------------------- guarded shims (other builders)
def _shim(module: str, name: str) -> Callable[..., Any] | None:
    """Import another builder's symbol if it has landed; None if it has not. Never a crash."""
    try:
        mod = __import__(module, fromlist=[name])
        fn = getattr(mod, name, None)
        return fn if callable(fn) else None
    except Exception:
        return None


def _kwargs_accepted(fn: Callable[..., Any]) -> set[str]:
    try:
        import inspect
        return set(inspect.signature(fn).parameters)
    except (TypeError, ValueError):
        return set()


def record_outcome(topic: str, outcome: str, **fields: Any) -> dict[str, Any]:
    """`libs.research.research_priors.record_outcome`, adapted to whatever it takes today.

    THE SHIM ADAPTS RATHER THAN GUESSES. The priors module landed with
    `record_outcome(outcome, *, family=..., model=..., representation=..., ...)`, not the
    `(topic, outcome)` shape this organ first assumed; calling it positionally would have
    recorded the topic AS the outcome. The signature is read and only the keywords it actually
    accepts are passed, so a later rename degrades to the local fallback instead of poisoning
    another builder's ledger.
    """
    fn = _shim("libs.research.research_priors", "record_outcome")
    if fn is not None:
        accepted = _kwargs_accepted(fn)
        kw = {k: v for k, v in fields.items() if k in accepted}
        if "model" in accepted and "model" not in kw:
            kw["model"] = topic
        try:
            if "outcome" in accepted or accepted:
                return {"backend": "research_priors", "topic": topic,
                        "result": str(fn(outcome, **kw))[:200]}
        except Exception as exc:
            return {"backend": "research_priors", "error": f"{type(exc).__name__}: {exc}"}
    return {"backend": "local_fallback", "topic": topic, "outcome": outcome, "fields": fields,
            "why": "libs.research.research_priors not on this tree yet; outcome recorded in the "
                   "artifact only, and the real ledger is picked up automatically once it lands"}


def prior_for(topic: str, default: float = 0.5, *, dimension: str = "model_repr"
              ) -> dict[str, Any]:
    """The posterior mean for `topic`, or the uninformative prior recorded AS uninformative."""
    fn = _shim("libs.research.research_priors", "prior_for")
    if fn is not None:
        for args in ((dimension, topic), (topic,)):
            try:
                got = fn(*args)
            except Exception:
                continue
            mean = getattr(got, "mean", None)
            try:
                value = float(mean if mean is not None else got)
            except (TypeError, ValueError):
                continue
            if 0.0 <= value <= 1.0:
                return {"backend": "research_priors", "prior": value,
                        "status": str(getattr(got, "status", "") or "")}
    return {"backend": "local_fallback", "prior": float(default),
            "why": "no priors module reachable; the uninformative prior is used and recorded "
                   "as uninformative rather than presented as evidence"}


def to_campaign(spec: Mapping[str, Any]) -> dict[str, Any]:
    """`libs.research.experiment_spec.ExperimentSpec(...).to_campaign()` once it lands."""
    cls = _shim("libs.research.experiment_spec", "ExperimentSpec")
    if cls is not None:
        try:
            obj = cls(**dict(spec))
            camp = getattr(obj, "to_campaign", None)
            if callable(camp):
                return {"backend": "experiment_spec", "campaign": camp()}
        except Exception as exc:
            return {"backend": "experiment_spec", "error": f"{type(exc).__name__}: {exc}",
                    "campaign": dict(spec)}
    return {"backend": "local_fallback", "campaign": dict(spec),
            "why": "libs.research.experiment_spec not on this tree yet; the spec is carried "
                   "verbatim and converts automatically once the module lands"}


def link_experiment(parent: str, child: str, relation: str) -> dict[str, Any]:
    """An edge in `libs.research.experiment_graph` when it exists; a recorded edge until then."""
    for fname in ("add_edge", "link", "record_edge"):
        fn = _shim("libs.research.experiment_graph", fname)
        if fn is not None:
            try:
                fn(parent, child, relation)
                return {"backend": f"experiment_graph.{fname}", "parent": parent,
                        "child": child, "relation": relation}
            except Exception:
                continue
    return {"backend": "local_fallback", "parent": parent, "child": child, "relation": relation,
            "why": "libs.research.experiment_graph not on this tree yet; the edge is published "
                   "in the artifact and re-emitted once the graph lands"}
