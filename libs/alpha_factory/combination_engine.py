"""COMBINATORIAL HYPOTHESIS GENERATION -- widening the mouth of a funnel wide everywhere else.

THE MEASURED GAP THIS CLOSES. `HypothesisEngine.generate` walks a fixed `_TEMPLATES` dict and can
emit, in total, across every category, **seven** hypotheses built from **thirteen** features. That
is not a throttle that can be turned up; it is the entire reachable space, and it never grows
unless a human writes a new template by hand.

Everything DOWNSTREAM of it is built for a large stream and is being fed seven items:
`hypothesis_novelty` does Jaccard de-duplication against priors, `idea_ranking_engine` and
`research_allocator` rank and budget, `alpha_family_tree` and `strategy_similarity_engine` track
lineage and redundancy, `libs/discovery/` carries monte-carlo survival, parameter stability and
fragility, and the validation layer carries DSR, PBO and CPCV. A desk with that apparatus and a
seven-item generator is not exploration-limited by its statistics. It is limited at the mouth.

WHAT THIS IS AND, MORE IMPORTANTLY, WHAT IT IS NOT.

This is a CANDIDATE ENUMERATOR. It emits the cross-product of (feature x feature x operator x
horizon x regime) as structured, testable statements. It confers NO belief. A generated
combination is a thing to test, and by construction most of them are noise -- which is the point:
the desk's edge is not in guessing well, it is in testing many and killing fast. Nothing here
promotes, sizes, or scores an edge.

**IT MULTIPLIES THE TRIAL COUNT, AND THAT IS A COST, NOT ONLY A BENEFIT.** Every combination
emitted is a trial that must be paid for in the multiple-testing deflation the desk already
applies -- the sqrt(2 ln N) hurdle, DSR, PBO. Generating 10,000 candidates and testing them all
against an undeflated bar would manufacture survivors out of pure noise, and would do it very
efficiently. So this module reports `n_trials` as a first-class field of its output: the number is
an INPUT TO THE DEFLATION, not a productivity metric, and any caller reporting "we generated
10,000 hypotheses" without carrying that number into its hurdle has used this module to
manufacture false discoveries faster.

THE HONEST LIMIT ON WHAT THIS BUYS. A cross-product is a SYSTEMATIC search of a space someone
still had to choose. It cannot invent a feature nobody supplied, and widening the generator does
not widen the data: the desk's binding constraint remains 16,560 pre-registered trials with zero
run, blocked on research data that does not reach an analysis clone. This module makes the funnel
mouth match the funnel; it does not fill the funnel.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field

from libs.alpha_factory.models import AlphaCategory, Hypothesis
from libs.core.ids import generate_id

#: Relations between two features. Each is a genuinely different economic claim, not a restatement:
#: an INTERACTION says the pair must co-occur, a CONDITION says one gates the other (and is
#: DIRECTIONAL -- `a` gated by `b` is a different hypothesis from `b` gated by `a`), a DIVERGENCE
#: says they disagree, a RATIO says the scale-free quotient carries the signal, and a LEAD says one
#: predicts the other's future value.
OPERATORS: tuple[str, ...] = ("interaction", "condition", "divergence", "ratio", "lead")

#: Operators for which (a, b) and (b, a) are DIFFERENT hypotheses. Everything else is symmetric and
#: emitting both orderings would double the trial count while adding no information -- which is the
#: worst possible trade, because the duplicate still costs deflation.
_DIRECTIONAL: frozenset[str] = frozenset({"condition", "divergence", "ratio", "lead"})

#: Bar horizons. Kept short and economically distinct rather than a dense grid: a grid over
#: horizons is the classic way to turn one hypothesis into fifty correlated ones, pay the deflation
#: for fifty, and learn what the one would have told you.
HORIZONS: tuple[str, ...] = ("1h", "4h", "1d", "1w")

#: Regime conditioning. `all` is the unconditional case and MUST be present -- a space in which
#: every hypothesis is regime-conditioned has no control, and "it works in regime X" is not
#: falsifiable without "it does not work unconditionally" to compare against.
REGIMES: tuple[str, ...] = ("all", "high_vol", "low_vol", "trending", "ranging")


@dataclass(frozen=True)
class Combination:
    """One enumerated candidate. Structured so the statement is DERIVED, never hand-written.

    The parts are kept as fields rather than baked into prose because every downstream consumer
    wants a different projection: novelty scoring wants the feature set, the family tree wants the
    category, a backtest wants the horizon and regime. A generator that emitted only a sentence
    would force every one of them to parse English back into structure.
    """

    category: str
    left: str
    right: str
    operator: str
    horizon: str
    regime: str

    @property
    def features(self) -> list[str]:
        return [self.left, self.right]

    @property
    def statement(self) -> str:
        """A falsifiable sentence. Phrased as a CLAIM ABOUT PREDICTION, never as a description --
        'X is high when Y is high' is a correlation nobody can trade or refute cleanly."""
        where = "" if self.regime == "all" else f" in {self.regime.replace('_', '-')} regimes"
        verb = {
            "interaction": f"{self.left} and {self.right} jointly predict",
            "condition": f"{self.left} predicts, conditioned on {self.right},",
            "divergence": f"divergence between {self.left} and {self.right} predicts",
            "ratio": f"the ratio of {self.left} to {self.right} predicts",
            "lead": f"{self.left} leads {self.right} and predicts",
        }[self.operator]
        return f"{verb} forward returns over {self.horizon}{where}"

    @property
    def key(self) -> tuple[str, ...]:
        """Identity for de-duplication. For SYMMETRIC operators the pair is sorted, so (a,b) and
        (b,a) collapse to one key -- without this the same claim is enumerated twice and paid for
        twice in the multiple-testing hurdle."""
        pair = (self.left, self.right)
        if self.operator not in _DIRECTIONAL:
            pair = tuple(sorted(pair))  # type: ignore[assignment]
        return (self.category, self.operator, self.horizon, self.regime, *pair)


@dataclass(frozen=True)
class CombinationSpace:
    """The enumerated space plus the number that must reach the deflation."""

    combinations: tuple[Combination, ...]
    n_trials: int
    features_used: tuple[str, ...]
    truncated: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __len__(self) -> int:
        return len(self.combinations)


def _pairs(features: Sequence[str], operator: str) -> Iterator[tuple[str, str]]:
    """Ordered pairs for directional operators, unordered for symmetric ones. A feature is never
    paired with itself: `x` interacting with `x` is `x`, and it would consume a trial to say so."""
    if operator in _DIRECTIONAL:
        return ((a, b) for a, b in itertools.permutations(features, 2))
    return iter(itertools.combinations(features, 2))


def enumerate_space(
    features: Sequence[str],
    *,
    category: AlphaCategory | str = AlphaCategory.CROSS_ASSET,
    operators: Sequence[str] = OPERATORS,
    horizons: Sequence[str] = HORIZONS,
    regimes: Sequence[str] = REGIMES,
    limit: int = 0,
) -> CombinationSpace:
    """Enumerate every distinct (pair x operator x horizon x regime) candidate.

    `limit=0` is UNBOUNDED, matching the desk's standing position that research generation carries
    no throttle (a cap on what may even be SURFACED throttles conversion before work begins). A
    non-zero limit truncates and SAYS SO in the result, because a silently-truncated space would
    make `n_trials` understate the search that was actually performed -- which is the one error
    here that biases toward false discovery rather than away from it.
    """
    cat = category.value if isinstance(category, AlphaCategory) else str(category)
    uniq = tuple(dict.fromkeys(f for f in features if f))     # order-preserving dedupe
    seen: set[tuple[str, ...]] = set()
    out: list[Combination] = []
    truncated = False
    for operator in operators:
        for horizon in horizons:
            for regime in regimes:
                for left, right in _pairs(uniq, operator):
                    c = Combination(cat, left, right, operator, horizon, regime)
                    if c.key in seen:
                        continue
                    seen.add(c.key)
                    if limit and len(out) >= limit:
                        truncated = True
                        break
                    out.append(c)
                if truncated:
                    break
            if truncated:
                break
        if truncated:
            break
    notes = []
    if len(uniq) < 2:
        notes.append("fewer than two distinct features -- no pair exists, so the space is empty")
    if truncated:
        notes.append(
            f"TRUNCATED at limit={limit}. n_trials reports what was ENUMERATED, not what the "
            "space contains; a hurdle computed from a truncated count understates the search.")
    return CombinationSpace(
        combinations=tuple(out), n_trials=len(out), features_used=uniq,
        truncated=truncated, notes=tuple(notes),
    )


def space_size(
    n_features: int,
    *,
    n_operators: int = len(OPERATORS),
    n_horizons: int = len(HORIZONS),
    n_regimes: int = len(REGIMES),
) -> int:
    """Size of the space WITHOUT enumerating it -- so a caller can see the trial count it is about
    to incur before paying for it.

    Directional operators contribute ordered pairs n(n-1), symmetric ones unordered n(n-1)/2. The
    asymmetry is not a detail: getting it wrong understates the hurdle, and understating the hurdle
    is how a desk manufactures survivors.
    """
    if n_features < 2:
        return 0
    ordered = n_features * (n_features - 1)
    n_dir = sum(1 for o in OPERATORS[:n_operators] if o in _DIRECTIONAL)
    n_sym = n_operators - n_dir
    return (n_dir * ordered + n_sym * ordered // 2) * n_horizons * n_regimes


def as_hypotheses(
    space: CombinationSpace,
    *,
    expected_edge: float = 0.0,
) -> list[Hypothesis]:
    """Adapt to the existing `Hypothesis` model so this feeds the machinery already built.

    `expected_edge` DEFAULTS TO ZERO, and that default is deliberate. `HypothesisEngine` seeds a
    template hypothesis with the category's historical success rate, which is defensible for a
    hand-authored, economically-argued statement. It is not defensible here: an enumerated
    combination has no prior, nobody argued for it, and most are noise by construction. Inheriting
    a category's success rate would launder the reputation of seven hand-written ideas onto
    thousands of machine-generated ones -- and every ranker downstream reads that field.
    """
    return [
        Hypothesis(
            id=generate_id("hyp"),
            statement=c.statement,
            category=c.category,
            features=c.features,
            expected_edge=expected_edge,
            rationale=(
                f"ENUMERATED candidate ({c.operator}, {c.horizon}, regime={c.regime}); "
                f"one of {space.n_trials} trials in this space -- the deflation hurdle must be "
                "computed from that count, not from the number that survive."
            ),
        )
        for c in space.combinations
    ]


def novel_only(
    space: CombinationSpace,
    priors: Sequence[object],
    *,
    redundant_threshold: float = 0.7,
) -> CombinationSpace:
    """Drop candidates that are redundant against prior (usually FAILED) ideas.

    THE TRIAL COUNT IS DELIBERATELY NOT REDUCED. Filtering after enumeration does not undo the
    search: the space was still swept, and the survivors were still selected from the full set.
    Recomputing `n_trials` from the filtered length is the single easiest way to make this module
    dangerous -- it would shrink the hurdle in exact proportion to how aggressively the desk
    filtered, so a harder filter would buy a weaker significance bar. `n_trials` is carried
    forward unchanged and the filtering is recorded in `notes`.
    """
    from libs.alpha_factory.hypothesis_novelty import hypothesis_novelty

    kept = [
        c for c in space.combinations
        if not hypothesis_novelty(
            c.statement, features=c.features, priors=priors,  # type: ignore[arg-type]
            redundant_threshold=redundant_threshold,
        ).is_redundant
    ]
    dropped = len(space.combinations) - len(kept)
    return CombinationSpace(
        combinations=tuple(kept),
        n_trials=space.n_trials,        # NOT len(kept) -- see docstring
        features_used=space.features_used,
        truncated=space.truncated,
        notes=(*space.notes,
               f"novelty filter dropped {dropped} redundant candidate(s) against "
               f"{len(priors)} prior(s); n_trials remains {space.n_trials} because the search was "
               "performed over the full space regardless of what was kept"),
    )


def iter_batches(space: CombinationSpace, size: int) -> Iterable[tuple[Combination, ...]]:
    """Chunk for execution. Enumeration is cheap and testing is not, so a caller that cannot run
    the whole space runs it in batches -- and the deflation still uses the FULL `n_trials`, since
    stopping early after a good batch is optional stopping and inflates significance."""
    if size <= 0:
        raise ValueError("batch size must be positive")
    items = space.combinations
    for i in range(0, len(items), size):
        yield items[i:i + size]
