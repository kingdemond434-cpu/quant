"""Tests for the evidence-dependent ceiling ladder.

WHY THIS FILE EXISTS SEPARATELY. Installing the ladder left test_sleeve_allocation.py fully green
while quietly gutting it: with default evidence fields every sleeve now sits at UNPROVEN, so
assertions that once compared 0.150 against 0.000 now compare 0.020 against 0.000. They still pass,
and they no longer test what their names claim. A suite that goes green for a weaker reason than it
did yesterday is the "test that cannot fail" defect arriving by drift rather than by design.

COLLECTABILITY (converted 2026-08-01). This shipped as a script ending in `raise SystemExit`, the
FOURTH instance in one day of a shape that aborts pytest during COLLECTION (INTERNALERROR, exit 3)
and runs zero tests repo-wide. It was written minutes after the first three were diagnosed, which
is the strongest possible argument that the class needed a MECHANISM and not another repair --
tests/test_suite_collectable.py is that mechanism, and it is what found this file. Assertions are
preserved verbatim; only the harness changed.
"""
from __future__ import annotations

import pytest

from libs.risk import sleeve_allocation as sa


def sleeve(**kw):
    base = {"name": "disc", "sharpe": 1.0, "n_closes": 500, "rho_to_base": 0.0,
            "max_drawdown": 0.10, "regimes_positive": 4, "t_stat": 5.0,
            "persistence": 0.75}
    base.update(kw)
    return sa.Sleeve(**base)


BASE = sa.Sleeve("systematic", sharpe=1.20, n_closes=200, is_base=True)


def share_of(s):
    p = sa.allocate([BASE, s], 100_000.0)
    return next(a for a in p.allocations if a.name == s.name)


RUNGS = {
    "UNPROVEN": {"n_closes": 5},
    "INITIAL": {"n_closes": 25, "t_stat": 1.6, "regimes_positive": 1,
                "persistence": 0.0},
    "STRONG": {"n_closes": 70, "t_stat": 2.6, "regimes_positive": 2,
               "persistence": 0.0},
    "DURABLE": {},
}


# ---- the ladder climbs -----------------------------------------------------------------------
@pytest.mark.parametrize("want,kw", list(RUNGS.items()))
def test_reaches_each_rung(want: str, kw: dict) -> None:
    t, cap, blocker = sa.evidence_tier(sleeve(**kw))
    assert t == want, f"cap {cap:.2f}; next -- {blocker}"


def test_ceiling_rises_monotonically_with_evidence() -> None:
    caps = [sa.evidence_tier(sleeve(**RUNGS[k]))[1]
            for k in ("UNPROVEN", "INITIAL", "STRONG", "DURABLE")]
    assert caps == [0.02, 0.10, 0.25, 0.60], caps


def test_tier_ceiling_is_not_binding_when_kelly_asks_for_less() -> None:
    """The tier ceiling only BINDS when the edge asks for more than it.

    At Sharpe 1.0 against a Sharpe-1.2 base, fractional Kelly wants exactly 0.25, so DURABLE
    status is irrelevant -- the sleeve is Kelly-limited, not tier-limited, and that is correct. A
    first draft asserted every DURABLE sleeve exceeds the old constant, which confused the CEILING
    with the ALLOCATION.
    """
    assert abs(share_of(sleeve()).share - 0.25) < 1e-9, f"{share_of(sleeve()).share:.3f}"


def test_durable_sleeve_with_the_edge_to_justify_it_exceeds_the_old_constant() -> None:
    got = share_of(sleeve(sharpe=2.4)).share
    assert got > 0.25, f"{got:.3f}"


# ---- conjunctive: one great number cannot buy a rung -----------------------------------------
def test_spectacular_sharpe_cannot_buy_a_rung_on_a_short_record() -> None:
    assert sa.evidence_tier(sleeve(sharpe=25.0, n_closes=5, t_stat=0.9))[0] == "UNPROVEN"


@pytest.mark.parametrize("field,bad", [("max_drawdown", 0.90), ("regimes_positive", 0),
                                       ("t_stat", 1.6), ("persistence", 0.0),
                                       ("rho_to_base", 0.95)])
def test_failing_one_condition_alone_blocks_durable(field: str, bad: float) -> None:
    t, cap, _ = sa.evidence_tier(sleeve(**{field: bad}))
    assert t != "DURABLE", f"-> {t} ({cap:.2f})"


# ---- demotion is immediate, not latched ------------------------------------------------------
def test_decayed_sleeve_is_demoted_at_once_no_ratchet() -> None:
    hot = sleeve()
    demoted = sa.Sleeve(**{**hot.__dict__, "t_stat": 0.4})
    assert sa.evidence_tier(demoted)[0] == "UNPROVEN", (
        "t-stat collapse -> straight back to the learning stake")


def test_rising_correlation_to_the_base_demotes() -> None:
    assert sa.evidence_tier(sleeve(rho_to_base=0.85))[1] < 0.60


# ---- defaults must fail upward, never promote by omission ------------------------------------
def test_omitted_evidence_fields_cannot_promote_a_sleeve() -> None:
    bare = sa.Sleeve("d", sharpe=5.0, n_closes=10_000)
    assert sa.evidence_tier(bare)[0] == "UNPROVEN", (
        "no drawdown/regime/track supplied -> lowest rung")


# ---- the blocker names the thing to fix ------------------------------------------------------
def test_blocker_names_the_specific_failing_condition_and_how_to_fix_it() -> None:
    _, _, why = sa.evidence_tier(sleeve(t_stat=2.6))
    assert "t>=" in why and "faster" in why, why


def test_calendar_span_does_not_gate_a_rung() -> None:
    """Gating on days punishes a fast book for being fast; the statistics are what matter."""
    assert (sa.evidence_tier(sleeve(track_days=14))[0]
            == sa.evidence_tier(sleeve(track_days=900))[0] == "DURABLE"), (
        "14 days and 900 days both reach DURABLE on identical statistics")


def test_tstat_not_sharpe_separates_a_hot_streak_from_an_edge() -> None:
    assert sa.evidence_tier(sleeve(sharpe=3.0, n_closes=25, t_stat=1.0))[0] == "UNPROVEN", (
        "Sharpe 3.0 on 25 closes at t=1.0 stays at the learning stake")


# ---- base_candidate surfaces the structural decision -----------------------------------------
def test_a_sleeve_outgrowing_the_top_rung_is_flagged_as_a_base_candidate() -> None:
    huge = share_of(sleeve(sharpe=12.0))
    assert huge.base_candidate and huge.share <= 0.60, (
        f"share {huge.share:.3f}, tier {huge.tier}, base_candidate={huge.base_candidate}")


# ---- aggregate budget still holds across many strong sleeves ---------------------------------
def test_aggregate_booster_share_cannot_exceed_the_top_rung() -> None:
    many = sa.allocate([BASE] + [sa.Sleeve(**{**sleeve().__dict__, "name": f"d{i}"})
                                 for i in range(5)], 100_000.0)
    tot = sum(a.share for a in many.allocations if a.name != "systematic")
    assert tot <= 0.60 + 1e-9, f"{tot:.3f}"


def test_shares_still_sum_to_one() -> None:
    many = sa.allocate([BASE] + [sa.Sleeve(**{**sleeve().__dict__, "name": f"d{i}"})
                                 for i in range(5)], 100_000.0)
    assert abs(sum(a.share for a in many.allocations) - 1.0) < 1e-9
