"""Where the search budget goes, where survivors come from, and why those are not the same place.

NOT `mechanism_census.py`, WHICH ALREADY EXISTS NEXT DOOR. That module is the mechanism ONTOLOGY
-- what a mechanism IS, its construction classes, coverage verdicts and classification. This one
is the FUNNEL: how many candidates each family produced, how many survived each stage, and where
the next trial is worth spending. Different questions, and an early draft of this file was
written straight over that one, which broke every importer of CONSTRUCTION_CLASS.

WHY THIS EXISTS (principal blueprint, 2026-08-29 -- "portfolio-aware discovery from birth" and
"live-to-research feedback")

Measured the same day, from the desk's own funnel artifacts:

    family                      candidates   certificates   yield
    discovered                      10,624              7   0.07%
    session_range_breakout             126             20  15.87%
    overnight_gap_decay                232             12   5.17%
    eight other families             1,308              0   0.00%

`discovered` takes 85% of every trial the desk spends and returns 17% of its certificates. Per
trial it is 227x less productive than `session_range_breakout`. Nothing was measuring this, so
nothing could act on it, and the allocation had never been anybody's decision -- it was the
accumulated residue of which generator happened to emit the most rows.

THE TRAP THIS MUST NOT FALL INTO, and an early version of this module fell straight into it. The
obvious response -- pour the budget into the 15.87% family -- would make the book WORSE, and the
first draft did exactly that, allocating 980 of 1000 trials to it and ZERO to seven mechanisms it
labelled "confidently barren".

Both halves of that were wrong. Concentrating makes the book worse because
`session_range_breakout` is the most-mined ground on this desk, its certificates are the most
correlated with each other, and the binding constraint here is not survivor count but
INDEPENDENCE: n_eff ~5.5 across 23 certificates. Twenty more clones of the thing the desk
already owns adds gross risk and no growth.

And zeroing the "barren" seven was worse. Those attempts ran through a validator this desk has
since found defective in four independent ways -- pooled-median costs instead of the fill hour, a
forward lane whose clocks reset every cycle, three verdict engines with three different bars, and
a missing module that blocked every sleeve at once. A zero from a broken test is evidence about
the test. Writing those mechanisms off would have made the defect permanent, because a mechanism
that is never searched can never be proven.

So: BREADTH IS THE OBJECTIVE AND YIELD IS THE TIEBREAK. Every known mechanism holds a guaranteed
floor (MIN_FAMILY_SHARE) and none may exceed a cap (MAX_FAMILY_SHARE). Yield ranks what happens
between those bounds; it never decides that something goes unsearched.

So research value multiplies four things, and a zero in any of them is a zero overall:

    P(survive)         Beta posterior from this family's own funnel record
    marginal value     what it adds to a book it is not yet part of (residual, not standalone)
    novelty            how much unlike the existing book it is
    information gain   how much a trial here would REDUCE uncertainty

THOMPSON SAMPLING, NOT THE POSTERIOR MEAN. The four families with zero certificates are not one
fact, they are two. `cross_asset_residual` failed 348 times: Beta(1, 349) is tight around 0.3%
and the desk can be confident it is barren for now. `asia_momentum` failed 15 times: Beta(1, 16)
is wide, its true rate could plausibly be 10%, and calling it barren on fifteen attempts is the
desk deciding something it has not measured. Sampling from the posterior explores the second and
abandons the first, automatically, with no threshold to tune -- which is exactly the distinction
a mean would erase.

LIVE FEEDBACK CLOSES THE LOOP. `record_forward_outcome` folds forward and live results back into
the same posterior, so a family that certifies easily and then decays in forward trading loses
budget without anyone deciding to take it away. Certification yield alone would keep rewarding a
family that has never survived contact with the market.
"""
from __future__ import annotations

