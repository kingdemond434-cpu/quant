"""WHERE THE NEXT TRIAL GOES, decided by where the gauntlet has actually certified.

THE MEASUREMENT THAT FORCED THIS (`research/conversion_ledger.py`, 2026-09-05, on the desk's own
`data/research_queue.json`: 46,835 cards judged, 49 certified, 0.105%). The loss is not spread
evenly across the docket. It is almost entirely one cell type:

    cell type (family x asset class)      certified / tried      rate     share of the docket
    overnight_gap_decay  x fx_exotic          18 /    122      14.75%              0.26%
    overnight_gap_decay  x fx_cross            3 /     42       7.14%              0.09%
    carry                x fx_exotic           2 /    138       1.45%              0.29%
    discovered           x fx_cross           12 /  6,543       0.18%             13.97%
    discovered           x fx_major            6 /  4,444       0.14%              9.49%
    discovered           x equity              8 / 25,876       0.03%             55.25%
    everything else                            0 /  9,670       0.00%             20.65%

Fifty-five per cent of every gauntlet trial the desk has ever spent went to the cell type that
certifies at three hundredths of a percent, and a quarter of one per cent went to the type that
certifies at fifteen. That is a 476x difference in certificates per unit of compute, and it is
the whole reason the funnel produces "9 candidates" while consuming the box around the clock.

WHAT THIS CHANGES, AND WHAT IT MUST NEVER CHANGE. It changes ONE thing: the ORDER and the BUDGET
SHARE in which the generators walk the universe, so a run bounded by wall clock or memory -- and
every run here is -- spends its bounded hour on ground that certifies. It changes no screen, no
threshold, no floor, no gate and no trial count. A cell proposed under this allocation faces the
identical ten gates at the identical bar. Raising a conversion rate by moving a bar converts
worse candidates and is the one thing forbidden outright; raising it by proposing where the bar
is actually cleared is the only honest lever there is.

    THIS IS THE SAME ARGUMENT `external_gauntlet` ALREADY MAKES for its build order ("a list
    order starves its own tail"), and `edge_search` for its class-balanced rotation. Both
    established that ORDER decides what a bounded run reaches. Neither asked which ground pays.

======================= WHY THE ESTIMATE IS SHRUNK, AND WHY IT EXPLORES =======================

Choosing where to search by observed pass rate is itself a selection, and an unshrunk one would
be the desk's own defect in a new costume: a cell type that went 2-for-2 by luck would outrank
one measured 18-for-122, and the search would chase noise. So:

  1. ALLOCATION READS A SHRUNK LOWER BOUND, never the raw rate -- and an interval ALONE is not
     enough, which is worth spelling out because it was the first thing tried here and it was
     wrong. 2/2 has a raw rate of 100% and a 95% Wilson lower bound of 34%; 18/122 has a raw rate
     of 14.8% and a bound of 9.5%. So the interval by itself STILL lets a coin flip outrank a
     measured lead: an interval asks "how sure am I about this type", never "how surprising is
     this type against the desk's own base rate", and the base rate here is 0.1%. Every type is
     therefore shrunk toward the pooled rate with `PRIOR_TRIALS` pseudo-trials BEFORE the bound
     is taken. A test pins the property rather than the constant.
  2. A FIXED SHARE OF EVERY BUDGET IS SPLIT EQUALLY OVER EVERY KNOWN CELL TYPE, FOREVER
     (`EXPLORE_SHARE`). Coverage stays a cycle and never becomes a finished sweep: a type that
     looks bad today keeps being sampled, so the estimate that demoted it keeps being revised and
     the demotion is reversible. Without this the allocator would freeze its own first opinion
     into the data that justifies it.
  3. NO TYPE MAY TAKE THE WHOLE BUDGET (`MAX_SHARE`). A 14.8% type is a lead, not a licence to
     stop looking anywhere else, and concentration in one family is the exact book concentration
     `orthogonal_sweep` exists to break.
  4. AN UNTRIED TYPE IS NOT A ZERO. It inherits the pooled prior and its explore share, because
     "never tested" and "tested and dead" are opposite facts and this desk has shipped that
     confusion before.

============================ WHAT THIS DOES NOT FIX, SAID PLAINLY ============================

The deflated-Sharpe hurdle charges a FIXED campaign trial count (`gate_policy`
`trial_count_basis`: fixed_campaign_trials(597)) no matter how many cells a sweep actually runs.
So reallocating trials neither relaxes nor tightens the multiplicity charge -- this allocator
cannot game that gate, and it does not try. It is also, separately, a mis-specification worth its
own report line: the charge does not grow with the search, which makes the bar too LOOSE, not too
strict. It is named here and left exactly alone, per the standing rule that a gate is never moved
to make a rate look better.

    python3 research/trial_allocator.py            # print the measured table and the weights
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
for _p in (str(BASE), str(BASE.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

QUEUE = BASE / "data" / "research_queue.json"
REPORT = BASE / "reports" / "TRIAL_ALLOCATION.json"

#: The share of every budget split EQUALLY over every known cell type, forever. This is the
#: reversibility guarantee, not a courtesy: without it the allocator's first opinion becomes the
#: only evidence it ever collects about the ground it demoted.
EXPLORE_SHARE = 0.30
#: No single cell type may hold more than this share of the exploit half. A lead is not a licence
#: to stop looking anywhere else, and one family owning the docket is the concentration the
#: orthogonal sweep exists to break.
MAX_SHARE = 0.35
#: Two-sided normal quantile for the Wilson interval. 1.96 = 95%.
WILSON_Z = 1.96
#: PSEUDO-TRIALS OF THE POOLED RATE EVERY CELL TYPE IS SHRUNK TOWARD, and the Wilson bound alone
#: is NOT a substitute for it -- which is worth stating because it was the first thing tried here
#: and it was wrong. The 95% lower bound of 2-for-2 is 34%; of 18-for-122 it is 9.5%. So an
#: interval alone still lets a coin flip outrank a measured lead, because an interval asks "how
#: sure am I about THIS type" and never "how surprising is this type against the desk's own base
#: rate", which is the question that matters when the base rate is 0.1%.
#:
#: So each type is shrunk toward the POOLED rate with this many pseudo-trials before the bound is
#: taken. The constant declares the count at which a type's own evidence begins to outweigh the
#: desk's base rate; the property it must buy is pinned in
#: `tests/test_trial_allocator.py::test_a_lucky_two_of_two_never_outranks_...`, so it cannot be
#: raised or lowered into meaninglessness without that test saying so.
PRIOR_TRIALS = 100.0
#: Verdict words the queue writes. PASSED is the only conversion; anything else is not a
#: certificate and must not be counted as one.
PASSED = "PASSED"


def wilson_lower(certified: float, tried: float, z: float = WILSON_Z) -> float:
    """The 95% lower bound on a pass rate.

    Wilson rather than the normal approximation because the rates here are tiny (3e-4) and the
    normal interval goes negative and meaningless at those counts. Accepts fractional counts so
    the shrunk (prior-augmented) counts below can be passed straight in.
    """
    n = max(0.0, float(tried))
    k = min(max(0.0, float(certified)), n)
    if n <= 0:
        return 0.0
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1.0 - p) / n + z * z / (4 * n * n))
    return max(0.0, centre - half)


def shrunk_lower(certified: int, tried: int, pooled: float,
                 prior: float = PRIOR_TRIALS) -> float:
    """THE NUMBER THE ALLOCATION READS: the lower bound AFTER shrinking toward the base rate.

    `prior` pseudo-trials at the desk's own pooled certification rate are added to every type
    before the bound is taken, so a type with almost no history is judged mostly by what the desk
    knows in general and only earns its own opinion by being measured. Large counts swamp the
    prior and the number converges on the plain Wilson bound.
    """
    return wilson_lower(certified + prior * max(0.0, pooled), tried + prior)


@dataclass(frozen=True)
class CellYield:
    """One (family, asset class) cell type and what the gauntlet did with it."""

    family: str
    asset_class: str
    tried: int
    certified: int
    #: The desk's pooled certification rate, carried so a row can be shrunk toward it. Defaults
    #: to zero, which is the most pessimistic prior available and never flatters a thin count.
    pooled: float = 0.0

    @property
    def key(self) -> tuple[str, str]:
        return (self.family, self.asset_class)

    @property
    def rate(self) -> float:
        return (self.certified / self.tried) if self.tried else 0.0

    @property
    def lower(self) -> float:
        return shrunk_lower(self.certified, self.tried, self.pooled)

    def as_dict(self) -> dict[str, Any]:
        return {"family": self.family, "asset_class": self.asset_class, "tried": self.tried,
                "certified": self.certified, "rate": round(self.rate, 6),
                "wilson_lower": round(wilson_lower(self.certified, self.tried), 6),
                "shrunk_lower": round(self.lower, 6)}


def asset_class_of(symbol: str) -> str:
    """The desk's own classifier, or `unknown` when it cannot be imported.

    Read defensively on purpose: this module is consulted from inside two generators whose whole
    value is that they keep running, and a classifier import failure must degrade the allocation
    to the incumbent order rather than take a sweep down.
    """
    try:
        from mt5desk.universe import asset_class
    except Exception:
        return "unknown"
    try:
        return str(asset_class(symbol) or "unknown")
    except Exception:
        return "unknown"


def _symbol_of(row: dict[str, Any]) -> str | None:
    """The instrument a judged card names, from its canonical cell.

    A card with no canonical cell has no instrument and is NOT counted in either the numerator
    or the denominator -- guessing the symbol out of the prose is how a denominator quietly
    acquires rows nothing judged.
    """
    cell = row.get("canonical_cell")
    if isinstance(cell, str) and "." in cell:
        return cell.split(".")[0]
    return None


def observed(queue_path: Path | None = None) -> list[CellYield]:
    """Certified / tried per (family, asset class), from the queue's own recorded verdicts.

    ONLY JUDGED CARDS COUNT. A card still PENDING, or blocked before the gauntlet ever saw it,
    is work not yet done and belongs in neither the numerator nor the denominator; counting it
    as a failure would make a queue look like a wall.
    """
    path = queue_path or QUEUE
    try:
        rows = json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(rows, list):
        return []
    tried: Counter[tuple[str, str]] = Counter()
    passed: Counter[tuple[str, str]] = Counter()
    for row in rows:
        if not isinstance(row, dict):
            continue
        verdict = row.get("canonical_verdict")
        if verdict not in (PASSED, "REJECTED"):
            continue
        sym = _symbol_of(row)
        if sym is None:
            continue
        key = (str(row.get("family") or "unknown"), asset_class_of(sym))
        tried[key] += 1
        if verdict == PASSED:
            passed[key] += 1
    pooled = (sum(passed.values()) / sum(tried.values())) if sum(tried.values()) else 0.0
    return sorted((CellYield(fam, cls, n, passed.get((fam, cls), 0), pooled)
                   for (fam, cls), n in tried.items()),
                  key=lambda y: (-y.lower, -y.tried, y.family, y.asset_class))


def pooled_rate(yields: list[CellYield]) -> float:
    """The desk's own base rate across every judged cell type. The prior everything shrinks to."""
    tried = sum(y.tried for y in yields)
    return (sum(y.certified for y in yields) / tried) if tried else 0.0


