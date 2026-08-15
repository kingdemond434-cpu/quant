"""EFFECTIVELY UNLIMITED FORWARD SEATS, WITHOUT LOOSENING A SINGLE BAR.

THE PROBLEM, MEASURED 2026-08-15. The cohort holds 13 clocks against `MAX_FORWARD_SLOTS = 12` with
zero free, so a new candidate waits ~90 days for a seat and then runs a 90-day clock: 181 days to a
first promotion. Breadth is the only route to a higher combined Sharpe -- S = s*sqrt(k) for k
uncorrelated sleeves -- so the seat queue is the binding constraint on the desk's entire objective.

THE OBVIOUS FIX IS THE WRONG ONE. Raising the cap to 50 puts 50 candidates in ONE Holm cohort, and
Holm's strongest bar is alpha/m: at m=12 that is a t of 2.87, at m=50 it is 3.29. Every existing
candidate's bar tightens because a new, unrelated one started. That is not a rule being obeyed, it
is a real cost paid by real hypotheses, and it is why the cap has held.

**WHAT ACTUALLY CONTROLS THE ERROR RATE IS THE FAMILY, NOT THE SEAT COUNT.** Simultaneous inference
corrects across hypotheses tested TOGETHER as one question. A funding-carry candidate and a
market-structure candidate are not one question; forcing them into a single cohort makes each pay
for the other's trials while answering nothing about either. Partitioning into pre-declared
families, each carrying its own m, is standard practice and it is not a loophole -- it is what the
correction was always for.

Under partition, a new clock in the FLOW family costs the MOMENTUM family exactly nothing. Seats
become per-family, families can be added, and the total is bounded only by how many genuinely
distinct questions the desk can ask. That is the "unlimited" that is real.

**AND THE COST IS STATED, BECAUSE THERE IS ONE.** FWER within each of F families does NOT control
FWER across all of them: with F families each at alpha, the chance of at least one false positive
somewhere approaches 1 - (1-alpha)^F. At F=4, alpha=0.05, that is 18.5% rather than 5%. The desk
does not get more discoveries for free; it gets them at a stated, bounded, per-family error rate
instead of a single global one that throttles breadth. `family_error_budget` prints that number
rather than leaving it to be discovered later.

**FAMILIES ARE DECLARED BEFORE THE DATA, LIKE EVERY OTHER TERM.** A family assigned after seeing
which candidates look good is a garden of forking paths with extra steps -- the partition would
become the free parameter. A name the taxonomy cannot place lands in UNCLASSIFIED, which is
deliberately never cheaper than the largest declared cohort rather than a free pass.

**THE TAXONOMY IS THE CENSUS'S, NOT THIS MODULE'S.** The first version declared five families from
a hand-written token list, beside `libs/research/mechanism_census.TAXONOMY` -- 26 classes, each
with a named PAYER, an economic definition, signature vocabulary, and a declared orthogonality,
already used to rank the desk's research agenda. Two taxonomies answering "why does this edge
exist" are two answers, and the one nobody maintains is the one that quietly disagrees. This module
now classifies through the census and holds only the multiplicity arithmetic.

**A CLASS EARNS ITS OWN ERROR BUDGET BY BEING A SEPARATE QUESTION, AND THE CENSUS ALREADY SCORES
THAT.** Partitioning is only legitimate between hypotheses that are not one question in disguise --
so classes the census itself declares as barely orthogonal (`price_continuation` 0.03,
`market_risk_premium` 0.05, `liquidity_provision_immediacy` 0.1) do NOT get separate cohorts. They
share one, because eleven price-pattern variants are one question however many names they carry.
The same number then governs both halves of the desk's growth arithmetic: a family that does not
add breadth does not get its own seats either.
"""

from __future__ import annotations

from statistics import NormalDist

from libs.research.mechanism_census import CLASS_BY_ID, classify

__all__ = [
    "CORRELATED_CORE",
    "ORTHOGONALITY_FLOOR",
    "UNCLASSIFIED",
    "bh_alpha",
    "bh_bar",
    "effective_m",
    "family_error_budget",
    "family_of",
    "partition",
]

#: Where a name the census cannot place lands. NOT a free pass: unclassified candidates share ONE
#: cohort and `effective_m` floors it at the largest declared family, so an un-named mechanism pays
#: the worst bar on the desk. That asymmetry is deliberate -- declaring the mechanism is the work,
#: and skipping it must never be the cheaper path.
UNCLASSIFIED = "unclassified"

#: The shared cohort for census classes that are barely orthogonal. Separate error control is only
#: justified between separate QUESTIONS; a class the census scores at 0.03 is the promiscuous
#: price-only vocabulary that most of the desk's history already lives in, and giving it its own
#: seat pool would manufacture breadth by renaming.
CORRELATED_CORE = "correlated_core"

#: Declared orthogonality at or above which a census class carries its own multiplicity cohort.
#:
#: THIS IS A THRESHOLD ON NUMBERS THE CENSUS PUBLISHED LONG BEFORE THIS COHORT EXISTED, which is
#: what keeps it from being a free parameter fitted to today's candidates. It is fixed here, dated
#: 2026-08-15, and changing it changes real statistical bars -- so it moves by a ledgered decision
#: or not at all. Raising it merges families (fewer seats, tighter bars); lowering it splits them
#: (more seats, higher global FWER), and `family_error_budget` prices that in both directions.
ORTHOGONALITY_FLOOR = 0.35