import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: EMPIRICAL-BAYES PRIOR, fitted to the desk's own funnel rather than assumed.
#:
#: This was Beta(1,1) -- uniform -- on the reasoning that an untried mechanism should be assumed
#: neither promising nor barren. That reasoning is wrong, and expensively so: a uniform prior
#: says a family with two attempts could plausibly certify at 50%, when the desk's measured base
#: rate across 12,535 candidates is 0.33%. `calendar_month`, on TWO attempts and zero
#: certificates, was allocated 505 of every 1000 trials -- half the desk's compute, on a family
#: about which nothing whatsoever is known.
#:
#: A prior centred on the observed base rate is not pessimism, it is the desk's own evidence. An
#: untried mechanism most likely resembles the average mechanism, not a coin flip.
#:
#: STRENGTH IS DELIBERATELY LOW. `PRIOR_STRENGTH` pseudo-observations means a family with 100
#: real attempts is barely touched by the prior while one with two is dominated by it -- which is
#: the correct ordering. Exploration is NOT bought here by inflating the success probability;
#: it is bought by the explicit information-gain term in `research_value`, which is high exactly
#: where the posterior is wide. Keeping those two jobs separate is what stops one lucky draw
#: from turning into a permanent budget share.
PRIOR_STRENGTH = 4.0

#: No mechanism may take more than this share of the research budget, however well it scores.
#:
#: A CONSTRAINT, NOT A MULTIPLIER, and the distinction is the point. Saturation and novelty are
#: multiplicative terms that express "this is worth less"; they were not enough, and could not be
#: -- `session_range_breakout`'s posterior (Beta(20, 107), tight around 0.157) simply does not
#: overlap a barren family's (Beta(0.01, 350)), so Thompson sampling correctly hands it nearly
#: every draw. That is the right answer to "which family most likely certifies next" and the
#: wrong answer to "how should this desk spend its search", because the two are different
#: questions and only the first is probabilistic.
#:
#: The desk's binding constraint is INDEPENDENCE (n_eff ~5.5 across 23 certificates). An
#: allocation that puts 95% of trials into one mechanism cannot produce an independent book no
#: matter how reliably that mechanism certifies. Expressing that as a cap keeps it visible and
#: auditable, where burying it in a fudged multiplier would leave the desk unable to say why it
#: explored what it explored.
MAX_FAMILY_SHARE = 0.20

#: EVERY known mechanism gets at least this share. Nothing is ever allocated zero.
#:
#: The first version zeroed seven families outright on "100+ attempts, zero certificates", and
#: called them CONFIDENTLY BARREN. That label was wrong, and the way it was wrong matters: those
#: attempts ran through a validator this desk has since found defective in at least four
#: independent ways -- costs charged at a pooled median instead of the hour each cell actually
#: fills, a forward lane whose clocks were restamped every cycle and could never reach day 14,
#: three verdict engines applying three different bars, and a missing module that blocked every
#: sleeve at once. A zero produced by a broken test is evidence about the test, not the
#: mechanism. LAWS L1.49: a gate that never properly ran is a claim the desk cannot cash.
#:
#: The deeper reason is that this desk's binding constraint is not yield, it is INDEPENDENCE
#: (n_eff ~5.5 across 23 certificates). Search that narrows toward whatever certified last
#: manufactures correlation -- it finds more of what the book already holds, worth close to
#: nothing, while the mechanisms that would actually diversify it go unvisited and therefore stay
#: unproven forever. A floor makes that impossible by construction.
MIN_FAMILY_SHARE = 0.02

#: Fallback base rate before any funnel has been read. Set to the desk's measured overall yield
#: so the module behaves identically on an empty artifact set rather than reverting to uniform.
DEFAULT_BASE_RATE = 0.0033

#: Stages a candidate passes through. The census counts each separately because they FAIL
#: DIFFERENTLY: a validity failure says the mechanism is wrong, a power failure says the sample
#: was small, and treating them as one number teaches the search the wrong lesson.
STAGES = ("candidates", "certified", "forward_enrolled", "forward_survived", "live")


