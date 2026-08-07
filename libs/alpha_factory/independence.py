"""INDEPENDENT SURVIVORS, NOT SURVIVOR COUNT -- redefining the number the desk is trying to raise.

THE OBJECTIVE THIS CORRECTS. "Boost our survivor count" is the wrong target, and it is wrong in a
way that gets worse the harder you work at it. Twenty variants of one factor are not twenty
discoveries; they are one discovery counted twenty times, and a research programme rewarded on the
raw count will reliably produce exactly that -- because near-duplicates are the cheapest thing a
generator can make. The count goes up, the portfolio does not diversify, and the drawdown when the
single underlying mechanism fails is twenty times the size everyone thought it was.

    Alpha A: Sharpe 2.0, 95% correlated with an existing survivor -> almost no incremental value
    Alpha B: Sharpe 1.4, largely independent                       -> potentially far more valuable

WorldQuant BRAIN's submission process reportedly incorporates correlation against the existing
alpha pool for this reason. The desk has DSR, PBO, CPCV and a trial ledger -- every one of which
polices whether a candidate is REAL -- and nothing whatever that asks whether it is NEW.

WHY THIS BELONGS TO E[log wealth] RATHER THAN TO TIDINESS. Geometric growth depends on the
portfolio's variance, and correlated positions do not diversify it. Adding a 0.95-correlated
survivor raises gross exposure while barely moving portfolio variance downward -- it consumes
capital and risk budget to buy almost nothing. Independence is not an aesthetic preference about
the research library; it is the term that actually compounds.

**AND IT MUST NEVER BE USED TO ADMIT A CANDIDATE.** Independence is a REDUNDANCY filter applied
AFTER the statistical gates, never a substitute for them. A perfectly uncorrelated candidate that
failed DSR is noise that happens to be uncorrelated with the desk's other noise, and promoting it
because it is "diversifying" would be the softest possible bar wearing the vocabulary of rigour.
Order is: survive the gates, THEN ask whether it adds anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: Above this |correlation| to an existing survivor, a candidate is a variant rather than a
#: discovery. 0.7 is deliberately below the 0.9-0.95 that "obviously the same thing" suggests:
#: two strategies at 0.7 share roughly half their variance, and the half they share is the half
#: that will fail together. A permissive threshold here is how a "diversified" book turns out to
#: be one bet.
REDUNDANT_ABOVE: float = 0.7

#: Minimum overlapping observations before a correlation may be believed at all. A correlation
#: computed on 12 shared bars is noise with a decimal point, and it fails in BOTH directions --
#: it can hide a duplicate or manufacture a diversifier.
MIN_OVERLAP: int = 60


@dataclass(frozen=True)
class IndependenceVerdict:
    """Whether a candidate ADDS anything to the existing survivor set."""

    verdict: str                  # "INDEPENDENT" | "REDUNDANT" | "UNMEASURED"
    max_abs_corr: float | None
    nearest: str | None
    reason: str


def _aligned(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Common non-NaN support of two return series, aligned by position.

    Positional alignment is an ASSUMPTION and callers must satisfy it: two series on different
    bar grids compared positionally produce a correlation about the misalignment, not the
    strategies. Documented rather than silently handled, because silently resampling here would
    hide a caller's bug inside a number nobody would question.
    """
    n = min(a.size, b.size)
    a, b = a[-n:], b[-n:]
    ok = ~(np.isnan(a) | np.isnan(b))
    return a[ok], b[ok]


