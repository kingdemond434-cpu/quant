"""The news fence inside a real E8-Gold pass (patch e8_news_fence/v2): a corrupt flag or a broken
fence never kills the pass; ON blocks and cancels, OFF shadow-bills, one bill per bracket."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent), str(_DESK / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_e8_gold_guard_and_open_risk as h  # noqa: E402
from mt5desk import calendar_us as cal  # noqa: E402
from mt5desk import news_fence as nf  # noqa: E402
from prop import e8_gold as g  # noqa: E402


def _setup(monkeypatch, tmp_path, flag: str | bytes | None, *, release_now: bool) -> Path:
    h._sandbox(monkeypatch, tmp_path)
    fp = tmp_path / "E8_NEWS_FENCE.json"
    if isinstance(flag, bytes):
        fp.write_bytes(flag)
    elif flag is not None:
        fp.write_text(flag, "utf-8")
    monkeypatch.setattr(nf, "FLAG", fp)
    if release_now:
        rel = [cal.Release(datetime.now(tz=UTC), "NFP")]
        monkeypatch.setattr(nf, "releases", lambda a, b: list(rel))
    return fp


def _rows(tmp_path: Path) -> list[dict]:
    p = tmp_path / "intents.json"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]


@pytest.mark.parametrize("flag", [
    '{"enabled": true}'.encode("utf-16"),                      # UTF-16 with BOM
    '{"enabled": true, "pre_min": 1e999}',                     # inf after json.loads
    '{"enabled": true, "post_min": 1000000000000}',            # 10**12
    '{"enabled": true, "pre_min": "15"}',
    "[1, 2",
])
def test_a_corrupt_flag_never_kills_the_pass_and_reads_off(monkeypatch, tmp_path, flag) -> None:
    _setup(monkeypatch, tmp_path, flag, release_now=True)
    doc = g.run(h._Venue(), h._MT5(), armed=False)
    assert doc.get("status") == "OK"
    assert doc["news_fence"]["enabled"] is False and "malformed" in doc["news_fence"]["why"]
    assert h._placed(doc) == ["afternoon"]                      # OFF: placement unaffected
    assert any(r.get("status") == "SHADOW_FENCE" for r in _rows(tmp_path))


def test_a_fence_that_raises_fails_open_and_alerts(monkeypatch, tmp_path) -> None:
    _setup(monkeypatch, tmp_path, '{"enabled": true}', release_now=False)

    def boom(now: datetime) -> None:
        raise RuntimeError("calendar exploded")
    monkeypatch.setattr(nf, "verdict", boom)
    doc = g.run(h._Venue(), h._MT5(), armed=False)
    assert doc.get("status") == "OK" and h._placed(doc) == ["afternoon"]
    assert "calendar exploded" in doc["news_fence"]["error"]
    assert any("failed open" in a for a in doc.get("alerts", []))


def test_on_inside_a_window_defers_the_bracket_and_bills_it(monkeypatch, tmp_path) -> None:
    _setup(monkeypatch, tmp_path, '{"enabled": true}', release_now=True)
    doc = g.run(h._Venue(), h._MT5(), armed=False)
    assert h._placed(doc) == []
    assert "news fence" in h._why(doc, "afternoon")
    held = [r for r in _rows(tmp_path) if r.get("rail") == "e8_news_fence"]
    assert [r["status"] for r in held] == ["RAIL_BLOCKED"]
    assert held[0]["missed_growth_risk_usd"] > 0


def test_off_inside_a_window_places_and_writes_the_shadow_row(monkeypatch, tmp_path) -> None:
    _setup(monkeypatch, tmp_path, None, release_now=True)
    doc = g.run(h._Venue(), h._MT5(), armed=False)
    assert h._placed(doc) == ["afternoon"]
    rows = [r for r in _rows(tmp_path) if r.get("rail") == "e8_news_fence"]
    assert rows and {r["status"] for r in rows} == {"SHADOW_FENCE"}


def test_on_cancels_a_resting_bracket_once_billed(monkeypatch, tmp_path) -> None:
    _setup(monkeypatch, tmp_path, '{"enabled": true}', release_now=True)
    st = json.loads(g.STATE.read_text("utf-8"))
    st["windows"]["london_am"] = {"placed_hour": 10.0, "position_id": None, "shadow": False,
                                  "orders": {"buy_stop": {"id": 555}, "sell_stop": {"id": 556}}}
    g.STATE.write_text(json.dumps(st), "utf-8")
    cancelled: list[int] = []

    class V(h._Venue):
        def cancel(self, order_id: int) -> bool:
            cancelled.append(int(order_id))
            return True
    doc = g.run(V(stops={555: 4310.5, 556: 4289.5}), h._MT5(), armed=False)
    assert sorted(cancelled) >= [555, 556]
    acts = [a for a in doc["actions"] if a.get("act") == "news_cancel"]
    assert {a["order_id"] for a in acts} == {555, 556} and all(a["ok"] for a in acts)
    bills = [r for r in _rows(tmp_path) if r.get("rail") == "e8_news_fence"
             and r.get("window") == "london_am"]
    assert len(bills) == 1                                      # one bracket, one bill


def test_a_failed_cancel_inside_a_window_raises_an_alert(monkeypatch, tmp_path) -> None:
    _setup(monkeypatch, tmp_path, '{"enabled": true}', release_now=True)
    st = json.loads(g.STATE.read_text("utf-8"))
    st["windows"]["london_am"] = {"placed_hour": 10.0, "position_id": None, "shadow": False,
                                  "orders": {"buy_stop": {"id": 555}}}
    g.STATE.write_text(json.dumps(st), "utf-8")

    class V(h._Venue):
        def cancel(self, order_id: int) -> bool:
            return False
    doc = g.run(V(stops={555: 4310.5}), h._MT5(), armed=False)
    assert any("NOT cancelled" in a for a in doc.get("alerts", []))


def test_on_without_a_calendar_fails_open_in_and_out_of_year(tmp_path) -> None:
    fp = tmp_path / "f.json"
    fp.write_text('{"enabled": true}', "utf-8")
    for when in (datetime(2027, 1, 8, 13, 30, tzinfo=UTC),       # no table for the year
                 datetime(2026, 10, 14, 12, 30, tzinfo=UTC)):    # in year, CPI month blind
        v = nf.verdict(when, flag_path=fp)
        assert v.enabled and not v.blocks and v.calendar_ok is False and v.uncovered
