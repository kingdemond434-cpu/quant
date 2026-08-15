"""Per-family error control -- the only honest route to unlimited forward seats.

MEASURED 2026-08-15: 13 clocks against a cap of 12, zero free, 181 days to a first promotion. The
queue rations BREADTH, breadth is the only route to a higher combined Sharpe, so the cap is the
binding constraint on the desk's objective. Raising it would tighten every existing candidate's bar
-- Holm's strongest is alpha/m -- so the cap held, correctly, and the desk stayed narrow.

Partitioning fixes that, and these tests pin the four things that make it legitimate rather than a
loophole: the taxonomy is the census's rather than one this module invented, a class earns its own
error budget by being a separate QUESTION, an undeclared mechanism never gets the cheaper bar, and
the cost is computed rather than waved away.
"""

from __future__ import annotations

from libs.research.mechanism_census import CLASS_BY_ID
from libs.validation.family_multiplicity import (
    CORRELATED_CORE,
    ORTHOGONALITY_FLOOR,
    UNCLASSIFIED,
    bh_alpha,
    bh_bar,
    effective_m,
    family_error_budget,
    family_of,
    partition,
)
from libs.validation.forward_stats import holm_bar


def test_THE_TAXONOMY_IS_THE_CENSUS_AND_NOT_A_SECOND_COPY() -> None:
    """TWO TAXONOMIES ARE TWO ANSWERS, and the one nobody maintains is the one that quietly
    disagrees. This module invented five token families beside `mechanism_census.TAXONOMY` -- 26
    classes with named payers, economic definitions and declared orthogonality, already ranking the
    research agenda. Every family name this returns must be a census class id."""
    live = ["H5_cvd_divergence", "oi_divergence", "cny_premium", "defi_utilisation",
            "stablecoin_supply_momentum", "walcl_reserve_impulse"]
    for name in live:
        fam = family_of(name)
        assert fam in CLASS_BY_ID, f"{name} -> {fam}, which is not a census class"


def test_A_NEW_CLOCK_IN_ONE_FAMILY_DOES_NOT_TIGHTEN_ANOTHERS_BAR() -> None:
    """THE WHOLE POINT. Under one cohort, starting a macro clock raises the bar a flow candidate
    must clear -- a real cost paid by a real hypothesis for an unrelated one."""
    before = partition(["H5_cvd_divergence", "oi_divergence"])
    after = partition(["H5_cvd_divergence", "oi_divergence",
                       "defi_utilisation", "cny_premium", "stablecoin_supply_momentum"])
    flow = "informed_order_flow"
    assert len(before[flow]) == len(after[flow]) == 1
    assert holm_bar(len(before[flow])) == holm_bar(len(after[flow]))
    # ... while the single-cohort bar would have moved against it
    assert holm_bar(2) < holm_bar(5)


def test_PARTITION_LOOSENS_NOTHING_INSIDE_A_FAMILY() -> None:
    """Members of one class still pay each other's multiplicity in full. The correction is
    applied, not evaded."""
    p = partition(["oi_divergence", "ls_contrarian", "funding_stress_reversal"])
    assert len(p["positioning_crowding_unwind"]) == 3
    assert holm_bar(3) == holm_bar(len(p["positioning_crowding_unwind"]))


def test_A_CLASS_EARNS_ITS_OWN_BUDGET_BY_BEING_A_SEPARATE_QUESTION() -> None:
    """ELEVEN PRICE PATTERNS ARE ONE QUESTION HOWEVER MANY NAMES THEY CARRY. The census scores
    `price_continuation` at 0.03 and `liquidity_provision_immediacy` at 0.1 -- its own statement
    that these are the promiscuous vocabulary most of the desk's history already lives in. Giving
    them separate seat pools would manufacture breadth by renaming, so they share one cohort."""
    assert CLASS_BY_ID["price_continuation"].orthogonality < ORTHOGONALITY_FLOOR
    assert CLASS_BY_ID["liquidity_provision_immediacy"].orthogonality < ORTHOGONALITY_FLOOR
    p = partition(["H2_volume_breakout", "H9_opening_range", "H10_vol_compression",
                   "H1_structural_fade", "H6_wyckoff", "H7_vwap_reversion", "H11_band_fade",
                   "H5_cvd_divergence"])
    assert len(p[CORRELATED_CORE]) == 7, "seven price/mean-reversion rules, one question"
    assert p["informed_order_flow"] == ["H5_cvd_divergence"]


