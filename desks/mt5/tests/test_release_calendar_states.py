"""Release calendar states: the three parsers read their saved fixtures, available_time is never
earlier than the publication, backfill is never judged, the expectation reads only prints known
before the release, every refusal (grounds, refused host, robots, stop codes, a wall) fails
closed with no data request, and every mapped symbol is in the universe registry. No network:
every request is served by a fake."""
from __future__ import annotations

import json
import sys
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import release_calendar_states as rc  # noqa: E402

FIX = DESK / "tests" / "fixtures" / "release_calendar"
ROBOTS_OK = (200, b"User-agent: *\nDisallow: /private/\n")
VERDICTS = {"CONFIRMED", "BLOCKED_ON_TERMS", "HARD_STOP", "NO_CALENDAR"}
ZERO_REGIONS = {"us", "kr", "gb", "sg", "za", "sa", "ca", "no", "mx", "il", "it", "ph", "ae",
                "ke", "pk", "nz", "eg", "cz", "hu", "ua", "bd", "lk", "co", "pe", "ea"}


# ----------------------------------------------------------------------------- parsers
def test_eurostat_fixture_parses_with_publisher_and_calendar_stamps() -> None:
    obs = rc.parse_eurostat((FIX / "eurostat_hicp.json").read_bytes(), "cpi_yoy")
    got = {(o.series, o.period): o for o in obs}
    assert got[("ea_cpi_yoy", "2026-09")].value == 2.4
    assert got[("cz_cpi_yoy", "2026-07")].value == 2.9
    assert got[("cz_cpi_yoy", "2026-09")].value == 2.6
    pub = datetime(2026, 10, 16, 9, tzinfo=UTC)
    # only the newest period of each geo carries the dataset's dissemination stamp
    assert got[("ea_cpi_yoy", "2026-09")].published == pub
    assert got[("ea_cpi_yoy", "2026-09")].planned == pub
    assert got[("ea_cpi_yoy", "2026-08")].published is None


def test_eurostat_refuses_an_unexpected_shape() -> None:
    doc = json.loads((FIX / "eurostat_hicp.json").read_text())
    doc["size"][1] = 2
    doc["dimension"]["unit"]["category"]["index"]["I15"] = 1
    with pytest.raises(rc.Refused, match="METADATA_MISMATCH"):
        rc.parse_eurostat(json.dumps(doc).encode(), "cpi_yoy")
    with pytest.raises(rc.Refused, match="UNPARSEABLE"):
        rc.parse_eurostat(b"<html>maintenance</html>", "cpi_yoy")


def test_ons_fixture_stamps_the_0700_london_release() -> None:
    obs = rc.parse_ons((FIX / "ons_d7g7.json").read_bytes(), "gb_cpi_yoy")
    assert [(o.period, o.value) for o in obs] == [("2026-07", 3.4), ("2026-08", 3.6)]
    # updateDate 2026-09-15T23:00Z is London midnight of 16 Sep; 07:00 BST is 06:00 UTC
    assert obs[1].published == datetime(2026, 9, 16, 6, tzinfo=UTC)


def test_statcan_fixture_reads_release_time_in_ottawa() -> None:
    obs = rc.parse_statcan((FIX / "statcan_wds.json").read_bytes())
    got = {(o.series, o.period): o for o in obs}
    assert got[("ca_cpi_index", "2026-09")].value == 166.4
    assert got[("ca_cpi_index", "2026-09")].published == datetime(2026, 10, 21, 12, 30,
                                                                    tzinfo=UTC)
    assert got[("ca_unemployment", "2026-09")].value == 6.9
    assert len(obs) == 3                               # the FAILED vector contributes nothing


# ------------------------------------------------------------------------ point in time
def test_stamp_is_never_earlier_than_publication() -> None:
    pub = datetime(2026, 10, 16, 9, tzinfo=UTC)
    seen = pub + timedelta(minutes=30)
    assert rc.stamp(pub, seen, None) == (seen, rc.BACKFILL)
    assert rc.stamp(pub, seen, pub - timedelta(hours=1)) == (pub, "live_publisher_stamp")
    # the previous read came after the stamp, so it does not bracket it: use when seen
    assert rc.stamp(pub, seen, pub + timedelta(minutes=10)) == (seen, "live_seen")
    # read long after the stamp: the stamp may be a date-only re-load, so use when seen
    late = pub + timedelta(hours=5)
    assert rc.stamp(pub, late, pub - timedelta(hours=1)) == (late, "live_seen")
    # a stamp in the future of the read is never used
    assert rc.stamp(seen + timedelta(hours=1), seen, pub - timedelta(hours=1))[1] == "live_seen"
    assert rc.stamp(None, seen, pub)[1] == "live_seen"


