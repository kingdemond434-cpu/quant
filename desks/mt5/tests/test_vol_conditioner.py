"""vol_conditioner (QG25-05/26-07/26-09): PIT rows, a GAIN on a planted IV effect, NO_GAIN or
UNMEASURED on noise, and the terms hold on the Yahoo/CBOE source. Synthetic only."""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK.parents[1]), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from macro import vol_conditioner as vc  # noqa: E402

N = 1100


def _world(tmp: Path, planted: bool, seed: int = 7) -> tuple[Path, Path]:
    rng = np.random.default_rng(seed)
    days = [date(2022, 1, 3) + timedelta(days=i) for i in range(N)]
    iv = 20 + 8 * np.sin(np.arange(N) / 23.0) + rng.normal(0, 1.5, N)
    ret = rng.normal(0, 0.01, N)
    if planted:
        # a high IV state (known the next day) is followed by a positive drift
        rank = pd.Series(iv).rolling(252, min_periods=20).apply(
            lambda w: (w <= w.iloc[-1]).mean(), raw=False).to_numpy()
        for i in range(2, N):
            if rank[i - 2] >= 0.8:
                ret[i] += 0.006
    closes = 100 * np.exp(np.cumsum(ret))
    ref = tmp / "ref"
    ref.mkdir()
    (ref / "VIX.json").write_text(json.dumps(
        {"fetched_at": "x", "series": {d.isoformat(): float(v) for d, v in zip(days, iv)}}))
    uni = tmp / "uni"
    uni.mkdir()
    idx = pd.DatetimeIndex([pd.Timestamp(d, tz="UTC") + pd.Timedelta(hours=20) for d in days])
    pd.DataFrame({"close": closes}, index=idx).to_parquet(uni / "US500_H1.parquet")
    return ref, uni


def test_rows_are_point_in_time() -> None:
    iv = {f"2026-01-{d:02d}": 20.0 + d for d in range(1, 29)}
    rows = vc.build_ground("^VIX", iv=iv, closes={})
    for r in rows:
        assert datetime.fromisoformat(r["available_time"]) >= (
            datetime.fromisoformat(r["event_time"]).replace(tzinfo=UTC) + vc.LAG)
        assert r["knowable_basis"] == "declared_lag"
    # the percentile of a day never uses that day or later
    assert rows[19]["iv_pct"] is None and rows[20]["iv_pct"] == 1.0


def test_planted_iv_effect_is_gain_and_noise_is_not(tmp_path: Path) -> None:
    now = datetime(2030, 1, 1, tzinfo=UTC)
    (tmp_path / "a").mkdir()
    ref, uni = _world(tmp_path / "a", planted=True)
    rep = vc.run(dry_run=True, reference=ref, universe_dir=uni, now=now)
    g = rep["grounds"]["^VIX"]
    assert g["status"] == "MEASURED" and g["symbol"] == "US500"
    by = {c["label"]: c for c in rep["contracts"]}
    assert by["iv_high->long"]["verdict"] == "GAIN"
    (tmp_path / "b").mkdir()
    ref, uni = _world(tmp_path / "b", planted=False, seed=11)
    noise = {c["label"]: c for c in vc.run(dry_run=True, reference=ref, universe_dir=uni,
                                           now=now)["contracts"]}
    assert noise["iv_high->long"]["verdict"] in ("NO_GAIN", "UNMEASURED")
    assert rep["grounds"]["^GVZ"]["status"] == "UNMEASURED"


def test_cells_are_held_by_the_terms_gate() -> None:
    from libs.research import sensor_engines as se
    got = se.emit_conditioner_cells("ws_vol_state_us500", ["iv_pct"], ["US500"], mechanism="m",
                                    falsifier="f", generator=vc.ENGINE, dry_run=True,
                                    data_source=f"{vc.VOL_SOURCE}:^VIX")
    assert got["status"] == "HELD_TERMS" and got["emitted"] == 0


def test_fred_substitute_is_the_source_when_present(tmp_path: Path) -> None:
    """Coordinator 2026-10-06: FRED's republished CBOE series replace the held Yahoo copy, on
    FRED's own clock, and the substitute is measured against the held source."""
    ref, uni = _world(tmp_path, planted=True)
    held = json.loads((ref / "VIX.json").read_text())["series"]
    fred = {"VIXCLS": [(d, v * 1.01 + 0.2) for d, v in sorted(held.items())]}
    rep = vc.run(dry_run=True, reference=ref, universe_dir=uni,
                 now=datetime(2030, 1, 1, tzinfo=UTC), series=fred)
    g = rep["grounds"]["^VIX"]
    assert g["data_source"] == "fred:VIXCLS"
    assert g["substitute"]["covered"] is True and g["substitute"]["corr"] > 0.99
    last = g["last"]
    # FRED's declared lag: day d is held at d+1 09:00 ET, never earlier
    d = datetime.fromisoformat(last["event_time"]).date()
    assert datetime.fromisoformat(last["available_time"]) >= datetime(
        d.year, d.month, d.day, 13, 0, tzinfo=UTC) + timedelta(days=1)
    from libs.research import sensor_engines as se
    # FRED republishes CBOE's index under CBOE's copyright notice, which FRED cannot license
    # (ToU FAQ Q3): the substitute is measured state, and its cells stay HELD (audit #211)
    held_cells = se.emit_conditioner_cells("ws_vol_state_us500", ["iv_pct"], ["US500"],
                                           mechanism="m", falsifier="f", generator=vc.ENGINE,
                                           dry_run=True, data_source=g["data_source"])
    assert held_cells["status"] == "HELD_TERMS" and held_cells["emitted"] == 0
