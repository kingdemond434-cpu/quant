"""THE TAXONOMY FENCE — a declared FAMILY may never assert an economic mechanism it does not have.

WHAT BROKE, and what this file stops from returning. `Family` is the desk's search-BUDGET
partition (it sets the DSR trial wall, the dedup identity and the campaign ordering), but its
labels read as economic mechanisms, so every "how many mechanisms have we tested" count was taken
off the family axis and overstated. Two independent instruments measured it on 2026-08-05:

  * `scripts/measure_cross_mechanism_corr.py` — `liquidity/shock_fade` against
    `mean_reversion/zscore_fade` at rho +0.953, and `momentum/time_series_mom` against
    `trend/vwap_trend` at +0.955. Different families, one trade.
  * `scripts/run_mechanism_census.py` — the 44-candidate maximum-power campaign's twelve declared
    families resolve to FOUR economic classes (price_continuation 20,
    liquidity_provision_immediacy 19, relative_value_convergence 4, market_risk_premium 1);
    effective classes 2.787, diversity 0.139.

HOW THE FENCE IS BUILT SO IT CATCHES THE DEFECT AND NOTHING ELSE. Only a family whose NAME claims
a PAYER can contradict the census — `carry`, `cross_asset`, `liquidity`, `risk_premia`. A family
that names a feature construction (`trend`, `mean_reversion`, `session`, ...) claims no payer, so
the census assigning it one is information rather than a conflict. That asymmetry is what lets a
LEGITIMATE NEW FAMILY PASS while a MISLABEL FAILS, and both directions are proved below on
synthetic specs rather than asserted.

The register `FAMILY_MECHANISM_DIVERGENCE` must match the computed divergence set EXACTLY, so a
new mislabel fails for being unrecorded and a fixed one fails for being stale.

ZERO AUTHORITY OVER ANY GATE. Nothing here reads or sets a threshold, a verdict or a bar; it
asserts only that labels tell the truth about themselves.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from libs.autodiscovery import generators as G
from libs.autodiscovery.generators import (
    FAMILY_ECONOMIC_CLAIM,
    FAMILY_MECHANISM_DIVERGENCE,
    GENERATORS,
    GeneratorSpec,
    census_class,
    family_mechanism_divergences,
    mechanism_class_counts,
)
from libs.autodiscovery.models import Family
from libs.research.mechanism_census import CLASS_BY_ID, CONSTRUCTION_CLASS

#: The two pairs `measure_cross_mechanism_corr.py` measured at rho > 0.95 across FAMILY lines, and
#: the correlation it reported. Pinned as documented facts: the taxonomy already says each pair is
#: one mechanism, so the measurement is a consequence of the classification rather than a surprise
#: about it. If a future edit ever splits one of these pairs into two economic classes, this file
#: fails and the split has to argue with a measured +0.95.
MEASURED_CROSS_FAMILY_TWINS: tuple[tuple[str, str, float], ...] = (
    ("shock_fade", "zscore_fade", 0.953),          # liquidity vs mean_reversion
    ("time_series_mom", "vwap_trend", 0.955),      # momentum vs trend
)

#: The one phrase in `generators.py` that makes the zero-carry fact discoverable without running
#: the census. Deliberately asserted BOTH WAYS below: the claim must be present while it is true
#: and must be removed the day a real carry generator ships.
ZERO_CARRY_CLAIM = "ZERO TRUE CARRY TESTS"

_TRUE_CARRY_CLASS = "derivative_carry_basis"

#: The census classes whose payer story IS a risk premium — somebody paying to shed a risk. A spec
#: may declare `MechanismType.RISK_PREMIUM` only if the census places it in one of these.
#:
#: SCOPED NARROWLY ON PURPOSE. The CRO's four-way prior (structural / behavioral / risk_premium /
#: liquidity) does not map one-to-one onto twenty census classes, and it should not: "absorption at
#: a failed range break" is defensibly structural OR liquidity, and forcing that choice would be a
#: fence inventing a taxonomy rather than enforcing one. `RISK_PREMIUM` is the exception because it
#: is the one value that names a PAYER outright, so it is checkable — and it is exactly the value
#: `drift_proxy` carried while being momentum, i.e. the family mislabel repeated one axis down.
RISK_PREMIUM_CLASSES = frozenset({
    "market_risk_premium", "derivative_carry_basis", "cross_sectional_risk_premium",
    "volatility_risk_premium",
})


def _spec(subtype: str) -> GeneratorSpec:
    return next(s for s in GENERATORS if s.subtype == subtype)


def _relabelled(spec: GeneratorSpec, *, family: Family | None = None,
                subtype: str | None = None) -> GeneratorSpec:
    """The same generator under a different LABEL — nothing but the label changes, which is the
    only kind of edit this whole change permits and the only kind these tests simulate."""
    return GeneratorSpec(family=spec.family if family is None else family,
                         subtype=spec.subtype if subtype is None else subtype,
                         fn=spec.fn, mechanism=spec.mechanism, edge_source=spec.edge_source,
                         failure_modes=list(spec.failure_modes),
                         param_variants=list(spec.param_variants))


# ------------------------------------------------------------------ the census owns the taxonomy
def test_every_generator_is_classified_by_the_census() -> None:
    """A generator the census has never placed is unmeasurable mechanism supply."""
    unplaced = sorted({s.subtype for s in GENERATORS} - set(CONSTRUCTION_CLASS))
    assert not unplaced, (
        f"{unplaced} ship from generators.py but carry no entry in "
        f"mechanism_census.CONSTRUCTION_CLASS. Classify them there — the census owns the "
        f"taxonomy — before they can be counted as mechanism supply."
    )


def test_census_class_of_every_spec_is_a_real_taxonomy_class() -> None:
    for spec in GENERATORS:
        assert census_class(spec) in CLASS_BY_ID, spec.subtype


def test_census_class_refuses_an_unclassified_construction() -> None:
    """The lookup raises rather than defaulting: no generator is absorbed into the nearest class."""
    orphan = _relabelled(_spec("ma_cross"), subtype="not_a_registered_construction")
    with pytest.raises(KeyError, match="CONSTRUCTION_CLASS"):
        census_class(orphan)


# --------------------------------------------------------------------------------- THE FENCE ---
def test_declared_family_never_contradicts_the_census_mechanism() -> None:
    computed = family_mechanism_divergences()
    unrecorded = sorted(set(computed) - set(FAMILY_MECHANISM_DIVERGENCE))
    stale = sorted(set(FAMILY_MECHANISM_DIVERGENCE) - set(computed))
    assert not unrecorded, (
        f"{unrecorded} sit under a family whose NAME claims an economic mechanism the census does "
        f"not grant them: {[(k, computed[k]) for k in unrecorded]}. Either the family is wrong or "
        f"the divergence is real and must be written into "
        f"generators.FAMILY_MECHANISM_DIVERGENCE with the reason — an unrecorded mislabel is how "
        f"the desk came to count 12 families as 12 mechanisms."
    )
    assert not stale, (
        f"{stale} are recorded as family/mechanism divergences but no longer diverge. Delete the "
        f"stale entries: a register that over-reports mislabels is lying in the other direction."
    )


def test_every_divergence_reason_names_the_real_class() -> None:
    """A register entry must say what the mechanism ACTUALLY is, not just that something is off."""
    computed = family_mechanism_divergences()
    for subtype, reason in FAMILY_MECHANISM_DIVERGENCE.items():
        entry = computed.get(subtype)
        if entry is None:
            continue          # stale entry; the exactness test above owns that failure
        actual = entry[1]
        assert actual in reason, (
            f"the FAMILY_MECHANISM_DIVERGENCE entry for '{subtype}' never names its real census "
            f"class '{actual}', so a reader learns the label is wrong without learning the truth"
        )


def test_a_risk_premium_prior_is_only_declared_where_somebody_pays_one() -> None:
    """The same overstatement one axis down. `MechanismType.RISK_PREMIUM` asserts a payer shedding
    a risk; declaring it on a rule the census calls price continuation claims a premium harvest
    that the implementation never touches."""
    for spec in GENERATORS:
        if spec.mechanism.value != "risk_premium":
            continue
        cls = census_class(spec)
        assert cls in RISK_PREMIUM_CLASSES, (
            f"'{spec.subtype}' declares a RISK_PREMIUM prior but the census classifies it as "
            f"'{cls}', whose payer is not shedding a risk. Declare the prior the implementation "
            f"earns (see drift_proxy, which carried RISK_PREMIUM while being 200-bar momentum)."
        )


def test_family_economic_claims_point_at_real_classes() -> None:
    for family, class_id in FAMILY_ECONOMIC_CLAIM.items():
        assert class_id in CLASS_BY_ID, f"{family} claims a class the census does not define"


# ------------------------------------------- the fence discriminates: new family in, mislabel out
def test_a_feature_named_family_never_registers_a_divergence() -> None:
    """A LEGITIMATE NEW FAMILY PASSES. `mean_reversion/zscore_fade` classifies as
    `liquidity_provision_immediacy` — a payer the family name never claimed — and that is not a
    contradiction. Any family whose name describes a construction behaves the same way, which is
    what keeps this fence from blocking honest additions."""
    fade = _spec("zscore_fade")
    assert census_class(fade) == "liquidity_provision_immediacy"
    assert fade.family not in FAMILY_ECONOMIC_CLAIM
    assert family_mechanism_divergences([fade]) == {}


def test_a_matching_payer_named_family_passes() -> None:
    """A payer-naming family that EARNS its name is clean: risk_premia/persistent_long."""
    assert family_mechanism_divergences([_spec("persistent_long")]) == {}
    assert family_mechanism_divergences([_spec("intermarket_difference")]) == {}


def test_a_mislabelled_spec_fails() -> None:
    """A MISLABEL FAILS. Park a price-continuation rule under a payer-naming family and the
    divergence is detected from the census alone — no keyword list, no per-spec allowlist."""
    mislabelled = _relabelled(_spec("time_series_mom"), family=Family.CARRY)
    assert family_mechanism_divergences([mislabelled]) == {
        "time_series_mom": ("derivative_carry_basis", "price_continuation")
    }
    moved = _relabelled(_spec("ma_cross"), family=Family.RISK_PREMIA)
    assert family_mechanism_divergences([moved]) == {
        "ma_cross": ("market_risk_premium", "price_continuation")
    }


# ------------------------------------------------------- the measured correlations, kept in view
@pytest.mark.parametrize(("left", "right", "rho"), MEASURED_CROSS_FAMILY_TWINS)
def test_measured_cross_family_twins_share_one_census_class(left: str, right: str,
                                                            rho: float) -> None:
    a, b = _spec(left), _spec(right)
    assert a.family is not b.family, f"{left}/{right} were measured ACROSS family lines"
    assert census_class(a) == census_class(b), (
        f"{left} and {right} correlate at +{rho:.3f} on the desk's own tape but this taxonomy "
        f"now places them in different economic classes ({census_class(a)} vs {census_class(b)}). "
        f"Two things that are the same trade must not be counted as two mechanisms."
    )


def test_family_count_overstates_mechanism_count() -> None:
    """The headline number, pinned as a relationship rather than as a constant so that genuinely
    new mechanism supply moves it in the right direction instead of breaking the fence."""
    n_families = len({s.family for s in GENERATORS})
    counts = mechanism_class_counts()
    assert sum(counts.values()) == len(GENERATORS)
    assert len(counts) < n_families, (
        "the family axis no longer overstates the mechanism axis, which would be excellent news "
        "and is worth a deliberate edit here rather than a silent pass"
    )


# --------------------------------------------------------------- the zero-carry fact, discoverable
def test_zero_true_carry_tests_is_both_true_and_stated() -> None:
    carry_specs = sorted(s.subtype for s in GENERATORS
                         if census_class(s) == _TRUE_CARRY_CLASS)
    doc = G.__doc__
    assert doc is not None
    if carry_specs:
        assert ZERO_CARRY_CLAIM not in doc, (
            f"{carry_specs} now test true carry, so generators.py must stop claiming "
            f"'{ZERO_CARRY_CLAIM}'"
        )
    else:
        assert ZERO_CARRY_CLAIM in doc, (
            f"no generator in this library tests {_TRUE_CARRY_CLASS}, and the module docstring "
            f"must say '{ZERO_CARRY_CLAIM}' so the fact is discoverable without running the census"
        )


def test_drift_proxy_is_declared_carry_and_classified_momentum() -> None:
    """The named instance, pinned: its family stays `carry` (a gate-bearing budget key) and its
    mechanism stays `price_continuation` (the truth), and the divergence stays on the record."""
    spec = _spec("drift_proxy")
    assert spec.family is Family.CARRY
    assert census_class(spec) == "price_continuation"
    assert "drift_proxy" in FAMILY_MECHANISM_DIVERGENCE
    assert spec.mechanism.value == "behavioral", (
        "drift_proxy is momentum_positions(lookback=200); a risk_premium prior on it is the same "
        "overstatement as the carry family label, one axis down"
    )


def test_the_mechanism_graph_carries_the_family_vs_mechanism_addendum() -> None:
    """The readable form lives in the doc whose binding rule was being broken — MECHANISM_GRAPH
    says every hypothesis must name its mechanism node, and the generator library was naming a
    feature family instead. Deliberately NOT a new docs artifact: `max_audit`'s §36(2) governance
    requires every docs/*.md to be claimed by a law, and an unclaimed one is exactly the
    inventory-accumulates failure this change is about."""
    doc = Path(__file__).resolve().parents[2] / "docs/research/MECHANISM_GRAPH.md"
    assert doc.exists()
    text = doc.read_text("utf-8")
    assert ZERO_CARRY_CLAIM in text.upper(), (
        "the zero-carry fact must stay readable in MECHANISM_GRAPH.md, not only in code"
    )
    assert "CONSTRUCTION_CLASS" in text, "the addendum must name the authority it defers to"