def family_of(name: str, cohort: list[str] | None = None) -> str:
    """The census class this candidate belongs to, or CORRELATED_CORE / UNCLASSIFIED.

    `cohort` is accepted and ignored: it existed to break ties between hand-written token families,
    and the census resolves ambiguity itself -- most matched signatures wins, ties by taxonomy
    priority, so a specific economic vocabulary always outbids the promiscuous price-only one. The
    parameter stays because callers pass it; the tie-break it used to drive is gone with the token
    list that needed it.

    The name is passed as BOTH text and construction id, so an explicit `CONSTRUCTION_CLASS` entry
    short-circuits keyword matching. An implementation beats a keyword every time -- that is the
    census's own rule, and it is how the eleven discretionary rules are placed.
    """
    del cohort
    cls_id, _ = classify(str(name), construction=str(name))
    if cls_id is None:
        return UNCLASSIFIED
    cls = CLASS_BY_ID.get(cls_id)
    if cls is None or cls.orthogonality < ORTHOGONALITY_FLOOR:
        return CORRELATED_CORE
    return cls_id


def partition(names: list[str]) -> dict[str, list[str]]:
    """Cohort -> {family: members}. The m each candidate is corrected against is the size of ITS
    family, not of the whole desk."""
    out: dict[str, list[str]] = {}
    for n in names:
        out.setdefault(family_of(n, names), []).append(str(n))
    return out


def effective_m(parts: dict[str, list[str]]) -> dict[str, int]:
    """Family -> the m each member is actually corrected against. NOT simply the family size.

    **UNCLASSIFIED IS FLOORED AT THE LARGEST DECLARED FAMILY, AND THIS IS THE WHOLE POINT.** The
    header promises that skipping the declaration is never the cheaper path, and plain `len()` did
    not deliver it: measured on the live cohort, UNCLASSIFIED held two members against `structure`'s
    eight, so an undeclared mechanism faced t=1.96 while a declared one faced t=2.50. Left alone,
    the dominant strategy is to name your candidate something the token list cannot match -- the
    partition would have quietly become opt-out, and the incentive runs the wrong way at exactly
    the moment a new mechanism arrives.

    A declared family is corrected against its own members, which is what partitioning is for.
    UNCLASSIFIED is corrected against the worst bar on the desk, which is what a refusal to declare
    should cost. The floor never LOOSENS a bar -- it is a max, so it can only tighten.
    """
    sizes = {fam: len(members) for fam, members in parts.items()}
    declared_max = max((n for fam, n in sizes.items() if fam != UNCLASSIFIED), default=0)
    if UNCLASSIFIED in sizes:
        sizes[UNCLASSIFIED] = max(sizes[UNCLASSIFIED], declared_max)
    return sizes


def bh_alpha(m: int, rank: int, *, alpha: float = 0.05) -> float:
    """Benjamini-Hochberg threshold for the rank-th of m (rank 1 = strongest).

    FDR, NOT FWER, AND THE DIFFERENCE IS THE WHOLE POINT AT SCALE. Holm controls the probability of
    ANY false positive and pays for it with alpha/m at the top -- at m=50 the strongest candidate
    needs a t of 3.29, which throws away real edges to avoid one false one. BH controls the
    expected PROPORTION of discoveries that are false, so its bar is alpha*rank/m: the k-th
    discovery is judged against how many discoveries are being made, not against the whole cohort.

    For a desk whose objective is GROWTH rather than publication, FDR is the correct instrument: a
    portfolio of twenty edges of which two are false compounds better than a portfolio of three
    that are certainly real. That is a stated risk preference and it belongs beside the number,
    which is why both bars are reported and neither silently replaces the other.
    """
    m = max(1, int(m))
    r = min(max(1, int(rank)), m)
    return alpha * r / m


def bh_bar(m: int, rank: int = 1, *, alpha: float = 0.05) -> float:
    """One-sided t threshold under BH. Same shape as `forward_stats.holm_bar` so the two are
    directly comparable at a call site."""
    return round(NormalDist().inv_cdf(1.0 - bh_alpha(m, rank, alpha=alpha)), 2)


def family_error_budget(n_families: int, *, alpha: float = 0.05) -> dict[str, float | str]:
    """What partitioning costs, computed rather than asserted.

    Per-family FWER control does NOT give global FWER control. Across F independent families each
    at alpha, the probability of at least one false positive somewhere is 1-(1-alpha)^F. This is
    the honest price of unlimited seats, and it is bounded, small at realistic F, and enormously
    cheaper than the alternative -- which is not "no false positives", it is "no breadth".
    """
    f = max(1, int(n_families))
    global_fwer = 1.0 - (1.0 - alpha) ** f
    return {
        "n_families": f, "alpha_per_family": alpha,
        "global_fwer": round(global_fwer, 4),
        "why": (f"{f} families each controlled at {alpha:.0%} gives a {global_fwer:.1%} chance of "
                "at least one false positive somewhere on the desk, against "
                f"{alpha:.0%} under one global cohort. That is the price of partitioning and it "
                "buys unlimited seats per family. It is NOT free and it is NOT hidden"),
    }