def weights(yields: list[CellYield], *, explore: float = EXPLORE_SHARE,
            cap: float = MAX_SHARE) -> dict[tuple[str, str], float]:
    """Budget share per cell type: an explore half split equally, an exploit half by lower bound.

    Sums to 1.0 over the types given. An empty or all-zero table degrades to UNIFORM, which is
    the incumbent behaviour -- an allocator with no evidence must not invent a preference.
    """
    if not yields:
        return {}
    n = len(yields)
    base = explore / n
    exploit_mass = max(0.0, 1.0 - explore)
    scores = {y.key: y.lower for y in yields}
    total = sum(scores.values())
    if total <= 0:
        return {y.key: 1.0 / n for y in yields}
    share = {k: base + exploit_mass * (v / total) for k, v in scores.items()}
    # A CAP THE TABLE CANNOT SATISFY IS NOT A CAP, IT IS A FLATTENER. With `n * cap < 1` every
    # type must exceed the cap for the weights to sum to one, so applying it drives the table to
    # uniform and destroys the ranking it was meant to bound. The cap is a CONCENTRATION limit
    # and concentration is not a meaningful idea across two cell types; it binds only once there
    # are enough types for one of them to actually dominate.
    if n * cap < 1.0:
        scale = sum(share.values()) or 1.0
        return {k: v / scale for k, v in share.items()}
    # THE CAP, APPLIED BY REDISTRIBUTION rather than by clipping. Clipping alone would leave the
    # weights summing to less than one and quietly shrink the budget the caller thinks it spent.
    for _ in range(n):
        over = {k: v for k, v in share.items() if v > cap}
        if not over:
            break
        spill = sum(v - cap for v in over.values())
        room = {k: v for k, v in share.items() if v < cap}
        if not room:
            break
        room_total = sum(room.values()) or 1.0
        for k in over:
            share[k] = cap
        for k, v in room.items():
            share[k] = min(cap, v + spill * (v / room_total))
    scale = sum(share.values()) or 1.0
    return {k: v / scale for k, v in share.items()}


