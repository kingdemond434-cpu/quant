"""The nine queued-repo families: registered, seeded, credited, firing, and causal."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import families_orthogonal as fo  # noqa: E402
from mt5desk import families_queued_repos as qr  # noqa: E402
from research import axis_registry as ax  # noqa: E402
from research import elitequant_breadth as eb  # noqa: E402


def _walk(n: int = 9000, seed: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 1.2 * np.exp(np.cumsum(rng.normal(0, 0.0012, n)))
    idx = pd.date_range("2019-01-01", periods=n, freq="h", tz="UTC")
    open_ = np.concatenate(([close[0]], close[:-1]))
    wick = np.abs(rng.normal(0, 0.0008, n)) * close
    vol = rng.lognormal(5, 0.6, n).round()
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) + wick,
                         "low": np.minimum(open_, close) - wick, "close": close,
                         "tick_volume": vol}, index=idx)


def test_registered_through_the_one_door_seeded_and_mapped():
    for name, fn in qr.QUEUED_REPO_FAMILIES.items():
        assert fo.ORTHOGONAL_FAMILIES[name] is fn
        assert fo.FAMILY_INPUTS[name][0].startswith("price only")
        assert eb.FAMILIES[name] is fn and eb.PARAM_GRID[name]
        assert "rewritten" in eb.ORIGIN[name]
        assert set(qr.CULTURE[name]) == {"source_culture", "participant_structure",
                                         "crowding_prior", "failure_mode_hypothesis"}
        assert ax.FAMILY_TABLE[name][1] == "price_only", name


def test_every_family_is_credited_to_a_rostered_seed_fetched_by_the_seeder():
    rows = json.loads((_DESK / "data" / "source_rosters" / "external_federation_seeds.json")
                      .read_text(encoding="utf-8"))["sources"]
    by_id = {r["id"]: r for r in rows}
    for name in qr.QUEUED_REPO_FAMILIES:
        sid = eb.SOURCE_ID[name]
        assert "elitequant_breadth" in by_id[sid]["config"]["fetched_by"], sid
    assert eb.SOURCE_ID["td_setup_exhaustion"] == "github:waditu/czsc"


def test_index_calendar_claims_are_screened_on_indices_only():
    assert eb.CLASS_ONLY["payday_dom"] == {"index"}
    assert eb.CLASS_ONLY["rare_losing_streak"] == {"index"}


@pytest.mark.parametrize("name", sorted(qr.QUEUED_REPO_FAMILIES))
def test_fires_with_a_sane_bracket_and_is_causal(name):
    d = _walk()
    fn = qr.QUEUED_REPO_FAMILIES[name]
    sigs = fn(d)
    if name not in ("rare_losing_streak", "quiet_grind", "ribbon_release"):
        assert len(sigs) >= 10, name
    close = d["close"]
    for s in sigs:
        px = float(close.loc[s.time])
        assert (px - s.stop) * s.side > 0 and (s.target - px) * s.side > 0, name
    cut = d.index[7000]
    part = {(s.time, s.side, round(s.stop, 10)) for s in fn(d.iloc[:7200]) if s.time < cut}
    assert part == {(s.time, s.side, round(s.stop, 10)) for s in sigs if s.time < cut}, name


def test_td_setup_fades_the_ninth_bar():
    n = 400
    close = np.r_[np.full(100, 1.0), 1.0 + 0.001 * np.arange(1, 13), np.full(n - 112, 1.012)]
    d = _walk(n)
    d["close"] = close
    d["open"] = np.r_[close[0], close[:-1]]
    d["high"] = np.maximum(d["open"], d["close"]) + 0.0005
    d["low"] = np.minimum(d["open"], d["close"]) - 0.0005
    sigs = qr.family_td_setup_exhaustion(d)
    assert sigs and sigs[0].side == -1
    assert sigs[0].time == d.index[100 + 9 - 1]       # the first rising close starts the run


def test_payday_is_the_fifteenth_or_the_friday_before():
    d = _walk(24 * 400)
    for s in qr.family_payday_dom(d):
        day = s.time.date()
        assert day.day == 15 or (day.weekday() == 4 and day.day in (13, 14))
        assert s.side == 1


def test_no_tick_volume_no_climax():
    d = _walk().drop(columns=["tick_volume"])
    assert qr.family_volume_climax_fade(d) == []
