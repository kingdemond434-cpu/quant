"""EIA-930 grid demand surprise: the metadata check fails closed, robots and the stop codes halt
the pass, the surprise / z / trigger math, the idempotent point-in-time store, the lake series the
family loads, and the cells it mints. No network: every request is served by a synthetic fake."""
from __future__ import annotations

import json
import math
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

from research import eia930_grid as eg  # noqa: E402

SENTINEL = "SENTINEL-EIA-KEY-0xC0FFEE"
ENV = {"EIA_API_KEY": SENTINEL}
T0 = datetime(2026, 11, 17, 12, tzinfo=UTC)
REGIONS = ("US48", "TEX", "CAL")


class FakeEIA:
    """Serves robots.txt, the v2 metadata and paged region-data rows for hours before `now`."""

    def __init__(self, now: datetime, *, spike: tuple[str, datetime, float] | None = None,
                 robots: tuple[int, bytes] = (200, b"User-agent: *\nAllow: /\n"),
                 child: str = "region-data", df_name: str = "Day-ahead demand forecast",
                 stop: int | None = None) -> None:
        self.now, self.spike, self.robots, self.child = now, spike, robots, child
        self.df_name, self.stop = df_name, stop
        self.urls: list[str] = []

    def keyed(self) -> list[str]:
        return [u for u in self.urls if not u.endswith("/robots.txt")]

    def _rows(self) -> list[dict[str, Any]]:
        start = T0 - timedelta(days=eg.BACKFILL_DAYS + 2)
        rows: list[dict[str, Any]] = []
        for ri, reg in enumerate(REGIONS):
            h = start
            i = 0
            while h <= self.now - timedelta(hours=2):
                df = 1000.0 * (ri + 1)
                d = df * (1 + 0.02 * math.sin(i * 0.7 + ri))
                if self.spike and self.spike[0] == reg and self.spike[1] == h:
                    d = df * (1 + self.spike[2])
                p = h.strftime("%Y-%m-%dT%H")
                rows.append({"period": p, "respondent": reg, "type": "D", "value": round(d, 3)})
                rows.append({"period": p, "respondent": reg, "type": "DF", "value": df})
                h += timedelta(hours=1)
                i += 1
            # a forecast for the hour still ahead: no actual yet, so no surprise
            rows.append({"period": (self.now + timedelta(hours=3)).strftime("%Y-%m-%dT%H"),
                         "respondent": reg, "type": "DF", "value": 1.0})
        return rows

    def __call__(self, url: str) -> tuple[int, bytes]:
        self.urls.append(url)
        parts = urllib.parse.urlsplit(url)
        if parts.path == "/robots.txt":
            return self.robots
        q = urllib.parse.parse_qs(parts.query)
        assert q.get("api_key") == [SENTINEL]
        path = parts.path.removeprefix("/v2/").strip("/")
        if self.stop:
            return self.stop, b""
        if path == "electricity/rto":
            resp: dict[str, Any] = {"routes": [{"id": self.child, "name": "Hourly demand"},
                                               {"id": "fuel-type-data", "name": "fuel"}]}
        elif path == "electricity/rto/region-data":
            resp = {"frequency": [{"id": "hourly"}, {"id": "local-hourly"}],
                    "facets": [{"id": "respondent"}, {"id": "type"}],
                    "data": {"value": {"units": "megawatthours"}}}
        elif path == "electricity/rto/region-data/facet/type":
            resp = {"facets": [{"id": "D", "name": "Demand"},
                               {"id": "DF", "name": self.df_name},
                               {"id": "NG", "name": "Net generation"}]}
        elif path == "electricity/rto/region-data/facet/respondent":
            resp = {"facets": [{"id": r, "name": r} for r in (*REGIONS, "ERCO")]}
        elif path == "electricity/rto/region-data/data":
            want = set(q.get("facets[respondent][]", []))
            start = eg.parse_period(q["start"][0])
            assert start is not None
            rows = [r for r in self._rows() if r["respondent"] in want
                    and (eg.parse_period(r["period"]) or start) >= start]
            rows.sort(key=lambda r: r["period"], reverse=True)
            off, ln = int(q["offset"][0]), int(q["length"][0])
            resp = {"total": str(len(rows)), "data": rows[off:off + ln]}
        else:
            return 404, b""
        return 200, json.dumps({"response": resp, "request": {"params": {
            "api_key": SENTINEL}}}).encode()


