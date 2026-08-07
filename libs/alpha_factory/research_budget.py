"""FORCED-QUOTA RESEARCH ALLOCATION and SEARCH-SPACE COVERAGE -- keeping the sweep out of a rut.

A generator that allocates purely by what has worked converges on what has worked. That is correct
locally and fatal globally: the regions that produced survivors get re-searched until they are
exhausted, the rest of the space is never entered, and the desk mistakes a thoroughly-mined seam
for the whole mine. Forced quotas exist to make exploration non-negotiable rather than something
that survives only while nothing better is competing for the budget.

FIVE MODES, and each answers a different question:
    EXPLOITATION    mutate around things that survived              -- deepen a known seam
    RECOMBINATION   join two previously unrelated survivors         -- the cheapest real novelty
    EXPLORATION     enter cells of the space nothing has tested     -- the anti-rut term
    FALSIFICATION   actively attack the desk's own best current idea -- red team, on purpose
    WILDCARD        unconstrained                                   -- the term that pays rarely

THE PROPERTY THAT MATTERS MOST HERE IS NOT THE SPLIT. It is that **EXPLOITATION OF AN EMPTY
SURVIVOR SET IS AN EMPTY ACT.** This desk has 434 candidates and 0 survivors. An allocator that
hands 40% of the budget to "mutate around survivors" when there are none does not merely waste
40% -- it reports a full allocation while doing three fifths of the work, and the shortfall is
invisible because every percentage still sums to one. So the allocation is REBALANCED onto the
modes that can actually run, and the reason is carried in the result. Same failure as L1.50's
survivor clause: full exploitation of an empty set reported as compliance.

COVERAGE IS NOT KNOWLEDGE, AND THIS MODULE REFUSES TO CONFLATE THEM. A cell that was tested on
forty bars and a cell that was never tested are both "not known", and only one of them looks
tested. `coverage_report` therefore counts a cell as covered only when it was tested with at least
`min_n` observations, and reports the underpowered count separately rather than folding it into
either bucket. A coverage number that counts underpowered cells as covered is an instrument for
believing the space has been searched when it has been skimmed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

#: Default split. Sums to 1.0. Deliberately NOT equal-weighted: exploitation is the largest single
#: share because deepening a real seam is the highest-expected-value action WHEN a seam exists --
#: and the whole point of the floors below is that this share cannot eat the others when it does
#: not.
DEFAULT_QUOTAS: dict[str, float] = {
    "exploitation": 0.40,
    "recombination": 0.25,
    "exploration": 0.20,
    "falsification": 0.10,
    "wildcard": 0.05,
}

#: Hard floors, applied AFTER any dynamic reweighting. This is the anti-rut mechanism and it is the
#: reason the quotas are worth having at all: without floors, a run of exploitation success
#: reweights toward exploitation, which produces more exploitation success, which reweights
#: further -- and the desk optimises itself into a local maximum by a sequence of individually
#: correct decisions. A floor is not a preference; it is the refusal to let that loop close.
FLOORS: dict[str, float] = {"exploration": 0.10, "falsification": 0.05}

MODES: tuple[str, ...] = tuple(DEFAULT_QUOTAS)

#: Modes that need at least one survivor to mean anything. With none, they are unrunnable and
#: their budget must go somewhere that can run rather than being reported as allocated.
_NEEDS_SURVIVORS: frozenset[str] = frozenset({"exploitation", "recombination", "falsification"})


@dataclass(frozen=True)
class Allocation:
    """A budget split, with the arithmetic that produced it kept visible."""

    counts: dict[str, int]
    weights: dict[str, float]
    total: int
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def allocated(self) -> int:
        return sum(self.counts.values())


def _normalise(w: Mapping[str, float]) -> dict[str, float]:
    total = sum(max(0.0, float(v)) for v in w.values())
    if total <= 0.0:
        n = len(w) or 1
        return dict.fromkeys(w, 1.0 / n)
    return {k: max(0.0, float(v)) / total for k, v in w.items()}


def apply_floors(weights: Mapping[str, float], floors: Mapping[str, float] = FLOORS
                 ) -> dict[str, float]:
    """Raise any mode below its floor, then renormalise what is left over the others.

    Renormalising the REMAINDER rather than everything is the part that is easy to get wrong: a
    naive renormalise-all scales the floored modes back down again, so the floor silently does not
    hold. Pinned by test.
    """
    w = dict(_normalise(weights))
    floored = {k: v for k, v in floors.items() if k in w and w[k] < v}
    if not floored:
        return w
    reserved = sum(floored.values())
    if reserved >= 1.0:                      # floors alone exhaust the budget -- honour them only
        return _normalise(dict(floored))
    rest = {k: v for k, v in w.items() if k not in floored}
    rest_total = sum(rest.values())
    out = dict(floored)
    for k, v in rest.items():
        out[k] = (v / rest_total * (1.0 - reserved)) if rest_total > 0 else 0.0
    return out


def allocate(
    total: int,
    *,
    weights: Mapping[str, float] | None = None,
    n_survivors: int = 0,
    floors: Mapping[str, float] = FLOORS,
) -> Allocation:
    """Split `total` experiments across the five modes.

    `n_survivors` is not decoration. With zero survivors the survivor-dependent modes cannot run,
    and allocating to them would report a full budget while silently under-spending it. Their share
    is moved to the modes that CAN run and the move is recorded.

    Remainders from integer division go to EXPLORATION rather than to the largest share. Rounding
    is small, but every rounding rule is a standing bias, and a bias toward exploration is the one
    that cannot trap the desk in a rut.
    """
    if total < 0:
        raise ValueError("total must be non-negative")
    w = apply_floors(weights if weights is not None else DEFAULT_QUOTAS, floors)
    notes: list[str] = []

    if n_survivors <= 0:
        dead = {k: v for k, v in w.items() if k in _NEEDS_SURVIVORS and v > 0}
        if dead:
            live = {k: v for k, v in w.items() if k not in _NEEDS_SURVIVORS}
            if sum(live.values()) <= 0:      # nothing runnable at all -- say so, invent nothing
                notes.append(
                    "NO SURVIVORS and no survivor-independent mode has weight: the budget is "
                    "unallocatable. This is NOT MEASURED, not an empty result.")
                return Allocation(dict.fromkeys(w, 0), dict(w), total, tuple(notes))
            moved = sum(dead.values())
            w = {**dict.fromkeys(dead, 0.0),
                 **{k: v / sum(live.values()) * (sum(live.values()) + moved)
                    for k, v in live.items()}}
            notes.append(
                f"NO SURVIVORS (n=0): {moved:.0%} of the budget was assigned to "
                f"{sorted(dead)} -- modes that mutate, recombine or attack EXISTING survivors and "
                "therefore cannot run. Reassigned to exploration/wildcard. Reporting this as a "
                "full allocation would claim work that cannot happen.")

    counts = {k: int(total * v) for k, v in w.items()}
    leftover = total - sum(counts.values())
    if leftover:
        sink = "exploration" if w.get("exploration", 0.0) > 0 else max(w, key=lambda k: w[k])
        counts[sink] += leftover
    return Allocation(counts, w, total, tuple(notes))


@dataclass(frozen=True)
class CoverageReport:
    """What fraction of each search dimension has actually been tested WITH POWER."""

    by_dimension: dict[str, float]
    covered: dict[str, tuple[str, ...]]
    uncovered: dict[str, tuple[str, ...]]
    underpowered: int
    n_tested_cells: int

    @property
    def weakest(self) -> str:
        """The dimension to point the next batch at. Ties break alphabetically so the answer is
        deterministic -- a report that reorders between runs cannot be diffed."""
        if not self.by_dimension:
            return ""
        return min(sorted(self.by_dimension), key=lambda k: self.by_dimension[k])


def coverage_report(
    space_values: Mapping[str, Sequence[str]],
    tested: Sequence[Mapping[str, object]],
    *,
    min_n: int = 30,
    n_key: str = "n",
) -> CoverageReport:
    """Coverage per dimension, counting only cells tested with at least `min_n` observations.

    THE UNDERPOWERED BUCKET IS THE POINT. A cell tested on 8 bars taught the desk nothing, and if
    it counted as covered the report would say the space had been searched when it had been
    skimmed -- then `weakest` would point the next batch AWAY from the region that most needs it.
    Underpowered cells are excluded from coverage and counted separately, so the number is
    reported rather than absorbed.
    """
    covered: dict[str, set[str]] = {d: set() for d in space_values}
    underpowered = 0
    for row in tested:
        try:
            n = int(row.get(n_key, 0))  # type: ignore[call-overload]
        except (TypeError, ValueError):
            n = 0
        if n < min_n:
            underpowered += 1
            continue
        for dim in space_values:
            v = row.get(dim)
            if isinstance(v, str) and v:
                covered[dim].add(v)
    by_dim, cov, unc = {}, {}, {}
    for dim, values in space_values.items():
        uniq = tuple(dict.fromkeys(values))
        hit = tuple(v for v in uniq if v in covered[dim])
        by_dim[dim] = (len(hit) / len(uniq)) if uniq else 0.0
        cov[dim] = hit
        unc[dim] = tuple(v for v in uniq if v not in covered[dim])
    return CoverageReport(
        by_dimension=by_dim, covered=cov, uncovered=unc,
        underpowered=underpowered, n_tested_cells=len(tested) - underpowered,
    )


def gap_lines(report: CoverageReport) -> list[str]:
    """Human-readable gap report -- the thing an operator or a panel seat actually reads."""
    out = [f"{d:<12} {p:6.1%}   unexplored: "
           f"{', '.join(report.uncovered[d][:6]) or '(none)'}"
           for d, p in sorted(report.by_dimension.items())]
    out.append(f"{'':<12}          powered cells: {report.n_tested_cells}, "
               f"underpowered (EXCLUDED from coverage, not counted as tested): "
               f"{report.underpowered}")
    if report.weakest:
        out.append(f"WEAKEST DIMENSION: {report.weakest} -- point the next batch here")
    return out


#: Dimensions an exhaustion claim must account for. NOT a preference list -- it is the set of axes
#: along which "we tested everything" can be true of one and false of the rest, which is exactly how
#: the invalid inference is made. A desk that has swept every FEATURE PAIR at one horizon, in one
#: regime, with one operator family has exhausted a slice and nothing more.
EXHAUSTION_AXES: tuple[str, ...] = (
    "feature", "operator", "interaction_depth", "horizon", "regime",
    "asset", "transformation", "model", "cross_domain",
)

#: Coverage below which an axis cannot support an exhaustion claim. Deliberately short of 1.0:
#: demanding literal totality would make the claim unfalsifiable in the other direction, and a
#: region genuinely worked to 95% should be abandonable. Above this, saturation is arguable.
EXHAUSTION_BAR: float = 0.95


@dataclass(frozen=True)
class ExhaustionVerdict:
    """Whether 'there is nothing left to test here' survives contact with the coverage record."""

    accepted: bool
    scope: str
    unsupported: tuple[str, ...]
    missing_axes: tuple[str, ...]
    reasons: tuple[str, ...]


def exhaustion_claim(
    scope: str,
    coverage_by_axis: Mapping[str, float],
    *,
    bar: float = EXHAUSTION_BAR,
    axes: Sequence[str] = EXHAUSTION_AXES,
) -> ExhaustionVerdict:
    """EXHAUSTION IS A CLAIM REQUIRING EVIDENCE, NEVER A DEFAULT.

    `DIGGING_CHARTER` already holds this rule for the SOURCE hunt -- "treat 'no free source exists'
    as a claim requiring EVIDENCE... never a default" -- and scopes itself out of the hypothesis
    space by its own precision note. This is the same rule for HYPOTHESES, where the invalid
    inference is:

        "we tested every combination expressible from our current feature set"
        -> "there are no worthwhile hypotheses left"

    Those are not equivalent, and the gap between them is enormous. Four series -- price, volume,
    funding, open interest -- support levels, changes, ratios, ranks, z-scores, rolling
    distributions, acceleration, persistence, interactions, conditional and nonlinear and
    regime-dependent and cross-sectional and lead/lag and multi-horizon relationships, and
    combinations of all of those. A feature set is not a hypothesis space; it is the alphabet.

    THE CLAIM IS NOT ALWAYS WRONG, WHICH IS WHY THIS RETURNS A VERDICT RATHER THAN A REFUSAL. Ten
    thousand variants of RSI-plus-momentum genuinely add nothing, and a rule of "never stop
    generating" would burn the budget on a saturated seam forever. So the standard is not
    "exhaustion is impossible" but "exhaustion must be DEMONSTRATED, PER AXIS, AT A NAMED SCOPE".

    AN AXIS ABSENT FROM THE EVIDENCE IS NOT AN AXIS AT 100%. Silence is the most likely way this
    check gets defeated -- a caller submits the three axes it happens to measure, every one clears
    the bar, and the claim passes while interaction depth, cross-domain transfer and model class
    were never considered at all. Missing axes are reported separately from failing ones because
    they mean different things: one is unfinished work, the other is unexamined work.
    """
    reasons: list[str] = []
    have = {a: float(coverage_by_axis.get(a, 0.0)) for a in axes}
    missing = tuple(a for a in axes if a not in coverage_by_axis)
    weak = tuple(a for a in axes if a in coverage_by_axis and have[a] < bar)
    if missing:
        reasons.append(
            f"NOT EVIDENCED on {len(missing)} axis/axes: {', '.join(missing)}. An axis absent from "
            "the record is UNEXAMINED, not complete -- and submitting only the axes one happens to "
            "measure is the easiest way to pass this check without having done the work.")
    if weak:
        reasons.append(
            "BELOW THE BAR: " + ", ".join(f"{a}={have[a]:.0%}" for a in weak)
            + f" (bar {bar:.0%}). Coverage of a slice is not exhaustion of the space.")
    if not reasons:
        reasons.append(
            f"ACCEPTED for scope '{scope}': every axis evidenced at or above {bar:.0%}. This "
            "retires THIS REGION only -- it is not a statement about the hypothesis space, and it "
            "does not survive the arrival of a new feature, venue, regime or transformation, any "
            "of which reopens it.")
    return ExhaustionVerdict(
        accepted=not (missing or weak), scope=scope,
        unsupported=weak, missing_axes=missing, reasons=tuple(reasons),
    )