def test_THE_TAPE_RULE_IS_THE_ONE_THE_DESK_DOES_NOT_ALREADY_HOLD() -> None:
    """H5 reads signed aggressive flow, which no other rule on the desk can see -- and the census
    scores informed_order_flow at 0.55 against price_continuation's 0.03. H4 reads the same tape
    and is NOT the same claim: 'unaccepted prices revert to where volume traded' is an immediacy
    argument, and filing it beside H5 would credit the desk with two informed-flow tests when it
    has one."""
    assert family_of("H5_cvd_divergence") == "informed_order_flow"
    assert family_of("H4_auction_value") == CORRELATED_CORE
    assert CLASS_BY_ID["informed_order_flow"].orthogonality >= ORTHOGONALITY_FLOOR


def test_AN_UNDECLARED_MECHANISM_IS_NOT_GIVEN_A_FREE_PASS() -> None:
    """A name the census cannot place lands in UNCLASSIFIED, which is never the cheaper bar."""
    assert family_of("zzz_unplaceable_thing") == UNCLASSIFIED
    p = partition(["zzz_one", "zzz_two", "zzz_three", "oi_divergence"])
    assert len(p[UNCLASSIFIED]) == 3


def test_THE_UNDECLARED_BAR_IS_FLOORED_AT_THE_WORST_DECLARED_ONE() -> None:
    """THE DEFECT THE LIVE COHORT EXPOSED. `len()` alone made UNCLASSIFIED the CHEAPEST bar on the
    desk the moment it held fewer members than the largest declared family. The dominant strategy
    becomes naming a candidate something the taxonomy cannot match, which turns the partition into
    opt-out at exactly the moment a genuinely new mechanism arrives."""
    p = partition(["zzz_unplaceable", "H2_volume_breakout", "H9_opening_range",
                   "H10_vol_compression", "H1_structural_fade"])
    eff = effective_m(p)
    assert len(p[UNCLASSIFIED]) == 1
    assert eff[UNCLASSIFIED] == eff[CORRELATED_CORE] == 4
    assert holm_bar(eff[UNCLASSIFIED]) >= max(holm_bar(v) for v in eff.values())


def test_THE_FLOOR_ONLY_EVER_TIGHTENS() -> None:
    """It is a max, so it cannot loosen a declared family's bar, and it cannot loosen UNCLASSIFIED's
    own when unclassified is already the largest cohort."""
    p = partition(["zzz_a", "zzz_b", "zzz_c", "zzz_d", "H2_volume_breakout"])
    eff = effective_m(p)
    assert eff[UNCLASSIFIED] == 4 and eff[CORRELATED_CORE] == 1
    for fam, members in p.items():
        assert eff[fam] >= len(members)


def test_BH_IS_LOOSER_THAN_HOLM_AND_ONLY_BELOW_THE_TOP_RANK() -> None:
    """FDR buys breadth by judging the k-th discovery against how many are being made. At rank 1
    the two agree exactly -- BH is not a blanket discount, and a caller cannot get a cheaper bar
    for its single best candidate by switching."""
    assert abs(bh_alpha(20, 1) - 0.05 / 20) < 1e-12, "rank 1 is alpha/m under both"
    assert bh_bar(20, 1) == holm_bar(20, 1)
    assert bh_bar(20, 10) < bh_bar(20, 1), "later discoveries face a looser bar under FDR"


def test_THE_COST_OF_PARTITIONING_IS_COMPUTED_NOT_WAVED_AWAY() -> None:
    """Per-family FWER does NOT give global FWER. The desk does not get breadth for free, and the
    number it does pay is stated on the artifact rather than discovered later."""
    b = family_error_budget(5)
    # the field is rounded for reporting; compare at that precision
    assert abs(float(b["global_fwer"]) - (1 - 0.95 ** 5)) < 1e-4
    assert float(b["global_fwer"]) > 0.05
    assert "NOT free" in str(b["why"]) and "NOT hidden" in str(b["why"])
    assert float(family_error_budget(1)["global_fwer"]) == 0.05


def test_THE_LIVE_COHORT_PARTITIONS_INTO_REAL_FAMILIES() -> None:
    """Against the actual names on the box, so this is exercised on the cohort it was built for
    rather than on invented ones."""
    live = ["defi_utilisation", "stablecoin_supply_momentum", "cny_premium",
            "walcl_reserve_impulse", "perpdex_funding::aster_BTCUSDT_level_rate::8h",
            "cashcarry", "crossasset", "trend_regime", "ls_contrarian", "oi_divergence"]
    p = partition(live)
    assert len(p) >= 4, "the live cohort spans several distinct mechanism claims"
    assert all(len(v) < len(live) for v in p.values())
    for members in p.values():
        assert holm_bar(len(members)) <= holm_bar(len(live))
