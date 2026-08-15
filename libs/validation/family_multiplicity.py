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
become the free parameter. `FAMILIES` below is fixed here, dated, and a name that matches none of
them lands in UNCLASSIFIED, which is deliberately the LARGEST cohort rather than a free pass.
"""

from __future__ import annotations

from statistics import NormalDist

__all__ = [
    "FAMILIES",
    "UNCLASSIFIED",
    "bh_alpha",
    "bh_bar",
    "effective_m",
    "family_error_budget",
    "family_of",
    "matches",
    "partition",
]

#: Pre-declared families, fixed 2026-08-15 before any candidate was assigned to one. Each is a
#: distinct QUESTION about why an edge exists, which is the only partition that justifies separate
#: error control -- splitting by symbol or by timeframe would be slicing one question, and the
#: correction would then be evaded rather than applied.
FAMILIES: dict[str, tuple[str, ...]] = {
    # why: someone is PAID to hold the other side (funding, basis, carry)
    "carry": ("funding", "carry", "basis", "perpdex", "cashcarry"),
    # why: capital is FORCED to move (liquidations, flows, supply, reserves)
    "flow": ("liquidation", "flow", "supply", "reserve", "walcl", "stablecoin", "obi", "cvd",
             "oi_divergence", "ls_contrarian"),
    # why: a price relationship is mechanically linked (cross-venue, cross-asset, premium)
    "relative_value": ("crossasset", "cross_asset", "premium", "cny", "kimchi", "ethbtc",
                       "rotation"),
    # why: participants behave predictably at structure (levels, breakouts, ranges)
    # `opening_range` added 2026-08-15 as a SPELLING of `orb`, not a new member: the rule the token
    # was declared to catch is named H9_opening_range and the abbreviation never matched it. The
    # move TIGHTENS that rule's bar (structure is the largest family), so it cannot be a partition
    # chosen to flatter -- the forking-paths hazard only runs in the other direction.
    "structure": ("trend", "momentum", "breakout", "wyckoff", "ict", "vwap", "band", "orb",
                  "opening_range", "compression", "supply_demand", "structural"),
    # why: on-chain or protocol mechanics (utilisation, defi, gas)
    "onchain": ("defi", "utilisation", "onchain", "gas"),
}

#: Where a name that matches no declared family lands. NOT a free pass: unclassified candidates
#: share ONE cohort, so an un-named mechanism pays the full multiplicity of every other un-named
#: one. That asymmetry is deliberate -- declaring the family is the work, and skipping it must not
#: be the cheaper path.
UNCLASSIFIED = "unclassified"


def matches(name: str) -> list[str]:
    """Every declared family this name matches. Usually one; occasionally more, and that matters."""
    low = str(name).lower()
    return sorted(fam for fam, toks in FAMILIES.items() if any(t in low for t in toks))


def family_of(name: str, cohort: list[str] | None = None) -> str:
    """The declared family for a candidate name, or UNCLASSIFIED.

    AMBIGUITY RESOLVES TOWARD THE TIGHTER BAR, NEVER TOWARD DICT ORDER. A real name from the live
    cohort -- `full_sweep_cross_asset_lead_1h_all_decay_breakout_decay_momentum` -- matches BOTH
    `relative_value` (cross_asset) and `structure` (breakout, momentum). First-match-wins would
    have assigned it by the declaration order of a dict literal, which is an invisible dependency
    deciding a real statistical threshold.

    When `cohort` is given, an ambiguous name joins the LARGEST matching family, so it pays the
    HIGHER multiplicity. That is the only safe direction: a candidate that might belong to two
    questions must not get the cheaper bar by accident of spelling. Without a cohort the tie
    breaks alphabetically, which is arbitrary but at least stated and stable.

    Substring matching on a fixed, pre-declared token list. Deliberately not clever: a classifier
    that inferred families from returns would assign them AFTER seeing the data, which is the one
    thing the partition may never do.
    """
    hits = matches(name)
    if not hits:
        return UNCLASSIFIED
    if len(hits) == 1 or cohort is None:
        return hits[0]
    sizes = {f: sum(1 for n in cohort if f in matches(n)) for f in hits}
    return max(hits, key=lambda f: (sizes[f], f))


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
