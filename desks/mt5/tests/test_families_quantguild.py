"""The two Quant Guild families: registered, firing, causal, and doing what they claim."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import families_orthogonal as fo  # noqa: E402
from mt5desk import families_quantguild as qg  # noqa: E402
from research import elitequant_breadth as eb  # noqa: E402


def _frame(close: np.ndarray, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2019-01-01", periods=len(close), freq="h", tz="UTC")
    open_ = np.concatenate(([close[0]], close[:-1]))
    wick = np.abs(rng.normal(0, 0.0004, len(close))) * close
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) + wick,
                         "low": np.minimum(open_, close) - wick, "close": close}, index=idx)


def _ou(n: int = 6000, phi: float = 0.98, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + rng.normal(0, 0.001)
    return _frame(1.1 * np.exp(x))


def _clustered(n: int = 9000, seed: int = 2) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.001, n)
    for start in rng.choice(np.arange(200, n - 20), 70, replace=False):
        for k in range(rng.integers(1, 5)):
            r[start + 3 * k] = rng.choice([-1, 1]) * 0.012
    return _frame(100 * np.exp(np.cumsum(r)))


def test_registered_through_the_one_door_and_seeded():
    for name, fn in qg.QUANTGUILD_FAMILIES.items():
        assert fo.ORTHOGONAL_FAMILIES[name] is fn
        assert fo.FAMILY_INPUTS[name][0] == "price only"
        assert eb.FAMILIES[name] is fn and eb.PARAM_GRID[name] and "rewritten" in eb.ORIGIN[name]
        assert set(qg.CULTURE[name]) == {"source_culture", "participant_structure",
                                         "crowding_prior", "failure_mode_hypothesis"}


def test_kalman_ou_fades_towards_the_mean_and_is_causal():
    d = _ou()
    sigs = qg.family_kalman_ou_level(d, window=480, entry_z=1.5)
    assert len(sigs) >= 10
    close = d["close"]
    for s in sigs:
        px = float(close.loc[s.time])
        assert (s.target - px) * s.side > 0 and (px - s.stop) * s.side > 0
    early = d.index[4000]
    part = {(s.time, s.side) for s in qg.family_kalman_ou_level(d.iloc[:4500], window=480)
            if s.time < early}
    assert part == {(s.time, s.side) for s in sigs if s.time < early}


def test_a_trending_walk_has_no_mean_to_revert_to():
    rng = np.random.default_rng(5)
    trend = _frame(np.exp(np.cumsum(rng.normal(0.0004, 0.001, 6000))))
    assert len(qg.family_kalman_ou_level(trend, window=480)) * 4 <= len(
        qg.family_kalman_ou_level(_ou(), window=480))


def test_hawkes_switch_fires_both_ways_and_is_causal():
    d = _clustered()
    sigs = qg.family_hawkes_jump_switch(d, window=4000, refit=240, min_events=40)
    tags = {s.tag.rsplit(":", 1)[-1] for s in sigs}
    assert sigs and tags <= {"follow", "fade"}
    early = d.index[7000]
    part = {(s.time, s.side) for s in qg.family_hawkes_jump_switch(
        d.iloc[:7600], window=4000, refit=240, min_events=40) if s.time < early}
    assert part == {(s.time, s.side) for s in sigs if s.time < early}


def test_no_jumps_no_trades():
    rng = np.random.default_rng(9)
    calm = _frame(np.exp(np.cumsum(rng.normal(0, 0.001, 6000))))
    assert qg.family_hawkes_jump_switch(calm, window=4000, min_events=80) == []


def test_every_seeded_family_is_credited_to_a_rostered_donor():
    import json
    rosters = ("elitequant_breadth_origins.json", "external_federation_seeds.json")
    ids = {r["id"] for name in rosters for r in json.loads(
        (_DESK / "data" / "source_rosters" / name).read_text(encoding="utf-8"))["sources"]}
    assert set(eb.SOURCE_ID.values()) <= ids
    assert eb.SOURCE_ID["kalman_ou_level"] == "github:romanmichaelpaolucci/Quant-Guild-Library"