def pairwise_corr(a: np.ndarray, b: np.ndarray, *, min_overlap: int = MIN_OVERLAP) -> float | None:
    """Pearson correlation on the common support, or None when it cannot be believed.

    None means NOT MEASURED and must never be rendered as 0.0. A zero correlation reads as
    "independent" -- the most flattering possible reading -- so an unmeasurable pair defaulting to
    zero would admit every duplicate whose overlap happened to be short (L1.28a).
    """
    x, y = _aligned(np.asarray(a, dtype=float), np.asarray(b, dtype=float))
    if x.size < min_overlap or float(np.std(x)) == 0.0 or float(np.std(y)) == 0.0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def assess(candidate: np.ndarray, survivors: dict[str, np.ndarray], *,
           threshold: float = REDUNDANT_ABOVE,
           min_overlap: int = MIN_OVERLAP) -> IndependenceVerdict:
    """Does `candidate` add anything the existing survivors do not already have?

    ABSOLUTE correlation, not signed: a candidate at -0.9 to an existing survivor is the same bet
    inverted. It carries no new information, and holding both is a hedge that costs two sets of
    fees to express approximately nothing.

    AN EMPTY SURVIVOR SET RETURNS INDEPENDENT, and that is honest rather than generous -- with
    nothing to be redundant against, the first survivor is independent by definition. It is also
    the desk's current state, so this branch is the live one.
    """
    if not survivors:
        return IndependenceVerdict(
            "INDEPENDENT", None, None,
            "no existing survivors -- the first is independent by definition, and this says "
            "nothing about its quality (the gates decide that)")

    worst_name, worst = None, -1.0
    unmeasured = []
    for name, series in survivors.items():
        c = pairwise_corr(candidate, series, min_overlap=min_overlap)
        if c is None:
            unmeasured.append(name)
            continue
        if abs(c) > worst:
            worst, worst_name = abs(c), name

    if worst < 0.0:
        return IndependenceVerdict(
            "UNMEASURED", None, None,
            f"no pair had {min_overlap}+ overlapping observations ({len(unmeasured)} survivor(s) "
            "unmeasurable). This is NOT independence -- it is an inability to check, and treating "
            "it as independence would admit a duplicate whose overlap happened to be short.")

    if worst >= threshold:
        return IndependenceVerdict(
            "REDUNDANT", worst, worst_name,
            f"|corr| {worst:.2f} to '{worst_name}' at or above {threshold:.2f}: a variant, not a "
            "discovery. Two series this close share the variance that will fail together, so the "
            "second adds gross exposure without adding diversification.")

    note = (f"|corr| {worst:.2f} to nearest ('{worst_name}'), below {threshold:.2f}")
    if unmeasured:
        note += (f" -- BUT {len(unmeasured)} survivor(s) could not be compared "
                 f"({', '.join(unmeasured[:3])}); the verdict rests on a partial pool")
    return IndependenceVerdict("INDEPENDENT", worst, worst_name, note)


@dataclass(frozen=True)
class DiversityReport:
    """The number the desk should actually be raising."""

    n_survivors: int
    n_independent: int
    clusters: tuple[tuple[str, ...], ...]
    unmeasured_pairs: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def headline(self) -> str:
        return (f"{self.n_independent} INDEPENDENT mechanism(s) across {self.n_survivors} "
                f"survivor(s)")


def cluster(survivors: dict[str, np.ndarray], *, threshold: float = REDUNDANT_ABOVE,
            min_overlap: int = MIN_OVERLAP) -> DiversityReport:
    """Group survivors into correlation clusters; the CLUSTER COUNT is the real discovery count.

    Single-linkage on |corr| >= threshold, chosen deliberately over a tighter linkage: single
    linkage merges A and C when both merely touch B, which is CONSERVATIVE for this purpose --
    it reports FEWER independent mechanisms. Every other choice here would flatter the number, and
    the number exists to be honest rather than encouraging.

    UNMEASURABLE PAIRS ARE COUNTED AND REPORTED. Two survivors that could not be compared are
    treated as separate clusters (they might be), so the independent count is an UPPER BOUND
    whenever `unmeasured_pairs` is non-zero -- and the report says so rather than leaving the
    reader to assume the pool was fully checked.
    """
    names = sorted(survivors)
    parent = {n: n for n in names}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    unmeasured = 0
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            c = pairwise_corr(survivors[a], survivors[b], min_overlap=min_overlap)
            if c is None:
                unmeasured += 1
                continue
            if abs(c) >= threshold:
                parent[find(a)] = find(b)

    groups: dict[str, list[str]] = {}
    for n in names:
        groups.setdefault(find(n), []).append(n)
    clusters = tuple(tuple(sorted(v)) for v in groups.values())

    notes = []
    if unmeasured:
        notes.append(
            f"{unmeasured} pair(s) had under {min_overlap} overlapping observations and were "
            "treated as SEPARATE clusters. The independent count is therefore an UPPER BOUND: "
            "some of those pairs may be duplicates nobody could see.")
    if len(clusters) < len(names):
        notes.append(
            f"{len(names)} survivors collapse to {len(clusters)} mechanism(s) -- the difference is "
            "the count the desk would have reported as discoveries.")
    return DiversityReport(len(names), len(clusters), clusters, unmeasured, tuple(notes))
