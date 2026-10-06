"""The two analyst families replay the store the organ wrote, point-in-time, on the bar clock.

* entry is the first bar OPENING at or after the knowable instant (first_seen_at), never the
  bar containing it;
* a backfilled view is never a signal;
* `side` flips the measured sign, and a cross-market lead fires only for its own lead group;
* the sweep cannot call either blind, and the gauntlet's `fn(h1, side=1, **params)` falls back
  to `fn(h1, **params)` when the cell carries its own side.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families_orthogonal as fo  # noqa: E402
from mt5desk import family_analyst_revision as far  # noqa: E402

from libs.research import analyst_views as av  # noqa: E402

T0 = datetime(2024, 3, 4, tzinfo=UTC)


def _h1(days: int = 60) -> pd.DataFrame:
    idx = pd.date_range(T0, T0 + timedelta(days=days), freq="1h", tz="UTC", inclusive="left")
    rng = np.random.default_rng(3)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, len(idx))))
    return pd.DataFrame({"open": close, "high": close * 1.002, "low": close * 0.998,
                         "close": close}, index=idx)


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> av.AnalystViewStore:
    path = tmp_path / "views.jsonl"
    monkeypatch.setenv("QUANT_ALPHA_CAPTURE_STORE", str(path))
    monkeypatch.setattr(av, "bar_clock", lambda: av.identity_clock)
    far._CACHE.clear()
    return av.AnalystViewStore(path)


def _view(pub: datetime, action: str, *, native: str, instrument: str | None = "NVIDIA",
          leads: list[str] | None = None, source: str = "yahoo_upgrades") -> av.AnalystView:
    return av.AnalystView(source=source, published_at=pub.isoformat(),
                          published_precision="datetime", issuer="X", title="t",
                          instrument=instrument, leads=leads or [], broker="B", action=action,
                          native_id=native).finish()


def test_entry_is_the_first_bar_opening_after_first_seen(store: av.AnalystViewStore) -> None:
    pub = T0 + timedelta(days=30, hours=9, minutes=10)
    seen = pub + timedelta(minutes=20)                       # 09:30: inside the 09:00 bar
    store.append([_view(pub, "up", native="a")], now=seen)
    sigs = fo.ORTHOGONAL_FAMILIES["analyst_revision_drift"](
        _h1(), symbol="NVIDIA", source="yahoo_upgrades", side=1, hold_days=2)
    assert len(sigs) == 1
    assert pd.Timestamp(sigs[0].time) == pd.Timestamp(T0 + timedelta(days=30, hours=10))
    assert sigs[0].side == 1 and sigs[0].ttl_bars == 48
    fade = far.family_analyst_revision_drift(_h1(), symbol="NVIDIA", source="yahoo_upgrades",
                                             side=-1)
    assert fade[0].side == -1
    assert not far.family_analyst_revision_drift(_h1(), symbol="Apple",
                                                 source="yahoo_upgrades")


def test_a_backfilled_view_is_never_a_signal(store: av.AnalystViewStore) -> None:
    pub = T0 + timedelta(days=10)
    store.append([_view(pub, "down", native="old")], now=pub + timedelta(days=20))
    assert not far.family_analyst_revision_drift(_h1(), symbol="NVIDIA",
                                                 source="yahoo_upgrades")


def test_a_cross_market_lead_fires_only_for_its_group(store: av.AnalystViewStore) -> None:
    pub = T0 + timedelta(days=25, hours=1)
    store.append([_view(pub, "up", native="k", instrument=None, leads=["kr_semis"],
                        source="naver_research")], now=pub + timedelta(hours=1))
    lead = fo.ORTHOGONAL_FAMILIES["analyst_cross_market_lead"]
    got = lead(_h1(), symbol="USDKRW", source="naver_research", lead="kr_semis", side=-1)
    assert len(got) == 1 and got[0].side == -1
    assert not lead(_h1(), symbol="USDKRW", source="naver_research", lead="cn_market")
    assert not lead(_h1(), symbol="HK50", source="naver_research", lead="kr_semis")


def test_the_sweep_cannot_call_them_blind_and_the_gauntlet_call_shape_works(
        store: av.AnalystViewStore) -> None:
    import orthogonal_sweep as osw
    for name in ("analyst_revision_drift", "analyst_cross_market_lead"):
        fn = fo.ORTHOGONAL_FAMILIES[name]
        assert osw._unsuppliable(fn, {}) is not None
        assert fo.FAMILY_INPUTS[name][0] != "price only"
    pub = T0 + timedelta(days=30, hours=2)
    store.append([_view(pub, "up", native="g")], now=pub)
    params = {"symbol": "NVIDIA", "source": "yahoo_upgrades", "side": -1, "hold_days": 5}
    fn = fo.ORTHOGONAL_FAMILIES["analyst_revision_drift"]
    with pytest.raises(TypeError):
        fn(_h1(), side=1, **params)                      # what external_gauntlet tries first
    assert fn(_h1(), **params)[0].side == -1             # and the fallback it then takes


def test_mechanism_tables_know_both_families() -> None:
    from libs.research import alpha_clusters as ac
    from research import axis_registry as ar
    assert ar.classify_family("analyst_revision_drift")[0] == "trend_persistence"
    assert ar.classify_family("analyst_cross_market_lead")[0] == "cross_market_lead"
    assert ac.FAMILY_CLUSTER["analyst_revision_drift"] == "news_reaction"
    assert ac.FAMILY_CLUSTER["analyst_cross_market_lead"] == "cross_asset_lead_lag"
