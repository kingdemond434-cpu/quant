"""A bet about where an instrument STANDS, which is not a bet about where it has been.

THE HOLE THIS FILLS. Every price family registered on this desk is a time-series claim -- given
this instrument's history, trade this instrument. None ranks the universe at a point in time. A
cross-sectional bet is a claim about DISPERSION, so it can be right on a day when every
time-series family is flat, and it can be SHORT an instrument every trend family is long. That
disagreement is the mechanism.

THE TEST THAT DECIDES WHETHER ANY OF THAT IS TRUE is
`test_the_strongest_riser_is_declined_when_its_peers_rise_harder`. If a family can be fooled into
buying the best absolute trend regardless of the cross-section, it is a trend family with a
ranking step bolted on, and it should be deleted rather than kept -- the desk's own warning about
"eight breakout variants" being one bet with eight names applies exactly.

THE OTHER LOAD-BEARING ONE is `test_a_peer_that_did_not_exist_yet_is_absent_from_the_ranking`.
Forward-filling a peer does not merely add a wrong row: it silently RE-RANKS every other
instrument at that bar, so the ranking is decided partly by instruments that were not quotable.
That is a lookahead leak wearing a data-hygiene costume, and it would not show up as an error
anywhere.

FIXTURES ARE BUILT FROM RANKS, not from prices that happen to rank a certain way -- each peer is
given an explicit drift so the intended ordering of the cross-section is a fact about the fixture
rather than a hope about the random seed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.family_cross_sectional import (  # noqa: E402
    MIN_PEERS,
    family_cross_sectional,
)

N = 600
IDX = pd.date_range("2026-01-01", periods=N, freq="h", tz="UTC")


def _frame(drift: float, seed: int, n: int = N, start: int = 0) -> pd.DataFrame:
    """A walk with a known per-bar drift, so its rank in the cross-section is by construction."""
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, 0.002, n)
    close = 100 * np.exp(np.cumsum(steps))
    o = np.r_[close[0], close[:-1]]
    return pd.DataFrame(
        {"open": o, "high": np.maximum(o, close) * 1.0005,
         "low": np.minimum(o, close) * 0.9995, "close": close},
        index=IDX[start:start + n])


def _universe(drifts: dict[str, float]) -> dict[str, pd.DataFrame]:
    return {s: _frame(d, seed=i + 1) for i, (s, d) in enumerate(sorted(drifts.items()))}


def _flat_peers(n: int, drift: float = 0.0) -> dict[str, pd.DataFrame]:
    return {f"P{i:02d}": _frame(drift, seed=100 + i) for i in range(n)}


# ------------------------------------------------------------- IS IT ACTUALLY CROSS-SECTIONAL?
def test_the_strongest_riser_is_declined_when_its_peers_rise_harder() -> None:
    """THE TEST THAT SEPARATES THIS FROM A TREND FAMILY.

    Identical instrument, identical absolute history, twice. In the first universe it is the
    strongest thing there is and must be bought; in the second every peer is stronger and it must
    be SOLD -- on exactly the same bars, with exactly the same price path.
    """
    me = _frame(0.0008, seed=1)
    weak = {f"P{i:02d}": _frame(0.0, seed=200 + i) for i in range(MIN_PEERS + 2)}
    strong = {f"P{i:02d}": _frame(0.0030, seed=200 + i) for i in range(MIN_PEERS + 2)}

    top = family_cross_sectional(me, peers={**weak, "ME": me}, symbol="ME", horizon=24)
    bottom = family_cross_sectional(me, peers={**strong, "ME": me}, symbol="ME", horizon=24)

    assert top, "the family produced nothing on a universe built for it"
    assert bottom, "the family fell silent instead of taking the other side"
    assert {s.side for s in top} == {1}, "the cross-section's leader was not bought"
    assert {s.side for s in bottom} == {-1}, (
        "an instrument that every peer outran was still bought: this is a trend family with a "
        "ranking step bolted on, not a cross-sectional one")


def test_a_middling_instrument_is_left_alone() -> None:
    """The extremes are the bet. A family that traded the middle of the cross-section would be
    trading nothing at all, at full cost."""
    drifts = {f"P{i:02d}": (i - 6) * 0.0005 for i in range(13)}
    peers = _universe(drifts)
    mid = sorted(drifts, key=lambda s: abs(drifts[s]))[0]
    assert family_cross_sectional(peers[mid], peers=peers, symbol=mid,
                                  horizon=24, top_frac=0.2) == []


def test_reversal_is_the_opposite_claim_and_a_separate_mode() -> None:
    """PAIRED BY BAR, not by overall sign. A drifting instrument is usually at the top of this
    cross-section and occasionally, on noise, at the bottom -- so momentum correctly emits the
    odd short and "all longs" is the wrong assertion. The claim being defended is that the two
    modes are exact opposites of each other, which is a statement about the SAME bars.
    """
    me = _frame(0.0008, seed=1)
    peers = {**_flat_peers(MIN_PEERS + 2), "ME": me}
    up = family_cross_sectional(me, peers=peers, symbol="ME", horizon=24, mode="momentum")
    down = family_cross_sectional(me, peers=peers, symbol="ME", horizon=24, mode="reversal")
    assert up and down
    assert [s.time for s in up] == [s.time for s in down], "the modes fired on different bars"
    assert all(a.side == -b.side for a, b in zip(up, down, strict=True)), (
        "the two modes are not opposite claims about the same standing")
    assert {s.side for s in up} == {1, -1} or {s.side for s in up} == {1}
    assert all(s.tag.startswith("xsec_momentum") for s in up)


# ------------------------------------------------------------------------ the ranking's honesty
def test_a_peer_that_did_not_exist_yet_is_absent_from_the_ranking() -> None:
    """FORWARD-FILLING A PEER RE-RANKS EVERYTHING. A late-listed instrument carried backwards
    does not just add a wrong row -- it changes every other instrument's percentile at that bar,
    so the ranking is decided partly by something that was not quotable."""
    me = _frame(0.0008, seed=1)
    peers = {**_flat_peers(MIN_PEERS + 2), "ME": me}
    late = _frame(0.01, seed=999, n=120, start=N - 120)      # only the last 120 bars exist
    with_late = family_cross_sectional(me, peers={**peers, "LATE": late}, symbol="ME",
                                       horizon=24)
    without = family_cross_sectional(me, peers=peers, symbol="ME", horizon=24)
    early = [s for s in with_late if s.time < IDX[N - 120]]
    early_without = [s for s in without if s.time < IDX[N - 120]]
    assert [(s.time, s.side) for s in early] == [(s.time, s.side) for s in early_without], (
        "a peer with no bars before this point changed the ranking before it existed")


def test_a_thin_cross_section_is_refused_rather_than_ranked() -> None:
    """Ranking against three instruments makes a top quintile of one and fires on nearly every
    bar. That is a small sort wearing a cross-section's name."""
    me = _frame(0.0008, seed=1)
    thin = {**_flat_peers(3), "ME": me}
    assert family_cross_sectional(me, peers=thin, symbol="ME", horizon=24) == []
    fat = {**_flat_peers(MIN_PEERS + 2), "ME": me}
    assert family_cross_sectional(me, peers=fat, symbol="ME", horizon=24)


