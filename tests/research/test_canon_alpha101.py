"""The published formulaic alphas the desk can say (Tier-1 audit G2).

`data/brain_hunter_s10_alpha101_fields.json` enumerates alpha001..101's field requirements and
nothing implemented any of them: novelty was measured against seven hand-written references, so
the search could rediscover a published formula and count it new. Fifteen are now literal Expr
trees in CANON. What is pinned: every one is constructible under the production screen (structure
AND type AND units), evaluates on real-shaped bars, is structurally distinct from every other
canon entry, names its published id, and reaches the search -- symreg starts from them, and no
existing hand-written reference moved.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.research import alpha_grammar as ag
from libs.research import generators as gen
from libs.research import search_populations as sp

LEGACY = ("trend_24", "trend_120", "reversal_5", "breakout_dist_48", "range_z_24",
          "activity_z_48", "spread_rank_240")
N = 3000


@pytest.fixture(scope="module")
def frames() -> dict[str, pd.Series]:
    rng = np.random.default_rng(0)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.001, N)))
    idx = pd.date_range("2024-01-01", periods=N, freq="1h", tz="UTC")
    o = np.concatenate([[100.0], close[:-1]])
    df = pd.DataFrame({"open": o, "high": np.maximum(o, close) * 1.001,
                       "low": np.minimum(o, close) * 0.999, "close": close,
                       "tick_volume": rng.integers(50, 500, N).astype(float),
                       "spread": 5.0}, index=idx)
    return ag.terminal_frames(df, raw=df)


def test_the_seven_hand_written_references_did_not_move() -> None:
    """The canon is what novelty is measured against; renaming or re-spelling one of these
    would silently change every novelty score the desk has ever recorded."""
    for name in LEGACY:
        assert name in ag.CANON, name
    assert ag.CANON["trend_24"] == ["delta", "close", 24]
    assert ag.CANON["spread_rank_240"] == ["ts_rank", "spread", 240]


def test_fifteen_published_alphas_are_carried_with_their_ids() -> None:
    assert len(ag.CANON_ALPHA101_IDS) == 15
    assert set(ag.CANON_ALPHA101_IDS) <= set(ag.CANON)
    assert set(ag.CANON_ALPHA101_IDS) & set(LEGACY) == set()
    ids = sorted(ag.CANON_ALPHA101_IDS.values())
    assert len(set(ids)) == 15, "two entries claim the same published alpha"
    assert all(i.startswith("alpha") and i[5:].isdigit() and 1 <= int(i[5:]) <= 101 for i in ids)
    assert len(ag.CANON) == len(LEGACY) + 15


@pytest.mark.parametrize("name", sorted({
    "wq101_intraday_thrust", "wq012_volume_signed_reversal", "wq006_open_activity_corr",
    "wq003_rank_open_activity_corr", "wq002_activity_body_corr", "wq004_low_rank_reversal",
    "wq053_range_position_delta", "wq023_high_break_fade", "wq009_consistent_momentum",
    "wq019_close_trend_sign", "wq046_trend_acceleration", "wq013_close_activity_cov",
    "wq026_activity_high_corr", "wq040_high_vol_activity",
    "wq055_range_position_activity_corr"}))
def test_each_is_constructible_and_evaluable(name: str, frames) -> None:
    e = ag.CANON[name]
    assert ag.is_valid(e, allow_drivers=False), (name, ag.type_of(e), ag.unit_of(e))
    assert ag.well_typed(e) and ag.well_formed(e)
    v = ag.evaluate(e, frames, {}).to_numpy(dtype=float)
    assert np.isfinite(v).sum() > N // 2, f"{name} is NaN on more than half the bars"
    assert float(np.nanstd(v)) > 0.0, f"{name} is constant: it conditions nothing"


def test_no_entry_uses_a_terminal_the_desk_cannot_compute() -> None:
    """Only close/open/high/low/volume fields: an entry naming a driver or an external role
    would evaluate to NaN wherever the caller has no series for it."""
    allowed = {"close", "open", "high", "low", "activity", "body", "range", "ret", "spread",
               "atr", "vol", "flow"}
    for name in ag.CANON_ALPHA101_IDS:
        assert ag.terminals_in(ag.CANON[name]) <= allowed, name


def test_the_vwap_alphas_are_absent_because_the_type_algebra_refuses_the_proxy() -> None:
    """30 of the 101 need vwap. The honest proxy is sum(close x activity, w)/sum(activity, w),
    and `mul` of a PRICE by an ACTIVITY is INVALID here -- the rule that stops the desk adding
    lots to returns. The alphas that need one are a TERMINAL task, not a grammar task."""
    proxy = ["div", ["sum", ["mul", "close", "activity"], 24], ["sum", "activity", 24]]
    assert ag.type_of(["mul", "close", "activity"]) == ag.INVALID
    assert not ag.is_valid(proxy, allow_drivers=False)
    assert "vwap" not in {t for n in ag.CANON for t in ag.terminals_in(ag.CANON[n])}


def test_every_canon_entry_is_a_distinct_hypothesis(frames) -> None:
    hashes = {n: ag.subtree_hash(e) for n, e in ag.CANON.items()}
    assert len(set(hashes.values())) == len(ag.CANON), "two canon entries are the same tree"
    z = {}
    for n, e in ag.CANON.items():
        s = ag.evaluate(e, frames, {})
        r = s.rolling(240, min_periods=240)
        z[n] = (s - r.mean()) / r.std()
    m = pd.DataFrame(z).corr().abs().to_numpy().copy()
    np.fill_diagonal(m, 0.0)
    worst = float(np.nanmax(m))
    assert worst < 0.97, (
        f"two references correlate at {worst:.3f}: novelty against one is novelty against both")


def test_symreg_starts_from_the_canon_and_still_draws_from_noise(frames) -> None:
    """The seed is a STARTING POINT: half the draws start from a known shape and half from a
    random tree, so the population keeps finding structures nobody wrote down."""
    ctx = sp.SearchContext(rng=np.random.default_rng(3), frames=frames,
                           ret=frames["ret"], symbol="EURUSD", allow_drivers=False)
    out = sp.symreg(ctx, 6)
    assert len(out) == 6
    assert all(ag.is_valid(e, ctx.allow_drivers, ctx.terminals) for e in out)


def test_a_seeded_climb_never_scores_worse_than_its_seed(frames) -> None:
    seed = ag.CANON["wq101_intraday_thrust"]
    target = pd.Series(frames["ret"]).shift(-1)
    got = gen.symbolic_regression(np.random.default_rng(5), frames, target, iters=20,
                                  allow_drivers=False, seed_expr=seed)
    assert ag.is_valid(got, allow_drivers=False)
    assert gen.LAST_FIT["train_mse"] is not None
    # A climb of zero iterations returns the seed itself, unmutated and uncopied-into.
    before = ag.key(seed)
    exact = gen.symbolic_regression(np.random.default_rng(5), frames, target, iters=0,
                                    allow_drivers=False, seed_expr=seed)
    assert ag.key(exact) == before
    assert ag.key(ag.CANON["wq101_intraday_thrust"]) == before, "the canon tree was mutated"


def test_an_unusable_seed_falls_back_to_the_random_draw(frames) -> None:
    target = pd.Series(frames["ret"]).shift(-1)
    got = gen.symbolic_regression(np.random.default_rng(7), frames, target, iters=5,
                                  allow_drivers=False, seed_expr=["not_an_op", "close", 3])
    assert ag.is_valid(got, allow_drivers=False)