@dataclass
class FamilyRecord:
    """One mechanism's whole funnel, plus what it costs to search."""

    family: str
    counts: dict[str, int] = field(default_factory=lambda: dict.fromkeys(STAGES, 0))
    #: Mean residual correlation of this family's certificates to the rest of the book. High
    #: means its survivors duplicate what the desk already holds.
    #: Beta prior for this family, set by `build` from the pooled base rate. Per-record rather
    #: than global so a caller can override it for one mechanism without a module-level mutation.
    prior_a: float = PRIOR_STRENGTH * DEFAULT_BASE_RATE
    prior_b: float = PRIOR_STRENGTH * (1.0 - DEFAULT_BASE_RATE)
    residual_corr: float | None = None
    #: Forward decay: certified expectancy minus realised forward expectancy, in R. Positive
    #: means the family looked better in the gauntlet than it turned out to be.
    forward_decay: float | None = None

    def denominator_known(self, stage: str = "certified") -> bool:
        """Is there a recorded count of ATTEMPTS for this stage?

        A family can have certificates and no recorded candidates, because not every generator
        writes to the same docket -- `dav_range_filter_adx` is certified through the qquant hunt,
        whose candidates never appear in `external_survivors.json`. Its pass rate is therefore
        not small, it is UNKNOWN, and those are different answers (LAWS L1.28a).

        Treating an absent denominator as zero attempts is how a family with one certificate and
        no docket scored a 67% pass rate and was allocated 637 of 1000 trials.
        """
        idx = STAGES.index(stage)
        if idx == 0:
            return True
        return self.counts.get(STAGES[idx - 1], 0) > 0

    def posterior(self, stage: str = "certified") -> tuple[float, float]:
        """Beta(a, b) over this family's pass rate INTO `stage` from the stage before it."""
        idx = STAGES.index(stage)
        prior_stage = STAGES[idx - 1] if idx > 0 else None
        trials = self.counts.get(prior_stage, 0) if prior_stage else 0
        passes = self.counts.get(stage, 0)
        # PASSES CANNOT EXCEED ATTEMPTS. Where they appear to, the docket is incomplete rather
        # than the family miraculous; clamping keeps the posterior coherent, and
        # `denominator_known` is what actually keeps such a family out of the allocation.
        trials = max(trials, passes)
        fails = max(0, trials - passes)
        return self.prior_a + passes, self.prior_b + fails

    def sample_rate(self, rng: random.Random, stage: str = "certified") -> float:
        """One Thompson draw from the pass-rate posterior."""
        a, b = self.posterior(stage)
        return rng.betavariate(a, b)

    def uncertainty(self, stage: str = "certified") -> float:
        """Posterior SD -- the information a further trial here could remove."""
        a, b = self.posterior(stage)
        return math.sqrt((a * b) / ((a + b) ** 2 * (a + b + 1.0)))


def _family_of(key: str, row: Any) -> str | None:
    """A row's family from the row ITSELF. Returns None rather than guessing.

    THE KEY IS NOT A FAMILY, and the first version of this function said so in its docstring and
    then parsed the key anyway as a fallback. The result was a census listing mechanisms named
    `5_wait_bars=8`, `json`, `asia#band=[0` and `FAILED_BREAK`, and an allocator that proposed
    spending 198 of 1000 trials on `5_wait_bars=8`. Sleeve keys carry symbols, sessions, regime
    conditions and parameter fragments in a shape that has already changed once; splitting on
    '.' finds whatever happens to sit in the third field.

    A row with no recorded family is UNATTRIBUTED and is counted as such. That is a real finding
    about the ledger -- a sleeve whose mechanism nothing records cannot be reasoned about -- and
    it is strictly better than a plausible-looking wrong answer that reaches a scheduler.
    """
    if isinstance(row, dict):
        # Every place a component ACTUALLY records the mechanism. Certificates carry it inside
        # `shadow_spec` (the block admission reads), forward rows inside `identity`, and some
        # write it flat. All three are recorded fields; none is a guess from the key.
        for container in (row, row.get("shadow_spec"), row.get("identity")):
            if isinstance(container, dict):
                fam = container.get("family")
                if fam:
                    return str(fam)
    return None