def _paths(tmp_path: Path) -> eg.Paths:
    (tmp_path / "data" / "universe").mkdir(parents=True)
    uni = {s: {"asset_class": "Energy" if s == "XNGUSD" else "Indices"}
           for s in ("XNGUSD", "US500", "US30", "NAS100", "US2000")}
    (tmp_path / "data" / "universe" / "universe.json").write_text(json.dumps(uni), "utf-8")
    return eg.Paths(desk=tmp_path)


def _run(paths: eg.Paths, fake: FakeEIA, now: datetime, minted: list[Any] | None = None,
         env: dict[str, str] | None = None) -> dict[str, Any]:
    def donate(seat: str, cands: list[dict[str, Any]], n: int) -> dict[str, Any]:
        if minted is not None:
            minted.extend(cands)
        return {"donated": len(cands)}
    return eg.run(paths, get=fake, now=now, environ=ENV if env is None else env,
                  sleep=lambda _s: None, donate=donate)


def _no_key_anywhere(paths: eg.Paths) -> None:
    for f in paths.desk.rglob("*"):
        if f.is_file():
            assert SENTINEL not in f.read_text("utf-8", errors="replace"), f


# ------------------------------------------------------------------------- fail closed ----
def test_missing_child_route_fails_closed_before_any_data_request(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    fake = FakeEIA(T0, child="something-else")
    doc = _run(paths, fake, T0)
    assert doc["status"] == "METADATA_MISMATCH"
    assert "region-data" in doc["fetch"]["why"]
    assert not any("/data/?" in u for u in fake.urls)
    assert doc["store_rows"] == 0 and not paths.obs.exists()
    assert doc["fetch"]["missed_growth"]
    assert "metadata" not in json.loads(paths.state.read_text("utf-8"))
    _no_key_anywhere(paths)


def test_forecast_facet_that_is_not_a_forecast_fails_closed(tmp_path: Path) -> None:
    doc = _run(_paths(tmp_path), FakeEIA(T0, df_name="Net generation"), T0)
    assert doc["status"] == "METADATA_MISMATCH"
    assert "DF" in doc["fetch"]["why"]


def test_data_row_without_expected_fields_is_a_mismatch() -> None:
    with pytest.raises(eg.Refused, match="METADATA_MISMATCH"):
        eg.parse_rows([{"period": "2026-11-17T05", "respondent": "US48", "value": 1.0}])
    with pytest.raises(eg.Refused, match="not hourly"):
        eg.parse_rows([{"period": "2026-11-17", "respondent": "US48", "type": "D",
                        "value": 1.0}])
    assert eg.parse_rows([{"period": "2026-11-17T05", "respondent": "US48", "type": "D",
                           "value": None}]) == []


@pytest.mark.parametrize("robots,refused", [
    ((200, b"User-agent: *\nDisallow: /v2/\n"), True),
    ((500, b""), True),
    ((200, b"<!DOCTYPE html><html></html>"), True),
    ((404, b""), False),
])
def test_robots_gate_refuses_before_any_keyed_request(tmp_path: Path, robots: tuple[int, bytes],
                                                      refused: bool) -> None:
    fake = FakeEIA(T0, robots=robots)
    doc = _run(_paths(tmp_path), fake, T0)
    if refused:
        assert doc["status"] == "ROBOTS_REFUSED"
        assert fake.keyed() == []
    else:
        assert doc["status"] == "OK"


def test_terms_switch_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(eg.TERMS_EVIDENCE, "machine_use_allowed", False)
    fake = FakeEIA(T0)
    doc = _run(_paths(tmp_path), fake, T0)
    assert doc["status"] == "BLOCKED_ON_TERMS" and fake.urls == []


def test_missing_key_is_blocked_auth(tmp_path: Path) -> None:
    fake = FakeEIA(T0)
    doc = _run(_paths(tmp_path), fake, T0, env={})
    assert doc["fetch"]["why"] == "BLOCKED_AUTH:EIA_API_KEY"
    assert fake.keyed() == []


@pytest.mark.parametrize("code", [401, 403, 429, 451])
def test_stop_codes_halt_the_pass_and_hold(tmp_path: Path, code: int) -> None:
    paths = _paths(tmp_path)
    fake = FakeEIA(T0, stop=code)
    doc = _run(paths, fake, T0)
    assert doc["status"] == "HARD_STOP"
    assert len(fake.keyed()) == 1                       # the first stop code ends the pass
    held = json.loads(paths.state.read_text("utf-8"))["hard_stop"]
    assert held["code"] == code
    # the next pass makes no request at all while the stop holds
    again = FakeEIA(T0 + timedelta(hours=1))
    doc = _run(paths, again, T0 + timedelta(hours=1))
    assert doc["status"] == "HARD_STOP" and again.urls == []
    later = FakeEIA(T0 + timedelta(hours=eg.HARD_STOP_H + 1))
    doc = _run(paths, later, T0 + timedelta(hours=eg.HARD_STOP_H + 1))
    if code == 451:
        assert held["until"] is None and later.urls == []       # a legal block needs a person
    else:
        assert doc["status"] == "OK"


def test_throttle_spaces_requests_and_bounds_the_pass() -> None:
    slept: list[float] = []
    c = eg.Client(lambda _u: (200, b'{"response": {}}'), SENTINEL, sleep=slept.append,
                  max_requests=3, min_interval_s=5.0)
    for _ in range(3):
        c.json("electricity/rto")
    assert len(slept) == 2 and all(0 < s <= 5.0 for s in slept)
    with pytest.raises(eg.Refused, match="BUDGET"):
        c.json("electricity/rto")


# ---------------------------------------------------------------------------- the math ----
def test_surprise_and_zscore() -> None:
    assert eg.surprise(1100.0, 1000.0) == pytest.approx(0.1)
    assert eg.surprise(900.0, 1000.0) == pytest.approx(-0.1)
    assert eg.surprise(900.0, 0.0) is None
    prior = [0.0, 1.0] * 100
    assert eg.zscore(prior[:10], 3.0) is None                     # below Z_MIN_H
    assert eg.zscore(prior, 1.5) == pytest.approx(2.0)            # mean .5, sd .5
    assert eg.zscore([0.2] * 200, 0.3) is None                    # zero sd: no z, never 0
    # the window is the trailing Z_WINDOW_H only
    long = [100.0] * 50 + [0.0, 1.0] * eg.Z_WINDOW_H
    assert eg.zscore(long, 1.5) == pytest.approx(2.0)


def test_z_uses_strictly_earlier_hours_only() -> None:
    store: dict[str, dict[str, Any]] = {}
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(eg.Z_MIN_H + 1):
        p = eg._iso(base + timedelta(hours=i))
        d = 1010.0 if i % 2 else 990.0
        if i == eg.Z_MIN_H:
            d = 1500.0
        for typ, v in (("D", d), ("DF", 1000.0)):
            store[eg.obs_key("TEX", typ, p)] = {
                "respondent": "TEX", "type": typ, "period": p, "value": v,
                "first_seen_at": p, "available_time": p, "pit_quality": "live"}
    pts = eg.surprise_series(store)["TEX"]
    assert pts[eg.Z_MIN_H - 1]["z"] is None
    assert pts[-1]["value"] == pytest.approx(0.5)
    assert pts[-1]["z"] == pytest.approx((0.5 - 0.0) / 0.01, rel=1e-3)


def test_threshold_is_bonferroni_over_regions_measured() -> None:
    assert eg.threshold(0) is None
    assert eg.threshold(1) == pytest.approx(1.95996, abs=1e-4)
    assert eg.threshold(14) == pytest.approx(2.9137, abs=1e-3)
    assert eg.threshold(14) > eg.threshold(3) > eg.threshold(1)


def test_trigger_flags_only_past_the_derived_bound_and_lines_every_stand_down() -> None:
    now = T0
    hour = eg._iso(now - timedelta(hours=2))
    fresh = eg._iso(now - timedelta(hours=1))

    def pt(z: float | None, n: int = 500, h: str = hour, done: str = fresh) -> dict[str, Any]:
        return {"hour": h, "hour_complete_at": done, "demand": 1.0, "forecast": 1.0,
                "surprise": 0.05, "z": z, "available_time": done, "pit_quality": "live",
                "n_points": n}
    old = eg._iso(now - timedelta(hours=40))
    latest = {"US48": pt(3.5), "TEX": pt(-2.5), "CAL": pt(0.3), "NE": pt(None, n=20),
              "NY": pt(4.0, h=old, done=old)}
    doc = eg.build_trigger(latest, now, source_status="OK",
                           regions=("US48", "TEX", "CAL", "NE", "NY", "SE"))
    assert doc["rule"]["k_measured"] == 3
    assert doc["rule"]["z_star"] == pytest.approx(eg.threshold(3), abs=1e-4)
    assert [f["region"] for f in doc["flags"]] == ["US48"]
    us = doc["flags"][0]
    assert us["direction"] == 1 and us["instruments"]["XNGUSD"] == 1
    assert set(us["instruments"]) == {"XNGUSD", "US500", "US30", "NAS100", "US2000"}
    assert doc["missed_growth_threshold"]["regions"] == ["TEX"]
    sd = doc["stand_down"]
    assert sd["NE"]["status"] == "NO_HISTORY" and sd["NY"]["status"] == "STALE"
    assert sd["SE"]["status"] == "UNMEASURED"
    assert all(v["missed_growth"] for v in sd.values())


def test_trigger_with_nothing_measured_is_unmeasured_not_quiet() -> None:
    doc = eg.build_trigger({}, T0, source_status="ROBOTS_REFUSED", regions=("US48",))
    assert doc["status"] == "UNMEASURED" and doc["rule"]["z_star"] is None
    assert doc["stand_down"]["US48"]["why"] == "ROBOTS_REFUSED"


def test_index_cfds_only_on_the_lower_48() -> None:
    assert set(eg.instruments_for("TEX")) == {"XNGUSD"}
    assert set(eg.instruments_for("US48")) == {"XNGUSD", "US500", "US30", "NAS100", "US2000"}


# --------------------------------------------------------------------------- the store ----
def test_merge_is_idempotent_and_keeps_the_first_value(tmp_path: Path) -> None:
    paths = eg.Paths(desk=tmp_path)
    h = datetime(2026, 11, 16, 5, tzinfo=UTC)
    rows = [{"respondent": "US48", "type": "D", "period": h, "value": 500.0},
            {"respondent": "US48", "type": "DF", "period": h, "value": 480.0}]
    store: dict[str, dict[str, Any]] = {}
    assert eg.merge(paths, store, rows, T0, backfill=False) == {"added": 2, "revised": 0}
    part = paths.obs / "2026-11-16.jsonl"
    n = len(part.read_text("utf-8").splitlines())
    assert eg.merge(paths, store, rows, T0, backfill=False) == {"added": 0, "revised": 0}
    assert len(part.read_text("utf-8").splitlines()) == n
    rev = [{**rows[0], "value": 505.0}]
    assert eg.merge(paths, store, rev, T0 + timedelta(hours=2), False)["revised"] == 1
    again = eg.load_store(paths)
    k = eg.obs_key("US48", "D", eg._iso(h))
    assert again[k]["value"] == 500.0 and again[k]["value_last"] == 505.0
    assert again[k]["n_revisions"] == 1
    # live availability: the hour is complete at period + 1h, or when first seen if later
    assert again[k]["available_time"] == eg._iso(T0)


def test_backfill_is_late_by_construction(tmp_path: Path) -> None:
    paths = eg.Paths(desk=tmp_path)
    h = T0 - timedelta(hours=5)
    store: dict[str, dict[str, Any]] = {}
    eg.merge(paths, store, [{"respondent": "TEX", "type": "D", "period": h, "value": 1.0}],
             T0, backfill=True)
    rec = next(iter(store.values()))
    assert rec["available_time"] == eg._iso(h + timedelta(hours=1 + eg.BACKFILL_LAG_H))
    assert rec["pit_quality"] == "backfill"


# ------------------------------------------------------------------------ end to end -----
def test_two_passes_publish_lake_trigger_and_cells(tmp_path: Path) -> None:
    from mt5desk.family_exogenous_conditioner import conditioner
    paths = _paths(tmp_path)
    minted: list[dict[str, Any]] = []
    first = _run(paths, FakeEIA(T0), T0, minted)
    assert first["status"] == "OK" and first["fetch"]["backfill"] is True
    assert first["fetch"]["requests"] > 5                 # metadata + more than one data page
    assert first["regions"]["TEX"]["pit_quality"] == "backfill"
    # backfill is timed a day late, so the first pass reads yesterday's grid at best
    assert first["regions"]["TEX"]["available_time"] <= eg._iso(T0)
    assert first["regions"]["TEX"]["hour"] <= eg._iso(T0 - timedelta(hours=1 + eg.BACKFILL_LAG_H))

    t1 = T0 + timedelta(hours=3)
    spike_hour = t1 - timedelta(hours=2)
    second = _run(paths, FakeEIA(t1, spike=("TEX", spike_hour, 0.25)), t1, minted)
    assert second["status"] == "OK" and second["fetch"]["backfill"] is False
    assert second["fetch"]["added"] > 0
    tex = second["regions"]["TEX"]
    assert tex["hour"] == eg._iso(spike_hour) and tex["surprise"] == pytest.approx(0.25)
    assert tex["z"] > 10 and tex["pit_quality"] == "live"
    trig = json.loads(paths.trigger.read_text("utf-8"))
    assert [f["region"] for f in trig["flags"]] == ["TEX"]
    assert trig["flags"][0]["instruments"] == {"XNGUSD": 1}
    assert "MIDW" in trig["stand_down"]                    # a region the API did not list

    # the lake series is the frame the family loads
    s = conditioner(eg.lake_name("TEX"), "value", "level_z", lag_hours=eg.LAG_HOURS,
                    z_window=eg.Z_WINDOW_H, root=paths.series)
    assert s is not None and len(s) > eg.MIN_POINTS

    syms = {c["symbol"] for c in minted}
    assert syms == {"XNGUSD", "US500", "US30", "NAS100", "US2000"}
    for c in minted:
        assert c["family"] == "exogenous_conditioner"
        if c["symbol"] != "XNGUSD":
            assert c["params"]["source"] == eg.lake_name("US48")
    assert second["cells"]["minted"] > 0
    _no_key_anywhere(paths)


def test_no_fetch_writes_from_the_store_without_a_request(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    fake = FakeEIA(T0)
    doc = eg.run(paths, fetch=False, get=fake, now=T0, environ=ENV,
                 donate=lambda *_a: {"donated": 0})
    assert doc["status"] == "NO_FETCH" and fake.urls == []
    assert json.loads(paths.trigger.read_text("utf-8"))["status"] == "UNMEASURED"