def class_weights(yields: list[CellYield], **kw: Any) -> dict[str, float]:
    """Budget share per ASSET CLASS -- what a symbol-ordering caller needs.

    A generator picks SYMBOLS, not (family, class) pairs, so the cell-type weights are summed
    over families to answer the question the caller can actually act on.
    """
    per_cell = weights(yields, **kw)
    out: dict[str, float] = {}
    for (_fam, cls), w in per_cell.items():
        out[cls] = out.get(cls, 0.0) + w
    total = sum(out.values()) or 1.0
    return {k: v / total for k, v in out.items()}


def order_symbols(symbols: list[str], cls_weights: dict[str, float] | None = None,
                  *, class_of: Any = None) -> list[str]:
    """`symbols` re-interleaved so that EVERY PREFIX is distributed by measured yield.

    WHY A PREFIX PROPERTY AND NOT A SORT. Every generator here is bounded -- edge_search takes
    the first 40, orthogonal_sweep and the gauntlet stop at a wall-clock or memory budget -- so
    the only thing an ordering decides is what the bounded run REACHES. A sort by weight would
    reach one class and never leave it; a weighted interleave reaches every class in proportion,
    at every budget, so a run cut short at any point has spent itself by the measured table.

    RELATIVE ORDER INSIDE A CLASS IS PRESERVED EXACTLY. Whatever the caller's own rotation
    cursor, mined-ground priority or staleness rule put first inside a class stays first inside
    that class; this decides only how the classes interleave. Coverage therefore stays a cycle
    and no symbol is ever dropped: the result is a permutation of the input, always.
    """
    if not symbols:
        return []
    classify = class_of or asset_class_of
    buckets: dict[str, list[str]] = {}
    for s in symbols:
        buckets.setdefault(str(classify(s)), []).append(s)
    if not cls_weights:
        cls_weights = dict.fromkeys(buckets, 1.0)
    present = {c: max(0.0, float(cls_weights.get(c, 0.0))) for c in buckets}
    if sum(present.values()) <= 0:
        present = dict.fromkeys(buckets, 1.0)
    total = sum(present.values())
    present = {c: v / total for c, v in present.items()}
    # Largest-deficit-first: at each step emit from the class whose emitted share is furthest
    # below its target. Deterministic, no RNG, and it degenerates to plain round-robin when the
    # weights are equal -- which is exactly the incumbent behaviour it must reduce to.
    taken: dict[str, int] = dict.fromkeys(buckets, 0)
    out: list[str] = []
    order = sorted(buckets)
    for _ in range(len(symbols)):
        live = [c for c in order if taken[c] < len(buckets[c])]
        if not live:
            break
        emitted = len(out)
        best = max(live, key=lambda c: (present[c] * (emitted + 1) - taken[c], -order.index(c)))
        out.append(buckets[best][taken[best]])
        taken[best] += 1
    return out


