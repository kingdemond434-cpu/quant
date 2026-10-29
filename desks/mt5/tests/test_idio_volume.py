"""F1: the idiosyncratic tick-volume spike, faded.

* a burst peculiar to one instrument is a spike; the same burst on every instrument is the
  common factor and is not;
* the z-score is trailing: changing the future never changes a past reading;
* the signal fades the spike bar and holds `hold_bars`;
* the fill hour's own spread (the per-symbol/hour cost surface) refuses an entry it would eat;
* 21 cells, registered, classified by the breadth steer's FAMILY_TABLE.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families_orthogonal as fo  # noqa: E402
from mt5desk import family_idio_volume as fiv  # noqa: E402

N = 3000
IDX = pd.date_range(datetime(2024, 1, 1, tzinfo=UTC), periods=N, freq="1h", tz="UTC")


def _bars(seed: int, common: np.ndarray, extra: dict[int, float] | None = None,
          moves: dict[int, float] | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    hour = IDX.hour.to_numpy()
    lv = 5.0 + 0.6 * np.sin(hour / 24 * 2 * np.pi) + common + rng.normal(0, 0.15, N)
    for i, bump in (extra or {}).items():
        lv[i] += bump
    vol = np.expm1(lv)
    close = 100 + np.cumsum(rng.normal(0, 0.05, N))
    opn = np.r_[close[0], close[:-1]]
    for i, mv in (moves or {}).items():
        close[i] = opn[i] + mv
    return pd.DataFrame({"open": opn, "high": np.maximum(opn, close) + 0.05,
                         "low": np.minimum(opn, close) - 0.05, "close": close,
                         "tick_volume": vol}, index=IDX)


def _panel(spike_at: int, common_at: int):
    common = np.random.default_rng(99).normal(0, 0.3, N)
    common[common_at] += 3.0                       # everyone gets busy together
    peers = [_bars(10 + k, common) for k in range(6)]
    target = _bars(1, common, extra={spike_at: 3.0}, moves={spike_at: 0.8})
    return target, peers


def test_an_idiosyncratic_burst_is_a_spike_and_a_common_one_is_not() -> None:
    target, peers = _panel(spike_at=2500, common_at=2600)
    z = fiv.idio_volume_z(target, peers)
    assert z is not None
    assert z.iloc[2500] > 4.0
    assert abs(z.iloc[2600]) < 3.0


def test_the_reading_is_trailing() -> None:
    target, peers = _panel(spike_at=2500, common_at=2600)
    z1 = fiv.idio_volume_z(target, peers)
    future = target.copy()
    future.iloc[2700:, future.columns.get_loc("tick_volume")] *= 50.0
    z2 = fiv.idio_volume_z(future, peers)
    assert z1 is not None and z2 is not None
    pd.testing.assert_series_equal(z1.iloc[:2700], z2.iloc[:2700])


def test_the_spike_is_faded_and_held() -> None:
    target, peers = _panel(spike_at=2500, common_at=2600)
    sigs = fiv.family_idio_volume_reversal(target, peers=peers, hold_bars=3)
    hit = [s for s in sigs if s.time == IDX[2500]]
    assert hit and hit[0].side == -1 and hit[0].ttl_bars == 3 and hit[0].wait_bars == 1


def test_the_fill_hours_spread_refuses_an_entry_it_would_eat() -> None:
    target, peers = _panel(spike_at=2500, common_at=2600)
    fill_hour = int(IDX[2501].hour)
    dear = {"symbols": {"USDZAR": {"tick_size": 1.0, "hours": {
        str(fill_hour): {"status": "MEASURED", "p50": 1e6}}}}}
    taken = fiv.family_idio_volume_reversal(target, peers=peers, symbol="USDZAR",
                                            surface={"symbols": {}})
    refused = fiv.family_idio_volume_reversal(target, peers=peers, symbol="USDZAR",
                                              surface=dear)
    assert any(s.time == IDX[2500] for s in taken)
    assert not any(s.time == IDX[2500] for s in refused)


def test_too_few_peers_refuses() -> None:
    target, peers = _panel(spike_at=2500, common_at=2600)
    assert fiv.idio_volume_z(target, peers[:2]) is None
    assert fiv.family_idio_volume_reversal(target, peers=peers[:2]) == []


def test_f1_cells_are_registered_distinct_and_classified() -> None:
    cells = fiv.f1_cells()
    assert len(cells) == len(fiv.F1_SYMBOLS) * len(fiv.F1_HOLDS) == 21
    ids = {(c["symbol"], tuple(sorted(c["params"].items()))) for c in cells}
    assert len(ids) == 21
    assert {c["symbol"] for c in cells} == {"EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "EURZAR",
                                            "USDZAR", "XAUUSD"}
    assert fo.ORTHOGONAL_FAMILIES["idio_volume_reversal"] is fiv.family_idio_volume_reversal
    from research.axis_registry import classify_family
    assert classify_family("idio_volume_reversal") == ("inventory_shock", "microstructure",
                                                       "market")


def test_f1_is_charged_once_by_its_own_grid_not_by_the_sweep() -> None:
    """The 21 donated cells are the whole F1 charge; the orthogonal sweep declines the family
    (NOT_SOURCED_HERE, with its reason) and is never handed a kwarg that would run it."""
    import ast

    import orthogonal_sweep as osw

    assert "idio_volume_reversal" in osw.NOT_SOURCED_HERE
    tree = ast.parse((DESK / "research" / "orthogonal_sweep.py").read_text("utf-8"))
    keys = {k.value for node in ast.walk(tree)
            if isinstance(node, ast.Assign) and node.targets
            and getattr(node.targets[0], "id", "") == "kwargs_by_family"
            and isinstance(node.value, ast.Dict)
            for k in node.value.keys if isinstance(k, ast.Constant)}
    assert keys and "idio_volume_reversal" not in keys


def test_the_fill_bars_own_recorded_spread_is_preferred_to_todays_surface() -> None:
    """Point-in-time cost: a fill bar that recorded a ruinous spread refuses even when today's
    surface says the hour is cheap; a bar that recorded none falls back to the surface."""
    target, peers = _panel(spike_at=2500, common_at=2600)
    fill_hour = int(IDX[2501].hour)
    cheap = {"symbols": {"USDZAR": {"tick_size": 1.0, "hours": {
        str(fill_hour): {"status": "MEASURED", "p50": 1e-9}}}}}
    recorded = target.assign(spread=0.0)
    recorded.iloc[2501, recorded.columns.get_loc("spread")] = 1e6
    refused = fiv.family_idio_volume_reversal(recorded, peers=peers, symbol="USDZAR",
                                              surface=cheap)
    assert not any(s.time == IDX[2500] for s in refused)
    blank = target.assign(spread=0.0)
    taken = fiv.family_idio_volume_reversal(blank, peers=peers, symbol="USDZAR", surface=cheap)
    assert any(s.time == IDX[2500] for s in taken)
    assert fiv.fill_spread("USDZAR", fill_hour, 5.0, cheap) == (5.0, "bar_pit")
    assert fiv.fill_spread("USDZAR", fill_hour, 0.0, cheap) == (1e-9, "surface_today")
    assert fiv.fill_spread("XAUUSD", 3, None, cheap) == (None, "unmeasured")


def test_f1_is_preregistered_with_its_disclosure() -> None:
    doc = (ROOT / "docs" / "research" / "F1_IDIO_VOLUME_PREREGISTRATION.md").read_text("utf-8")
    for needle in ("z > 3.0", "1, 2 and 4", "0.25 \u00d7 ATR", "21 cells", "p = 0.0125",
                   "CONTINUATION", "separately charged trial"):
        assert needle in doc, needle
    assert all(c["preregistration"].endswith("F1_IDIO_VOLUME_PREREGISTRATION.md")
               for c in fiv.f1_cells())


def test_the_breadth_sweep_does_not_charge_f1_a_second_time() -> None:
    """breadth_sweep.default_families excludes F1 by name (PREREGISTERED_ELSEWHERE) and keeps
    mining every other family exactly as before (audit MF4, narrowed)."""
    from research import breadth_sweep as bs

    ok, blocked = bs.default_families()
    assert set(bs.PREREGISTERED_ELSEWHERE) == {"idio_volume_reversal", "style_premia"}
    assert "idio_volume_reversal" not in ok
    assert blocked["idio_volume_reversal"].startswith("preregistered elsewhere")
    # The other NOT_SOURCED_HERE families are set aside only by NAME and only as void at their
    # defaults (audit 0b66b08de), each with its reason -- never wholesale.
    for void in ("lead_lag", "triangle", "exogenous_conditioner"):
        assert void not in ok and blocked[void].startswith("void at defaults"), void
