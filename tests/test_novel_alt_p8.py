"""Pass-8 novel styles in alt_proxies: P8-N1 EU day-ahead power stress (Energy-Charts, LIVE on
CC BY 4.0 zones) and P8-N2 OpenSky departures (IDEAS_ONLY, NEEDS_KEY). Parse, PIT stamp, FAILED
passes, person-held hard stops, the PIT consumer and the terms rows. No network: every fetch goes
through an injected getter."""
from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.parse
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import alt_proxies as A  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
EC = FIX / "energy_charts"
NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)
POWER = A.BY_ID["eu_power_dayahead"]
SKY = A.BY_ID["opensky_departures"]


def _http(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x/", code, "no", {}, io.BytesIO(b""))  # type: ignore[arg-type]


class Getter:
    def __init__(self, robots: Any, pages: list[Any]) -> None:
        self.robots, self.pages = robots, list(pages)
        self.urls: list[str] = []

    def __call__(self, url: str) -> tuple[bytes, str]:
        self.urls.append(url)
        item = self.robots if url.endswith("/robots.txt") else self.pages.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item, "application/json"

    @property
    def data_urls(self) -> list[str]:
        return [u for u in self.urls if not u.endswith("/robots.txt")]


def _run(getter: Getter, tmp: Path, sst: dict[str, Any] | None = None,
         store: dict[str, Any] | None = None, clock: Any = None
         ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    sst = {} if sst is None else sst
    store = {} if store is None else store
    rec = A.collect_power(A.Paths(tmp / "desk"), POWER, sst, store, NOW, fetch=True,
                          fixtures=None, deadline=float("inf"), getter=getter,
                          sleep=lambda _s: None, clock=clock or (lambda: NOW))
    return rec, store, sst


def _caught_up_sst() -> dict[str, Any]:
    """Cursors one window from tomorrow, so each zone asks exactly one request."""
    since = (NOW - timedelta(days=5)).date().isoformat()
    return {"power_from": dict.fromkeys(A.POWER_ZONES, since)}


# ============================================================================ parse
def test_power_fixture_parses_complete_delivery_days_only() -> None:
    obs = {(o.series, o.period): o.value for o in
           A.parse_power_dayahead((EC / "price_de_lu.json").read_bytes(), A.Ctx(part="de_lu"))}
    assert ("de_lu_dayahead_base", date(2026, 10, 12)) in obs
    assert ("de_lu_dayahead_peak", date(2026, 10, 13)) in obs
    assert ("de_lu_dayahead_base", date(2026, 10, 14)) not in obs       # partial day: never
    # 12 peak hours at +30, one hour at -120 on the 12th: base = 80 + (360 - 120) / 24
    assert obs[("de_lu_dayahead_base", date(2026, 10, 12))] == pytest.approx(90.0)
    assert obs[("de_lu_dayahead_peak", date(2026, 10, 13))] == pytest.approx(115.0)


def test_a_body_without_the_cc_by_licence_is_never_read() -> None:
    body = (EC / "price_restricted.json").read_bytes()
    assert A.power_licence_error(body).startswith("LICENCE_CHANGED")  # type: ignore[union-attr]
    assert A.parse_power_dayahead(body, A.Ctx(part="de_lu")) == []
    assert A.power_licence_error(b"<html>blocked</html>").startswith("NOT_JSON")  # type: ignore[union-attr]


def test_only_cc_by_zones_are_ever_requested() -> None:
    assert set(A.POWER_ZONES) == {"DE-LU", "FR"}
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(
        A.power_request("FR", date(2026, 1, 1), date(2026, 1, 31), NOW).url).query)
    assert q == {"bzn": ["FR"], "start": ["2026-01-01"], "end": ["2026-01-31"]}
    assert A.POWER_URL.startswith("https://api.energy-charts.info/")


def test_opensky_fixture_parses_departures_per_country() -> None:
    obs = {(o.series, o.period): o.value for o in A.parse_opensky_departures(
        (FIX / "opensky" / "departures.json").read_bytes(), A.Ctx())}
    assert obs[("cn_departures", date(2026, 10, 12))] == 5
    assert obs[("tr_departures", date(2026, 10, 13))] == 1
    assert not any(s.startswith("gb") for s, _ in obs)                   # unmapped: discarded


# ============================================================================ PIT
def test_power_stamp_is_d_minus_1_1400_brussels_and_never_earlier_than_the_read() -> None:
    # summer (CEST, UTC+2) and winter (CET, UTC+1), both on the latest stated deadline
    assert A.rule_power_dayahead(date(2026, 7, 2)) == datetime(2026, 7, 1, 12, tzinfo=UTC)
    assert A.rule_power_dayahead(date(2026, 1, 15)) == datetime(2026, 1, 14, 13, tzinfo=UTC)
    for d in (date(2026, 3, 29), date(2026, 3, 30), date(2026, 10, 25), date(2026, 10, 26)):
        t = A.rule_power_dayahead(d)
        # never before the 12:45 CET preliminary results of D-1, in either regime
        assert t >= datetime(d.year, d.month, d.day, tzinfo=UTC) - timedelta(hours=12)
    assert A.cet_day_hours(date(2026, 3, 29)) == 23 and A.cet_day_hours(date(2026, 10, 25)) == 25
    store: dict[str, Any] = {}
    early_read = datetime(2026, 10, 12, 11, 0, tzinfo=UTC)                 # before 14:00 CEST
    A.merge_vintages(store, POWER, [A.Obs("fr_dayahead_base", date(2026, 10, 13), 61.0)],
                     early_read)
    assert store["fr_dayahead_base|2026-10-13"]["published_time"] == "2026-10-12T12:00:00+00:00"
    A.merge_vintages(store, POWER, [A.Obs("fr_dayahead_base", date(2025, 1, 2), 90.0)], NOW)
    row = store["fr_dayahead_base|2025-01-02"]
    assert row["published_time"] == NOW.isoformat() and row["pit_quality"] == "backfill"
    pts = A.build_points(POWER, store)["fr_dayahead_base"]
    assert {p["d"]: p["pit_quality"] for p in pts}["2025-01-02"] == "backfill"


def test_each_response_is_stamped_at_its_own_fetch_time(tmp_path: Path) -> None:
    body_de, body_fr = (EC / "price_de_lu.json").read_bytes(), (EC / "price_fr.json").read_bytes()
    t1, t2 = NOW + timedelta(minutes=1), NOW + timedelta(minutes=2)
    ticks = iter([t1, t2])
    rec, store, _ = _run(Getter(_http(404), [body_de, body_fr]), tmp_path, _caught_up_sst(),
                         clock=lambda: next(ticks))
    assert rec["outcome"] == "OK"
    assert store["de_lu_dayahead_base|2026-10-13"]["first_seen_at"] == t1.isoformat()
    assert store["fr_dayahead_base|2026-10-13"]["first_seen_at"] == t2.isoformat()


# ============================================================================ pass outcomes
def test_an_empty_power_pass_is_failed_never_zero(tmp_path: Path) -> None:
    empty = json.dumps({"license_info": "CC BY 4.0 from Bundesnetzagentur | SMARD.de",
                        "unix_seconds": [], "price": []}).encode()
    rec, store, _ = _run(Getter(_http(404), [empty, empty]), tmp_path, _caught_up_sst())
    assert rec["status"] == "FAILED:EMPTY" and rec["errors"] and not store


def test_a_reread_with_nothing_new_is_unchanged(tmp_path: Path) -> None:
    body_de, body_fr = (EC / "price_de_lu.json").read_bytes(), (EC / "price_fr.json").read_bytes()
    rec, store, sst = _run(Getter(_http(404), [body_de, body_fr]), tmp_path, _caught_up_sst())
    assert rec["outcome"] == "OK"
    rec2, _, _ = _run(Getter(_http(404), [body_de, body_fr]), tmp_path, sst, store)
    assert rec2["outcome"] == "UNCHANGED" and rec2["parsed"] > 0


def test_the_cursor_walks_windows_until_tomorrow_is_served(tmp_path: Path) -> None:
    body = (EC / "price_de_lu.json").read_bytes()
    since = (NOW - timedelta(days=A.POWER_CHUNK_D + 10)).date().isoformat()
    sst = {"power_from": dict.fromkeys(A.POWER_ZONES, since)}
    g = Getter(_http(404), [body] * 4)
    rec, _, sst = _run(g, tmp_path, sst)
    assert len(g.data_urls) == 4 and rec["caught_up"] == {"DE-LU": True, "FR": True}
    tomorrow = (NOW + timedelta(days=1)).date()
    assert sst["power_from"]["FR"] == (tomorrow - timedelta(days=A.POWER_RECENT_D)).isoformat()


@pytest.mark.parametrize("code", [401, 403, 429])
def test_a_403_hard_stops_and_waits_for_a_person(code: int, tmp_path: Path) -> None:
    body = (EC / "price_de_lu.json").read_bytes()
    g = Getter(_http(404), [_http(code), body])
    rec, _, sst = _run(g, tmp_path, _caught_up_sst())
    assert rec["status"] == "FAILED:HARD_STOP" and len(g.data_urls) == 1
    hold = sst["hard_stop"]
    assert hold["released_by"] is None and "person" in hold["release"]
    assert hold["missed_growth"]["delta_elogw"] == "UNMEASURED"
    # a year later, still held: no clock releases it, nothing is asked
    g2 = Getter(_http(404), [body, body])
    rec2 = A.collect_power(A.Paths(tmp_path / "desk"), POWER, sst, {},
                           NOW + timedelta(days=400), fetch=True, fixtures=None,
                           deadline=float("inf"), getter=g2, sleep=lambda _s: None)
    assert rec2["status"] == "HELD:HARD_STOP" and g2.urls == []
    sst["hard_stop"]["released_by"] = "a person"
    rec3, _, _ = _run(Getter(_http(404), [body, (EC / "price_fr.json").read_bytes()]),
                      tmp_path, sst)
    assert rec3["outcome"] == "OK" and sst["hard_stop_released"]


def test_a_licence_change_mid_pass_is_held_for_a_person(tmp_path: Path) -> None:
    rec, store, sst = _run(Getter(_http(404), [(EC / "price_restricted.json").read_bytes()]),
                           tmp_path, _caught_up_sst())
    assert rec["status"] == "FAILED:LICENCE_CHANGED" and not store and sst["hard_stop"]


def test_robots_decides_every_power_pass(tmp_path: Path) -> None:
    g = Getter(b"User-agent: *\nDisallow: /\n", [b"{}"])
    rec, _, _ = _run(g, tmp_path)
    assert rec["status"] == "FAILED:ROBOTS_DISALLOW" and g.data_urls == []
    g = Getter(OSError("timeout"), [b"{}"])
    rec, _, _ = _run(g, tmp_path)
    assert rec["status"] == "FAILED:ROBOTS_UNREADABLE" and g.data_urls == []
    g = Getter(_http(403), [b"{}"])
    rec, _, sst = _run(g, tmp_path)
    assert rec["status"] == "FAILED:HARD_STOP" and g.data_urls == [] and sst["hard_stop"]


# ============================================================================ consumer
def test_the_power_consumer_cannot_see_a_same_day_or_unpublished_value(tmp_path: Path) -> None:
    store: dict[str, Any] = {}
    seen = datetime(2026, 10, 12, 13, tzinfo=UTC)
    A.merge_vintages(store, POWER, [A.Obs("de_lu_dayahead_base", date(2026, 10, 12), 70.0),
                                    A.Obs("de_lu_dayahead_base", date(2026, 10, 13), 95.0)],
                     seen)
    p = tmp_path / "eu_power_dayahead.json"
    p.write_text(json.dumps(store), "utf-8")
    # at 13:30 UTC on the 12th: the 13th was auctioned, but is a later period; the 12th is
    # the decision's own day -- neither is visible
    got = A.power_stress_asof(datetime(2026, 10, 12, 13, 30, tzinfo=UTC), p)
    assert got["status"] == "UNMEASURED" and got["instruments"] == {}
    got = A.power_stress_asof(datetime(2026, 10, 13, 9, tzinfo=UTC), p)
    assert got["series"]["de_lu_dayahead_base"]["period"] == "2026-10-12"
    legs = {r["series"]: r["prior_sign"] for r in got["instruments"]["GER40"]}
    assert legs == {"de_lu_dayahead_base": -1}
    assert set(got["instruments"]) == {"GER40", "EURUSD", "EURCHF", "XNGUSD"}
    assert got["style"]["style_tag"] == "novel" and got["style"]["verdict"] == "UNMEASURED"
    # a value read later than the decision is invisible even when its period is older
    late = A.series_asof("eu_power_dayahead", datetime(2026, 10, 12, 12, tzinfo=UTC), p)
    assert late["status"] == "UNMEASURED"


def test_every_mapped_instrument_is_the_ones_named() -> None:
    syms = {s for m in POWER.series_instruments.values() for s in m}
    assert syms == {"EURUSD", "EURCHF", "GER40", "FRA40", "XNGUSD"}
    assert set(SKY.instruments) == {"USDCNH", "USDTRY", "USDMXN", "USDZAR", "USDJPY"}
    assert all(A.may_mint(s) for s in syms | set(SKY.instruments))


# ============================================================================ terms
def test_the_terms_rows_exist_with_verbatim_clauses() -> None:
    assert A.TERMS["eu_power_dayahead"][0] == "confirmed" and POWER.terms == "confirmed"
    ev = A.TERMS_EVIDENCE["eu_power_dayahead"]
    assert "CC BY 4.0" in ev["terms_quote"] and ev["terms_url"].startswith("https://api.energy")
    assert "private and internal use only" in ev["restriction_quote"] and ev["credit"]
    assert "SOURCE_POLICY" in ev["register"]
    assert A.TERMS["opensky_departures"][0] == "refused" and SKY.terms == "refused"
    sk = A.TERMS_EVIDENCE["opensky_departures"]
    assert "non-profit research" in sk["terms_quote"] and "IDEAS_ONLY" in sk["judgement"]
    assert sk["missed_growth_delta_elogw"] == "UNMEASURED" and "PERSON" in sk["release"]
    assert SKY.key_env == "OPENSKY_CLIENT_ID"
    assert A.status_of(SKY) == "BLOCKED_ON_TERMS:refused"


def test_opensky_is_never_fetched_and_carries_its_hold(tmp_path: Path) -> None:
    def boom(url: str) -> tuple[bytes, str]:
        raise AssertionError(f"fetched {url}")
    rec = A.collect(A.Paths(tmp_path / "desk"), SKY, {}, NOW, fetch=True, fixtures=None,
                    deadline=float("inf"), getter=boom)
    assert rec["requests"] == 0 and rec["ideas_only"] is True
    assert rec["missed_growth"]["delta_elogw"] == "UNMEASURED" and "PERSON" in rec["release"]


# ============================================================================ the leg
def test_the_fixture_pass_writes_the_power_store_axis_and_report(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    rep = A.run(paths, fixtures=FIX, donate=False, now=NOW)
    rec = rep["sources"]["eu_power_dayahead"]
    assert rec["outcome"] == "OK" and rec["parsed"] > 0
    assert rec["series"]["de_lu_dayahead_base"] == 2 and rec["series"]["fr_dayahead_base"] == 2
    store = json.loads((paths.obs_dir / "eu_power_dayahead.json").read_text("utf-8"))
    assert all(r["published_time"] >= NOW.isoformat() for r in store.values())
    assert (paths.axes / "alt_eu_power_dayahead.json").exists()
    assert rep["sources"]["opensky_departures"]["requests"] == 0
    assert set(rep["novel_styles"]) == {"eu_power_dayahead", "opensky_departures"}
    assert json.loads(paths.report.read_text("utf-8"))["sources"]["eu_power_dayahead"]
