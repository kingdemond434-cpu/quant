"""Exact spellings of one rule share a BUILD, never a verdict -- and only when provably identical.

`research/cell_equivalence.py` lets `scripts/warm_gauntlet_cache.py` build one member of a group
and serve the others' cache keys from its series. The judge's cache is where a wrong identity is
undetectable (two cells sharing a series serve each other's returns), so every canonicalising rule
is pinned here against the REAL `external_gauntlet.build_cell` on the same bars: the two spellings
must produce identical signals, or the rule is wrong.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK / "research"), str(_DESK / "scripts"), str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cell_equivalence as E  # noqa: E402
from desks.mt5.scripts import external_gauntlet as G  # noqa: E402

FAMILIES = ("engulfing_reversal", "range_reversion", "momentum_volgate", "trend_ma_cross",
            "asia_momentum", "session_range_breakout")


@pytest.fixture(scope="module")
def bars() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    idx = pd.date_range("2024-01-01", periods=24 * 400, freq="h", tz="UTC")
    close = 1.1 + np.cumsum(rng.normal(0, 0.0012, len(idx)))
    spread = np.abs(rng.normal(0, 0.0015, len(idx))) + 0.0003
    return pd.DataFrame({"open": np.r_[close[0], close[:-1]], "high": close + spread,
                         "low": close - spread, "close": close,
                         "tick_volume": rng.integers(50, 500, len(idx))}, index=idx)


def _sigs(family: str, params: dict, bars: pd.DataFrame) -> list:
    obj = G.build_cell("EURUSD", family, params, {}, h1_override=bars)
    assert obj, f"{family} {params} did not build: {G.LAST_BUILD_FAILURE}"
    return [(s.time, int(s.side), round(float(s.stop), 10), round(float(s.target), 10))
            for s in (obj["sigs"] or [])]


def _defaulted(family: str) -> dict:
    fn = E.family_fn(family)
    out = {}
    for k, p in inspect.signature(fn).parameters.items():
        if isinstance(p.default, (int, float, str)) and not isinstance(p.default, bool) \
                and k not in E.REWRITTEN_KEYS:
            out[k] = p.default
    return out


@pytest.mark.parametrize("family", FAMILIES)
def test_every_spelling_rule_builds_the_identical_trade(family: str, bars: pd.DataFrame) -> None:
    base = _sigs(family, {}, bars)
    spelled = {**_defaulted(family), "timeframe": "H1", "representation": "price_only",
               "regime": "unconditional", "entry_timing": "instant", "side_mode": "follow",
               "execution_style": "market"}
    fn_names = set(inspect.signature(E.family_fn(family)).parameters)
    spelled = {k: v for k, v in spelled.items() if k not in fn_names or k in _defaulted(family)}
    assert E.canonical_params(family, spelled) == {}, "every rule should strip to the bare cell"
    assert _sigs(family, spelled, bars) == base


def test_a_real_difference_is_never_collapsed() -> None:
    """A non-default value, a type-changed default and a non-no-op modifier all stay distinct."""
    d = _defaulted("engulfing_reversal")
    k, v = next((k, v) for k, v in d.items() if isinstance(v, int))
    assert E.canonical_params("engulfing_reversal", {k: v + 1}) == {k: v + 1}
    assert E.canonical_params("engulfing_reversal", {k: float(v)}) == {k: float(v)}
    assert E.canonical_params("engulfing_reversal", {"regime": "high_vol"}) == \
        {"regime": "high_vol"}
    assert E.canonical_params("engulfing_reversal", {"side_mode": "revert"}) == \
        {"side_mode": "revert"}
    assert E.canonical_params("engulfing_reversal", {"timeframe": "M5"}) == {"timeframe": "M5"}


def test_unknown_family_and_rewritten_keys_are_never_touched() -> None:
    assert E.canonical_params("no_such_family", {"rr": 1.8}) is None
    assert E.canonical_params("carry", {"input_symbol": "X"}) in (None, {"input_symbol": "X"})


def test_groups_account_for_every_input_exactly_once() -> None:
    specs = [{"sym": "EURUSD", "family": "engulfing_reversal", "tf": "H1", "params": p}
             for p in ({}, {"representation": "macro"}, {"timeframe": "H1"}, {"rr": 9.9})]
    specs.append({"sym": "EURUSD", "family": "no_such_family", "tf": "H1", "params": {}})
    gr = E.groups(specs)
    members = [id(sp) for v in gr.values() for sp in v]
    assert sorted(members) == sorted(id(sp) for sp in specs)
    sizes = sorted(len(v) for v in gr.values())
    assert sizes == [1, 1, 3], "three spellings of one rule, one real variant, one unknown family"


# ------------------------------------------- the cached SERIES, through the sealed judge's own path
def _sealed_series(spec: dict, bars: pd.DataFrame, cache: Path,
                   monkeypatch: pytest.MonkeyPatch) -> tuple[str, pd.Series, pd.Series]:
    """Build `spec` exactly as the SEALED pre-warm does (`external_gauntlet._warm_one`: its own
    frame, data day, cache key, `build_cell`, both cost arms, `cache_save`) and load it back the
    way the sealed sweep's loop does (`cache_load`)."""
    monkeypatch.setattr(G, "CACHE_DIR", cache)
    G._FRAME_CACHE.clear()
    G._FRAME_CACHE[("EURUSD", "H1")] = G.families._h1(bars)
    out = G._warm_one(spec, {})
    assert out["status"] == "WARMED", out
    got = G.cache_load(out["ckey"])
    assert got is not None
    return out["ckey"], got[0], got[1]