def test_the_ranking_is_dimensionless_so_it_does_not_rank_volatility() -> None:
    """RAW RETURNS RANK VOLATILITY. USDJPY moves in figures and EURCHF in pips, so a family
    ranking raw moves buys whatever is noisiest. Dividing by each instrument's own ATR is what
    makes 'further than its peers' mean the same thing on both -- so a peer that is merely LOUDER
    but no more displaced in ATRs must not outrank a quiet one that moved further."""
    quiet = _frame(0.0008, seed=1)
    loud = quiet.copy()
    for col in ("open", "high", "low", "close"):
        loud[col] = 100 * np.exp(np.log(quiet[col] / 100) * 1.0)
    loud["high"] = loud[["open", "close"]].max(axis=1) * 1.02      # 40x the range, same path
    loud["low"] = loud[["open", "close"]].min(axis=1) * 0.98
    peers = {**_flat_peers(MIN_PEERS + 2), "QUIET": quiet, "LOUD": loud}
    q = family_cross_sectional(quiet, peers=peers, symbol="QUIET", horizon=24)
    ln = family_cross_sectional(loud, peers=peers, symbol="LOUD", horizon=24)
    assert q, "the quiet instrument with real displacement was not ranked at the top"
    assert len(q) >= len(ln), (
        "the louder instrument outranked the one that actually moved further in ATRs; the "
        "feature is ranking volatility rather than displacement")


# ------------------------------------------------------------------------------- refusals
@pytest.mark.parametrize(("kw", "why"), [
    ({"peers": None}, "no peer set"),
    ({"symbol": "NOT_IN_THE_SET"}, "the traded symbol is not in the cross-section"),
    ({"mode": "whatever"}, "an unknown mode"),
    ({"top_frac": 0.9}, "a fraction that is not an extreme"),
])
def test_it_refuses_rather_than_inventing_a_cross_section(kw, why) -> None:
    me = _frame(0.0008, seed=1)
    args = {"peers": {**_flat_peers(MIN_PEERS + 2), "ME": me}, "symbol": "ME", "horizon": 24}
    args.update(kw)
    assert family_cross_sectional(me, **args) == [], why


def test_a_cascade_of_one_standing_is_one_trade() -> None:
    """An instrument does not leave the top decile in an hour, so without a cooldown this fires
    on every bar of a persistent standing and reports one dislocation as fifty."""
    me = _frame(0.0008, seed=1)
    peers = {**_flat_peers(MIN_PEERS + 2), "ME": me}
    tight = family_cross_sectional(me, peers=peers, symbol="ME", horizon=24, cooldown_bars=1)
    loose = family_cross_sectional(me, peers=peers, symbol="ME", horizon=24, cooldown_bars=48)
    assert len(loose) < len(tight)


def test_it_enters_at_the_next_open_like_every_other_family() -> None:
    me = _frame(0.0008, seed=1)
    sig = family_cross_sectional(me, peers={**_flat_peers(MIN_PEERS + 2), "ME": me},
                                 symbol="ME", horizon=24)
    assert sig and all(s.trigger is None and s.wait_bars == 1 for s in sig)