def build(base: Path) -> dict[str, FamilyRecord]:
    """Read the funnel from the artifacts each stage already writes.

    Deliberately NOT a new ledger. Every number here is derived from a file some other component
    writes for its own reasons, so the census cannot drift from reality by forgetting to record
    something -- it has nothing of its own to forget.
    """
    recs: dict[str, FamilyRecord] = defaultdict(lambda: FamilyRecord(family="?"))
    #: Rows whose mechanism nothing records. Reported, never guessed at -- see `_family_of`.
    unattributed: Counter[str] = Counter()

    def rec(fam: str) -> FamilyRecord:
        r = recs[fam]
        if r.family == "?":
            r.family = fam
        return r

    cand = base / "desks" / "mt5" / "data" / "hypotheses" / "external_survivors.json"
    if cand.exists():
        try:
            rows = json.loads(cand.read_text("utf-8"))
            for fam, n in Counter(h.get("family") for h in rows).items():
                if fam:
                    rec(str(fam)).counts["candidates"] = n
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    certs = base / "desks" / "mt5" / "reports" / "UNIVERSAL_SURVIVORS.json"
    if certs.exists():
        try:
            surv = json.loads(certs.read_text("utf-8")).get("survivors") or {}
            for key, row in surv.items():
                fam = _family_of(key, row)
                if fam:
                    rec(fam).counts["certified"] += 1
                else:
                    unattributed["certified"] += 1
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    shadow = base / "desks" / "mt5" / "reports" / "shadow"
    for name in ("shadow_state.json", "qquant_shadow_state.json",
                 "scalp_shadow_state.json", "external_shadow_state.json"):
        p = shadow / name
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = data.get("sleeves", data) if isinstance(data, dict) else {}
        for key, row in rows.items():
            fam = _family_of(key, row)
            if not fam or not isinstance(row, dict):
                unattributed["forward"] += 1
                continue
            r = rec(fam)
            r.counts["forward_enrolled"] += 1
            status = str(row.get("status") or "")
            if status in ("PROMOTION CANDIDATE", "PROMOTION_CANDIDATE", "PROMOTED"):
                r.counts["forward_survived"] += 1
            if status == "PROMOTED":
                r.counts["live"] += 1
    # FIT THE PRIOR TO WHAT THIS DESK ACTUALLY YIELDS, then apply it to every family. Computed
    # after all stages are counted so it reflects the whole funnel, not the first file read.
    tot_c = sum(r.counts.get("candidates", 0) for r in recs.values())
    tot_s = sum(r.counts.get("certified", 0) for r in recs.values())
    base_rate = (tot_s / tot_c) if tot_c > 0 else DEFAULT_BASE_RATE
    base_rate = min(max(base_rate, 1e-4), 0.5)  # never 0 (kills exploration) and never absurd
    for r in recs.values():
        r.prior_a = PRIOR_STRENGTH * base_rate
        r.prior_b = PRIOR_STRENGTH * (1.0 - base_rate)

    if unattributed:
        recs["__UNATTRIBUTED__"] = FamilyRecord(
            family="__UNATTRIBUTED__",
            counts={**dict.fromkeys(STAGES, 0),
                    "certified": unattributed.get("certified", 0),
                    "forward_enrolled": unattributed.get("forward", 0)})
    return dict(recs)


def saturation_penalty(r: FamilyRecord, book_certificates: int) -> float:
    """How much LESS a further certificate from this family is worth to the book.

    A STRUCTURAL PROXY FOR RESIDUAL CORRELATION, and named as one. The honest measure is the
    residual correlation of this family's return stream to the book's, which needs per-family
    forward series that most families here do not yet have. What IS available is the family's
    share of the existing book, and that share is a strong proxy: a mechanism supplying half the
    desk's certificates is, by construction, half of what any new certificate must diversify
    against.

    WHY THIS TERM DECIDES THE ALLOCATION. Without it the allocator is a yield-chaser. Measured
    2026-08-29 with marginal value stubbed to 1.0, it put 980 of 1000 trials into
    `session_range_breakout` -- the single most-mined family on the desk, holding 20 of 41
    certificates -- which is precisely the concentration that produced n_eff ~5.5 across 23
    certificates. Maximising certificate count and maximising the book are different objectives,
    and only this term tells them apart.

    1/(1+share) rather than (1-share): a dominant family is throttled hard but never to zero,
    because a mechanism being over-represented is a reason to stop PREFERRING it, not a reason to
    stop checking whether it still works.
    """
    if book_certificates <= 0:
        return 1.0
    share = r.counts.get("certified", 0) / book_certificates
    return 1.0 / (1.0 + 4.0 * share)