def allocate_symbols(symbols: list[str], per_run: int, cls_weights: dict[str, float] | None,
                     cursors: dict[str, int] | None = None,
                     *, class_of: Any = None) -> tuple[list[str], dict[str, int]]:
    """Which symbols a bounded run searches, and each class's advanced rotation cursor.

    WHY A PER-CLASS CURSOR AND NOT ONE GLOBAL ONE, which is the whole point and was not obvious.
    A single cursor sweeping one list gives every symbol exactly one search per cycle NO MATTER
    WHAT ORDER the list is in -- so re-ordering alone cannot change the long-run mix by a single
    trial. It moves timing and nothing else. The mix is set by how OFTEN each class's cycle comes
    round, and that is a budget question, not an ordering one. This is what the measurement
    demanded: 61.5% of every judged cell was an equity CFD certifying at 0.03%, and no amount of
    re-sorting a shared cursor would have moved that number.

    COVERAGE STAYS A CYCLE FOR EVERY CLASS, WITHOUT EXCEPTION. Each class keeps its own cursor
    and receives AT LEAST ONE symbol per run while the budget lasts, so no class is ever
    declared finished and no symbol is ever dropped -- a class simply comes round more or less
    often, in proportion to what the gauntlet has actually certified there. That floor is the
    reversibility guarantee at the symbol level: the evidence that demoted a class keeps being
    refreshed on newer bars, so the demotion can be undone by the data that caused it.
    """
    if not symbols or per_run <= 0:
        return [], dict(cursors or {})
    classify = class_of or asset_class_of
    buckets: dict[str, list[str]] = {}
    for s in symbols:
        buckets.setdefault(str(classify(s)), []).append(s)
    weights_now = {c: max(0.0, float((cls_weights or {}).get(c, 0.0))) for c in buckets}
    if sum(weights_now.values()) <= 0:
        weights_now = dict.fromkeys(buckets, 1.0)
    weight_sum = sum(weights_now.values())
    budget = min(per_run, len(symbols))
    quota = dict.fromkeys(buckets, 0)
    # THE FLOOR FIRST: one symbol per class while the budget allows, so no class is ever declared
    # finished. Then one seat at a time to whichever class is furthest below its weighted
    # entitlement AND still has an unsearched symbol.
    #
    # CAPACITY-AWARE, seat by seat, because a share a small class cannot fill must go to a class
    # that can -- otherwise a heavily weighted small class silently shrinks the whole run. Found
    # by `test_a_budget_larger_than_the_universe_takes_everything_once`: a 999-symbol budget over
    # a 30-symbol universe returned 22 seats, because unfillable quota was simply dropped.
    for cls in sorted(buckets):
        if sum(quota.values()) >= budget:
            break
        quota[cls] = 1
    while sum(quota.values()) < budget:
        room = [c for c in sorted(buckets) if quota[c] < len(buckets[c])]
        if not room:
            break
        assigned = sum(quota.values())
        quota[max(room, key=lambda c: weights_now[c] / weight_sum * (assigned + 1) - quota[c])
              ] += 1
    out_cursors = dict(cursors or {})
    picked: dict[str, list[str]] = {}
    for cls, names in buckets.items():
        take = min(quota.get(cls, 0), len(names))
        if take <= 0:
            continue
        start = int(out_cursors.get(cls, 0)) % len(names)
        rotated = names[start:] + names[:start]
        picked[cls] = rotated[:take]
        out_cursors[cls] = (start + take) % len(names)
    flat = [s for names in picked.values() for s in names]
    return order_symbols(flat, weights_now, class_of=classify), out_cursors


