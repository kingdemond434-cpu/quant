"""The producer-economics chain, end to end, and the two ways it silently fabricates signal.

This mechanism (`treasury_cost_base_liquidation`, orthogonality 0.70) was registered, wired, and
starved: nothing populated `MarketSeries.hashprice`, so the generator returned zeros forever while
looking provisioned. Feeding it real data introduces the opposite hazard -- real sources have gaps,
and the two ways a gap turns into a trade are what most of this file tests.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from libs.autodiscovery.crypto_adapter import (
    _attach_producer,
    _load_producer_economics,
)
from libs.autodiscovery.generators import _producer_margin_stress
from libs.autodiscovery.models import MarketSeries

def _load_script(name: str):
    """`scripts/` is not a package, so import the module by path."""
    path = Path(__file__).resolve().parents[2] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_FETCH = _load_script("fetch_producer_economics")


def _series(hashprice, difficulty=None, n=None):
    n = n or len(hashprice)
    close = np.full(n, 100.0)
    return MarketSeries(
        close=close, high=close * 1.01, low=close * 0.99,
        volume=np.full(n, 1.0), hour=np.zeros(n),
        hashprice=np.asarray(hashprice, dtype="float64"),
        difficulty=None if difficulty is None else np.asarray(difficulty, dtype="float64"),
    )


# --------------------------------------------------------------------------- unit normalisation

def test_hashrate_unit_detected_from_level():
    # ~700 EH/s expressed in TH/s.
    raw = {f"2026-01-{d:02d}": 7.0e8 for d in range(1, 29)}
    out, unit = _FETCH._to_ph(raw)
    assert unit == "TH/s"
    assert math.isclose(next(iter(out.values())), 7.0e5)      # -> 700,000 PH/s


def test_mid_series_unit_change_is_refused_not_rescaled():
    """A source that switches units puts a 1000x step in hashprice's DENOMINATOR.

    That reads as the deepest margin compression on record on the day the source changed its mind,
    and the generator would short it. It is a fabricated regime, so it must not be accepted.
    """
    raw = {f"2026-01-{d:02d}": 7.0e8 for d in range(1, 15)}
    raw.update({f"2026-01-{d:02d}": 7.0e11 for d in range(15, 29)})
    with pytest.raises(ValueError, match="unit change or a corrupt point"):
        _FETCH._to_ph(raw)


def test_implausible_level_is_refused_rather_than_guessed():
    with pytest.raises(ValueError, match="refusing to guess"):
        _FETCH._to_ph({f"2026-01-{d:02d}": 3.0 for d in range(1, 29)})


# ------------------------------------------------------------------- the starvation, now ended

def test_generator_is_flat_without_producer_data():
    """Unchanged contract: no data means no claim, not a guess."""
    assert not np.any(_producer_margin_stress(_series(np.full(300, np.nan)), {}))
    s = MarketSeries(close=np.full(300, 100.0), high=np.full(300, 101.0),
                     low=np.full(300, 99.0), volume=np.ones(300), hour=np.zeros(300))
    assert not np.any(_producer_margin_stress(s, {}))


#: 260 healthy days at 60 $/PH/day, then a 40-day margin squeeze to 45. The squeeze has to stay
#: SHORTER than the 90-bar window: once it fills the whole lookback the mean has followed price
#: down, the z-score returns to ~0, and the mechanism correctly stops calling it stress.
_HEALTHY, _SQUEEZED = 60.0, 45.0
_SQUEEZE = np.concatenate([np.full(260, _HEALTHY), np.full(40, _SQUEEZED)])


def test_compression_regime_goes_short():
    diff = np.full(300, 1.0e14)                     # capacity has NOT left
    out = _producer_margin_stress(_series(_SQUEEZE, diff), {})
    assert (out[-40:] == -1.0).all()


def test_capitulation_regime_goes_long_and_holds():
    """Difficulty is a step function; the long must persist, not expire with the retarget."""
    diff = np.concatenate([np.full(260, 1.0e14), np.full(40, 0.85e14)])
    out = _producer_margin_stress(_series(_SQUEEZE, diff), {})
    assert (out[-40:] == 1.0).all(), "the long died inside the recovery it exists to catch"


# ------------------------------------------------------ gaps must not become the loudest signal

def test_absent_hashprice_day_does_not_become_a_maximum_conviction_short():
    """THE REGRESSION THIS FILE EXISTS FOR.

    The generator used to `nan_to_num(..., nan=0.0)`. Zero hashprice is not "unknown", it asserts
    that a PH/s of hashrate earned nothing -- the deepest compression physically possible. Every
    day the source failed to publish would have opened a short at full size.
    """
    # A gently rising margin: no bar of this is ever a standard deviation BELOW its own window, so
    # a correct generator trades nothing here and any position is manufactured by the gap alone.
    hp = 60.0 + 0.01 * np.arange(300.0)
    diff = np.full(300, 1.0e14)
    assert not np.any(_producer_margin_stress(_series(hp, diff), {})), "baseline already trades"

    gapped = hp.copy()
    gapped[290] = np.nan                             # a plain source outage, nothing more
    out = _producer_margin_stress(_series(gapped, diff), {})
    assert out[290] == 0.0, "a data gap produced a position"
    assert not np.any(out), "a gap manufactured trades in a series with no stress in it"

    # And the contrast that makes the point: this is what the old zero-fill did with that gap.
    zeroed = hp.copy()
    zeroed[290] = 0.0
    assert _producer_margin_stress(_series(zeroed, diff), {})[290] == -1.0


def test_missing_difficulty_day_is_no_position_not_a_short():
    """A hole in difficulty is not evidence that capacity is still online.

    Falling through to `eased = False` would read absence as confirmation of the compression
    regime, on precisely the axis that distinguishes the two legs.
    """
    diff = np.concatenate([np.full(260, 1.0e14), np.full(40, 0.85e14)])
    diff[280] = np.nan
    out = _producer_margin_stress(_series(_SQUEEZE, diff), {})
    assert out[280] == 0.0, "an unobservable regime produced a position"
    # `ndarray.max()` propagates NaN: one gap in the lookback used to make `peak` NaN, fail the
    # `peak > 0` test, and silently disable the capitulation leg for a full window afterwards.
    assert out[-1] == 1.0, "one absent difficulty day silently flipped the mechanism"
    assert (np.delete(out[-40:], 20) == 1.0).all()


def test_rolling_stats_require_a_real_sample():
    """A z-score off a handful of survivors is noise wearing a threshold."""
    hp = np.full(300, np.nan)
    hp[:5] = 60.0
    hp[299] = 1.0
    assert _producer_margin_stress(_series(hp), {})[299] == 0.0


# --------------------------------------------------------------------------------- the join

def test_attach_leaves_gaps_absent_and_never_forward_fills():
    idx = pd.to_datetime([f"2026-01-{d:02d}" for d in range(1, 6)])
    df = pd.DataFrame({"close": [1.0] * 5}, index=idx)
    _attach_producer(df, {"2026-01-01": {"hashprice": 50.0, "difficulty": 1.0},
                          "2026-01-02": {"hashprice": 49.0, "difficulty": 1.0},
                          # 03 absent on purpose
                          "2026-01-04": {"hashprice": 47.0, "difficulty": 1.0},
                          "2026-01-05": {"hashprice": 46.0, "difficulty": 1.0}})
    hp = df["hashprice"].to_numpy()
    assert math.isnan(hp[2]), "a missing day was filled with a number nobody measured"
    assert hp[3] == 47.0 and hp[0] == 50.0


def test_attach_adds_no_column_when_nothing_overlaps():
    """Better a flat generator than a column of NaN masquerading as coverage."""
    idx = pd.to_datetime([f"2026-01-{d:02d}" for d in range(1, 4)])
    df = pd.DataFrame({"close": [1.0] * 3}, index=idx)
    _attach_producer(df, {"2019-01-01": {"hashprice": 50.0}})
    assert "hashprice" not in df.columns


def test_missing_sidecar_is_empty_not_an_exception(tmp_path):
    assert _load_producer_economics(tmp_path / "nope.json") == ({}, ())
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", "utf-8")
    assert _load_producer_economics(bad) == ({}, ())


def test_sidecar_round_trip(tmp_path):
    out = tmp_path / "producer_economics.json"
    _FETCH.merge({"2026-01-01": {"hashprice": 50.0, "difficulty": 1.0e14}}, out)
    _FETCH.merge({"2026-01-02": {"hashprice": 49.0, "difficulty": 1.0e14}}, out)
    series, syms = _load_producer_economics(out)
    assert set(series) == {"2026-01-01", "2026-01-02"}, "merge dropped prior history"
    assert "BTCUSDT" in syms
    assert json.loads(out.read_text("utf-8"))["series"]["2026-01-02"]["hashprice"] == 49.0
