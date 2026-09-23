"""TIER-1 W11: the forward posterior, the marginal-breadth admission and the factor tier.

All three were published for months and read by nothing. Each enters the allocator as a
HEAT-NEUTRAL tilt of the sleeve's posterior mean -- the raw factors are divided by their own
mean, so the mean tilt across the book is exactly 1.0 and the total the heat law resolved cannot
move. What is pinned here is that property (the thing that makes this not a reduction), that each
tilt is TWO-SIDED, and that an absent or thin report is neutral rather than a guess.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from libs.portfolio import allocator_evidence as AE


def _post(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"at": "2026-09-22T00:00:00+00:00", "sleeves": rows}


def test_the_forward_posterior_tilt_is_two_sided_and_heat_neutral() -> None:
    doc = _post([{"name": "a", "mu_shrunk_family": 0.30, "n": 400, "rho_book": 0.1},
                 {"name": "b", "mu_shrunk_family": 0.00, "n": 400, "rho_book": 0.1},
                 {"name": "c", "mu_shrunk_family": -0.30, "n": 400, "rho_book": 0.1}])
    terms, why = AE.posterior_prior_factors(doc)
    assert set(terms) == {"a", "b", "c"} and "POSTERIOR_ALPHA.json read" in why
    f = {k: v.factor for k, v in terms.items()}
    assert f["a"] > 1.0 > f["c"]                       # two-sided: one up, one down
    assert abs(sum(f.values()) / 3 - 1.0) < 1e-9       # heat-neutral: mean tilt is exactly 1.0
    assert all(AE.TILT_LO <= v <= AE.TILT_HI for v in f.values())


def test_a_thin_forward_count_shrinks_the_tilt_toward_one() -> None:
    fat = AE.posterior_prior_factors(_post(
        [{"name": "a", "mu_shrunk_family": 0.30, "n": 400},
         {"name": "b", "mu_shrunk_family": -0.30, "n": 400}]))[0]["a"].factor
    thin = AE.posterior_prior_factors(_post(
        [{"name": "a", "mu_shrunk_family": 0.30, "n": 1},
         {"name": "b", "mu_shrunk_family": -0.30, "n": 1}]))[0]["a"].factor
    assert fat > thin >= 1.0


def test_marginal_breadth_rewards_the_sleeve_the_book_does_not_already_own() -> None:
    terms, why = AE.marginal_breadth_factors(_post(
        [{"name": "owned", "rho_book": 0.9, "mu_shrunk_family": 0.1, "n": 100},
         {"name": "independent", "rho_book": 0.0, "mu_shrunk_family": 0.1, "n": 100}]))
    assert terms["independent"].factor > 1.0 > terms["owned"].factor, why
    assert abs(sum(t.factor for t in terms.values()) / 2 - 1.0) < 1e-9


def test_the_factor_tier_moves_a_sleeve_that_repeats_the_book_down_and_an_orthogonal_one_up(
) -> None:
    doc = {"book": {"usd": 1.0, "gold": 0.0},
           "sleeves": [{"name": "same", "exposures": {"usd": 0.9, "gold": 0.0}},
                       {"name": "other", "exposures": {"usd": 0.0, "gold": 0.8}}]}
    terms, why = AE.factor_tier_factors(doc)
    assert terms["same"].factor < 1.0 < terms["other"].factor, why
    assert abs(sum(t.factor for t in terms.values()) / 2 - 1.0) < 1e-9


def test_a_book_that_shares_everything_is_not_moved_at_all() -> None:
    """The property that makes this not a shrink: a concentration the WHOLE book shares
    normalises back to exactly 1.0 for every sleeve."""
    doc = {"book": {"usd": 1.0},
           "sleeves": [{"name": "a", "exposures": {"usd": 1.0}},
                       {"name": "b", "exposures": {"usd": 1.0}}]}
    terms, _ = AE.factor_tier_factors(doc)
    assert all(abs(t.factor - 1.0) < 1e-9 for t in terms.values())


def test_absent_or_thin_reports_are_exactly_neutral_and_say_why() -> None:
    for fn in (AE.posterior_prior_factors, AE.marginal_breadth_factors, AE.factor_tier_factors):
        terms, why = fn(None)
        assert terms == {} and why
        terms, why = fn({"sleeves": []})
        assert terms == {} and why
    one, why = AE.posterior_prior_factors(_post([{"name": "solo", "mu_shrunk_family": 1.0,
                                                  "n": 9}]))
    assert one == {} and "needs two" in why


def test_the_three_terms_are_declared_consumed_and_the_allocator_imports_them() -> None:
    for name in ("forward_posterior_prior", "marginal_breadth", "factor_tier"):
        spec = AE.SPEC_BY_NAME[name]
        assert spec.priced_inside_allocator is False and spec.consumed_as
        assert name in AE.CONSUMED_TILT_TERMS
    src = Path(AE.__file__).resolve().parents[2] / "desks" / "mt5" / "research" / "pf_allocator.py"
    text = src.read_text("utf-8")
    assert "posterior_prior_factors" in text and "marginal_breadth_factors" in text
    assert "factor_tier_factors" in text and "read_research_evidence" in text
    assert "posterior_doc=_post_doc" in text and "exposure_doc=_exp_doc" in text
