"""AN ASYMMETRY CLAIM IS A CLAIM ABOUT COMPETITORS, AND MUST BE EVIDENCED LIKE ONE.

The comfortable failure here is a desk telling itself its data is special. `info_class_map.py`
already maps modality x access and files `exchange_api_ohlcv` -- identical bytes for every
participant on earth -- alongside self-recorded L2 tape that nobody else has, both as "covered".
This axis exists to separate them, and it is worthless if a claim can be asserted rather than
argued.

Both directions are tested: the constructor refuses an unevidenced claim, and a claim nobody has
re-checked degrades to UNVERIFIED rather than continuing to be believed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from libs.data.asymmetry import (
    ASYMMETRY_CLASSES,
    DEPTH_LEVELS,
    AsymmetrySource,
    Portfolio,
)

TODAY = datetime.now(tz=UTC).date().isoformat()


def _old(days: int) -> str:
    return (datetime.now(tz=UTC) - timedelta(days=days)).date().isoformat()


def test_an_exclusive_claim_must_say_why_it_cannot_be_replicated() -> None:
    """THE COMFORTABLE ERROR. Recording an asset with no stated reason a competitor cannot obtain
    it is recording a wish."""
    with pytest.raises(ValueError, match="why_not_replicable"):
        AsymmetrySource(name="x", asymmetry="EXCLUSIVE", depth=3, verified=TODAY)


def test_reconstructible_needs_evidence_too() -> None:
    with pytest.raises(ValueError, match="why_not_replicable"):
        AsymmetrySource(name="x", asymmetry="RECONSTRUCTIBLE", depth=1, verified=TODAY)


def test_commodity_needs_no_evidence() -> None:
    """Claiming NO advantage is not a claim that needs defending."""
    s = AsymmetrySource(name="ohlcv", asymmetry="COMMODITY", depth=5, verified=TODAY)
    assert s.weight == 0.0


def test_an_unknown_class_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown asymmetry class"):
        AsymmetrySource(name="x", asymmetry="SPECIAL", depth=1, verified=TODAY)


def test_a_bad_date_is_refused() -> None:
    with pytest.raises(ValueError, match="ISO date"):
        AsymmetrySource(name="x", asymmetry="COMMODITY", depth=1, verified="last tuesday")


def test_a_stale_claim_reports_unverified_and_earns_nothing() -> None:
    """A RECONSTRUCTIBLE advantage lasts until somebody productises it -- the desk's own graveyard
    carries vendor-replacement entries that are exactly that transition. An unchecked claim is
    'not measured' being read as 'measured and fine', applied to the one asset that supposedly
    justifies the enterprise."""
    s = AsymmetrySource(name="x", asymmetry="RECONSTRUCTIBLE", depth=4,
                        verified=_old(400), why_not_replicable="clustering is the expensive part")
    assert s.stale
    assert s.effective_class == "UNVERIFIED"
    assert s.weight == 0.0
    assert s.realised == 0.0


def test_a_fresh_claim_is_live() -> None:
    s = AsymmetrySource(name="x", asymmetry="RECONSTRUCTIBLE", depth=4, verified=TODAY,
                        why_not_replicable="clustering is the expensive part")
    assert not s.stale
    assert s.weight == ASYMMETRY_CLASSES["RECONSTRUCTIBLE"][0]


def test_exclusive_claims_have_a_longer_half_life_than_reconstructible_ones() -> None:
    """A self-recorded tape does not stop being exclusive; a processing advantage erodes the
    moment somebody productises it."""
    assert ASYMMETRY_CLASSES["EXCLUSIVE"][1] > ASYMMETRY_CLASSES["RECONSTRUCTIBLE"][1]


def test_realised_asymmetry_is_the_product_and_a_zero_kills_it() -> None:
    """THE NUMBER A BREADTH-ONLY MAP CANNOT EXPRESS. Holding irreplaceable data at depth 0
    realises exactly nothing -- which is the desk's own position on its execution fills."""
    deep = AsymmetrySource(name="a", asymmetry="EXCLUSIVE", depth=5, verified=TODAY,
                           why_not_replicable="cannot be reconstructed after the fact")
    shallow = AsymmetrySource(name="b", asymmetry="EXCLUSIVE", depth=0, verified=TODAY,
                              why_not_replicable="cannot be reconstructed after the fact")
    assert shallow.realised == 0.0
    assert deep.realised == 1.0
    assert deep.weight == shallow.weight, "same asset, same asymmetry -- only depth differs"


def test_shallow_gold_ranks_high_asymmetry_low_depth_first() -> None:
    """Acquiring another asymmetric source while an existing one sits at depth 1 raises the
    headline count and LOWERS realised asymmetry."""
    p = Portfolio(sources=(
        AsymmetrySource("deep", "EXCLUSIVE", 5, TODAY, why_not_replicable="destroyed at source"),
        AsymmetrySource("gold", "EXCLUSIVE", 0, TODAY, why_not_replicable="destroyed at source"),
        AsymmetrySource("cheap", "COMMODITY", 1, TODAY),
    ))
    names = [s.name for s in p.shallow_gold()]
    assert names[0] == "gold"
    assert "deep" not in names and "cheap" not in names


def test_breadth_excludes_commodity_and_unverified() -> None:
    """Counting sources with no advantage as 'asymmetric breadth' is how the number becomes a
    vanity metric."""
    p = Portfolio(sources=(
        AsymmetrySource("live", "EXCLUSIVE", 3, TODAY, why_not_replicable="destroyed at source"),
        AsymmetrySource("stale", "RECONSTRUCTIBLE", 3, _old(400), why_not_replicable="work"),
        AsymmetrySource("commodity", "COMMODITY", 5, TODAY),
    ))
    assert p.breadth == 1


def test_the_depth_ladder_is_about_artefacts_not_effort() -> None:
    """'We looked at it a lot' is not a depth. Every rung names something that exists on disk."""
    assert DEPTH_LEVELS[0].startswith("UNTOUCHED")
    assert "graveyard" in DEPTH_LEVELS[5]
    assert max(DEPTH_LEVELS) == 5
