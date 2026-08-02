"""ALPHA GENEALOGY, BREEDING, and THEORY INDUCTION -- three of the seven ancestor organs.

WHY BUILD THESE BEFORE THERE ARE ANCESTORS. The principal's argument, and it is correct: this is
furniture bought before moving in. The desk has 420 dead candidates and zero survivors, so a
lineage graph looks premature -- except that the 420 ALREADY have parentage (family, lens, seat,
generation), and the question "which ancestral lines produced anything" is answerable today and
becomes unanswerable later, because nobody records provenance retroactively. Every day these are
missing is a day of parentage written into a log nobody structured.

  ALPHA GENEALOGY -- LIVE. Descent with modification, recorded. The payoff is not sentiment: if
  one lens or one family produced 3 of 4 near-misses, generation effort belongs THERE, and a desk
  that cannot see its own lineage allocates generation uniformly over ground of wildly different
  fertility. Fertility here is measured against the region's OWN attempt count, so a family that
  got 200 attempts and 2 near-misses does not outrank one that got 6 and 2.

  ALPHA BREEDING -- LIVE, and the controls are the hard part. Crossover of two specs is trivial;
  what stops it degenerating is (a) an incest bound, because breeding two near-identical parents
  produces a child that is a paraphrase of both and consumes a gauntlet slot to prove it, and
  (b) parents must have EARNED breeding rights by getting somewhere, or the population converges
  on whatever the generator happens to emit most often.

  THEORY INDUCTION -- DORMANT until >=3 survivors share a mechanism class. Inducing "the general
  principle behind our edges" from zero edges is not induction, it is prose. It arms from a DATA
  condition and names it, like every other dormant organ here, so nobody has to remember.

Pure, dependency-free, reports only. No promotion authority: a bred child is a CANDIDATE and
enters the same funnel at the same bar as anything else.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field

__all__ = [
    "BREEDING_MIN_STAGE",
    "INCEST_MAX",
    "THEORY_MIN_SURVIVORS",
    "Lineage",
    "Specimen",
    "breed",
    "diversity",
    "effective_population",
    "fertility",
    "induce_theory",
    "lineage_report",
    "similarity",
]

#: Two parents more similar than this produce a paraphrase, not a child. Set from the desk's own
#: trivial-variation work: fingerprint overlap above ~0.7 is where "new hypothesis" stops meaning
#: anything and a gauntlet slot gets spent proving two spellings of one idea.
INCEST_MAX = 0.70

#: A parent must have reached at least this gate to breed. Breeding rights are EARNED: without
#: this the population converges on whatever the generator emits most often, which is a measure
#: of the generator's habits and not of the market.
BREEDING_MIN_STAGE = 3

#: Survivors sharing a mechanism class before theory induction arms. Three is the smallest number
#: that can distinguish a principle from a coincidence and a pair.
THEORY_MIN_SURVIVORS = 3


@dataclass(frozen=True)
class Specimen:
    """One hypothesis with its parentage. `stage` is the furthest gate it reached."""

    id: str
    family: str = ""
    mechanism: str = ""
    lens: str = ""
    terms: tuple[str, ...] = ()
    parents: tuple[str, ...] = ()
    generation: int = 0
    stage: int = 0                      # furthest gate reached; 11 = deployed
    survived: bool = False


def similarity(a: Specimen, b: Specimen) -> float:
    """Jaccard over terms, with mechanism and family folded in as terms.

    Terms rather than free text on purpose: two hypotheses phrased differently around the same
    mechanism and the same data are the same hypothesis, and a text-distance measure would score
    them as distant precisely because the wording differs.
    """
    def _bag(s: Specimen) -> set[str]:
        return set(s.terms) | {t for t in (s.mechanism, s.family) if t}

    sa, sb = _bag(a), _bag(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


@dataclass
class Lineage:
    """The descent graph. Append-only: a dead line is evidence, not clutter."""

    specimens: dict[str, Specimen] = field(default_factory=dict)

    def add(self, s: Specimen) -> None:
        self.specimens[s.id] = s

    def children(self, sid: str) -> list[Specimen]:
        return [s for s in self.specimens.values() if sid in s.parents]

    def ancestors(self, sid: str, *, _seen: set[str] | None = None) -> list[str]:
        """Transitive parentage. Cycle-guarded -- a malformed import that made a specimen its own
        ancestor would otherwise hang the report rather than raise."""
        seen = _seen if _seen is not None else set()
        out: list[str] = []
        for p in self.specimens.get(sid, Specimen(sid)).parents:
            if p in seen:
                continue
            seen.add(p)
            out.append(p)
            out.extend(self.ancestors(p, _seen=seen))
        return out

    def depth(self, sid: str) -> int:
        return len(self.ancestors(sid))


def fertility(lineage: Lineage, *, key: str = "family") -> list[dict]:
    """Which ancestral lines actually produce, RATE-ADJUSTED.

    THE ADJUSTMENT IS THE POINT. Ranking lines by raw survivor count hands the top spot to
    whichever line the generator emitted most of -- a measure of the generator's habits, not of
    the market. Rate-adjusting inverts that: a family with 6 attempts and 2 deep runs outranks one
    with 200 attempts and 2, which is the allocation a desk actually wants.

    A line with a single attempt is not evidence of fertility either way, so the score is shrunk
    toward the population mean by attempt count (a plain Beta-style shrink). Without it one lucky
    first attempt would look like the most fertile ground on the desk.
    """
    groups: dict[str, list[Specimen]] = defaultdict(list)
    for s in lineage.specimens.values():
        groups[getattr(s, key, "") or "unattributed"].append(s)

    total_deep = sum(1 for s in lineage.specimens.values() if s.stage >= BREEDING_MIN_STAGE)
    total_n = max(1, len(lineage.specimens))
    prior = total_deep / total_n
    out = []
    for name, members in groups.items():
        n = len(members)
        deep = sum(1 for s in members if s.stage >= BREEDING_MIN_STAGE)
        surv = sum(1 for s in members if s.survived)
        # shrink toward the population rate; k=5 pseudo-attempts, so a 1-attempt line cannot lead
        rate = (deep + prior * 5.0) / (n + 5.0)
        out.append({
            key: name,
            "n": n,
            "reached_stage": deep,
            "survivors": surv,
            "best_stage": max((s.stage for s in members), default=0),
            "fertility": round(rate, 4),
            "raw_rate": round(deep / n, 4) if n else 0.0,
        })
    return sorted(out, key=lambda d: (-d["fertility"], -d["n"]))


def lineage_report(lineage: Lineage) -> dict:
    """The whole graph, with the honest headline when there is nothing to be proud of yet."""
    n = len(lineage.specimens)
    survivors = [s for s in lineage.specimens.values() if s.survived]
    deep = [s for s in lineage.specimens.values() if s.stage >= BREEDING_MIN_STAGE]
    gens = [s.generation for s in lineage.specimens.values()] or [0]
    return {
        "specimens": n,
        "survivors": len(survivors),
        "reached_breeding_stage": len(deep),
        "max_generation": max(gens),
        "by_family": fertility(lineage, key="family")[:12],
        "by_lens": fertility(lineage, key="lens")[:12],
        # A GRAVEYARD-ONLY POPULATION HAS NO VARIANCE TO RANK. Every entry reached the gauntlet
        # and every entry died, so "reached_stage" is 100% everywhere and the ranking degenerates
        # into a shrunk count of attempts wearing the word "fertility". Reporting that as a
        # finding would point generation at whichever tag happens to be most common in a list of
        # FAILURES -- precisely backwards. Found by the first live run.
        "discriminating": len({s.stage for s in lineage.specimens.values()}) > 1 or bool(survivors),
        "note": ("EVERY SPECIMEN SHARES ONE STAGE AND NONE SURVIVED, so fertility has nothing to "
                 "rank on: the ordering below is a shrunk attempt-count, not a measure of which "
                 "ground pays. Acting on it would point generation at whichever tag is most "
                 "common in a list of FAILURES. Feed live candidates with real stages before "
                 "reading this ranking."
                 if len({s.stage for s in lineage.specimens.values()}) <= 1 and not survivors else
                 "zero survivors is a MEASUREMENT of the ground, not of this graph. With no "
                 "survivors, fertility ranks by how FAR lines got -- which is the only signal "
                 "available and is still strictly better than allocating generation uniformly."
                 if not survivors else
                 f"{len(survivors)} survivor(s): allocate generation toward their lines and "
                 "spawn second-order questions around them"),
    }


def _child_id(a: Specimen, b: Specimen, terms: tuple[str, ...]) -> str:
    h = hashlib.sha1("|".join(sorted({a.id, b.id}) + sorted(terms)).encode()).hexdigest()[:10]
    return f"X-{h}"


def breed(parents: list[Specimen], *, max_children: int = 20,
          incest_max: float = INCEST_MAX,
          min_stage: int = BREEDING_MIN_STAGE) -> dict:
    """Cross eligible parents into candidate offspring. Returns children AND every rejection.

    REJECTIONS ARE RETURNED, NOT DROPPED. "We bred 4 children" and "we bred 4 children from 190
    attempted pairings, 186 rejected as near-duplicates" describe completely different states of
    the population, and only the second tells the desk its parents have stopped being diverse.

    A child is a CANDIDATE. It carries no inherited credibility whatsoever: both parents reaching
    stage 5 says nothing about the child, and the funnel bar is identical to a freshly generated
    hypothesis. Inherited standing is exactly how a breeding programme launders a weak idea.
    """
    eligible = [p for p in parents if p.stage >= min_stage]
    children: list[Specimen] = []
    rejected: list[dict] = []
    seen: set[str] = set()

    for i, a in enumerate(eligible):
        for b in eligible[i + 1:]:
            sim = similarity(a, b)
            if sim > incest_max:
                rejected.append({"pair": [a.id, b.id], "similarity": round(sim, 3),
                                 "reason": "too similar -- the child would be a paraphrase of "
                                           "both and would spend a gauntlet slot proving it"})
                continue
            terms = tuple(sorted(set(a.terms) | set(b.terms)))
            cid = _child_id(a, b, terms)
            if cid in seen:
                continue
            seen.add(cid)
            children.append(Specimen(
                id=cid,
                family=a.family or b.family,
                mechanism=f"{a.mechanism} x {b.mechanism}".strip(" x"),
                lens=f"{a.lens}+{b.lens}".strip("+"),
                terms=terms,
                parents=(a.id, b.id),
                generation=max(a.generation, b.generation) + 1,
            ))
            if len(children) >= max_children:
                break
        if len(children) >= max_children:
            break

    capped = len(children) >= max_children
    total_pairs = len(eligible) * (len(eligible) - 1) // 2
    scanned = len(children) + len(rejected)
    return {
        "eligible_parents": len(eligible),
        "ineligible": len(parents) - len(eligible),
        "children": children,
        "rejected_pairings": rejected[:20],
        "n_rejected": len(rejected),
        # THE CAP TRUNCATES THE SCAN, and without saying so the rejection count is read as a
        # population measure when it is really "how far we got before stopping". 0 rejections out
        # of 24 children looks like a perfectly diverse pool and may mean 24 pairs were examined
        # out of 820. Found by the first live run over the graveyard.
        "pairs_scanned": scanned,
        "pairs_total": total_pairs,
        "scan_truncated": capped and scanned < total_pairs,
        "note": (f"{len(children)} candidate(s) from {len(eligible)} eligible parent(s); "
                 f"{len(rejected)} pairing(s) rejected as near-duplicates. Every child enters "
                 "the funnel at the FULL bar -- parentage confers no credibility, and inherited "
                 "standing is how a breeding programme launders a weak idea."),
        "diversity_warning": (
            "parents have converged: most pairings are near-duplicates, so breeding is now "
            "producing paraphrases. Widen generation before breeding again."
            if len(rejected) > 3 * max(1, len(children)) else ""),
        "scan_note": (
            f"stopped at the {max_children}-child cap after {scanned} of {total_pairs} possible "
            "pairings -- the rejection count above measures how far the scan got, NOT how "
            "diverse the pool is, and no diversity conclusion may be drawn from it"
            if capped and scanned < total_pairs else ""),
    }


def induce_theory(specimens: list[Specimen],
                  *, minimum: int = THEORY_MIN_SURVIVORS) -> dict:
    """DORMANT until enough survivors share a mechanism class. Arms from a data condition.

    "What is the general principle behind our edges, and what ELSE does it predict?" is the
    highest-leverage question a desk can ask -- one induced principle generates a family of
    predictions that no per-hypothesis search would have reached. It is also strictly
    unanswerable from zero survivors, and answering it anyway produces confident prose that reads
    exactly like a theory, which is worse than saying nothing.

    When it arms, it returns the shared terms as the CANDIDATE principle and the non-shared terms
    as the axes along which to look for the next prediction -- deliberately not a narrative. A
    narrative is what a model would supply, and it would supply one whether or not there is a
    principle there.
    """
    survivors = [s for s in specimens if s.survived]
    by_mech: dict[str, list[Specimen]] = defaultdict(list)
    for s in survivors:
        by_mech[s.mechanism or "unclassified"].append(s)
    ready = {m: g for m, g in by_mech.items() if len(g) >= minimum}
    if not ready:
        best = max((len(g) for g in by_mech.values()), default=0)
        return {
            "state": "DORMANT",
            "survivors": len(survivors),
            "largest_mechanism_class": best,
            "arms_at": minimum,
            "note": (f"no mechanism class has {minimum} survivors ({best} is the largest). "
                     "Inducing a principle from fewer is not induction, it is prose that reads "
                     "like a theory. Arms automatically from the specimen record."),
        }
    out = []
    for mech, group in sorted(ready.items(), key=lambda kv: -len(kv[1])):
        shared = set(group[0].terms)
        for s in group[1:]:
            shared &= set(s.terms)
        varying = sorted({t for s in group for t in s.terms} - shared)
        out.append({
            "mechanism": mech,
            "n_survivors": len(group),
            "invariant_terms": sorted(shared),
            "varying_terms": varying,
            "candidate_principle": (
                f"edges in '{mech}' persist where "
                f"{', '.join(sorted(shared)) or '<no shared term>'} holds, independently of "
                f"{', '.join(varying[:6]) or '<nothing observed to vary>'}"),
            "next_predictions": [
                f"the same invariant should hold under a NEW value of {v}" for v in varying[:5]],
            "caution": ("this is an induced pattern over a handful of survivors, not a proven "
                        "law. Its predictions are hypotheses and enter the funnel at the full "
                        "bar; the theory earns standing only if they survive."),
        })
    return {"state": "ACTIVE", "survivors": len(survivors), "theories": out}


def diversity(specimens: list[Specimen]) -> float:
    """Mean pairwise DISTANCE across a population. Falls as breeding converges.

    Reported as a number the caller can trend rather than a verdict: a population that stops
    diversifying is the failure mode of every breeding programme, and it arrives gradually.
    """
    if len(specimens) < 2:
        return 1.0
    sims = [similarity(a, b)
            for i, a in enumerate(specimens) for b in specimens[i + 1:]]
    return round(1.0 - (sum(sims) / len(sims)), 4) if sims else 1.0


def effective_population(specimens: list[Specimen]) -> float:
    """Distinct-lineage count discounted by similarity -- how many INDEPENDENT ideas are really
    in the pool. A population of 200 paraphrases has an effective size near 1, and a desk that
    counted 200 would believe it was exploring."""
    if not specimens:
        return 0.0
    d = diversity(specimens)
    return round(len(specimens) ** (d if d > 0 else 1e-9), 2) if d > 0 else 1.0
