"""implied_move (audit #9, QG25-06): eve-implied move vs the event's realised move, PIT, GAIN on
a planted effect and not on noise. Synthetic only."""
from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK.parents[1]), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from macro import implied_move as im  # noqa: E402

N = 2200


def _world(tmp: Path, planted: bool, seed: int = 5
           ) -> tuple[Path, dict[str, list[tuple[str, float]]], list[tuple[str, datetime]]]:
    rng = np.random.default_rng(seed)
    days = [date(2018, 1, 1) + timedelta(days=i) for i in range(N)]
    vix = 18 + 7 * np.sin(np.arange(N) / 37.0) + rng.normal(0, 1.0, N)
    rets = rng.normal(0, 0.008, N)
    events = []
    for i in range(30, N - 2, 21):
        ev = days[i]
        events.append(("NFP", datetime(ev.year, ev.month, ev.day, 12, 30, tzinfo=UTC)))
        sig = (vix[i - 1] / 100 / np.sqrt(252)) if planted else 0.012
        rets[i] = rng.normal(0, 2.2 * sig)
        vix[i] = vix[i - 1] - 1.5                       # the crush
    closes = 100 * np.exp(np.cumsum(rets))
    idx = pd.DatetimeIndex([pd.Timestamp(d, tz="UTC") + pd.Timedelta(hours=20) for d in days])
    pd.DataFrame({"close": closes}, index=idx).to_parquet(tmp / "US500_H1.parquet")
    series = {"VIXCLS": [(d.isoformat(), float(v)) for d, v in zip(days, vix, strict=True)]}
    return tmp, series, events


def test_rows_are_pit_and_the_crush_is_measured(tmp_path: Path) -> None:
    uni, series, events = _world(tmp_path, planted=True)
    now = datetime(2024, 1, 1, tzinfo=UTC)
    rep = im.run(dry_run=True, universe_dir=uni, now=now, series=series, events=events)
    s = rep["symbols"]["US500"]
    last = s["last"]
    assert last["crush"] > 0 and last["pre_day"] < last["event_day"]
    assert datetime.fromisoformat(last["event_at"]) <= now
    rows = im.lake_rows([last], "VIXCLS")
    pre, post = rows
    assert datetime.fromisoformat(pre["available_time"]) > datetime.fromisoformat(
        last["pre_day"]).replace(tzinfo=UTC)
    # the post-event ratio is never known before the event day's close is
    assert datetime.fromisoformat(post["available_time"]) >= datetime.fromisoformat(
        last["event_day"]).replace(tzinfo=UTC) + timedelta(hours=25)
    assert rep["unmeasured"]["BOJ"].startswith("no FRED-republished")
    assert s["data_source"] == "fred:VIXCLS"


def test_planted_implied_effect_is_gain_and_noise_is_not(tmp_path: Path) -> None:
    now = datetime(2030, 1, 1, tzinfo=UTC)
    (tmp_path / "a").mkdir()
    uni, series, events = _world(tmp_path / "a", planted=True)
    by = {c["label"]: c for c in im.run(dry_run=True, universe_dir=uni, now=now, series=series,
                                        events=events)["contracts"]}
    assert by["implied_pre->|move|"]["verdict"] == "GAIN"
    (tmp_path / "b").mkdir()
    uni, series, events = _world(tmp_path / "b", planted=False, seed=8)
    nb = {c["label"]: c for c in im.run(dry_run=True, universe_dir=uni, now=now, series=series,
                                        events=events)["contracts"]}
    assert nb["implied_pre->|move|"]["verdict"] in ("NO_GAIN", "UNMEASURED")
