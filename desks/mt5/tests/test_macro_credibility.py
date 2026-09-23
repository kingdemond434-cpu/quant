"""Source credibility must be a LEARNED hierarchy, not a tier list with better manners.

The properties pinned here are the ones that distinguish the two. A tier's prior is overturnable
by its members' measured record. A source with no record IS its tier and no more. Three outlets
carrying one wire are worth barely more than one, and the ledger's own co-report rate is what
says so. A contested report produces a probability AND raised uncertainty AND both branches --
never a confident direction. And speed is reported separately from reliability, because a source
that is always right and always late has an unpriced fraction of zero and is worth nothing to
trade on.
"""

from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from macro.credibility import (  # noqa: E402
    MIN_TIER_SOURCES,
    TIER_PRIOR,
    Claim,
    CredibilityModel,
    redundancy_from_ledger,
)
from macro.ledger import MIN_SOURCE_N  # noqa: E402
from macro.schema import Status  # noqa: E402


def test_the_prior_ordering_is_defensible_and_is_only_a_prior() -> None:
    order = ["OFFICIAL", "WIRE", "SPECIALIST", "SOCIAL_OSINT"]
    means = [TIER_PRIOR[t][0] / sum(TIER_PRIOR[t]) for t in order]
    assert means == sorted(means, reverse=True), "official > wire > specialist > social, a priori"
    # And no tier is pinned at certainty -- a prior evidence can never move is not a prior.
    assert all(0.0 < m < 1.0 for m in means)


def test_an_unmeasured_source_is_exactly_its_tier() -> None:
    m = CredibilityModel()
    m.tier_of["some_blog"] = "SOCIAL_OSINT"
    p = m.posterior("some_blog")
    a, b = TIER_PRIOR["SOCIAL_OSINT"]
    assert (p.alpha, p.beta) == (a, b)
    assert p.status == Status.UNMEASURED


def test_an_unregistered_source_lands_on_UNKNOWN_never_on_trust() -> None:
    p = CredibilityModel().posterior("never_seen_before")
    assert p.tier == "UNKNOWN"
    assert p.p_true < TIER_PRIOR["OFFICIAL"][0] / sum(TIER_PRIOR["OFFICIAL"])


def test_a_tier_prior_is_overturned_by_its_members_measured_record() -> None:
    """The hierarchy LEARNS. A tier whose members keep being wrong loses its strength."""
    m = CredibilityModel()
    outcomes = {}
    tier_of = {}
    for i in range(MIN_TIER_SOURCES + 2):
        sid = f"wire{i}"
        # Wires seeded at ~0.91 prior, but measured at 0.4.
        outcomes[sid] = {"verified": 20, "falsified": 30, "leads": []}
        tier_of[sid] = "WIRE"
    before = TIER_PRIOR["WIRE"][0] / sum(TIER_PRIOR["WIRE"])
    m.fit(outcomes, tier_of=tier_of)
    a, b = m.tiers["WIRE"]
    after = a / (a + b)
    assert m.tier_status["WIRE"] == Status.MEASURED
    assert after < before, "measured outcomes must be able to move the tier down"
    assert 0.3 < after < 0.5


def test_a_thin_tier_keeps_its_prior_and_says_so() -> None:
    """Re-fitting a tier from two sources would let one bad source rewrite the prior for
    everything under it."""
    m = CredibilityModel()
    m.fit({"w0": {"verified": 20, "falsified": 30}}, tier_of={"w0": "WIRE"})
    assert m.tier_status["WIRE"] == Status.UNMEASURED
    assert m.tiers["WIRE"] == TIER_PRIOR["WIRE"]


def test_a_source_moves_toward_its_own_evidence_as_the_record_accumulates() -> None:
    m = CredibilityModel()
    m.tier_of["blog"] = "SOCIAL_OSINT"
    prior = m.posterior("blog").p_true
    m.fit({"blog": {"verified": 200, "falsified": 5}}, tier_of={"blog": "SOCIAL_OSINT"})
    after = m.posterior("blog").p_true
    assert after > prior + 0.3, "a source with a strong record must outrun its tier"
    assert m.posterior("blog").status == Status.MEASURED


