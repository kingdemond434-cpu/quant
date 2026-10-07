"""The permitted risk state (coordinator, 2026-10-07): a VIXCLS/BAML drop-in from our own bars."""
from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[2] / "desks" / "mt5"
for _p in (str(_DESK.parents[1]), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from macro import own_risk_index as ori  # noqa: E402

from libs.data import own_risk  # noqa: E402
from libs.data.terms_hold import gauntlet_terms  # noqa: E402
from libs.research.alpha_dsl import FieldCatalogue  # noqa: E402
from libs.tiers.world_macro import kind_of  # noqa: E402

N = 400


def _bars(uni: Path, symbol: str, seed: int, scale: float = 1.0) -> None:
    rng = np.random.default_rng(seed)
    days = [date(2024, 1, 1) + timedelta(days=i) for i in range(N)]
    vol = 0.01 * scale * (1.0 + 0.8 * (np.arange(N) > N - 60))       # a late vol shock
    rows, idx, px = [], [], 100.0
    for i, d in enumerate(days):
        o, c = px, px * float(np.exp(rng.normal(0, vol[i])))
        rows.append((o, max(o, c) * (1 + vol[i]), min(o, c) * (1 - vol[i]), c))
        idx.append(pd.Timestamp(d, tz="UTC") + pd.Timedelta(hours=20))
        px = c
    pd.DataFrame(rows, columns=["open", "high", "low", "close"],
                 index=pd.DatetimeIndex(idx)).to_parquet(uni / f"{symbol}_H1.parquet")


def _world(tmp: Path, banks: bool = True, cfd: bool = False) -> Path:
    uni = tmp / "uni"
    uni.mkdir()
    _bars(uni, "US500", 1)
    _bars(uni, "NAS100", 2, 1.3)
    if banks:
        for k, s in enumerate(("JPMorganChase", "Citigroup", "WellsFargo")):
            _bars(uni, s, 10 + k)
        _bars(uni, "US2000", 20)
    if cfd:
        _bars(uni, "VIX", 30)
    return uni


def test_series_are_built_point_in_time_and_read_as_a_drop_in(tmp_path: Path) -> None:
    uni = _world(tmp_path)
    now = datetime(2030, 1, 1, tzinfo=UTC)
    arch, axes = tmp_path / "own.json", tmp_path / "axes" / "own_risk.json"
    rep = ori.run(universe_dir=uni, now=now, archive=arch, axes=axes)
    assert rep["status"] == "MEASURED" and rep["credit"]["status"] == "MEASURED"
    assert rep["sources"][own_risk.RISK].startswith(own_risk.RISK_RV)
    got = own_risk.load_pit(arch, as_of=now)
    assert set(got) == set(own_risk.SERIES)
    first, last = got[own_risk.RISK][0], got[own_risk.RISK][-1]
    assert last[1] > first[1]                                   # the late shock is seen
    # PIT: as of a day's own close plus one hour, that day is knowable; one hour earlier it is not
    day = got[own_risk.RISK][100][0]
    avail = own_risk.available_at(own_risk.RISK, day, arch)
    assert avail is not None
    assert own_risk.load_pit(arch, as_of=avail)[own_risk.RISK][-1][0] == day
    assert own_risk.load_pit(arch, as_of=avail - timedelta(minutes=1))[own_risk.RISK][-1][0] < day
    assert own_risk.risk_drop_in(arch, as_of=now)["VIXCLS"] == got[own_risk.RISK]
    # our own data passes the closed terms gate
    assert gauntlet_terms(own_risk.DATA_SOURCE)[0] is True


def test_the_world_model_reads_vol_and_credit_nodes(tmp_path: Path) -> None:
    uni = _world(tmp_path)
    axes = tmp_path / "axes"
    ori.run(universe_dir=uni, now=datetime(2030, 1, 1, tzinfo=UTC),
            archive=tmp_path / "own.json", axes=axes / "own_risk.json")
    cat = FieldCatalogue(axes_dir=axes)
    fields = {f.name: f for f in cat.fields if f.source == "axis:own_risk"}
    assert {"own_risk.own_vol_index", "own_risk.own_credit_stress"} <= set(fields)
    assert kind_of("own_risk.own_vol_index", "macro_level") == "vol"
    assert kind_of("own_risk.own_credit_stress", "macro_level") == "credit"
    f = fields["own_risk.own_vol_index"]
    assert f.causal()
    s = cat.series(f, pd.date_range("2024-06-01", periods=10, freq="D", tz="UTC"))
    assert s is not None and s.notna().all()


def test_credit_is_unmeasured_without_credit_sensitive_members(tmp_path: Path) -> None:
    uni = _world(tmp_path, banks=False)
    rep = ori.run(universe_dir=uni, now=datetime(2030, 1, 1, tzinfo=UTC),
                  archive=tmp_path / "own.json", axes=tmp_path / "axes.json")
    assert rep["status"] == "MEASURED"
    assert rep["credit"]["status"] == "UNMEASURED" and "BAML" in rep["credit"]["why"]
    assert own_risk.CREDIT not in own_risk.load_pit(tmp_path / "own.json",
                                                    as_of=datetime(2030, 1, 1, tzinfo=UTC))


def test_the_broker_vix_cfd_wins_when_listed(tmp_path: Path) -> None:
    uni = _world(tmp_path, cfd=True)
    rep = ori.run(universe_dir=uni, now=datetime(2030, 1, 1, tzinfo=UTC),
                  archive=tmp_path / "own.json", axes=tmp_path / "axes.json")
    assert rep["broker_vix_cfd"] == "VIX" and rep["sources"][own_risk.RISK] == "broker_cfd:VIX"


def test_the_vixcls_comparison_is_research_only_and_honest() -> None:
    own = [[f"2024-01-{d:02d}", 10.0 + d, "x"] for d in range(1, 31)]
    assert ori.comparison(own, {}, "")["status"] == "UNMEASURED"
    days = [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(200)]
    rng = np.random.default_rng(3)
    lvl = 15 + np.cumsum(rng.normal(0, 0.5, 200)).clip(-10, 30)
    own = [[d, float(v), "x"] for d, v in zip(days, lvl, strict=True)]
    vix = {d: float(v) * 1.2 + 2.0 for d, v in zip(days, lvl, strict=True)}
    got = ori.comparison(own, vix, "test")
    assert got["status"] == "MEASURED" and got["corr_level"] > 0.99
    assert abs(got["ols_vix_on_own"]["slope"] - 1.2) < 1e-6
    assert "research-only" in got["note"]


def test_the_forced_flow_calendar_is_own_data() -> None:
    assert gauntlet_terms("forced_flow_calendar")[0] is True
