"""google_trends_miner: an unmeasurable trend emits no row, never a trend_pct of 0."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import google_trends_miner as gtm  # noqa: E402


def _tl(vals: list[float]) -> list[dict]:
    return [{"value": [v]} for v in vals]


def test_short_or_zero_based_timelines_are_unmeasured() -> None:
    assert gtm.trend_reading(_tl([10, 20, 30])) is None
    assert gtm.trend_reading(_tl([0, 0, 0, 0, 5, 5, 5, 5])) is None
    assert gtm.trend_reading(_tl([10, 10, 10, 10, 15, 15, 15, 15])) == pytest.approx(50.0)


def test_the_miner_emits_nothing_for_an_unmeasurable_term(monkeypatch: pytest.MonkeyPatch
                                                          ) -> None:
    class Resp:
        status_code = 200
        text = '"timelineData": ' + json.dumps(_tl([40, 50, 60]))

    monkeypatch.setattr(gtm.requests, "get", lambda *a, **k: Resp())
    assert gtm.mine_google_trends() == []

    class Long(Resp):
        text = '"timelineData": ' + json.dumps(_tl([10, 10, 10, 10, 20, 20, 20, 20]))

    monkeypatch.setattr(gtm.requests, "get", lambda *a, **k: Long())
    rows = gtm.mine_google_trends()
    assert rows and all(r["trend_pct"] == 100.0 for r in rows)


def test_the_embedded_timeline_decodes_whole() -> None:
    page = 'x "timelineData": [{"value": [3]}, {"value": [4]}], "other": [1]'
    assert gtm.timeline_from(page) == [{"value": [3]}, {"value": [4]}]
    assert gtm.timeline_from("nothing here") == []
