"""The orthogonal sweep paired XAUUSD with 3M, and called that cross-asset research.

MEASURED 2026-08-28 on the live sweep report. The peer and factor sets were
`[s for s in symbols if s != sym][:12]` over an ALPHABETICALLY sorted universe, so:

  * `relative_value` and `correlation_regime` ran XAUUSD against **3M**, the industrial
    conglomerate share CFD, and every FX cross against whichever of `3M / ADAUSD / ADP / AMD /
    AT&T` sorted first. Both families reported "ran on 297 symbols" -- coverage that reads as
    healthy while measuring ~590 economically arbitrary pairings. A survivor out of that is a
    spurious pairing that consumes a forward slot and corrupts the prior, and the real mechanism
    was never tested, so the family would die on evidence that was never about it.
  * `pca_residual` was absent from the kwargs map entirely, so it ran with `factors=None`, hit
    its own `len(factors) < 4` refusal and returned `[]` on all 297 symbols -- reported as
    `no-signals (4+ factor instruments' H1)`, a message quoting the family's own requirement
    while the sweep held the frames three lines away. Absence read as a clean verdict, on the one
    family built to break the single-family concentration that blocks N_eff.
  * `calendar_month` takes required keyword-only `active_month`/`side_bias` (source evidence, not
    searched parameters), so calling it blind raised TypeError on all 297 symbols -- and those
    297 crashes were filed into `input_gaps` beside genuine acquisition gaps, where a bug reads
    as a missing feed and nobody investigates.

Selection is STRUCTURAL -- symbol string, `asset_class`, `bars` -- so there is nothing to leak.
A peer chosen by measured correlation would be a conditioning variable picked with knowledge of
the whole sample, which is the look-ahead this desk has paid for before.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1]
for p in (str(BASE), str(BASE / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import orthogonal_sweep as osw  # noqa: E402


def _meta(**rows: tuple[str, int]) -> dict:
    return {sym: {"asset_class": cls, "bars": bars} for sym, (cls, bars) in rows.items()}


META = _meta(
    # Alphabetically first, and economically unrelated to everything below -- the old peer.
    **{"3M": ("Equities", 9739)},
    ADAUSD=("Crypto", 60000),
    ExxonMobil=("Equities", 21003),
    XAUUSD=("Commodities", 49932),
    XAUAUD=("Commodities", 30000),
    XAGUSD=("Commodities", 40000),
    EURJPY=("Forex", 50000),
    EURCHF=("Forex", 53867),
    USDJPY=("Forex", 52000),
    US500=("Indices", 43262),
    NAS100=("Indices", 41000),
    XNGUSD=("Energy", 33277),
    Thin=("Bonds", 40),
)
SYMBOLS = sorted(META)


def test_the_peer_is_related_not_alphabetically_first() -> None:
    """The bug, exactly: XAUUSD's peer was 3M because '3' sorts before everything."""
    assert SYMBOLS[0] == "3M", "fixture must reproduce the alphabetical trap"

    assert osw._peer_symbol("XAUUSD", SYMBOLS, META) in {"XAUAUD", "XAGUSD"}
    assert osw._peer_symbol("EURJPY", SYMBOLS, META) in {"EURCHF", "USDJPY"}
    assert osw._peer_symbol("USDJPY", SYMBOLS, META) in {"EURJPY", "USDJPY"} - {"USDJPY"}
    # Non-FX names have no legs to share, so the peer falls back to the same asset class --
    # still related, still never the alphabetical head unless it belongs there.
    assert osw._peer_symbol("US500", SYMBOLS, META) == "NAS100"
    assert osw._peer_symbol("3M", SYMBOLS, META) == "ExxonMobil"


def test_the_peer_prefers_the_distinguishing_leg() -> None:
    """USD is shared by half the universe; the other leg is what makes the pair that pair."""
    peer = osw._peer_symbol("XAUUSD", SYMBOLS, META)
    assert peer is not None and "XAU" in peer, (
        "a USD-leg match would make every USD pair a peer of every other; the non-USD leg is "
        "the one that carries the instrument's identity")


