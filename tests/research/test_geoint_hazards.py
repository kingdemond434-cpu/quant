"""GEOINT hazards (N3 natural-hazard shocks, N4 chokepoint transit) and the leg join: fixtures."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research.alt_proxies as A  # noqa: E402
import research.geoint_hazards as G  # noqa: E402
from mt5desk import family_hazard_shock as H  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "geoint_hazards"
NOW = datetime(2026, 10, 14, 1, 0, tzinfo=UTC)


def _run(tmp: Path, **kw: object) -> dict:
    return G.run(
        fixtures=FIX,
        now=NOW,
        report=tmp / "GEOINT_HAZARDS.json",
        state_path=tmp / "state.json",
        series_dir=tmp / "series",
        style_novelty_path=tmp / "absent.json",
        **kw,
    )  # type: ignore[arg-type]


def test_usgs_keeps_m6_quakes_inside_the_declared_boxes_only() -> None:
    rows = G.parse_usgs((FIX / "usgs_4.5_day.geojson").read_bytes(), NOW)
    assert sorted((r["kind"], r["magnitude"]) for r in rows) == [
        ("quake_cl", 7.1),
        ("quake_jp", 6.4),
    ]
    jp = next(r for r in rows if r["kind"] == "quake_jp")
    origin = datetime.fromisoformat(jp["event_time"])
    assert datetime.fromisoformat(jp["available_time"]) == origin + G.PUBLICATION_SLACK


def test_a_gulf_cone_is_an_event_at_its_advisory_issuance_and_an_open_ocean_cone_is_not() -> None:
    storms = {
        s["id"]: s for s in G.parse_nhc_current((FIX / "nhc_current_storms.json").read_bytes())
    }
    assert set(storms) == {"al052026", "al062026"}  # the EP storm is not Atlantic
    gulf = G.storm_event(storms["al052026"], (FIX / "nhc_cone_al052026.kmz").read_bytes(), NOW)
    assert gulf is not None and gulf["kind"] == "storm_gulf"
    assert gulf["available_time"] == "2026-10-13T21:00:00+00:00"
    assert (
        G.storm_event(storms["al062026"], (FIX / "nhc_cone_al062026.kmz").read_bytes(), NOW) is None
    )


def test_the_leg_writes_the_lake_frame_terms_cells_and_novelty(tmp_path: Path) -> None:
    doc = _run(tmp_path, donate=False)
    assert doc["N3"]["events_by_kind"] == {
        "quake_jp": 2,
        "quake_tw": 0,
        "quake_cl": 1,
        "storm_gulf": 1,
    }
    frame = pd.read_csv(tmp_path / "series" / G.SERIES_FILE)
    assert set(frame["kind"]) == {"quake_jp", "quake_cl", "storm_gulf"}
    assert {"available_time", "event_time", "first_seen_at"} <= set(frame.columns)
    on_disk = json.loads((tmp_path / "GEOINT_HAZARDS.json").read_text("utf-8"))
    assert on_disk["terms"]["usgs_earthquakes"]["verdict"] == "CONFIRMED"
    assert "programatic interface" in on_disk["terms"]["usgs_earthquakes"]["automation_quote"]
    assert on_disk["N3"]["n_cells"] == 8 * 8 and on_disk["N3"]["n_donatable"] == 0
    assert on_disk["N3"]["trials_charged_here"] == 0
    assert {v["verdict"] for v in on_disk["novelty"]["lanes"].values()} == {"UNMEASURED"}
    assert set(on_disk["novelty"]["lanes"]) == {"N3", "N4"}
    assert on_disk["geoint_sources"]["copernicus_s5p"]["status"] == "NEEDS_KEY"
    assert on_disk["geoint_sources"]["copernicus_s5p"]["cdsapi_key_grants_cdse"] == "NO"
    assert on_disk["N4"]["terms"] == "confirmed"


def test_a_second_pass_does_not_duplicate_events(tmp_path: Path) -> None:
    _run(tmp_path, donate=False)
    doc = _run(tmp_path, donate=False)
    assert doc["N3"]["n_events"] == 4 and doc["collect"]["added"] == 0


def test_a_held_or_failing_source_is_named_not_zeroed(tmp_path: Path) -> None:
    def boom(url: str) -> bytes:
        raise OSError("refused")

    store: dict = {}
    rec = G.collect(store, {}, NOW, fetch=True, fixtures=None, deadline=1e18, getter=boom)
    assert rec["requests"] >= 2 and rec["errors"] and store == {}


# ------------------------------------------------------------------------------ PIT magnitude
def _pit_rows() -> dict[str, dict]:
    rows = G.parse_quakeml((FIX / "quakeml_pit_cases.xml").read_bytes(), NOW)
    assert rows is not None
    return {r["event_id"]: r for r in rows}


def test_fdsn_backfill_asks_for_every_magnitude_below_the_line() -> None:
    url = G.fdsn_url("quake_jp", "2011-01-01", "2012-01-01")
    assert "includeallmagnitudes=true" in url and "format=xml" in url
    assert f"minmagnitude={G.BACKFILL_QUERY_MIN}" in url and G.BACKFILL_QUERY_MIN < G.MIN_MAGNITUDE


def test_an_upgraded_quake_is_not_in_the_set_before_its_upgrade() -> None:
    rows = _pit_rows()
    up = rows["usgs:usup0001"]
    assert up["pit_basis"] == "upgrade_creation_time" and up["first_sighting_magnitude"] == 5.8
    upgrade = datetime(2024, 4, 3, 3, 0, tzinfo=UTC)
    assert datetime.fromisoformat(up["available_time"]) == upgrade
    origin_plus_slack = datetime.fromisoformat(up["event_time"]) + G.PUBLICATION_SLACK
    assert "usgs:usup0001" not in G.members_as_of(rows, origin_plus_slack)
    assert "usgs:usup0001" not in G.members_as_of(rows, upgrade - timedelta(seconds=1))
    assert "usgs:usup0001" in G.members_as_of(rows, upgrade)


def test_a_downgraded_quake_keeps_its_first_sighting_membership() -> None:
    rows = _pit_rows()
    dn = rows["usgs:usdn0001"]  # reviewed 5.7 today: v1 dropped it entirely
    assert dn["reviewed_magnitude"] == 5.7 and dn["magnitude"] == 6.1
    assert dn["pit_basis"] == "first_sighting_creation_time"
    assert dn["available_time"] == "2024-01-01T08:10:00+00:00"  # 07:30 sighting, origin+slack
    assert "usgs:usdn0001" in G.members_as_of(rows, datetime(2024, 6, 1, tzinfo=UTC))


def test_a_missing_creation_time_uses_the_magnitude_margin() -> None:
    rows = _pit_rows()
    assert "usgs:usnt0001" not in rows  # M6.1, no creationTime: inside the margin
    nt = rows["usgs:usnt0002"]  # M6.6 >= MARGIN_MAGNITUDE
    assert nt["pit_basis"] == "margin" and G.MARGIN_MAGNITUDE == 6.3
    assert (
        datetime.fromisoformat(nt["available_time"])
        == datetime.fromisoformat(nt["event_time"]) + G.PUBLICATION_SLACK
    )
    assert "usgs:usob0001" not in rows  # outside every box
    assert G.parse_quakeml(b"<not xml", NOW) is None  # unparsable is None, never "no quakes"


def test_a_sighting_is_never_stamped_before_origin_plus_slack() -> None:
    mb = _pit_rows()["usgs:usmb0001"]  # own mb 6.0 created at origin + 12 min
    assert mb["pit_basis"] == "first_sighting_creation_time"
    assert (
        datetime.fromisoformat(mb["available_time"])
        == datetime.fromisoformat(mb["event_time"]) + G.PUBLICATION_SLACK
    )


def test_only_the_event_sources_own_magnitudes_time_an_entry() -> None:
    rows = _pit_rows()
    assert "usgs:usfa0001" not in rows  # JMA Ml 6.1 beside us Mww 5.8: never
    mb = rows["usgs:usmb0001"]  # own mb 6.0 later revised to Mww 5.8
    assert mb["magnitude_type"] == "mb" and mb["preferred_type"] == "Mww"
    assert mb["non_preferred_type"] is True


def test_a_sub_six_timed_sighting_with_an_untimed_margin_magnitude_takes_the_margin() -> None:
    mx = _pit_rows()["usgs:usmx0001"]
    assert mx["pit_basis"] == "margin" and mx["magnitude"] == 6.5


def test_a_late_foreign_preferred_magnitude_enters_by_margin_no_earlier_than_its_creation() -> None:
    lf = _pit_rows()["usgs:uslf0001"]  # own 5.9 at +5m; JMA 6.5 created at +2d
    assert lf["pit_basis"] == "margin" and lf["magnitude"] == 6.5
    assert lf["available_time"] == "2024-08-10T07:42:00+00:00"


def _live(mag: float, updated: datetime, eid: str = "us7000live") -> bytes:
    origin = datetime(2026, 10, 13, 22, 0, tzinfo=UTC)
    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": eid,
                    "properties": {
                        "mag": mag,
                        "time": int(origin.timestamp() * 1000),
                        "updated": int(updated.timestamp() * 1000),
                        "type": "earthquake",
                    },
                    "geometry": {"type": "Point", "coordinates": [142.3, 38.1, 10.0]},
                }
            ],
        }
    ).encode()


def test_live_feed_records_the_first_sighting_and_never_revises_membership() -> None:
    store: dict = {}
    sightings: dict = {}
    t1 = datetime(2026, 10, 13, 22, 20, tzinfo=UTC)
    G.merge(store, G.parse_usgs(_live(5.8, t1), t1 + timedelta(minutes=5), sightings))
    assert store == {} and sightings["usgs:us7000live"]["first_magnitude"] == 5.8
    t2 = datetime(2026, 10, 14, 2, 0, tzinfo=UTC)  # upgraded to 6.2 at t2
    G.merge(store, G.parse_usgs(_live(6.2, t2), t2 + timedelta(minutes=30), sightings))
    row = store["usgs:us7000live"]
    assert row["available_time"] == t2.isoformat() and row["first_sighting_magnitude"] == 5.8
    assert "usgs:us7000live" not in G.members_as_of(store, t2 - timedelta(seconds=1))
    assert sightings["usgs:us7000live"]["first_magnitude"] == 5.8  # never revised

    store2: dict = {}
    sightings2: dict = {}
    G.merge(store2, G.parse_usgs(_live(6.1, t1, "us7000dn"), t1, sightings2))
    G.merge(store2, G.parse_usgs(_live(5.7, t2, "us7000dn"), t2, sightings2))  # downgraded
    assert store2["usgs:us7000dn"]["magnitude"] == 6.1  # membership kept


def test_v1_state_with_reviewed_magnitude_rows_is_migrated() -> None:
    state = {
        "events": {
            "usgs:old": {"source_id": "usgs_earthquakes", "pit_basis": "origin+publication_slack"},
            "nhc:al01": {"source_id": "nhc_current_storms", "pit_basis": "advisory_issuance"},
        },
        "backfilled": {"quake_jp": "2026-10-14"},
    }
    assert G.migrate(state) == 1
    assert set(state["events"]) == {"nhc:al01"} and "backfilled" not in state
    assert G.migrate(state) == 0


# ------------------------------------------------------------------------------ donation, fixtures
def test_cells_are_donated_once_per_identity_including_rolled_up_contracts(tmp_path: Path) -> None:
    import gzip

    cells = G.n3_cells({}, NOW)[:4]
    sent: list[list[dict]] = []

    def fake(source: str, rows: list[dict], tests_run: int) -> Path:
        sent.append(rows)
        seat = tmp_path / source
        seat.mkdir(exist_ok=True)
        out = seat / f"discoveries_{len(sent)}.json"
        out.write_text(json.dumps({"discoveries": rows}), "utf-8")
        return out

    first = G.donate_new(cells, intel=tmp_path, donate_fn=fake)
    assert first["donated"] == 4 and first["already_donated"] == 0
    again = G.donate_new(cells, intel=tmp_path, donate_fn=fake)
    assert again == {"donated": 0, "already_donated": 4} and len(sent) == 1
    # disk_guard rolls aged contracts into rollup_<day>.jsonl.gz: still donated.
    (tmp_path / G.SOURCE / "discoveries_1.json").unlink()
    with gzip.open(tmp_path / G.SOURCE / "rollup_20261014.jsonl.gz", "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({"discoveries": cells[:3]}) + "\n")
    third = G.donate_new(cells, intel=tmp_path, donate_fn=fake)
    assert third["donated"] == 1 and sent[-1] == [cells[3]]


def test_fixtures_never_write_into_production(tmp_path: Path) -> None:
    with pytest.raises(G.FixturesIntoProduction):
        G.run(fixtures=FIX, now=NOW, style_novelty_path=tmp_path / "absent.json")
    assert G.main(["--once", "--fixtures", str(FIX)]) == 2
    assert G.main(["--once", "--fixtures", str(FIX), "--out", str(tmp_path)]) == 0
    assert (tmp_path / G.REPORT.name).exists() and (tmp_path / "state.json").exists()


# ------------------------------------------------------------------------------ the family
def _bars(start: datetime, n: int, drift: float = 0.0) -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq="h", tz="UTC")
    c = 150.0 + drift * np.arange(n)
    return pd.DataFrame({"open": c, "high": c + 0.2, "low": c - 0.2, "close": c}, index=idx)


def _frame(tmp: Path, at: datetime, kind: str = "quake_jp") -> Path:
    d = tmp / "series"
    d.mkdir(exist_ok=True)
    pd.DataFrame(
        [{"event_id": "e1", "kind": kind, "magnitude": 6.5, "available_time": at.isoformat()}]
    ).to_csv(d / f"{H.SERIES_ID}.csv", index=False)
    H._CACHE.clear()
    return d


def test_drift_enters_on_the_first_bar_opening_after_the_notice(tmp_path: Path) -> None:
    start = datetime(2026, 3, 1, tzinfo=UTC)
    notice = start + timedelta(hours=40, minutes=20)
    root = _frame(tmp_path, notice)
    sigs = H.family_hazard_shock(
        _bars(start, 120), symbol="USDJPY", kind="quake_jp", prior_side=-1, series_root=root
    )
    assert len(sigs) == 1 and sigs[0].side == -1
    assert sigs[0].time == pd.Timestamp(start + timedelta(hours=41))  # never the bar holding it


def test_fade_trades_against_the_move_since_the_notice(tmp_path: Path) -> None:
    start = datetime(2026, 3, 1, tzinfo=UTC)
    root = _frame(tmp_path, start + timedelta(hours=40))
    sigs = H.family_hazard_shock(
        _bars(start, 120, drift=0.05),
        symbol="USDJPY",
        kind="quake_jp",
        mode="fade",
        series_root=root,
    )
    assert len(sigs) == 1 and sigs[0].side == -1  # price rose -> fade short


def test_hazard_family_refuses_without_its_frame_or_its_kind(tmp_path: Path) -> None:
    bars = _bars(datetime(2026, 3, 1, tzinfo=UTC), 120)
    H._CACHE.clear()
    assert H.family_hazard_shock(bars, symbol="USDJPY", kind="quake_jp", series_root=tmp_path) == []
    root = _frame(tmp_path, datetime(2026, 3, 2, tzinfo=UTC))
    assert H.family_hazard_shock(bars, symbol="USDJPY", kind="quake_tw", series_root=root) == []
    assert H.family_hazard_shock(bars, symbol="USDJPY", kind="volcano", series_root=root) == []


def test_hazard_family_is_registered() -> None:
    from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES
    from research.axis_registry import FAMILY_TABLE

    assert ORTHOGONAL_FAMILIES["hazard_shock"] is H.family_hazard_shock
    assert FAMILY_TABLE["hazard_shock"] == ("volatility_shock", "event", "market")


# ------------------------------------------------------------------------------ N4 and wiring
def test_chokepoint_transits_now_map_to_oil_gold_and_usdjpy() -> None:
    src = A.BY_ID["imf_portwatch_chokepoints"]
    assert set(src.instruments) == {"XTIUSD", "XBRUSD", "XAUUSD", "USDJPY"}
    assert src.terms == "confirmed" and "commercial" in A.TERMS_EVIDENCE[src.id]["terms_quote"]
    assert "suez_canal_transits" in src.signal_series


def test_alt_proxies_and_geoint_ride_a_department_that_reaches_the_tail() -> None:
    import hourly_cycle as hc

    assert hc.department_of("alt_proxies") == "intel"
    assert hc.department_of("geoint_hazards") == "intel"
    assert hc.LEG_BUDGET_SEC["geoint_hazards"] >= 120
    from libs.research.layers import LEG_LAYER

    assert LEG_LAYER["geoint_hazards"] == "information"


@pytest.mark.parametrize(
    "sid", ["cn_firms_industrial", "imf_portwatch_ports", "imf_portwatch_chokepoints"]
)
def test_geoint_series_sources_are_confirmed_and_on_the_alt_proxies_clock(sid: str) -> None:
    src = A.BY_ID[sid]
    assert src.terms == "confirmed"
    status = A.status_of(src, environ={"FIRMS_MAP_KEY": "x"})
    assert status == "UNMEASURED_LIVE_YIELD"


def test_http_get_fails_closed_when_robots_cannot_be_read_or_disallow(monkeypatch) -> None:
    """robots_gate: an unreadable robots.txt is a refusal, and a Disallow stops the fetch before
    any request to the data URL is made."""
    import urllib.robotparser

    gh = G
    calls: list[str] = []

    def _no_request(*a, **k):
        calls.append("data")
        raise AssertionError("a data request went out past the robots gate")

    monkeypatch.setattr(gh.urllib.request, "urlopen", _no_request)
    host = "https://earthquake.usgs.gov"
    monkeypatch.setattr(gh, "_ROBOTS", {host: "robots.txt unreadable (URLError)"})
    with pytest.raises(gh.RobotsRefused):
        gh.http_get(gh.USGS_LIVE)
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(["User-agent: *", "Disallow: /"])
    monkeypatch.setattr(gh, "_ROBOTS", {host: rp})
    with pytest.raises(gh.RobotsRefused):
        gh.http_get(gh.USGS_LIVE)
    assert calls == []
    allow = urllib.robotparser.RobotFileParser()
    allow.parse([])
    monkeypatch.setattr(gh, "_ROBOTS", {host: allow})
    assert gh.robots_refusal(gh.USGS_LIVE) is None


def test_a_redirect_hop_is_fenced_again_before_it_is_followed(monkeypatch) -> None:
    """Auditor SF1 on #1241: an allowed host's 30x into a refused path is never followed."""
    import urllib.robotparser
    allow = urllib.robotparser.RobotFileParser()
    allow.parse([])
    deny = urllib.robotparser.RobotFileParser()
    deny.parse(["User-agent: *", "Disallow: /"])
    monkeypatch.setattr(G, "_ROBOTS", {"https://earthquake.usgs.gov": allow,
                                       "https://elsewhere.example": deny})
    h = G._FencedRedirect()
    req = G.urllib.request.Request(G.USGS_LIVE)
    with pytest.raises(G.RobotsRefused):
        h.redirect_request(req, None, 302, "Found", {}, "https://elsewhere.example/x")
    ok = h.redirect_request(req, None, 302, "Found", {}, "https://earthquake.usgs.gov/other")
    assert ok is not None and ok.full_url == "https://earthquake.usgs.gov/other"