def research_value(r: FamilyRecord, rng: random.Random,
                   novelty: float = 1.0, marginal_value: float = 1.0) -> dict[str, Any]:
    """What one more trial in this mechanism is worth. Higher is better.

    A PRODUCT, not a weighted sum, and that is the whole design. A sum lets a family compensate
    for adding nothing to the portfolio by having a high pass rate -- which is precisely how a
    book ends up with twenty-three names and five and a half bets. Under a product, a mechanism
    that duplicates what the desk already owns is worth ~0 however reliably it certifies.
    """
    p = r.sample_rate(rng)                      # Thompson: explores the barely-tried
    info = r.uncertainty()                      # what a trial here would resolve
    decay_penalty = 1.0
    if r.forward_decay is not None and r.forward_decay > 0:
        # A family that certifies well and then decays forward has been telling the gauntlet
        # something untrue. Yield alone would keep rewarding it.
        decay_penalty = 1.0 / (1.0 + r.forward_decay)
    value = p * novelty * marginal_value * (1.0 + info) * decay_penalty
    return {"family": r.family, "value": value, "sampled_pass_rate": round(p, 5),
            "uncertainty": round(info, 5), "novelty": novelty,
            "marginal_value": marginal_value, "decay_penalty": round(decay_penalty, 4),
            "counts": dict(r.counts)}


