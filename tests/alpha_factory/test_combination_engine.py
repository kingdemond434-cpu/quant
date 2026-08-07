"""COMBINATORIAL HYPOTHESIS GENERATION -- and the four ways it could quietly manufacture survivors.

The measured gap: `HypothesisEngine.generate` can emit SEVEN hypotheses in total, from thirteen
features, and never more without a human writing a new template. Everything downstream -- novelty
de-duplication, ROI ranking, family trees, monte-carlo survival, DSR/PBO/CPCV -- is built to
process a large stream. The funnel is wide everywhere except at its mouth.

MOST OF THIS FILE TESTS THE HURDLE, NOT THE ENUMERATION. Enumerating a cross-product is easy and
almost impossible to get wrong in a way that hurts. What is easy to get wrong, and catastrophic, is
the TRIAL COUNT that flows into multiple-testing deflation. A generator that emits 10,000
candidates and understates the search that produced them is not a research accelerator, it is a
false-discovery accelerator -- it would find "survivors" in pure noise, quickly, and with every
downstream statistic agreeing.

The four ways, each pinned below:
  1. `n_trials` recomputed after novelty filtering -- a harder filter would buy a WEAKER
     significance bar, which is precisely backwards.
  2. Silent truncation -- a capped space reporting the capped count as if it were the whole search.
  3. Symmetric pairs enumerated in both orders -- the same claim paid for twice.
  4. Enumerated candidates inheriting a hand-authored category's historical success rate, laundering
     the reputation of seven argued ideas onto thousands of machine-generated ones.
"""

from __future__ import annotations

import pytest

from libs.alpha_factory.combination_engine import (
    HORIZONS,
    OPERATORS,
    REGIMES,
    as_hypotheses,
    enumerate_space,
    iter_batches,
    novel_only,
    space_size,
)
from libs.alpha_factory.hypothesis_engine import _TEMPLATES
from libs.alpha_factory.hypothesis_novelty import PriorIdea

_F = ("funding_rate", "open_interest", "taker_buy_frac", "realized_vol", "basis")


# ------------------------------------------------------------------ the gap this exists to close

def test_THE_TEMPLATE_ENGINE_CAN_NEVER_EXCEED_A_HANDFUL() -> None:
    """The finding, asserted so it cannot be waved away as an impression. If someone later adds
    templates this test still passes -- it bounds the ORDER OF MAGNITUDE, not the exact count --
    but the gap it documents is three orders wide and no amount of hand-authoring closes that."""
    total = sum(len(v) for v in _TEMPLATES.values())
    assert total < 50, "template count is now large enough that this file's premise needs review"
    combinatorial = space_size(len(_F))
    assert combinatorial > 100 * total, (
        f"five features already enumerate {combinatorial} candidates against {total} templates -- "
        "if that ratio has collapsed, the enumerator has been narrowed and should be re-argued")


# --------------------------------------------------------------------- the trial count is the point

def test_NOVELTY_FILTERING_DOES_NOT_SHRINK_THE_TRIAL_COUNT() -> None:
    """THE MOST DANGEROUS AVAILABLE BUG IN THIS MODULE.

    The search was performed over the FULL space; the survivors were selected from all of it. If
    `n_trials` were recomputed as the number kept, then filtering harder would shrink the
    multiple-testing hurdle in exact proportion -- so the more aggressively the desk pruned, the
    easier it would be to clear significance. That is a machine for manufacturing survivors, and it
    would look like good hygiene the whole way.
    """
    space = enumerate_space(_F, operators=("interaction",), horizons=("1d",), regimes=("all",))
    priors = [PriorIdea(id="p1", statement=c.statement, features=c.features, lesson="died")
              for c in space.combinations[:5]]
    filtered = novel_only(space, priors)

    assert len(filtered) < len(space), "the filter dropped nothing -- this test proves nothing"
    assert filtered.n_trials == space.n_trials, (
        "n_trials shrank with the filter: a harder prune now buys a weaker significance bar")
    assert any("n_trials remains" in n for n in filtered.notes), (
        "the reason must travel with the artifact, or the next reader 'fixes' it")


