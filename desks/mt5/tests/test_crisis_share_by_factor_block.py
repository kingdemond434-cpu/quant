"""Crisis correlation per FACTOR BLOCK, under the book-wide scalar: relief where measured, never
a harder stress anywhere.

One scalar `crisis_common_share` fused every sleeve onto one common factor at the same loading,
so a gold sleeve paid for a USD co-explosion it does not share. `conditional_covariance.calibrate`
now measures the stress-regime correlation inside each block `libs/risk/fx_factors` can name
(USD leg, JPY leg, metals) and hands each sleeve its block's share -- with the ratcheted scalar
as the CEILING, so the only thing this can do to a sleeve's crisis worlds is make them less
fused. These pin the decomposition, the cap, the shrinkage, and that the allocator's book can
only gain heat from it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.portfolio.conditional_covariance import (  # noqa: E402
    FACTOR_BLOCKS,
    MIN_BLOCK_SLEEVES,
    block_shares,
    calibrate,
    factor_blocks_of,
)
from libs.portfolio.robust_elog import (  # noqa: E402
    SleeveEvidence,
    WorldConfig,
    optimise,
    sample_worlds,
    score_book,
)

STANDING = WorldConfig()


# ------------------------------------------------------------------------------ the decomposition
def test_symbols_land_in_the_blocks_their_legs_name() -> None:
    assert factor_blocks_of("EURUSD") == ("USD",)
    assert factor_blocks_of("EURJPY") == ("JPY",)
    assert factor_blocks_of("USDJPY") == ("USD", "JPY")
    assert factor_blocks_of("XAUUSD") == ("USD", "metals")
    assert factor_blocks_of("XAGUSD") == ("USD", "metals")
    assert factor_blocks_of("gold") == ("USD", "metals"), "the armed gold windows are metals"
    assert factor_blocks_of("EURGBP") == (), "a cross with neither leg is in no shocked block"
    assert factor_blocks_of("US500") == (), "not a cross: never guessed into a block"
    assert factor_blocks_of("NatGas") == ()
    assert factor_blocks_of("") == ()
    assert FACTOR_BLOCKS == ("USD", "JPY", "metals")


# --------------------------------------------------------------------------- the block measurement
def _blocks(n_days: int, seed: int, usd_share: float, metal_share: float,
            with_xauusd: bool = False) -> tuple:
    """Four USD-leg sleeves fused at `usd_share`, three EUR-quoted metals sleeves at
    `metal_share`, independent between the two blocks; plus one EURGBP in no block.

    The metals are quoted in EUR so the two blocks are DISJOINT: XAUUSD's quote leg is real
    dollar risk (`fx_factors.decompose` books it so), which is exactly what the two-block test
    below adds with `with_xauusd`.
    """
    rng = np.random.default_rng(seed)
    f_usd = rng.standard_normal(n_days)[:, None]
    f_met = rng.standard_normal(n_days)[:, None]
    usd = np.sqrt(usd_share) * f_usd + np.sqrt(1 - usd_share) * rng.standard_normal((n_days, 4))
    met = (np.sqrt(metal_share) * f_met
           + np.sqrt(1 - metal_share) * rng.standard_normal((n_days, 3)))
    other = rng.standard_normal((n_days, 1))
    cols = [usd, met, other]
    names = ["EURUSD_a", "GBPUSD_a", "AUDUSD_a", "NZDUSD_a", "XAUEUR_a", "XAGEUR_a", "XPTEUR_a",
             "EURGBP_a"]
    symbols = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "XAUEUR", "XAGEUR", "XPTEUR", "EURGBP"]
    if with_xauusd:
        cols.append(np.sqrt(metal_share) * f_met
                    + np.sqrt(1 - metal_share) * rng.standard_normal((n_days, 1)))
        names.append("XAUUSD_a")
        symbols.append("XAUUSD")
    return np.hstack(cols), names, symbols


def test_a_block_measured_less_fused_than_the_scalar_is_relieved_and_the_rest_stand() -> None:
    hist, names, symbols = _blocks(3000, 1, usd_share=0.70, metal_share=0.10)
    by_block, share, blocks = block_shares(hist, names, symbols, scalar=0.55, lam=0.98,
                                           n_days=3000)
    assert by_block["metals"].status == "MEASURED"
    assert by_block["metals"].applied_share < 0.55
    assert by_block["metals"].mean_corr == pytest.approx(0.10, abs=0.06)
    # The USD block measured MORE fused than the scalar: reported, and carried AT the scalar.
    assert by_block["USD"].mean_corr > 0.55
    assert by_block["USD"].status == "AT_SCALAR"
    assert by_block["USD"].applied_share == pytest.approx(0.55)
    assert "ceiling" in by_block["USD"].why
    # JPY has no member: unmeasured, scalar stands.
    assert by_block["JPY"].status == "UNMEASURED" and by_block["JPY"].applied_share == 0.55
    # Only relieved sleeves are listed; the USD ones and the EURGBP carry the scalar unlisted.
    assert set(share) == {"XAUEUR_a", "XAGEUR_a", "XPTEUR_a"}
    assert blocks["EURGBP_a"] == ()
    assert all(v < 0.55 for v in share.values())


def test_a_sleeve_in_two_blocks_takes_the_higher_applied_share() -> None:
    """XAUUSD is metals AND USD. It rides the metals factor here, so it dilutes the USD block
    below the scalar too -- and it is stressed at the HIGHER of the two applied shares (USD's),
    never at the metals' lower one and never past the scalar."""
    hist, names, symbols = _blocks(3000, 2, usd_share=0.70, metal_share=0.10, with_xauusd=True)
    by_block, share, blocks = block_shares(hist, names, symbols, scalar=0.55, lam=0.98,
                                           n_days=3000)
    assert blocks["XAUUSD_a"] == ("USD", "metals")
    assert by_block["metals"].applied_share < by_block["USD"].applied_share <= 0.55
    assert share["XAUUSD_a"] == pytest.approx(by_block["USD"].applied_share)
    assert share["XAUEUR_a"] == pytest.approx(by_block["metals"].applied_share)


def test_a_thin_block_is_not_measured_and_carries_the_scalar() -> None:
    rng = np.random.default_rng(3)
    hist = rng.standard_normal((500, 2))
    by_block, share, _ = block_shares(hist, ["EURUSD_a", "GBPUSD_a"], ["EURUSD", "GBPUSD"],
                                      scalar=0.55, lam=0.9, n_days=500)
    assert MIN_BLOCK_SLEEVES == 3
    assert by_block["USD"].status == "UNMEASURED" and by_block["USD"].n_sleeves == 2
    assert share == {}


def test_thin_stress_evidence_moves_a_block_only_a_little() -> None:
    hist, names, symbols = _blocks(3000, 4, usd_share=0.55, metal_share=0.05)
    little = block_shares(hist, names, symbols, scalar=0.55, lam=0.20, n_days=3000)[0]
    lot = block_shares(hist, names, symbols, scalar=0.55, lam=0.95, n_days=3000)[0]
    assert lot["metals"].applied_share < little["metals"].applied_share < 0.55


# ------------------------------------------------------------------------- through `calibrate`
def test_calibrate_without_symbols_is_exactly_what_it_was() -> None:
    hist, _names, _ = _blocks(1500, 5, usd_share=0.70, metal_share=0.10)
    labels = ["calm"] * 900 + ["hot"] * 600
    hist[900:] *= 3.0
    cal = calibrate(hist, labels, standing_share=STANDING.crisis_common_share,
                    standing_vol_mult=STANDING.crisis_vol_mult)
    assert cal.by_block == {} and cal.share_by_sleeve == {}
    assert set(cal.as_overrides()) == {"crisis_common_share", "crisis_vol_mult"}


def test_calibrate_with_symbols_relieves_the_metals_block_and_keeps_the_ratchet() -> None:
    hist, names, symbols = _blocks(1500, 6, usd_share=0.70, metal_share=0.10)
    labels = ["calm"] * 900 + ["hot"] * 600
    hist[900:] *= 3.0
    cal = calibrate(hist, labels, standing_share=STANDING.crisis_common_share,
                    standing_vol_mult=STANDING.crisis_vol_mult, symbols=symbols, names=names)
    assert cal.stress_regime == "hot"
    # The book-wide scalar still ratchets: never below the standing constant.
    assert cal.crisis_common_share >= STANDING.crisis_common_share
    assert cal.by_block["metals"].status == "MEASURED"
    assert cal.by_block["metals"].n_days == 600
    assert all(v <= cal.crisis_common_share for v in cal.share_by_sleeve.values())
    over = cal.as_overrides()
    assert "crisis_common_share_by_sleeve" in over
    for key in over:
        assert hasattr(STANDING, key), key
    cfg = WorldConfig(**over)                       # the overrides ARE WorldConfig fields
    assert dict(cfg.crisis_common_share_by_sleeve) == cal.share_by_sleeve
    assert "factor blocks" in cal.note
    # A symbol mapping keyed by name is accepted too.
    cal2 = calibrate(hist, labels, standing_share=STANDING.crisis_common_share,
                     standing_vol_mult=STANDING.crisis_vol_mult,
                     symbols=dict(zip(names, symbols, strict=True)), names=names)
    assert cal2.share_by_sleeve == cal.share_by_sleeve


def test_a_block_share_is_never_above_the_scalar_however_fused_it_measures() -> None:
    hist, names, symbols = _blocks(1500, 7, usd_share=0.90, metal_share=0.90)
    labels = ["calm"] * 900 + ["hot"] * 600
    hist[900:] *= 3.0
    cal = calibrate(hist, labels, standing_share=STANDING.crisis_common_share,
                    standing_vol_mult=STANDING.crisis_vol_mult, symbols=symbols, names=names)
    for b in cal.by_block.values():
        assert b.applied_share <= cal.crisis_common_share + 1e-12, b
    assert cal.share_by_sleeve == {}, "nothing below the scalar means nothing is listed"


# ------------------------------------------------------------- the law: heat can only go up
def test_relieving_a_block_never_lowers_any_sleeve_or_the_total() -> None:
    """The metals block keeps its independence in crisis worlds, so the free optimum gives the
    metals sleeves at least what it gave them under the scalar, the total is at least what it
    was, and a mandated 20% is still exactly 20%."""
    # Sleeves shaped like the desk's own: flat three days in four, a USD factor through the FX
    # legs, the metals independent of it. Measured over 18 (population, seed) combinations
    # before this fixture was pinned: relief never lowered the total or a metals sleeve.
    rng = np.random.default_rng(8)
    n, act = 700, 0.25
    f_usd = rng.standard_normal(n)
    ev = []
    for name in ("EURUSD_a", "GBPUSD_a", "AUDUSD_a"):
        z = 0.7 * f_usd + 0.7 * rng.standard_normal(n)
        r = (z + 0.06 / act) * (rng.random(n) < act)
        ev.append(SleeveEvidence(name=name, daily_r=r, symbol=name[:6], family="fx",
                                 forward_days=60))
    for name in ("XAUEUR_a", "XAGEUR_a", "XPTEUR_a"):
        r = (rng.standard_normal(n) + 0.06 / act) * (rng.random(n) < act)
        ev.append(SleeveEvidence(name=name, daily_r=r, symbol=name[:6], family="met",
                                 forward_days=60))
    relief = tuple((e.name, 0.15) for e in ev if e.family == "met")
    base_cfg = WorldConfig(n_worlds=64, n_rows=160, seed=5, crisis_prob=0.30)
    relieved_cfg = WorldConfig(n_worlds=64, n_rows=160, seed=5, crisis_prob=0.30,
                               crisis_common_share_by_sleeve=relief)
    w_base, w_rel = sample_worlds(ev, base_cfg), sample_worlds(ev, relieved_cfg)
    before = optimise(ev, hard_cap=0.45, target=None, cfg=base_cfg, worlds=w_base)
    after = optimise(ev, hard_cap=0.45, target=None, cfg=relieved_cfg, worlds=w_rel)
    assert before.total_heat > 0.01, "fixture: the book must want heat for relief to show"
    assert after.total_heat >= before.total_heat - 1e-6, (before.total_heat, after.total_heat)
    for e in ev:
        if e.family == "met":
            assert after.heat[e.name] >= before.heat[e.name] - 1e-4, e.name
    # The SAME book, scored on the relieved worlds, grows at least as fast: the relief acts
    # through crisis-world variance drag, not through a re-composition.
    same_before = score_book(ev, before.heat, cfg=base_cfg, worlds=w_base)
    same_after = score_book(ev, before.heat, cfg=relieved_cfg, worlds=w_rel)
    assert same_after["mean_log_growth"] >= same_before["mean_log_growth"] - 1e-9
    assert same_after["robust_score"] >= same_before["robust_score"] - 1e-9
    mandated = optimise(ev, hard_cap=0.45, target=0.20, cfg=relieved_cfg, worlds=w_rel,
                        max_per_sleeve=0.10)
    assert mandated.total_heat == pytest.approx(0.20, abs=1e-6)
    assert all(v <= 0.10 + 1e-9 for v in mandated.heat.values())