def _pt(period: str, value: float, at: str, quality: str = "live_seen") -> dict[str, Any]:
    return {"period": period, "value": value, "available_time": at, "known_at": at,
            "pit_quality": quality}


def test_expectation_reads_only_prints_known_before_the_release() -> None:
    s = [_pt("2026-07", 2.0, "2026-08-10T09:00:00+00:00"),
         _pt("2026-08", 3.0, "2026-09-30T09:00:00+00:00")]      # published LATE
    rel = datetime(2026, 9, 20, 9, tzinfo=UTC)
    # August was not yet known at the September release: no random-walk expectation
    assert rc.expectation(s, rel, "last", "2026-09") is None
    rel2 = datetime(2026, 10, 20, 9, tzinfo=UTC)
    assert rc.expectation(s, rel2, "last", "2026-09") == 3.0
    assert rc.expectation(s, rel2, "trailing_mean3", "2026-09") is None


def test_backfill_is_never_judged_but_scales_live_surprises() -> None:
    read = "2026-10-01T00:00:00+00:00"
    pts = [_pt(f"2025-{m:02d}", 2.0 + (m % 3) * 0.1, read, rc.BACKFILL) for m in range(1, 13)]
    pts += [_pt("2026-01", 2.2, read, rc.BACKFILL)]
    pts += [_pt("2026-02", 2.9, "2026-10-02T09:00:00+00:00", "live_publisher_stamp")]
    rows = rc.surprises(pts, "level")
    assert [r["period"] for r in rows] == ["2026-02"]
    r = rows[0]
    assert r["expectation"] == 2.2 and r["surprise"] == pytest.approx(0.7)
    assert r["surprise_z"] is not None
    assert r["scale_basis"]["backfill"] >= rc.SCALE_MIN and r["scale_basis"]["live"] == 0


def test_yoy_is_backfill_when_either_leg_is() -> None:
    a = _pt("2025-09", 100.0, "2026-10-01T00:00:00+00:00", rc.BACKFILL)
    b = _pt("2026-09", 103.0, "2026-10-21T12:30:00+00:00", "live_publisher_stamp")
    (y,) = rc.yoy([a, b])
    assert y["value"] == pytest.approx(3.0) and y["pit_quality"] == rc.BACKFILL


# ------------------------------------------------------------------------- the full pass
def _hicp(periods: list[str], values: dict[str, list[float]], published: str) -> bytes:
    geos = list(values)
    flat: dict[str, float] = {}
    for gi, g in enumerate(geos):
        for ti, v in enumerate(values[g]):
            flat[str(gi * len(periods) + ti)] = v
    return json.dumps({
        "id": ["freq", "unit", "coicop18", "geo", "time"],
        "size": [1, 1, 1, len(geos), len(periods)], "value": flat,
        "updated": published,
        "dimension": {"freq": {"category": {"index": {"M": 0}}},
                      "unit": {"category": {"index": {"RCH_A": 0}}},
                      "coicop18": {"category": {"index": {"TOTAL": 0}}},
                      "geo": {"category": {"index": {g: i for i, g in enumerate(geos)}}},
                      "time": {"category": {"index": {p: i for i, p in enumerate(periods)}}}},
        "extension": {"annotation": [
            {"type": "DISSEMINATION_TIMESTAMP_DATA", "date": published},
            {"type": "DISSEMINATION_TIMESTAMP_PLANNED", "date": published}]}}).encode()


def _months(n: int, end: str) -> list[str]:
    return [rc._shift_month(end, k) for k in range(n - 1, -1, -1)]


class Fake:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.robots: dict[str, tuple[int, bytes]] = {}
        self.data: dict[str, tuple[int, bytes]] = {}

    def __call__(self, url: str, data: bytes | None = None) -> tuple[int, bytes]:
        self.calls.append(url)
        parts = urllib.parse.urlsplit(url)
        if parts.path == "/robots.txt":
            return self.robots.get(parts.netloc, ROBOTS_OK)
        for key, ans in self.data.items():
            if key in url:
                return ans
        return 404, b""