def certificates_per_1000(yields: list[CellYield], share: dict[str, float]) -> float:
    """Expected certificates per 1,000 trials if the budget were split by `share` over CLASSES.

    Each class is priced at its own Wilson LOWER bound, pooled over the families tried in it and
    weighted by how those families were actually sampled. The lower bound is used on purpose:
    this number is a floor on what the allocation buys, never a forecast of what it might.
    """
    by_class: dict[str, tuple[int, int]] = {}
    for y in yields:
        t, c = by_class.get(y.asset_class, (0, 0))
        by_class[y.asset_class] = (t + y.tried, c + y.certified)
    pooled = pooled_rate(yields)
    total = sum(max(0.0, v) for v in share.values()) or 1.0
    out = 0.0
    for cls, w in share.items():
        tried, certified = by_class.get(cls, (0, 0))
        out += (w / total) * shrunk_lower(certified, tried, pooled) * 1000.0
    return out


def incumbent_class_share(yields: list[CellYield]) -> dict[str, float]:
    """The share each class ACTUALLY received, from the judged docket itself.

    This is the honest "without" arm of the rent line: not a guess at what a flat rotation would
    do, but what the desk's own generators, cursors and class-balanced weave demonstrably did.
    """
    by_class: Counter[str] = Counter()
    for y in yields:
        by_class[y.asset_class] += y.tried
    total = sum(by_class.values()) or 1
    return {c: n / total for c, n in by_class.items()}


