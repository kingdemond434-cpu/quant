"""The descriptor-keyed archive beside the elite (Tier-1 audit G16).

grep for map-elites / quality-diversity / behaviour-descriptor across the tree returned zero
matches; the only elite was one Pareto front of eight, so the best tree the desk ever found in
"reversal x intraday x bull/high_vol x fx_major" was discarded the moment eight globally-better
trees existed. What is pinned: a cell is (mechanism class, horizon bucket, regime, asset class);
the archive keeps the BEST expression per cell and a worse arrival never displaces it; the
champions breed beside the elite without duplicating it; the occupancy published is filled over
POSSIBLE, with every axis's vocabulary stated.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import alpha_evolution as ae  # noqa: E402

from libs.research import alpha_fitness as af  # noqa: E402
from libs.research import alpha_grammar as ag  # noqa: E402


def _bars(n: int = 1500, seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 1.10 + np.cumsum(rng.normal(0, 0.0005, n))
    open_ = np.concatenate([[1.10], close[:-1]])
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) + 0.0003,
                         "low": np.minimum(open_, close) - 0.0003, "close": close,
                         "tick_volume": 100.0, "spread": 5.0}, index=idx)


def _ev() -> ae._Evaluator:
    return ae._Evaluator("EURUSD", _bars(), 1e-4, {}, None, af.Book(),
                         regime="bull/high_vol", asset_class="fx_major")


def _put(ev: ae._Evaluator, expr, side: str, fit: float) -> str:
    k = f"{ag.key(expr)}|{side}"
    ev.rows[k] = {"params": {**ae.RECIPE, "expr": expr, "side_mode": side},
                  "expr": ag.to_str(expr), "stage": 1, "fitness": fit}
    ev._archive_put(k, fit)
    return k


# --------------------------------------------------------------------------- the descriptor
def test_the_mechanism_class_follows_the_trees_structure_and_side() -> None:
    assert ae.mechanism_class(["delta", "close", 24], "follow") == "momentum:follow"
    assert ae.mechanism_class(["delta", "close", 24], "fade") == "reversal"
    assert ae.mechanism_class(["zscore", "range", 24], "follow") == "normalised_extreme:follow"
    assert ae.mechanism_class(["corr", "close", "activity", 24], "fade") == "co_movement:fade"
    assert ae.mechanism_class(["group_rank", "ret", "vol", 48], "follow") == \
        "state_conditional:follow"
    assert ae.mechanism_class(["bars_since_max", "high", 120], "follow") == \
        "distance_from_extreme:follow"
    assert ae.mechanism_class("close", "follow") == "level:follow"
    assert set(ae.MECHANISM_CLASSES) >= {"reversal", "momentum:follow", "level:fade"}
    # six shapes x two sides, with momentum-faded named reversal: twelve distinct classes
    assert len(ae.MECHANISM_CLASSES) == len(set(ae.MECHANISM_CLASSES)) == 12


def test_the_horizon_bucket_is_read_off_hold_bars() -> None:
    assert ae.horizon_bucket(1) == "scalp" and ae.horizon_bucket(4) == "scalp"
    assert ae.horizon_bucket(8) == "intraday" and ae.horizon_bucket(24) == "intraday"
    assert ae.horizon_bucket(48) == "swing" and ae.horizon_bucket(500) == "position"
    assert ae.horizon_bucket(ae.RECIPE["hold_bars"]) == "intraday"


def test_the_regime_axis_reads_the_state_vector_and_says_unlabelled_otherwise() -> None:
    doc = {"global": {"top": "bull/high_vol", "labels": ["bear/mid_vol", "bull/high_vol"]},
           "assets": {"EURUSD@H1": {"top": "bull/mid_vol", "labels": ["bull/mid_vol"]}}}
    assert ae.regime_label("EURUSD", doc) == "bull/mid_vol"          # the instrument's own fit
    assert ae.regime_label("XAUUSD", doc) == "bull/high_vol"         # the global fallback
    assert ae.regime_label("XAUUSD", {}) == ae.UNLABELLED            # a real answer, not a guess
    assert ae.regime_labels_known(doc) == ("bear/mid_vol", "bull/high_vol", "bull/mid_vol")
    assert ae.regime_labels_known({}) == (ae.UNLABELLED,)


# --------------------------------------------------------------------------- the archive
def test_the_archive_keeps_the_best_per_cell_and_a_worse_arrival_never_displaces_it() -> None:
    ev = _ev()
    k_mom = _put(ev, ["delta", "close", 24], "follow", 1.0)
    _put(ev, ["delta", "close", 120], "follow", 0.4)                 # same cell, worse: ignored
    k_rev = _put(ev, ["delta", "close", 5], "fade", 0.2)             # a different cell
    k_z = _put(ev, ["zscore", "range", 24], "follow", 3.0)
    cells = {c[0]: key for c, (_f, key) in ev.archive.items()}
    assert cells["momentum:follow"] == k_mom
    assert cells["reversal"] == k_rev
    assert cells["normalised_extreme:follow"] == k_z
    assert len(ev.archive) == 3
    # A better arrival in an occupied cell takes it over.
    k_mom2 = _put(ev, ["delta", "close", 48], "follow", 1.5)
    assert {c[0]: key for c, (_f, key) in ev.archive.items()}["momentum:follow"] == k_mom2
    # And a non-finite fitness never enters.
    assert ev._archive_put(k_mom, float("nan")) is False


def test_every_cell_carries_the_four_descriptor_axes() -> None:
    ev = _ev()
    _put(ev, ["delta", "close", 24], "follow", 1.0)
    (cell,) = ev.archive
    assert cell == ("momentum:follow", "intraday", "bull/high_vol", "fx_major")
    rep = ev.archive_report()
    assert rep["cells_filled"] == 1 and rep["regime"] == "bull/high_vol"
    assert rep["cells"][0]["expr"] == "delta(close, 24)" and rep["cells"][0]["fitness"] == 1.0


def test_champions_breed_beside_the_elite_without_duplicating_it() -> None:
    ev = _ev()
    _put(ev, ["delta", "close", 24], "follow", 1.0)
    _put(ev, ["delta", "close", 5], "fade", 0.2)
    _put(ev, ["zscore", "range", 24], "follow", 3.0)
    elite = [(["zscore", "range", 24], "follow"), (["delta", "close", 24], "follow")]
    parents = ae._parents(ev, elite)
    assert parents[:2] == elite, "the elite keeps its order and comes first"
    assert (["delta", "close", 5], "fade") in parents, (
        "the reversal cell's champion is not on the front and must still be a parent")
    assert len(parents) == 3, "an elite member that is also a champion is not listed twice"
    # Champions come best cell first.
    assert ev.champions()[0] == (["zscore", "range", 24], "follow")


def test_occupancy_is_filled_over_possible_with_the_axes_stated() -> None:
    per_symbol = {
        "EURUSD": {"map_elites": {"asset_class": "fx_major", "cells": [
            {"mechanism_class": "reversal", "horizon": "intraday", "regime": "bull/high_vol",
             "asset_class": "fx_major"},
            {"mechanism_class": "momentum:follow", "horizon": "intraday",
             "regime": "bull/high_vol", "asset_class": "fx_major"}]}},
        "XAUUSD": {"map_elites": {"asset_class": "metal", "cells": [
            {"mechanism_class": "reversal", "horizon": "intraday", "regime": "bull/high_vol",
             "asset_class": "metal"}]}},
    }
    regimes = ("bear/mid_vol", "bull/high_vol", "bull/low_vol")
    s = ae.map_elites_summary(per_symbol, regimes)
    possible = len(ae.MECHANISM_CLASSES) * len(ae.HORIZON_NAMES) * 3 * 2
    assert s["cells_possible"] == possible and s["cells_filled"] == 3
    assert s["occupancy"] == pytest.approx(3 / possible, abs=1e-4)   # reported to 4 dp
    assert s["axes"]["asset_classes"] == ["fx_major", "metal"]
    assert s["axes"]["regimes"] == list(regimes)
    # An empty sweep is 0 of a stated denominator, never a division by zero.
    empty = ae.map_elites_summary({}, (ae.UNLABELLED,))
    assert empty["cells_filled"] == 0 and empty["cells_possible"] > 0