def _desk(tmp_path: Path, only: str = "eurostat_hicp") -> rc.Paths:
    (tmp_path / "data" / "universe").mkdir(parents=True)
    uni = json.loads((DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    (tmp_path / "data" / "universe" / "universe.json").write_text(json.dumps(uni))
    (tmp_path / "data" / "release_calendar_grounds.json").write_text(
        (DESK / "data" / "release_calendar_grounds.json").read_text("utf-8"))
    return rc.Paths(desk=tmp_path)


def _only(monkeypatch: pytest.MonkeyPatch, rid: str) -> None:
    monkeypatch.setattr(rc, "ROUTES", {rid: rc.ROUTES[rid]})
    monkeypatch.setattr(rc, "STATES", tuple(s for s in rc.STATES if s.route == rid))


def _run(paths: rc.Paths, fake: Fake, now: datetime) -> dict[str, Any]:
    return rc.run(paths, get=fake, now=now, sleep=lambda _s: None,
                  donate=lambda _seat, cands, _n: {"donated": len(cands)})


def test_first_pass_is_backfill_and_a_new_print_is_a_live_event(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _only(monkeypatch, "eurostat_hicp")
    paths = _desk(tmp_path)
    fake = Fake()
    hist = _months(30, "2026-08")
    vals = {"EA": [2.0 + (i % 5) * 0.1 for i in range(30)],
            "CZ": [3.0 + (i % 4) * 0.2 for i in range(30)]}
    fake.data["prc_hicp_minr"] = (200, _hicp(hist, vals, "2026-09-17T11:00:00+0200"))
    t1 = datetime(2026, 10, 15, 9, tzinfo=UTC)                     # Thursday
    doc = _run(paths, fake, t1)
    assert doc["routes"]["eurostat_hicp"]["status"] == "OK"
    assert doc["routes"]["eurostat_hicp"]["store_rows"] == 60
    assert doc["clock"]["n_events"] == 0 and doc["lake"] == []       # backfill is never judged
    # the next release lands at 11:00 CEST on 16 Oct and is read at 09:30 UTC
    vals2 = {g: [*v, v[-1] + 0.9] for g, v in vals.items()}
    fake.data["prc_hicp_minr"] = (200, _hicp([*hist, "2026-09"], vals2,
                                             "2026-10-16T11:00:00+0200"))
    t2 = datetime(2026, 10, 16, 9, 30, tzinfo=UTC)
    doc = _run(paths, fake, t2)
    st = doc["states"]["ea_cpi_yoy"]
    assert st["period"] == "2026-09" and st["pit_quality"] == "live_publisher_stamp"
    assert st["available_time"] == "2026-10-16T09:00:00+00:00"
    assert st["surprise"] == pytest.approx(0.9) and st["surprise_z"] is not None
    assert st["symbols"] == ["EURUSD"] and st["priors"] == {"EURUSD": 1}
    assert doc["states"]["cz_cpi_yoy"]["priors"] == {"EURCZK": -1, "USDCZK": -1}
    clock = json.loads(paths.clock.read_text())
    assert clock["n_events"] == 2
    assert all(e["at"] >= "2026-10-16T09:00:00+00:00" for e in clock["events"])
    lake = (paths.series / "rcs_ea_cpi_yoy.csv").read_text()
    assert "live_publisher_stamp" in lake and "backfill" not in lake
    # below MIN_LIVE_RELEASES: no cell, a missed-growth line
    assert doc["cells"]["grid"] == 0 and "missed_growth" in st
    # re-reading the same answer appends nothing
    n = len((paths.store / "eurostat_hicp.jsonl").read_text().splitlines())
    _run(paths, fake, t2 + timedelta(hours=1))
    assert len((paths.store / "eurostat_hicp.jsonl").read_text().splitlines()) == n


@pytest.mark.parametrize("code", [401, 403, 429, 451])
def test_stop_codes_hard_stop_the_route(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                        code: int) -> None:
    _only(monkeypatch, "eurostat_hicp")
    paths = _desk(tmp_path)
    fake = Fake()
    fake.data["prc_hicp_minr"] = (code, b"")
    now = datetime(2026, 10, 16, 9, tzinfo=UTC)
    doc = _run(paths, fake, now)
    assert doc["routes"]["eurostat_hicp"]["status"] == "HARD_STOP"
    assert "eurostat_hicp" in doc["missed_growth"]
    before = len(fake.calls)
    doc = _run(paths, fake, now + timedelta(hours=2))
    assert doc["routes"]["eurostat_hicp"]["status"] == "HARD_STOP"
    assert len(fake.calls) == before                                # nothing requested
    held = json.loads(paths.state.read_text())["routes"]["eurostat_hicp"]["hard_stop"]
    assert (held["until"] is None) == (code == 451)


def test_a_wall_is_a_permanent_hard_stop(tmp_path: Path,
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    _only(monkeypatch, "eurostat_hicp")
    paths = _desk(tmp_path)
    fake = Fake()
    fake.data["prc_hicp_minr"] = (200, b"<html><script src='/_Incapsula_Resource'></script>")
    doc = _run(paths, fake, datetime(2026, 10, 16, 9, tzinfo=UTC))
    assert doc["routes"]["eurostat_hicp"]["why"].startswith("HARD_STOP:WALL")
    held = json.loads(paths.state.read_text())["routes"]["eurostat_hicp"]["hard_stop"]
    assert held["until"] is None


def test_robots_refusal_makes_no_data_request(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    _only(monkeypatch, "eurostat_hicp")
    paths = _desk(tmp_path)
    fake = Fake()
    fake.robots["ec.europa.eu"] = (200, b"User-agent: *\nDisallow: /eurostat/api/\n")
    fake.data["prc_hicp_minr"] = (200, b"{}")
    doc = _run(paths, fake, datetime(2026, 10, 16, 9, tzinfo=UTC))
    assert doc["routes"]["eurostat_hicp"]["status"] == "ROBOTS_REFUSED"
    assert all(urllib.parse.urlsplit(u).path == "/robots.txt" for u in fake.calls)
    fake2 = Fake()
    fake2.robots["ec.europa.eu"] = (200, b"<html>not robots</html>")
    paths2 = _desk(tmp_path / "b")
    doc = _run(paths2, fake2, datetime(2026, 10, 16, 9, tzinfo=UTC))
    assert doc["routes"]["eurostat_hicp"]["status"] == "ROBOTS_REFUSED"


def test_grounds_refusal_makes_no_request_at_all(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    _only(monkeypatch, "eurostat_hicp")
    paths = _desk(tmp_path)
    doc = json.loads(paths.grounds.read_text())
    for r in doc["regions"]:
        if r["region"] == "cz":
            r["verdict"] = "BLOCKED_ON_TERMS"
    paths.grounds.write_text(json.dumps(doc))
    fake = Fake()
    out = _run(paths, fake, datetime(2026, 10, 16, 9, tzinfo=UTC))
    assert out["routes"]["eurostat_hicp"]["status"] == "BLOCKED_ON_TERMS"
    assert fake.calls == []
    paths.grounds.unlink()                                  # no grounds file: unread terms
    out = _run(paths, fake, datetime(2026, 10, 16, 9, tzinfo=UTC))
    assert out["routes"]["eurostat_hicp"]["status"] == "BLOCKED_ON_TERMS"
    assert fake.calls == []


def test_refused_host_is_never_contacted(monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.data import refused_hosts
    monkeypatch.setitem(refused_hosts.REFUSED_HOSTS, "europa.eu", "test refusal")
    fake = Fake()
    client = rc.Client(fake, sleep=lambda _s: None)
    grounds = rc.load_grounds()
    route = rc.ROUTES["eurostat_hicp"]
    why = rc.access_refusal(route, route.url(datetime(2026, 10, 16, tzinfo=UTC)), client, grounds)
    assert why is not None and why.startswith("BLOCKED_ON_TERMS")
    assert fake.calls == []


def test_statcan_route_posts_and_parses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _only(monkeypatch, "statcan_wds")
    paths = _desk(tmp_path)
    seen: list[bytes | None] = []

    def get(url: str, data: bytes | None = None) -> tuple[int, bytes]:
        if url.endswith("/robots.txt"):
            return ROBOTS_OK
        seen.append(data)
        return 200, (FIX / "statcan_wds.json").read_bytes()

    doc = rc.run(paths, get=get, now=datetime(2026, 10, 21, 13, tzinfo=UTC),
                 sleep=lambda _s: None, donate=lambda *_a: {"donated": 0})
    assert doc["routes"]["statcan_wds"]["status"] == "OK"
    assert seen and json.loads(seen[0] or b"[]")[0]["vectorId"] == 41690973


# --------------------------------------------------------------- grounds and the mapping
def test_grounds_cover_every_zero_region_with_a_known_verdict() -> None:
    g = rc.load_grounds()
    assert set(g) == ZERO_REGIONS
    for region, row in g.items():
        assert row["verdict"] in VERDICTS, region
        if row["verdict"] == "CONFIRMED":
            assert row["terms_url"] and row["terms_quote"], region
        if row["built"]:
            assert row["verdict"] == "CONFIRMED", region


def test_routes_serve_only_built_regions() -> None:
    g = rc.load_grounds()
    served = {r for route in rc.ROUTES.values() for r in route.regions}
    assert served == {r for r, row in g.items() if row["built"]}
    assert all(rc.region_refusal(route.regions, g) is None for route in rc.ROUTES.values())


def test_every_mapped_symbol_is_in_the_universe_registry() -> None:
    uni = json.loads((DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    g = rc.load_grounds()
    for s in rc.STATES:
        assert s.priors, s.name
        for sym, sign in s.priors.items():
            assert sym in uni, sym
            assert sign in (1, -1)
            assert sym in g[s.region]["symbols"], (s.region, sym)
    for row in g.values():
        for sym in row["symbols"]:
            assert sym in uni, sym


def test_family_is_registered() -> None:
    import axis_registry
    assert rc.FAMILY in axis_registry.registered_families()