def test_TRUNCATION_IS_NEVER_SILENT() -> None:
    """A capped space whose count reads like a complete search understates the hurdle. Every other
    error in this module biases toward testing too much; this one biases toward believing too
    much, which is the direction that costs money."""
    space = enumerate_space(_F, limit=10)
    assert space.truncated is True
    assert len(space) == 10
    assert any("TRUNCATED" in n for n in space.notes)
    assert any("understates the search" in n for n in space.notes)


def test_UNLIMITED_IS_THE_DEFAULT() -> None:
    """The desk's standing position: no throttle on research GENERATION. A cap on what may even be
    surfaced throttles conversion before the work begins."""
    space = enumerate_space(_F)
    assert space.truncated is False
    assert len(space) == space_size(len(_F))


def test_space_size_MATCHES_THE_ENUMERATION_EXACTLY() -> None:
    """The whole value of `space_size` is letting a caller see the trial count BEFORE paying for
    it. A predictor that disagrees with the enumerator is worse than none, because it would be
    trusted."""
    for n in (2, 3, 5, 8):
        feats = tuple(f"f{i}" for i in range(n))
        assert space_size(n) == len(enumerate_space(feats)), f"mismatch at n={n}"


@pytest.mark.parametrize("n", [0, 1])
def test_FEWER_THAN_TWO_FEATURES_IS_AN_EMPTY_SPACE_NOT_AN_ERROR(n: int) -> None:
    """No pair exists. Returning an empty space with a stated reason lets a caller report NOT
    MEASURED; raising would abort a sweep because one category happened to be thin."""
    space = enumerate_space(tuple(f"f{i}" for i in range(n)))
    assert len(space) == 0 and space.n_trials == 0
    assert space_size(n) == 0
    if n < 2:
        assert any("no pair exists" in note for note in space.notes)


# ------------------------------------------------------------------------- no duplicate claims

def test_SYMMETRIC_OPERATORS_DO_NOT_ENUMERATE_BOTH_ORDERINGS() -> None:
    """`interaction` is symmetric: 'a and b jointly predict' is the same claim as 'b and a'.
    Emitting both doubles the trial count and adds nothing -- the worst possible trade, because
    the duplicate is still paid for in the hurdle."""
    space = enumerate_space(("a", "b", "c"), operators=("interaction",),
                            horizons=("1d",), regimes=("all",))
    assert len(space) == 3, f"expected C(3,2)=3 unordered pairs, got {len(space)}"


def test_DIRECTIONAL_OPERATORS_DO_ENUMERATE_BOTH_ORDERINGS() -> None:
    """And the converse, which matters as much: 'a predicts conditioned on b' is a genuinely
    different claim from 'b predicts conditioned on a'. Collapsing them would silently delete half
    the hypothesis space while looking like de-duplication."""
    space = enumerate_space(("a", "b", "c"), operators=("condition",),
                            horizons=("1d",), regimes=("all",))
    assert len(space) == 6, f"expected P(3,2)=6 ordered pairs, got {len(space)}"


def test_NO_FEATURE_IS_PAIRED_WITH_ITSELF() -> None:
    """`x` interacting with `x` is `x`. It would consume a trial to say so."""
    for c in enumerate_space(_F).combinations:
        assert c.left != c.right


def test_EVERY_CANDIDATE_IS_DISTINCT() -> None:
    space = enumerate_space(_F)
    keys = [c.key for c in space.combinations]
    assert len(set(keys)) == len(keys)
    statements = {(c.statement, c.category) for c in space.combinations}
    assert len(statements) == len(space), "two candidates render to the same sentence"