def test_the_factor_basket_spans_asset_classes_and_is_deep_enough() -> None:
    """pca_residual REFUSES below four factors, so a basket that cannot span cannot ever run."""
    basket = osw._factor_symbols(SYMBOLS, META)

    assert len(basket) >= 4, "below four, pca_residual returns [] by its own design"
    assert len(basket) <= osw.FACTOR_BASKET_MAX
    classes = {META[s]["asset_class"] for s in basket}
    assert len(classes) >= 4, f"latent forces must SPAN, got only {classes}"
    # A THIN MEMBER TRUNCATES EVERY RESIDUAL: the factor matrix is an intersection.
    assert "Thin" not in basket, "a 40-bar instrument would cost every symbol its history"


def test_the_factor_basket_is_stable_across_calls() -> None:
    """Identity is recorded as `factor_symbols`; a basket that reshuffles is not an identity."""
    assert osw._factor_symbols(SYMBOLS, META) == osw._factor_symbols(SYMBOLS, META)


def _kwargs_map_keys() -> dict[str, set[str]]:
    """`kwargs_by_family` as {family: {kwarg names}}, read from the AST rather than by string
    slicing -- a substring search over this file would pass on a commented-out line."""
    import ast
    tree = ast.parse((BASE / "research" / "orthogonal_sweep.py").read_text("utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and node.targets
                and getattr(node.targets[0], "id", "") == "kwargs_by_family"
                and isinstance(node.value, ast.Dict)):
            return {k.value: {kk.value for kk in v.keys}          # type: ignore[union-attr]
                    for k, v in zip(node.value.keys, node.value.values, strict=True)
                    if isinstance(k, ast.Constant) and isinstance(v, ast.Dict)}
    raise AssertionError("kwargs_by_family literal not found -- the wiring moved, re-pin it")


@pytest.mark.parametrize("family", ["pca_residual", "cross_asset_residual"])
def test_the_residual_families_are_handed_the_factors(family: str) -> None:
    """pca_residual was never in the kwargs map at all -- that is the whole 297-symbol zero."""
    kwargs_map = _kwargs_map_keys()
    assert family in kwargs_map, (
        f"{family} takes `factors` and refuses without them; omitting it from the map turns a "
        f"wiring bug into 297 rows that read as a missing data feed")
    assert "factors" in kwargs_map[family]


def test_every_family_needing_an_input_is_wired_to_one() -> None:
    """The recursion: a family declaring a non-price input must appear in the kwargs map.

    This is what would have caught pca_residual on the day it was added -- the family declared
    its need in FAMILY_INPUTS, the sweep never wired it, and the only symptom was a zero that
    looked like missing data.
    """
    from mt5desk.families_orthogonal import FAMILY_INPUTS, ORTHOGONAL_FAMILIES

    kwargs_map = _kwargs_map_keys()
    unwired = []
    for fam, fn in ORTHOGONAL_FAMILIES.items():
        need, _source = FAMILY_INPUTS.get(fam, ("", None))
        if not need or need == "price only":
            continue
        if (fam in kwargs_map or osw._unsuppliable(fn, {})
                or fam in osw.NOT_SOURCED_HERE):
            continue        # wired, needs source evidence, or declared out of scope with a reason
        unwired.append(f"{fam} (needs {need})")
    assert not unwired, (
        "these families declare an input the sweep never passes, so they return [] on every "
        f"symbol and it reads as a data gap: {unwired}")


def test_the_macro_regime_is_a_series_not_a_broadcast_scalar() -> None:
    """The old reader broadcast one scalar over all history: constant, and dated in the future.

    Constant means `macro > regime_high` puts every bar in one regime and the family degenerates
    to unconditional. Dated in the future means a 2019 bar conditioned on a 2026 reading -- the
    conditioning-variable look-ahead, which fails toward a FALSE POSITIVE that nothing downstream
    catches. Both are pinned here because the second is invisible in any output.
    """
    import pandas as pd

    idx = pd.date_range("2024-06-01", "2026-08-01", freq="1h", tz="UTC")
    series = osw._macro_series(idx)
    if series is None:
        pytest.skip("data/fred_macro.json unavailable in this tree -- UNMEASURED, not a pass")

    valid = series.dropna()
    assert len(valid) > 250, "a regime series needs history to rank against"
    assert valid.nunique() > 10, "a broadcast scalar has exactly one value; this must vary"
    assert 0.0 <= float(valid.min()) and float(valid.max()) <= 1.0, (
        "the family compares against regime_high=0.5, so the transform must land in [0,1]")
    assert 0.02 < float((valid > 0.5).mean()) < 0.98, (
        "a regime variable that is always on one side of the threshold conditions nothing")


def test_the_macro_regime_has_no_look_ahead() -> None:
    """Truncate the bar index early: a past bar's value may not move when later bars exist."""
    import pandas as pd

    full_idx = pd.date_range("2024-06-01", "2026-08-01", freq="1h", tz="UTC")
    full = osw._macro_series(full_idx)
    if full is None:
        pytest.skip("data/fred_macro.json unavailable in this tree -- UNMEASURED, not a pass")
    early = osw._macro_series(full_idx[full_idx < "2025-06-01"])
    assert early is not None

    common = early.dropna().index.intersection(full.dropna().index)
    assert len(common) > 500, "control needs overlap to be worth anything"
    assert float((early.reindex(common) - full.reindex(common)).abs().max()) == 0.0, (
        "a value changed when future observations were added -- the rank is looking ahead")


def test_the_macro_series_is_lagged_behind_its_own_print() -> None:
    """A print dated D is not knowable at D's open; zero lag is a same-bar leak."""
    assert osw.MACRO_PUBLICATION_LAG_D >= 1
    # Monthly releases must stay out until vintages cover them: their observation date precedes
    # publication by weeks, which no lag constant can repair.
    for monthly in ("UNRATE", "CPIAUCSL", "PAYEMS", "INDPRO", "CPILFESL", "UMCSENT"):
        assert monthly not in osw.DAILY_MACRO_SERIES, (
            f"{monthly} is published weeks after its observation date; joining it on that date "
            f"conditions a bar on a number nobody had")


def test_every_declared_exclusion_carries_its_reason() -> None:
    """A silent exclusion is the same defect as a silent zero, one indirection further out."""
    from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES

    for fam, why in osw.NOT_SOURCED_HERE.items():
        assert fam in ORTHOGONAL_FAMILIES, f"{fam} excluded but no such family exists"
        assert len(why) > 40, f"{fam} excluded without a reason worth reading"


def test_a_family_needing_source_evidence_is_named_not_crashed() -> None:
    """calendar_month's month and direction are evidence; a blind call is a TypeError, not a gap."""
    from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES

    need = osw._unsuppliable(ORTHOGONAL_FAMILIES["calendar_month"], {})
    assert need is not None and "active_month" in need and "side_bias" in need

    # Everything the sweep can actually supply must remain callable -- this must not become a
    # blanket skip that quietly stops running the families that were working.
    for fam in ("turn_of_month", "vol_mean_reversion", "vol_transition", "drawdown_conditional"):
        assert osw._unsuppliable(ORTHOGONAL_FAMILIES[fam], {}) is None, fam
    assert osw._unsuppliable(ORTHOGONAL_FAMILIES["pca_residual"],
                             {"factors": []}) is None


def test_errors_are_reported_apart_from_input_gaps() -> None:
    """A crash filed under input_gaps reads as missing data; 297 of them sat there unread."""
    src = (BASE / "research" / "orthogonal_sweep.py").read_text("utf-8")
    assert '"family_errors": errors' in src
    assert "errors[key] = errors.get(key, 0) + 1" in src, (
        "exceptions must accumulate in their own dict, never into `gaps`")