def target_stage(ledger: Path | None = None) -> dict[str, Any]:
    """The funnel stage this allocation is aimed at, read from the conversion ledger.

    WHY THE ALLOCATOR READS THE LEDGER RATHER THAN ASSUMING ITS OWN IMPORTANCE. A component that
    decides where the desk spends its compute must name, from a measurement it did not make
    itself, WHICH stage it is trying to move -- otherwise the first thing to go stale is the
    reason it exists, and nobody would notice because the allocator would still produce weights.
    If the ledger later names a different binding stage, this row says so and the allocation is
    up for review; the allocator does not get to keep pointing at a constraint that has moved.
    """
    path = ledger or (BASE / "data" / "conversion_ledger.json")
    try:
        doc = json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return {"binding_stage": None, "measured_at": None,
                "why": f"{path.name} absent on this host -- the allocation still works from the "
                       f"queue's own verdicts, but nothing here confirms it is aimed at the "
                       f"stage the funnel is actually losing at"}
    return {"binding_stage": doc.get("binding_stage"),
            "binding_rate_when_measured": doc.get("binding_rate"),
            "measured_at": doc.get("generated_utc"),
            "aimed_correctly": doc.get("binding_stage") == GATE_STAGE,
            "why": ("this allocation moves the trial mix INTO the gauntlet, so it is aimed at the "
                    "stage above only while that stage is the one the ledger names binding")}


#: The stage this allocator is built to move. Named so `target_stage` can say plainly when the
#: constraint has moved somewhere this component cannot help with.
GATE_STAGE = "gauntlet_verdict -> ten_gate_certificate"


def rent(yields: list[CellYield] | None = None) -> dict[str, Any]:
    """ModuleRent for this component: certificates per 1,000 gauntlet trials, with minus without.

    UNIT IS NAMED, NOT ASSUMED (the rule `libs/ops/module_rent.py` sets for every ledger whose
    natural unit is not log-wealth). No exchange rate exists between a certificate and E[log W]
    at this stage of the funnel -- a certificate's forward expectancy is measured later, by its
    own clock, and pricing one here would be inventing the number this desk exists to measure.
    So `rent` is in certificates per 1,000 trials and `rent_logw_per_day` is None, with the
    reason carried on the row.

    THE EX-ANTE NUMBER IS A PROJECTION AND SAYS SO. It re-prices the SAME judged docket under the
    two allocations, which is a counterfactual on already-collected evidence, not forward
    evidence. `forward_basis` names what must be measured to settle it: certificates per 1,000
    cells whose `created_at` is after the allocation landed. Until that window has cells, the
    forward verdict is UNMEASURED -- never folded into the projection.
    """
    ys = observed() if yields is None else yields
    if not ys:
        return {"module": "trial_allocator", "kind": "proposer", "verdict": "UNMEASURED",
                "why": f"{QUEUE} absent or carries no judged card on this host",
                "unit": "certificates per 1000 gauntlet trials", "rent_logw_per_day": None}
    with_share = class_weights(ys)
    without_share = incumbent_class_share(ys)
    with_rate = certificates_per_1000(ys, with_share)
    without_rate = certificates_per_1000(ys, without_share)
    tried = sum(y.tried for y in ys)
    certified = sum(y.certified for y in ys)
    return {
        "module": "trial_allocator",
        "kind": "proposer",
        "ledger": "desks/mt5/data/conversion_ledger.json",
        "rule": ("certificates per 1,000 gauntlet trials under the measured allocation minus "
                 "the same statistic under the allocation the docket actually received; both "
                 "priced at the Wilson lower bound of each class's own certified/tried"),
        "unit": "certificates per 1000 gauntlet trials",
        "rent": round(with_rate - without_rate, 4),
        "with": round(with_rate, 4),
        "without": round(without_rate, 4),
        "rent_logw_per_day": None,
        "rent_logw_why": ("no exchange rate exists from a certificate to log-wealth at this "
                          "stage; the certificate's forward expectancy is measured by its own "
                          "clock and inventing it here would fabricate the desk's objective"),
        "basis": "EX_ANTE_COUNTERFACTUAL_ON_JUDGED_DOCKET",
        "n_trials": tried,
        "n_certificates": certified,
        "forward_basis": ("certificates per 1,000 judged cells whose created_at is after this "
                          "allocation landed, against the same statistic on the cells before it"),
        "forward_verdict": "UNMEASURED",
        "target": target_stage(),
        "verdict": ("EARNS" if with_rate > without_rate else
                    "COSTS" if with_rate < without_rate else "NOT_BINDING"),
    }


