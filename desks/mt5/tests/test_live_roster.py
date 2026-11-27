"""ROOT R10 (2026-11-27): one live roster, every account; E8 gold is in it."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from prop import live_roster as lr  # noqa: E402
from prop import zero_live_page as z  # noqa: E402

NOW = datetime(2026, 11, 27, 5, 10, tzinfo=UTC)          # a Friday, market open


def _paths(tmp_path: Path, *, gold_at: datetime = NOW) -> dict[str, Path]:
    p = {k: tmp_path / f"{k}.json" for k in ("e8_gold", "e8_book", "ftmo", "fusion")}
    p["pause"] = tmp_path / "GATEWAY_PAUSED"
    p["e8_gold"].write_text(json.dumps({
        "at": gold_at.isoformat(), "placed": [{"window": "asia", "legs": []}],
        "sizing_source": {"asia": "e8_speed_lift", "london_am": "session_probe",
                          "afternoon": "pinned_zero"},
        "kelly_risk": {"asia": 0.0075, "london_am": 0.00074}}), encoding="utf-8")
    p["e8_book"].write_text(json.dumps({"generated_utc": NOW.isoformat(), "sleeves": [
        {"symbol": "EURUSD", "family": "srb", "key": "EURUSD.srb", "risk_frac": 0.002}]}),
        encoding="utf-8")
    p["ftmo"].write_text(json.dumps({"generated_utc": NOW.isoformat(), "deployable": True,
                                     "executable": {"XAUUSD.asia@M30": 0.01, "GBPUSD.x": 0.0,
                                                    "bad": True}}), encoding="utf-8")
    p["fusion"].write_text(json.dumps({"sleeves": [
        {"name": "s1", "status": "LIVE", "symbol": "USDJPY", "probe": True,
         "certificate": {"cell": "c1"}}, {"name": "s2", "status": "STANDBY"}, "junk"]}),
        encoding="utf-8")
    return p


def test_every_account_is_in_one_roster_with_its_size_source(tmp_path) -> None:
    doc = lr.build(NOW, paths=_paths(tmp_path), exposure=False)
    by = {(r["account"], r["sleeve"]): r for r in doc["rows"]}
    assert by[("e8", "gold_asia")]["state"] == "PLACED"
    assert by[("e8", "gold_asia")]["size_source"] == "e8_speed_lift"
    assert by[("e8", "gold_london_am")]["fraction"] == 0.00074
    assert ("e8", "gold_afternoon") not in by                # pinned zero carries no risk
    assert by[("e8", "EURUSD.srb")]["lane"] == "e8_executor"
    assert {k for k in by if k[0] == "ftmo"} == {("ftmo", "XAUUSD.asia@M30")}
    assert by[("fusion", "s1")]["size_source"] == "probe_tier"
    assert by[("fusion", "s1")]["cert_key"] == "c1"
    assert doc["accounts"] == {"e8": 3, "ftmo": 1, "fusion": 1}


def test_a_stale_or_absent_source_is_named_and_never_an_empty_book(tmp_path) -> None:
    p = _paths(tmp_path, gold_at=NOW - timedelta(hours=5))
    p["ftmo"].unlink()
    doc = lr.build(NOW, paths=p, exposure=False)
    assert doc["sources"]["e8_gold"]["status"] == "STALE"
    assert doc["sources"]["ftmo"]["status"] == "ABSENT"
    assert not any(r["lane"] == "e8_gold" for r in doc["rows"])


def test_the_reader_refuses_a_stale_roster(tmp_path) -> None:
    out = tmp_path / "LIVE_ROSTER.json"
    lr.publish(NOW, out=out, paths=_paths(tmp_path), exposure=False)
    assert len(lr.rows("e8", path=out, now=NOW)) == 3
    assert lr.rows(path=out, now=NOW + timedelta(hours=4)) == []
    assert lr.status(path=out, now=NOW + timedelta(hours=4)) == "STALE"


def test_the_zero_live_page_counts_e8_gold_as_e8_trading(tmp_path, monkeypatch) -> None:
    p = _paths(tmp_path)
    p["e8_book"].write_text(json.dumps({"generated_utc": NOW.isoformat(), "sleeves": []}),
                            encoding="utf-8")
    for attr, key in (("E8_GOLD", "e8_gold"), ("E8_BOOK", "e8_book"), ("FTMO_BOOK", "ftmo"),
                      ("SLEEVES", "fusion"), ("PAUSE", "pause")):
        monkeypatch.setattr(z, attr, p[key])
    doc = z.assess(NOW)
    assert doc["accounts"]["e8"]["status"] == z.LIVE and doc["accounts"]["e8"]["via"] == "e8_gold"
    assert "e8" not in doc["not_trading"]


def test_gold_never_hides_a_broken_e8_book(tmp_path, monkeypatch) -> None:
    """Audit MF1: an UNMEASURED E8_BOOK keeps E8 down and paging even while gold trades."""
    p = _paths(tmp_path)
    p["e8_book"].write_text("{torn", encoding="utf-8")
    for attr, key in (("E8_GOLD", "e8_gold"), ("E8_BOOK", "e8_book"), ("FTMO_BOOK", "ftmo"),
                      ("SLEEVES", "fusion"), ("PAUSE", "pause")):
        monkeypatch.setattr(z, attr, p[key])
    doc = z.assess(NOW)
    assert doc["accounts"]["e8"]["status"] == z.UNMEASURED
    assert doc["accounts"]["e8"]["gold_live"] == 2
    assert "e8" in doc["not_trading"] and doc["page"] is True