def test_DUPLICATE_INPUT_FEATURES_ARE_COLLAPSED() -> None:
    """A caller assembling features from several sources will hand over duplicates. Enumerating
    them would inflate the trial count with claims that are literally identical."""
    space = enumerate_space(("a", "b", "a", "b", ""))
    assert space.features_used == ("a", "b")
    assert len(space) == space_size(2)


# --------------------------------------------------------------------- the statements themselves

def test_THE_UNCONDITIONAL_REGIME_IS_ALWAYS_IN_THE_SPACE() -> None:
    """A space in which every hypothesis is regime-conditioned has no control. 'It works in
    high-vol regimes' is unfalsifiable without 'it does not work unconditionally' to compare
    against, and regime-conditioning is exactly where a researcher goes to rescue a dead result."""
    assert "all" in REGIMES
    regimes = {c.regime for c in enumerate_space(_F).combinations}
    assert "all" in regimes


def test_STATEMENTS_ARE_PREDICTIVE_CLAIMS_NOT_DESCRIPTIONS() -> None:
    """'X is high when Y is high' is a correlation nobody can trade or refute cleanly. Every
    statement must name a forward horizon, which is what makes it falsifiable."""
    for c in enumerate_space(_F).combinations:
        assert "predict" in c.statement
        assert c.horizon in c.statement, "a statement with no horizon is not testable"
        if c.regime != "all":
            assert "regimes" in c.statement


def test_EVERY_OPERATOR_RENDERS(  ) -> None:
    """A KeyError in the statement renderer would surface mid-sweep, after the enumeration cost is
    already paid."""
    for op in OPERATORS:
        space = enumerate_space(("a", "b"), operators=(op,), horizons=HORIZONS[:1],
                                regimes=("all",))
        assert len(space) >= 1
        assert space.combinations[0].statement


# --------------------------------------------------------------------- adapting to the machinery

def test_ENUMERATED_CANDIDATES_CARRY_NO_INHERITED_EDGE() -> None:
    """`HypothesisEngine` seeds each template with its category's historical success rate, which is
    defensible for a hand-authored, economically-argued statement. It is NOT defensible here:
    nobody argued for an enumerated combination and most are noise by construction. Inheriting the
    category's rate would launder the reputation of seven human ideas onto thousands of machine
    ones -- and every ranker downstream reads that field."""
    hyps = as_hypotheses(enumerate_space(("a", "b")))
    assert hyps and all(h.expected_edge == 0.0 for h in hyps)


def test_THE_TRIAL_COUNT_TRAVELS_INTO_THE_RATIONALE() -> None:
    """The number has to reach a human reading one hypothesis in isolation, because that is how it
    will be read -- one row in a ranked list, with no memory of the sweep that produced it."""
    space = enumerate_space(_F)
    h = as_hypotheses(space)[0]
    assert str(space.n_trials) in h.rationale
    assert "deflation" in h.rationale


def test_HYPOTHESES_KEEP_THEIR_STRUCTURE() -> None:
    """Downstream consumers want different projections -- novelty wants features, the family tree
    wants the category. A generator emitting only prose forces each to parse English back into
    structure."""
    space = enumerate_space(_F)
    for c, h in zip(space.combinations, as_hypotheses(space), strict=True):
        assert h.features == c.features
        assert h.category == c.category
        assert h.statement == c.statement


# ------------------------------------------------------------------------- execution in batches

def test_BATCHES_PARTITION_THE_SPACE_EXACTLY() -> None:
    """Nothing lost, nothing tested twice -- a dropped batch silently shrinks the real search
    below the reported n_trials, and a repeated one double-counts a result."""
    space = enumerate_space(_F, operators=("interaction",), horizons=("1d",), regimes=("all",))
    seen = [c for batch in iter_batches(space, 3) for c in batch]
    assert seen == list(space.combinations)


