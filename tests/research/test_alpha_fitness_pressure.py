"""The three search-side pressures (Tier-1 audit G3/G9): turnover, crowding, existing exposure.

Each is pinned the way the rest of the fitness is pinned: it measures what it says on data built
to have the property, it is 0.0 AND named in `unmeasured` when it cannot be measured, and it
subtracts. None of them is a gate -- an expression that pays them still faces the ten gates --
and the test at the bottom is the ordering the whole item exists for: the same candidate proposed
into a family that already holds half the certified canon scores BELOW itself proposed into an
empty family.

No network, no desk files: every path is a tmp_path.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from libs.research import alpha_fitness as af


def _days(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")


# --------------------------------------------------------------------------- turnover
def test_turnover_is_the_position_change_rate_and_a_holder_pays_almost_nothing() -> None:
    flipper = pd.Series([1.0, -1.0] * 200)                     # a full flip every bar
    holder = pd.Series([1.0] * 200 + [-1.0] * 200)             # one flip in four hundred bars
    entering = pd.Series([0.0, 1.0] * 200)                     # in and out of flat: half a flip
    assert af.turnover_term(flipper)[0] == pytest.approx(1.0)
    assert af.turnover_term(holder)[0] == pytest.approx(1.0 / 399)
    assert af.turnover_term(entering)[0] == pytest.approx(0.5)
    # A NaN in the path is flat, not a crash.
    with_nan = pd.Series([1.0, np.nan] * 200)
    assert 0.0 < af.turnover_term(with_nan)[0] <= 0.5


def test_turnover_without_a_path_is_unmeasured_not_zero() -> None:
    v, why = af.turnover_term(None)
    assert v == 0.0 and "unmeasured" in why
    v, why = af.turnover_term(pd.Series([1.0] * 5))
    assert v == 0.0 and "unmeasured" in why


# --------------------------------------------------------------------------- crowding
def _peers(n: int, k: int, seed: int) -> tuple[pd.Series, ...]:
    rng = np.random.default_rng(seed)
    return tuple(pd.Series(rng.normal(0.01, 0.02, n), index=_days(n)) for _ in range(k))


def test_a_candidate_whose_edge_decays_against_its_peers_is_charged() -> None:
    n = 600
    rng = np.random.default_rng(1)
    peers = _peers(n, 6, seed=2)
    # Early half: far above every peer. Late half: far below. The residual against the peer
    # median compresses and the percentile falls -- the crowding module's two tells, together.
    edge = np.concatenate([np.full(n // 2, 0.08), np.full(n // 2, -0.06)])
    cand = pd.Series(edge + rng.normal(0.0, 0.005, n), index=_days(n))
    value, detail, why = af.crowding_term(cand, peers, name="decayer")
    assert value > 0.5, (value, detail, why)
    assert detail["sufficient"] is True and detail["residual_drift_r"] < 0
    assert "compressed" in why and "unmeasured" not in why


def test_a_stable_edge_is_not_charged_and_is_measured_not_unmeasured() -> None:
    n = 600
    rng = np.random.default_rng(3)
    peers = _peers(n, 6, seed=4)
    cand = pd.Series(0.05 + rng.normal(0.0, 0.005, n), index=_days(n))
    value, detail, why = af.crowding_term(cand, peers, name="steady")
    assert value == 0.0
    assert detail["snapshots"] == af.CROWDING_BLOCKS and "unmeasured" not in why


def test_an_edge_that_improves_against_its_peers_is_never_charged() -> None:
    n = 600
    peers = _peers(n, 5, seed=5)
    edge = np.concatenate([np.full(n // 2, -0.02), np.full(n // 2, 0.08)])
    cand = pd.Series(edge, index=_days(n))
    assert af.crowding_term(cand, peers)[0] == 0.0


def test_crowding_needs_a_cross_section_and_an_overlap() -> None:
    cand = pd.Series(np.zeros(600), index=_days(600))
    v, _d, why = af.crowding_term(cand, _peers(600, 2, seed=6))
    assert v == 0.0 and "unmeasured" in why and "peer" in why
    v, _d, why = af.crowding_term(pd.Series(np.zeros(50), index=_days(50)), _peers(50, 5, seed=7))
    assert v == 0.0 and "unmeasured" in why


# --------------------------------------------------------------------------- existing exposure
def _canon(tmp_path, families: dict[str, int]):
    survivors = {}
    for fam, k in families.items():
        for i in range(k):
            survivors[f"{fam}.{i}"] = {"sym": "EURUSD",
                                       "shadow_spec": {"symbol": "EURUSD", "family": fam}}
    p = tmp_path / "canon.json"
    p.write_text(json.dumps({"n": len(survivors), "survivors": survivors}), "utf-8")
    return p


def test_existing_exposure_is_the_familys_share_of_the_certified_canon(tmp_path) -> None:
    canon = _canon(tmp_path, {"discovered": 32, "session_range_breakout": 20,
                              "overnight_gap_decay": 12, "carry": 1, "dav_range_filter_adx": 1})
    v, why = af.existing_exposure_term("discovered", canon=canon)
    assert v == pytest.approx(32 / 66) and "32 of 66" in why
    v, why = af.existing_exposure_term("carry", canon=canon)
    assert v == pytest.approx(1 / 66)
    v, why = af.existing_exposure_term("formula", canon=canon)
    assert v == 0.0 and "0 of 66" in why and "unmeasured" not in why


def test_existing_exposure_without_a_family_or_a_canon_is_unmeasured(tmp_path) -> None:
    v, why = af.existing_exposure_term("", canon=_canon(tmp_path, {"carry": 3}))
    assert v == 0.0 and "unmeasured" in why
    v, why = af.existing_exposure_term("carry", canon=tmp_path / "absent.json")
    assert v == 0.0 and "unmeasured" in why


def test_the_canon_is_re_read_when_it_changes(tmp_path) -> None:
    canon = _canon(tmp_path, {"carry": 4})
    assert af.existing_exposure_term("carry", canon=canon)[0] == pytest.approx(1.0)
    import os
    import time
    canon2 = _canon(tmp_path, {"carry": 1, "jump": 3})
    os.utime(canon2, (time.time() + 5, time.time() + 5))       # a strictly newer mtime
    assert af.existing_exposure_term("carry", canon=canon2)[0] == pytest.approx(0.25)


# --------------------------------------------------------------------------- the ordering
def test_the_same_candidate_into_a_saturated_family_scores_below_itself(tmp_path, monkeypatch
                                                                          ) -> None:
    canon = _canon(tmp_path, {"session_range_breakout": 20, "carry": 1})
    monkeypatch.setattr(af, "CANON_PATH", canon)
    rng = np.random.default_rng(9)
    daily = pd.Series(rng.normal(0.02, 0.05, 300), index=_days(300))
    saturated = af.evaluate(af.Candidate(daily=daily, family="session_range_breakout"), af.Book())
    empty = af.evaluate(af.Candidate(daily=daily, family="jump"), af.Book())
    assert saturated.existing_exposure == pytest.approx(20 / 21)
    assert empty.existing_exposure == 0.0
    assert saturated.score() < empty.score()
    assert "existing_exposure" not in saturated.unmeasured
    # And the penalties are signed as objectives to MINIMISE in the multi-objective sort.
    obj = saturated.objectives()
    assert obj["existing_exposure"] < 0.0 and obj["turnover"] == 0.0


def test_a_flipping_expression_scores_below_a_holding_one_all_else_equal() -> None:
    rng = np.random.default_rng(10)
    daily = pd.Series(rng.normal(0.02, 0.05, 300), index=_days(300))
    flip = af.evaluate(af.Candidate(daily=daily, position=pd.Series([1.0, -1.0] * 300)),
                       af.Book())
    hold = af.evaluate(af.Candidate(daily=daily, position=pd.Series([1.0] * 600)), af.Book())
    assert flip.turnover == pytest.approx(1.0) and hold.turnover == 0.0
    assert flip.score() < hold.score()