def test_independent_confirmations_raise_the_posterior() -> None:
    m = CredibilityModel()
    for s in ("a", "b", "c"):
        m.tier_of[s] = "SPECIALIST"
    one = m.combine([Claim("a")])
    three = m.combine([Claim("a"), Claim("b"), Claim("c")])
    assert three.p_true > one.p_true


def test_correlated_sources_are_discounted_by_their_measured_co_report_rate() -> None:
    """Three wires quoting one wire is one observation wearing three coats."""
    clusters = [["a", "b", "c"]] * 10          # they always appear together
    rho = redundancy_from_ledger(clusters)
    assert rho[("a", "b")] == 1.0

    independent = CredibilityModel()
    correlated = CredibilityModel()
    for m in (independent, correlated):
        for s in ("a", "b", "c"):
            m.tier_of[s] = "SPECIALIST"
    correlated.redundancy.update(rho)
    claims = [Claim("a"), Claim("b"), Claim("c")]
    assert correlated.combine(claims).p_true < independent.combine(claims).p_true


def test_a_contested_report_raises_uncertainty_and_carries_both_branches() -> None:
    """The honest output for a disputed claim is a probability and MORE uncertainty, never a
    confident direction."""
    m = CredibilityModel()
    m.tier_of.update({"a": "WIRE", "b": "WIRE"})
    agreed = m.combine([Claim("a", True), Claim("b", True)])
    contested = m.combine([Claim("a", True), Claim("b", False)])

    assert contested.contested is True
    assert contested.uncertainty_mult > agreed.uncertainty_mult >= 1.0
    assert contested.uncertainty_mult > 1.0
    # Both branches, weighted -- the world sampler carries the disagreement rather than a winner.
    t, f = contested.branches
    assert t["true"] is True and f["true"] is False
    assert abs(t["p"] + f["p"] - 1.0) < 1e-9
    assert "CONTESTED" in contested.basis


def test_a_balanced_conflict_lands_near_a_half_with_the_largest_penalty() -> None:
    m = CredibilityModel()
    m.tier_of.update({"a": "WIRE", "b": "WIRE"})
    c = m.combine([Claim("a", True), Claim("b", False)])
    assert abs(c.p_true - 0.5) < 0.2
    assert c.uncertainty_mult > 1.5


def test_speed_is_reported_separately_from_reliability() -> None:
    """A source can be perfectly reliable and useless."""
    m = CredibilityModel()
    m.fit(
        {"late_but_right": {"verified": 100, "falsified": 2,
                            "leads": [-120.0] * (MIN_SOURCE_N + 2)},
         "early": {"verified": 60, "falsified": 20, "leads": [45.0] * (MIN_SOURCE_N + 2)}},
        tier_of={"late_but_right": "OFFICIAL", "early": "SPECIALIST"})
    late = m.posterior("late_but_right")
    early = m.posterior("early")
    assert late.p_true > early.p_true, "the reliable source is more reliable"
    assert late.lead_s is not None and late.lead_s < 0, "and it arrives after the move"
    rows = {r["source"]: r for r in m.report()["sources"]}
    assert rows["late_but_right"]["verdict"] == "reliable_but_late"
    assert rows["early"]["verdict"] == "reliable_and_early"


def test_no_claims_at_all_is_UNMEASURED_with_raised_uncertainty() -> None:
    c = CredibilityModel().combine([])
    assert c.status == Status.UNMEASURED
    assert c.p_true == 0.5
    assert c.uncertainty_mult > 1.0


def test_the_model_round_trips_through_disk(tmp_path: Path) -> None:
    m = CredibilityModel(path=tmp_path / "c.json")
    m.fit({f"w{i}": {"verified": 30, "falsified": 3} for i in range(MIN_TIER_SOURCES + 1)},
          tier_of={f"w{i}": "WIRE" for i in range(MIN_TIER_SOURCES + 1)})
    m.save()
    back = CredibilityModel(path=tmp_path / "c.json").load()
    assert back.tier_status["WIRE"] == Status.MEASURED
    assert abs(back.tiers["WIRE"][0] - m.tiers["WIRE"][0]) < 1e-6
