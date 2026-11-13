"""The event calendar is built from the publishers' own pages, in UTC, and never worsens."""
from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from libs.data import event_calendar as ec

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "event_calendar"
NOW = datetime(2026, 11, 13, 20, 25, tzinfo=UTC)


def _pages() -> dict[str, str | None]:
    return {f.name[:-8]: gzip.decompress(f.read_bytes()).decode("utf-8", "replace")
            for f in FIX.glob("*.html.gz")}


@pytest.fixture(scope="module")
def doc() -> dict:
    return ec.build(_pages(), NOW)


def _ev(doc: dict, publisher: str) -> list[dict]:
    return [e for e in doc["events"] if e["publisher"] == publisher]


def test_every_parsed_publisher_yields_events(doc) -> None:
    for pid in ("fed_fomc", "bls_cpi", "bls_empsit", "bea_schedule", "ecb_mp_meetings",
                "boe_mpc_dates", "boj_mpm", "snb_events", "boc_schedule"):
        assert doc["coverage"][pid]["status"] == "OK", pid
    assert doc["coverage"]["rba_schedule"]["status"] == "UNMEASURED"


def test_valid_through_is_the_earliest_core_horizon(doc) -> None:
    core = [doc["coverage"][p]["through"] for p in ec.CORE]
    assert doc["valid_through"] == min(core) and doc["valid_through"] >= "2027-01-01"


def test_publisher_zones_convert_to_utc_across_daylight_saving(doc) -> None:
    fed = {e["utc"] for e in _ev(doc, "Fed")}
    assert "2026-12-09T19:00:00Z" in fed            # 14:00 EST
    assert "2026-09-16T18:00:00Z" in fed            # 14:00 EDT
    assert any(e["utc"] == "2026-12-17T13:15:00Z" for e in _ev(doc, "ECB"))   # 14:15 CET
    assert any(e["utc"] == "2026-12-10T08:30:00Z" for e in _ev(doc, "SNB"))   # 09:30 CET
    assert any(e["utc"] == "2026-12-09T14:45:00Z" for e in _ev(doc, "BoC"))   # 09:45 EST
    nfp = [e for e in _ev(doc, "BLS") if "Employment" in e["name"]]
    assert any(e["utc"].endswith("T13:30:00Z") for e in nfp)                 # 08:30 EST


def test_bea_rows_carry_their_own_titles_and_impact(doc) -> None:
    bea = _ev(doc, "BEA")
    gdp = [e for e in bea if e["name"].startswith("GDP (Second")]
    assert gdp and gdp[0]["impact"] == "high" and gdp[0]["utc"] == "2026-11-25T13:30:00Z"
    assert all(e["name"] not in ("Release", "N", "ews") for e in bea)


def test_rows_carry_the_guard_schema_and_their_source(doc) -> None:
    for e in doc["events"]:
        assert set(e) >= {"utc", "name", "impact", "source", "fetched_at", "local"}
        assert e["utc"].endswith("Z") and e["source"].startswith("https://")
    assert ec.refusal(doc) is None


def test_the_guard_reads_the_built_calendar(tmp_path, doc) -> None:
    from libs.execution import event_guard as eg
    p = tmp_path / "cal.json"
    p.write_text(json.dumps(doc), "utf-8")
    at = datetime(2026, 12, 9, 18, 50, tzinfo=UTC)
    assert eg.check(at, calendar=p).state == "BLACKOUT"
    assert eg.check(datetime(2026, 12, 1, 3, 0, tzinfo=UTC), calendar=p).state == "CLEAR"


def test_a_missing_core_page_empties_valid_through_and_reads_stale() -> None:
    pages = _pages()
    pages["bls_cpi"] = None
    d = ec.build(pages, NOW, {"bls_cpi": "HTTP 403"})
    assert d["valid_through"] == ""
    assert d["coverage"]["bls_cpi"]["why"] == "HTTP 403"
    assert ec.health(d, NOW)["state"] == "STALE"


def test_an_unread_core_page_carries_its_last_good_events_then_expires(doc) -> None:
    pages = _pages()
    pages["bls_cpi"] = None
    later = NOW + timedelta(days=7)
    d = ec.carry_forward(ec.build(pages, later, {"bls_cpi": "HTTP 503"}), doc, later)
    assert d["coverage"]["bls_cpi"]["status"] == "CARRIED" and d["valid_through"]
    assert ec.refusal(d) is None
    much_later = NOW + timedelta(days=ec.CARRY_MAX_D + 1)
    d2 = ec.carry_forward(ec.build(pages, much_later, {}), doc, much_later)
    assert d2["coverage"]["bls_cpi"]["status"] == "UNMEASURED" and d2["valid_through"] == ""


def test_refusal_names_a_worse_calendar() -> None:
    assert ec.refusal({"events": []})
    row = {"utc": "2026-12-09T19:00:00Z", "name": "x", "publisher": "Fed"}
    assert "duplicate" in (ec.refusal({"events": [row, dict(row)]}) or "")
    assert "UTC" in (ec.refusal({"events": [{**row, "utc": "2026-12-09 19:00"}]}) or "")


def test_fetch_goes_through_the_robots_gate_under_an_honest_ua() -> None:
    seen: list[tuple[str, str]] = []

    def get(url, headers=None, **_kw):
        seen.append((url, headers["User-Agent"]))
        return SimpleNamespace(ok=False, status=403, text="", error="x")

    def refusal(url):
        return "robots.txt disallows this path" if "bea.gov" in url else None

    pages, refused = ec.fetch_pages(get, refusal)
    assert pages["bea_schedule"] is None and refused["bea_schedule"].startswith("ROBOTS")
    assert all("bea.gov" not in u for u, _ in seen)
    assert all("Mozilla" not in ua and ua.startswith(ec.ROBOTS_AGENT) for _, ua in seen)
    assert refused["fed_fomc"] == "HTTP 403"


def test_due_is_weekly_and_early_when_a_core_page_was_missed(doc) -> None:
    assert ec.due(None, NOW)
    assert ec.due(doc, NOW + timedelta(days=1)) is None
    assert ec.due(doc, NOW + timedelta(days=ec.REFRESH_D))
    bad = {**doc, "coverage": {**doc["coverage"], "bls_cpi": {"status": "CARRIED"}}}
    assert "bls_cpi" in (ec.due(bad, NOW) or "")


def test_the_hand_written_calendar_is_due_and_its_health_is_judged() -> None:
    old = {"valid_through": "2027-12-08", "generated": "2026-08-29T02:53:51Z",
           "events": [{"utc": "2027-12-08T19:00:00Z"}]}
    assert ec.due(old, NOW)
    assert ec.health(old, NOW)["state"] == "STALE"          # 76 days unrefreshed
