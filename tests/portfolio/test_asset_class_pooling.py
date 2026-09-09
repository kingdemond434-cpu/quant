"""The asset class is the level above the mechanism, and it can only ever relieve the shrink."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.portfolio import robust_elog as re  # noqa: E402

WORLDS = 2000


def _ev(name, symbol, family, mean, n=400, seed=0):
    rng = np.random.default_rng(seed)
    return re.SleeveEvidence(name=name, daily_r=rng.normal(mean, 0.5, n), family=family,
                             symbol=symbol, n_trials=1)


def _centre(ev) -> np.ndarray:
    """The posterior centre per sleeve. The draws are post_mean + se * z with a fixed seed, so
    the column mean over many worlds isolates the centre the pooling produced."""
    mu, _ = re._posterior_mu(ev, np.random.default_rng(11), WORLDS)
    return mu.mean(axis=0)


def test_the_classifier_is_the_desks_own_and_never_raises() -> None:
    assert re._asset_class("XAUUSD") == "metal" and re._asset_class("XAGUSD") == "metal"
    assert re._asset_class("EURUSD") == "fx_major"
    # NO SYMBOL IS NOT A CLASS. The desk classifier falls back to "equity" for an unrecognised
    # ticker, so an empty symbol would put every metadata-less sleeve into one group and let
    # them borrow each other's means. Empty must be its own answer, and it must never raise.
    # "unknown" is the classifier saying it could not place the ticker, and that is not a group
    # to borrow inside either -- both collapse to "", which never pools.
    for blank in ("", None, "   ", 12345, "!!!"):
        assert re._asset_class(blank) == ""


def test_a_losing_class_never_pulls_a_sleeve_below_where_it_sits_without_the_level() -> None:
    """THE STANDING ORDER IN ARITHMETIC. The class mean enters through max(., 0), so a class
    whose established members lose money contributes exactly nothing -- the thin sleeve lands
    where it landed before this level existed, never lower."""
    thin = _ev("thin", "XAGUSD", "new_mechanism", 0.0, n=30, seed=1)
    losers = [_ev("a", "XAUUSD", "proven", -0.40, n=1200, seed=2),
              _ev("b", "XPTUSD", "proven", -0.40, n=1200, seed=3)]
    mixed = [_ev("a", "EURUSD", "proven", -0.40, n=1200, seed=2),
             _ev("b", "US500", "proven", -0.40, n=1200, seed=3)]
    same_class = _centre([thin, *losers])[0]
    other_class = _centre([thin, *mixed])[0]
    assert same_class >= other_class - 1e-9, (
        "a losing metals class must not drag a thin metal below the same sleeve sitting beside "
        "instruments of other classes")


def test_a_thin_instrument_inherits_from_a_proven_class() -> None:
    """A new metal beside two established, profitable metals must land ABOVE the same sleeve
    beside two established instruments of other classes. That inheritance is the point of P11."""
    thin = _ev("thin", "XAGUSD", "new_mechanism", 0.0, n=30, seed=1)
    metals = [_ev("a", "XAUUSD", "proven", 0.40, n=1200, seed=2),
              _ev("b", "XPTUSD", "proven", 0.40, n=1200, seed=3)]
    others = [_ev("a", "EURUSD", "proven", 0.40, n=1200, seed=2),
              _ev("b", "US500", "proven", 0.40, n=1200, seed=3)]
    assert _centre([thin, *metals])[0] > _centre([thin, *others])[0]


def test_the_established_sleeves_are_barely_moved_by_the_level() -> None:
    """A sleeve with its own long history is already lam_s ~ 1, so the outer levels reach it
    hardly at all -- the class level must not become a back door into resizing the book."""
    fat = _ev("fat", "XAUUSD", "proven", 0.40, n=1200, seed=2)
    with_metal = _centre([fat, _ev("b", "XPTUSD", "proven", 0.40, n=1200, seed=3)])[0]
    with_other = _centre([fat, _ev("b", "US500", "proven", 0.40, n=1200, seed=3)])[0]
    assert abs(with_metal - with_other) < 0.01


def test_the_scales_and_the_one_sidedness_are_pinned() -> None:
    src = Path(re.__file__).read_text("utf-8")
    assert "k_class = 240.0" in src, "a class is a weaker claim than a mechanism and needs more"
    assert "k_sleeve, k_family = 60.0, 120.0" in src, "the two inner scales are unchanged"
    assert "max(cls_mean[c], 0.0)" in src, "the level must stay one-sided"


def test_a_sleeve_with_no_symbol_borrows_nothing() -> None:
    """REGRESSION. Two unrelated sleeves carrying no symbol were pooled into one class, and the
    short one stopped being shrunk toward no-edge -- the protection the posterior exists for."""
    short = re.SleeveEvidence(name="short", daily_r=np.random.default_rng(1).normal(0.10, 1.0, 40))
    long_ = re.SleeveEvidence(name="long", daily_r=np.random.default_rng(2).normal(0.10, 1.0, 4000))
    c = _centre([short, long_])
    assert abs(float(c[0])) < abs(float(c[1])), "the short backtest must still be pulled harder"