def allocate(recs: dict[str, FamilyRecord], budget: int, *, seed: int,
             novelty: dict[str, float] | None = None,
             marginal: dict[str, float] | None = None) -> dict[str, int]:
    """Split `budget` trials across mechanisms by sampled research value.

    `seed` is REQUIRED rather than defaulted: an allocation that cannot be reproduced cannot be
    audited, and this decides where the desk spends its compute.
    """
    rng = random.Random(seed)  # noqa: S311
    novelty = novelty or {}
    # __UNATTRIBUTED__ is a defect report, not a mechanism; allocating trials to it would be
    # spending compute on a bookkeeping gap.
    # __UNATTRIBUTED__ is a defect report, not a mechanism; allocating trials to it would be
    # spending compute on a bookkeeping gap. A family with no recorded denominator is excluded
    # for the same reason -- its pass rate is unknown, and an unknown must not outrank a measured
    # one just because uncertainty flatters it.
    pool = [(f, r) for f, r in sorted(recs.items())
            if f != "__UNATTRIBUTED__" and r.denominator_known()]
    if not pool:
        return {}
    # DEFAULT MARGINAL VALUE IS SATURATION, NOT 1.0. A caller with real residual correlations
    # should pass them; absent that, stubbing this to 1.0 turns the allocator into a yield-chaser
    # and concentrates the book, so the structural proxy is the default rather than the fallback.
    book = sum(r.counts.get("certified", 0) for _, r in pool)
    marginal = dict(marginal or {})
    for f, r in pool:
        marginal.setdefault(f, saturation_penalty(r, book))

    # TRUE THOMPSON SAMPLING: one draw per CHUNK, each chunk to that draw's winner. The first
    # version drew once per family and split the budget proportionally, which is a different and
    # much worse algorithm -- it turns a single lucky draw into a permanent share. It gave
    # `calendar_month` 520 of 1000 trials on the strength of TWO attempts, because Beta(1, 3) can
    # sample high once and proportional scaling then treats that one sample as the answer.
    #
    # Redrawing per chunk lets a wide posterior win sometimes and lose usually, which is exactly
    # the exploration behaviour the posterior width is supposed to buy. A barely-tried family
    # gets a real share, not the whole desk.
    chunks = min(200, max(1, budget))
    per_chunk = budget / chunks
    tally: dict[str, float] = {f: 0.0 for f, _ in pool}
    for _ in range(chunks):
        best_f, best_v = None, float("-inf")
        for f, r in pool:
            v = research_value(r, rng, novelty.get(f, 1.0), marginal.get(f, 1.0))["value"]
            if v > best_v:
                best_f, best_v = f, v
        if best_f is not None:
            tally[best_f] += per_chunk
    # FLOOR FIRST, THEN CAP. The floor is reserved off the top so it cannot be competed away:
    # taking it out of the leftovers would let a dominant family win it back through the sampling
    # it already dominates, which is how a "guaranteed minimum" quietly becomes zero.
    floor = budget * MIN_FAMILY_SHARE
    reserved = floor * len(pool)
    if reserved >= budget:
        # More mechanisms than the floor can cover: spread the whole budget evenly. Breadth beats
        # depth here deliberately -- with this many unexplored axes the desk does not yet know
        # enough for depth to be the right call.
        share = budget / len(pool)
        return {f: round(share) for f, _ in pool if round(share) >= 1}

    cap = budget * MAX_FAMILY_SHARE
    for f in tally:
        tally[f] = floor + tally[f] * (budget - reserved) / budget

    overflow = 0.0
    for f, v in list(tally.items()):
        if v > cap:
            overflow += v - cap
            tally[f] = cap
    if overflow > 0:
        headroom = {f: cap - v for f, v in tally.items() if v < cap}
        room = sum(headroom.values())
        if room > 0:
            for f, h in headroom.items():
                tally[f] += overflow * h / room

    out = {f: round(v) for f, v in tally.items() if v >= 1}
    if not out:
        # Every draw scored zero: spread evenly rather than starving the search entirely,
        # because a desk that stops looking never finds out it was wrong.
        share = max(1, budget // len(pool))
        return {f: share for f, _ in pool}
    return out


def report(recs: dict[str, FamilyRecord], *, seed: int = 0) -> dict[str, Any]:
    """Human- and machine-readable census, ordered by where the next trial should go."""
    rng = random.Random(seed)  # noqa: S311
    # Rank only what is actually allocatable, and by the SAME rule `allocate` uses. A report that
    # ranked the excluded rows at the top -- because an unknown denominator flatters a posterior
    # -- would show a reader the opposite of what the scheduler is going to do.
    rankable = {f: r for f, r in recs.items()
                if f != "__UNATTRIBUTED__" and r.denominator_known()}
    scored = sorted((research_value(r, rng) for r in rankable.values()),
                    key=lambda s: -s["value"])
    total_cand = sum(r.counts.get("candidates", 0) for r in recs.values())
    total_cert = sum(r.counts.get("certified", 0) for r in recs.values())
    return {
        "families": len(recs), "rankable": len(rankable),
        "unattributed": dict(recs["__UNATTRIBUTED__"].counts) if "__UNATTRIBUTED__" in recs
        else {},
        "total_candidates": total_cand, "total_certified": total_cert,
        "overall_yield_pct": round(100.0 * total_cert / total_cand, 4) if total_cand else 0.0,
        "ranked": scored,
        # NOT "barren". These were attempted many times through a validator since found
        # defective in four independent ways; the zero describes the test, not the mechanism.
        # They keep their exploration floor and get re-tested, never written off.
        "unconfirmed_high_attempts": [s["family"] for s in scored
                                      if s["counts"].get("candidates", 0) >= 100
                                      and s["counts"].get("certified", 0) == 0],
        "no_denominator": sorted(f for f, r in recs.items()
                                 if f != "__UNATTRIBUTED__" and not r.denominator_known()),
        "barely_attempted": [s["family"] for s in scored
                            if s["counts"].get("candidates", 0) < 100
                            and s["counts"].get("certified", 0) == 0],
    }