#: The capability-graph node this component owes, in the shape `libs/ops/capability_graph.Node`
#: takes. It is DECLARED HERE because the graph's registry lives outside this desk's research
#: tree; the entry below is copied into `libs/ops/capability_graph.NODES` verbatim. Declaring it
#: in the module it describes means the two cannot drift apart unnoticed -- a test asserts the
#: paths named here are the paths this module actually reads and writes.
CAPABILITY_NODE: dict[str, Any] = {
    "name": "trial_allocator",
    "module": "desks/mt5/research/trial_allocator.py",
    "writes": ("desks/mt5/reports/TRIAL_ALLOCATION.json",),
    "reads": ("desks/mt5/data/research_queue.json",
              "desks/mt5/data/conversion_ledger.json"),
    # It decides ORDER and BUDGET SHARE, never a position, a size or a certificate. Empty
    # authority is the accurate declaration and it is what keeps this out of the money path.
    "authority": (),
}


def run() -> dict[str, Any]:
    """The hourly organ entry point: measure, weight, and publish. Reads only."""
    ys = observed()
    cls = class_weights(ys)
    report = {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "explore_share": EXPLORE_SHARE, "max_share": MAX_SHARE,
        "n_cell_types": len(ys),
        "cell_type_yield": [y.as_dict() for y in ys],
        "class_weights": {k: round(v, 5) for k, v in sorted(cls.items())},
        "class_share_received": {k: round(v, 5)
                                 for k, v in sorted(incumbent_class_share(ys).items())},
        "rent": rent(ys),
        "law": ("order and budget share only: no screen, threshold, floor or gate is touched, "
                "and a cell proposed under this allocation faces the identical ten gates"),
        # The hourly pass reads its YIELD counters off this report. `cell_types` is the honest
        # counter for a measurement organ: it proposes no candidate and must never be counted as
        # if it had, but a pass where it measured NOTHING must not read as a silent success. It
        # is a COUNT and the table above is `cell_type_yield` -- one name per shape, because the
        # first version of this dict used one key for both and the count silently ate the table.
        "cell_types": len(ys),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1), "utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    rep = run()
    if not args.quiet:
        # Recomputed from `observed()` rather than rebuilt out of the report: a CellYield
        # reconstructed from the printed row would lose `pooled` and silently print weights the
        # allocator never used.
        ys = observed()
        w = weights(ys)
        print(f"{'family':28s} {'class':10s} {'cert':>5s} {'tried':>7s} {'rate':>9s} "
              f"{'wilson_lo':>10s} {'shrunk_lo':>10s} {'weight':>8s}")
        for y in ys[:25]:
            print(f"{y.family:28s} {y.asset_class:10s} {y.certified:5d} "
                  f"{y.tried:7d} {y.rate:9.5f} {wilson_lower(y.certified, y.tried):10.5f} "
                  f"{y.lower:10.5f} {w.get(y.key, 0.0):8.4f}")
        r = rep["rent"]
        print(f"\nrent: {r.get('rent')} {r.get('unit')} "
              f"(with {r.get('with')} vs without {r.get('without')}) -> {r.get('verdict')}")
        print(f"-> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
