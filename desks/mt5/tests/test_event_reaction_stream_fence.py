"""An event_reaction cell on a share CFD is judged on ITS OWN disclosure stream or not at all.

THE DEFECT PINNED (audit of PR #140, 2026-09-30). The sealed gauntlet and the forward clock hand
every event_reaction cell the one event index they know -- the Forex Factory macro calendar --
unless the cell names its own `event_stream`. For FX, indices and metals that calendar is the
declared stream. For a single-name equity it is not, and a share-CFD cell with no stream would have
been judged on US payrolls under the disclosure lane's name. Such a cell is now refused as
UNBUILDABLE with the named cause MISSING_EVENT_STREAM: at the family (which the sealed build_cell
turns into a named failed build), and at the emitter, which never mints one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import disclosure_events as DE  # noqa: E402
from mt5desk import family_event_reaction as FER  # noqa: E402

from research import universe_policy as UP  # noqa: E402

EQUITY = "AlibabaGroup"
FX = "EURUSD"


def _bars(n: int = 400) -> pd.DataFrame:
    idx = pd.date_range("2026-04-01", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 0.3, n))
    o = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, close) * 1.001,
                         "low": np.minimum(o, close) * 0.999, "close": close}, index=idx)


def _calendar(symbol: str) -> list[dict]:
    return [{"symbol": symbol, "at": t.isoformat()}
            for t in pd.date_range("2026-04-05", periods=8, freq="3D", tz="UTC")]


@pytest.fixture(autouse=True)
def _registry_classes() -> None:
    if not (UP.is_equity(EQUITY) and not UP.is_equity(FX)):
        pytest.skip("this tree's registry does not classify AlibabaGroup / EURUSD")


def test_a_share_cfd_with_no_stream_is_refused_by_name() -> None:
    why = FER.stream_refusal(EQUITY, "")
    assert why is not None and why.startswith(FER.MISSING_EVENT_STREAM)
    with pytest.raises(FER.MissingEventStream) as got:
        FER.family_event_reaction(_bars(), events=_calendar(EQUITY), symbol=EQUITY, clock="bars")
    assert got.value.cause == FER.MISSING_EVENT_STREAM
    # a TypeError, so the sealed build_cell's retry path turns it into a NAMED failed build
    assert isinstance(got.value, TypeError)


def test_an_unreadable_stream_is_refused_on_any_symbol() -> None:
    for sym in (EQUITY, FX):
        assert FER.stream_refusal(sym, "not:a:stream") is not None
        with pytest.raises(FER.MissingEventStream):
            FER.family_event_reaction(_bars(), events=None, symbol=sym,
                                      event_stream="not:a:stream")


def test_a_declared_stream_and_the_macro_calendar_lane_still_build() -> None:
    spec = DE.make_spec("cn", "self", "earnings", "any", 1)
    assert FER.stream_refusal(EQUITY, spec) is None
    # an FX cell's calendar IS its declared stream: unchanged by the fence
    assert FER.stream_refusal(FX, "") is None
    sigs = FER.family_event_reaction(_bars(), events=_calendar(FX), symbol=FX, clock="bars")
    assert sigs, "the macro-calendar lane stopped producing signals"


def test_the_sealed_build_cell_reports_the_refusal_as_an_unbuildable_cell(monkeypatch) -> None:
    from desks.mt5.scripts import external_gauntlet as G

    from research import orthogonal_sweep as inputs

    monkeypatch.setattr(inputs, "_event_index", lambda: pd.DatetimeIndex(
        [r["at"] for r in _calendar(EQUITY)]))
    got = G.build_cell(EQUITY, "event_reaction", {"symbol": EQUITY}, {}, h1_override=_bars())
    assert got is None
    assert G.LAST_BUILD_FAILURE is not None
    assert FER.MISSING_EVENT_STREAM in G.LAST_BUILD_FAILURE


def test_the_emitter_mints_no_event_lane_row_without_a_readable_stream(monkeypatch) -> None:
    from research import corporate_disclosure as CD

    real = DE.make_spec
    monkeypatch.setattr(DE, "make_spec", lambda *a, **k: "")
    res = CD.Resolver({})
    res.targets = {}
    monkeypatch.setattr(CD, "SOURCES", [{"id": "fence"}])
    monkeypatch.setattr(CD, "_events", lambda _p: [
        {"country": "cn", "symbols": [EQUITY], "category": "earnings", "direction": 0,
         "at": d.isoformat()}
        for d in pd.date_range("2026-01-05", periods=CD.MIN_EVENT_DAYS + 2, freq="7D", tz="UTC")])
    rows = CD.enumerate_specs(res, {})
    assert not [r for r in rows if r["family"] in ("event_reaction", "news_reaction")]
    assert CD.STREAM_REFUSALS.get(FER.MISSING_EVENT_STREAM, 0) > 0
    # and with the real spec maker every minted event-lane row carries a readable stream
    monkeypatch.setattr(DE, "make_spec", real)
    rows = CD.enumerate_specs(res, {})
    lane = [r for r in rows if r["family"] in ("event_reaction", "news_reaction")]
    assert lane and all(FER.stream_refusal(r["params"]["symbol"], r["params"]["event_stream"])
                        is None for r in lane)
    assert CD.STREAM_REFUSALS == {}