@pytest.mark.parametrize("bad", [0, -1])
def test_A_NONPOSITIVE_BATCH_SIZE_RAISES(bad: int) -> None:
    """Rather than looping forever inside a scheduled organ, which is the failure that produces no
    error, no output, and a process that never finishes."""
    with pytest.raises(ValueError, match="positive"):
        list(iter_batches(enumerate_space(("a", "b")), bad))


# ------------------------------------------------ the transform axis (the DSL's missing half)

def test_TRANSFORMS_ARE_THE_AXIS_THE_GENERATOR_DID_NOT_HAVE() -> None:
    """The concrete answer to "what does the public operator taxonomy expose that we never tried":
    we combined RAW features and never transformed them. Raw funding, its cross-sectional rank and
    its change are three different hypotheses -- and that taxonomy is dominated by exactly these."""
    from libs.alpha_factory.combination_engine import TRANSFORMS
    assert "identity" in TRANSFORMS and TRANSFORMS[0] == "identity", (
        "identity must be present and first -- a space where every feature is transformed has no "
        "control, and 'the rank works' is uninterpretable without 'the level does not'")
    assert len(TRANSFORMS) >= 6


def test_A_TRANSFORMED_FEATURE_IS_A_DIFFERENT_HYPOTHESIS() -> None:
    """If rank(x) and x collapsed to one key, the whole axis would add nothing while appearing to
    multiply the space -- the worst possible outcome, since the trial count would still rise."""
    plain = enumerate_space(("a", "b"), transforms=("identity",))
    with_tf = enumerate_space(("a", "b"), transforms=("identity", "rank"))
    assert len(with_tf) == len(plain) * 4, "T^2 growth: each side transforms independently"
    keys = {c.key for c in with_tf.combinations}
    assert len(keys) == len(with_tf), "transformed variants collided on one key"


def test_THE_TRANSFORM_REACHES_THE_STATEMENT() -> None:
    """A statement that renders the raw feature name while testing a transformed one is a lie in
    the artifact a human reads."""
    from libs.alpha_factory.combination_engine import Combination
    c = Combination("x", "funding", "oi", "ratio", "4h", "high_vol", "rank", "delta")
    assert "rank(funding)" in c.statement and "delta(oi)" in c.statement
    assert c.features == ["rank(funding)", "delta(oi)"]


def test_CROSS_SECTIONAL_TRANSFORMS_ARE_FLAGGED() -> None:
    """A DATA REQUIREMENT, not a preference: a cross-sectional transform computed on a single
    symbol degenerates to a constant, which turns a whole arm into a no-op that still consumes
    trials and still raises the hurdle for everything else."""
    from libs.alpha_factory.combination_engine import Combination
    assert Combination("x", "a", "b", "ratio", "1d", "all", "rank", "identity").needs_panel
    assert not Combination("x", "a", "b", "ratio", "1d", "all", "delta", "sign").needs_panel


def test_space_size_STILL_PREDICTS_THE_ENUMERATION_WITH_TRANSFORMS() -> None:
    """The predictor must stay honest, because its whole purpose is letting a caller see the trial
    count BEFORE paying for it."""
    from libs.alpha_factory.combination_engine import TRANSFORMS
    for n_tf in (1, 2, 4):
        feats = ("a", "b", "c")
        got = len(enumerate_space(feats, transforms=TRANSFORMS[:n_tf]))
        assert got == space_size(3, n_transforms=n_tf), f"mismatch at {n_tf} transforms"


def test_THE_TRIAL_COUNT_RISES_WITH_THE_SPACE() -> None:
    """The cost of the new axis must land in n_trials, or the hurdle would be computed from a
    search smaller than the one performed -- manufacturing significance."""
    from libs.alpha_factory.combination_engine import TRANSFORMS
    small = enumerate_space(("a", "b"), transforms=("identity",))
    big = enumerate_space(("a", "b"), transforms=TRANSFORMS[:4])
    assert big.n_trials == len(big) > small.n_trials == len(small)