def _identical(a: pd.Series, b: pd.Series) -> bool:
    return (a.index.equals(b.index)
            and np.array_equal(a.to_numpy(float), b.to_numpy(float), equal_nan=True))


@pytest.mark.parametrize("family", FAMILIES)
def test_twins_cache_bit_identical_series_under_the_sealed_build(
        family: str, bars: pd.DataFrame, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """THE PROOF THE BUILD CAN BE SHARED: both spellings, built by the sealed judge's own warm
    path, cache the SAME 1x and 3x daily series, byte for byte, under DIFFERENT keys. And the
    warmer's fan-out copy of the leader's file, loaded by the sealed `cache_load` under the
    follower's key, is that same series -- so the follower is judged on exactly what the judge
    would have built for it."""
    import warm_gauntlet_cache as W

    spelled = {**_defaulted(family), "timeframe": "H1", "representation": "price_only",
               "regime": "unconditional", "entry_timing": "instant", "side_mode": "follow",
               "execution_style": "market"}
    fn_names = set(inspect.signature(E.family_fn(family)).parameters)
    spelled = {k: v for k, v in spelled.items() if k not in fn_names or k in _defaulted(family)}
    leader = {"sym": "EURUSD", "family": family, "params": {}}
    twin = {"sym": "EURUSD", "family": family, "params": spelled}
    assert E.equivalence_key("EURUSD", family, {}, "H1") == \
        E.equivalence_key("EURUSD", family, spelled, "H1")
    k1, a1, a3 = _sealed_series(leader, bars, tmp_path / "c1", monkeypatch)
    k2, b1, b3 = _sealed_series(twin, bars, tmp_path / "c2", monkeypatch)
    assert k1 != k2, "each spelling keeps its own cache key and its own verdict"
    assert _identical(a1, b1) and _identical(a3, b3)
    # The warmer's fan-out: the twin's key served from the leader's file.
    fan = tmp_path / "fan"
    fan.mkdir()
    (fan / f"{k1}.npz").write_bytes((tmp_path / "c1" / f"{k1}.npz").read_bytes())
    monkeypatch.setattr(G, "CACHE_DIR", fan)
    assert W.fan_out(G, k1, [k2]) == 1
    served = G.cache_load(k2)
    assert served is not None
    assert _identical(served[0], b1) and _identical(served[1], b3)
