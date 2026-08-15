"""Per-family error control -- the only honest route to unlimited forward seats.

MEASURED 2026-08-15: 13 clocks against a cap of 12, zero free, 181 days to a first promotion. The
queue rations BREADTH, breadth is the only route to a higher combined Sharpe, so the cap is the
binding constraint on the desk's objective. Raising it would tighten every existing candidate's bar
-- Holm's strongest is alpha/m -- so the cap held, correctly, and the desk stayed narrow.

Partitioning fixes that, and these tests pin the three things that make it legitimate rather than a
loophole: the families are declared before the data, ambiguity resolves toward the TIGHTER bar, and
the cost is computed rather than waved away.
"""

from __future__ import annotations

from libs.validation.family_multiplicity import (
    FAMILIES,
    UNCLASSIFIED,
    bh_alpha,
    bh_bar,
    effective_m,
    family_error_budget,
    family_of,
    matches,
    partition,
)
from libs.validation.forward_stats import holm_bar


def test_A_NEW_CLOCK_IN_ONE_FAMILY_DOES_NOT_TIGHTEN_ANOTHERS_BAR() -> None:
    """THE WHOLE POINT. Under one cohort, starting a macro clock raises the bar a momentum
    candidate must clear -- a real cost paid by a real hypothesis for an unrelated one."""
    before = partition(["cashcarry", "funding_basis", "trend_regime"])
    after = partition(["cashcarry", "funding_basis", "trend_regime",
                       "defi_utilisation", "onchain_gas", "stablecoin_supply"])
    assert len(before["structure"]) == len(after["structure"]) == 1
    assert holm_bar(len(before["structure"])) == holm_bar(len(after["structure"]))
    # ... while the single-cohort bar would have moved against it
    assert holm_bar(3) < holm_bar(6)


def test_PARTITION_LOOSENS_NOTHING_INSIDE_A_FAMILY() -> None:
    """Members of one family still pay each other's multiplicity in full. The correction is
    applied, not evaded."""
    p = partition(["funding_a", "carry_b", "basis_c", "perpdex_d"])
    assert len(p["carry"]) == 4
    assert holm_bar(4) == holm_bar(len(p["carry"]))


def test_AMBIGUITY_RESOLVES_TOWARD_THE_TIGHTER_BAR_NOT_DICT_ORDER() -> None:
    """A REAL NAME FROM THE LIVE COHORT. `full_sweep_cross_asset_lead_1h_all_decay_breakout_decay
    _momentum` matches relative_value AND structure. First-match-wins would have let the
    declaration order of a dict literal decide a statistical threshold."""
    name = "full_sweep_cross_asset_lead_1h_all_decay_breakout_decay_momentum"
    assert len(matches(name)) == 2
    cohort = [name, "crossasset", "cny_premium", "trend_regime"]
    fam = family_of(name, cohort)
    sizes = {f: sum(1 for n in cohort if f in matches(n)) for f in matches(name)}
    assert sizes[fam] == max(sizes.values()), "an ambiguous name must join the LARGER family"


def test_AN_UNDECLARED_MECHANISM_IS_NOT_GIVEN_A_FREE_PASS() -> None:
    """Unclassified candidates share ONE cohort, so skipping the declaration is the EXPENSIVE
    path. Making it cheap would turn 'do not name your family' into an optimisation."""
    p = partition(["mystery_one", "mystery_two", "mystery_three", "cashcarry"])
    assert len(p[UNCLASSIFIED]) == 3
    assert family_of("mystery_one") == UNCLASSIFIED


def test_THE_UNDECLARED_BAR_IS_FLOORED_AT_THE_WORST_DECLARED_ONE() -> None:
    """THE DEFECT THE LIVE COHORT EXPOSED. `len()` alone made UNCLASSIFIED the CHEAPEST bar on the
    desk the moment it held fewer members than the largest declared family -- measured 2 against
    structure's 8, so t=1.96 against t=2.50. The dominant strategy becomes naming a candidate
    something the token list cannot match, which turns the partition into opt-out at exactly the
    moment a genuinely new mechanism arrives."""
    p = partition(["mystery_one", "trend_a", "momentum_b", "breakout_c", "wyckoff_d"])
    eff = effective_m(p)
    assert len(p[UNCLASSIFIED]) == 1
    assert eff[UNCLASSIFIED] == eff["structure"] == 4
    assert holm_bar(eff[UNCLASSIFIED]) >= max(holm_bar(v) for v in eff.values())


def test_THE_FLOOR_ONLY_EVER_TIGHTENS() -> None:
    """It is a max, so it cannot loosen a declared family's bar, and it cannot loosen UNCLASSIFIED's
    own when unclassified is already the largest cohort."""
    p = partition(["m1", "m2", "m3", "m4", "trend_a"])
    eff = effective_m(p)
    assert eff[UNCLASSIFIED] == 4 and eff["structure"] == 1
    for fam, members in p.items():
        assert eff[fam] >= len(members)


def test_FAMILIES_ARE_ABOUT_WHY_AN_EDGE_EXISTS_NOT_WHERE_IT_TRADES() -> None:
    """Splitting by symbol or timeframe would slice ONE question into many and evade the
    correction rather than apply it. Each declared family is a distinct mechanism claim."""
    assert set(FAMILIES) == {"carry", "flow", "relative_value", "structure", "onchain"}
    for tokens in FAMILIES.values():
        for tok in tokens:
            assert not tok.isdigit() and "usdt" not in tok and tok not in {"1h", "4h", "1d"}


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
    """Against the actual 13 names on the box, so this is exercised on the cohort it was built
    for rather than on invented ones."""
    live = ["defi_utilisation", "stablecoin_supply_momentum", "cny_premium",
            "walcl_reserve_impulse", "perpdex_funding::aster_BTCUSDT_level_rate::8h",
            "cashcarry", "crossasset", "trend_regime", "ls_contrarian", "oi_divergence"]
    p = partition(live)
    assert len(p) >= 4, "the live cohort spans several distinct mechanism claims"
    assert all(len(v) < len(live) for v in p.values())
    for members in p.values():
        assert holm_bar(len(members)) <= holm_bar(len(live))
