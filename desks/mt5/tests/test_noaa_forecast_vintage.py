"""NOAA CPC forecast vintages: parse the real formats, store each issue once, revise honestly.

FIXTURES (tests/fixtures/noaa/) are VERBATIM excerpts of NOAA CPC public-domain products, read
2026-11-11 (this container cannot reach noaa.gov with curl; they were read through WebFetch):
  UtilityGas.Heating.20261110.txt  the whole file at
      https://ftp.cpc.ncep.noaa.gov/htdocs/degree_days/weighted/daily_forecasts_7day/2026/11/10/UtilityGas.Heating.txt
  Population.Cooling.20261004.txt  the whole file served that day at
      https://ftp.cpc.ncep.noaa.gov/htdocs/degree_days/weighted/daily_forecasts_7day/latest/Population.Cooling.txt
  ddforecast.20261015.txt          header plus the first three target months of the first two
      region blocks of https://www.cpc.ncep.noaa.gov/pacdir/DDdir/ddforecast.txt
"""
from __future__ import annotations

import gzip
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("pyarrow")

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import noaa_forecast_vintage as nfv  # noqa: E402

FIX = DESK / "tests" / "fixtures" / "noaa"
REG = json.loads(nfv.SOURCES.read_text("utf-8"))
REGIONS = {str(k): str(v) for k, v in REG["census_divisions"].items()}
GAS = next(p for p in REG["products"] if p["id"] == "cpc_dd7_gas_hdd")
MONTHLY = next(p for p in REG["products"] if p["id"] == "cpc_dd_monthly")
NOW = datetime(2026, 11, 10, 18, 0, tzinfo=UTC)


def _fx(name: str) -> str:
    return (FIX / name).read_text("utf-8")


def _shift_issue(text: str, old: str, new: str, bump: int = 0) -> str:
    """A later issue of the same 7-day file: new stamp, one more day of HDD on New England."""
    out = text.replace(f"Issued 0000UTC {old}", f"Issued 0000UTC {new}")
    if bump:
        out = out.replace("1|17|16|20|25|27|25|24|154", f"1|17|{16 + bump}|20|25|27|25|24|"
                                                        f"{154 + bump}")
    return out


# ----------------------------------------------------------------------------- parsers

def test_dd7_parses_issue_time_days_and_total() -> None:
    issue, rows = nfv.parse_cpc_dd7(_fx("UtilityGas.Heating.20261110.txt"), GAS, REGIONS)
    assert issue == datetime(2026, 11, 10, 0, 0, tzinfo=UTC)
    days = [r for r in rows if r["target_kind"] == "day"]
    totals = [r for r in rows if r["target_kind"] == "period_total"]
    assert len(days) == 10 * 7 and len(totals) == 10
    ne = {r["target_start"]: r["value"] for r in days if r["region"] == "new_england"}
    assert ne["2026-11-10"] == 17 and ne["2026-11-16"] == 24
    conus = next(r for r in totals if r["region"] == "conus")
    assert (conus["value"], conus["target_start"], conus["target_end"]) == \
        (113, "2026-11-10", "2026-11-16")
    assert {r["measure"] for r in rows} == {"hdd"}


def test_dd7_cooling_file_and_unstamped_file() -> None:
    cdd = next(p for p in REG["products"] if p["id"] == "cpc_dd7_pop_cdd")
    issue, rows = nfv.parse_cpc_dd7(_fx("Population.Cooling.20261004.txt"), cdd, REGIONS)
    assert issue == datetime(2026, 10, 4, tzinfo=UTC)
    assert next(r["value"] for r in rows if r["region"] == "pacific"
                and r["target_kind"] == "period_total") == 71
    # no issue stamp in the header: unusable, never guessed
    body = "\n".join(_fx("Population.Cooling.20261004.txt").splitlines()[1:])
    assert nfv.parse_cpc_dd7(body, cdd, REGIONS) == (None, [])


def test_monthly_parses_header_time_regions_and_bounds() -> None:
    issue, rows = nfv.parse_cpc_dd_monthly(_fx("ddforecast.20261015.txt"), MONTHLY, REGIONS)
    # 300 PM EDT = 19:00 UTC
    assert issue == datetime(2026, 10, 15, 19, 0, tzinfo=UTC)
    assert {r["region"] for r in rows} == {"new_england", "mid_atlantic"}
    jan = next(r for r in rows if r["region"] == "new_england" and r["measure"] == "hdd"
               and r["target_start"] == "2027-01-01")
    assert jan["value"] == 1184 and jan["target_end"] == "2027-01-31"
    assert jan["values"] == {"p90": 976, "mean": 1184, "p10": 1409, "normal": 1260,
                             "departure": -76}
    assert len(rows) == 2 * 3 * 2


def test_monthly_issue_time_est_and_am() -> None:
    t = nfv.monthly_issue_time(" 830 AM EST THU 15 JAN 2026\n")
    assert t == datetime(2026, 1, 15, 13, 30, tzinfo=UTC)
    assert nfv.monthly_issue_time("no stamp here") is None


# ----------------------------------------------------------------------------- PIT

def test_knowable_from_is_fetch_when_live_and_lag_when_archived() -> None:
    issue = datetime(2026, 11, 10, tzinfo=UTC)
    live = datetime(2026, 11, 10, 15, tzinfo=UTC)
    assert nfv.knowable_from(issue, live, 24) == (live, "fetch_time")
    late = datetime(2027, 1, 1, tzinfo=UTC)
    assert nfv.knowable_from(issue, late, 24) == (datetime(2026, 11, 11, tzinfo=UTC),
                                                  "declared_publish_lag")


# ----------------------------------------------------------------------------- the pass

class FakeHost:
    def __init__(self, files: dict[str, tuple[int, str]], robots: tuple[int, str] = (404, "")):
        self.files = files
        self.robots = robots
        self.calls: list[str] = []

    def __call__(self, url: str) -> tuple[int | None, str, str]:
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            return self.robots[0], self.robots[1], ""
        st, body = self.files.get(url, (404, ""))
        return st, body, "" if st == 200 else f"HTTP {st}"


def _url(day: str) -> str:
    y, m, d = day.split("-")
    return str(GAS["url"]).format(yyyy=y, mm=m, dd=d)


def _reg(**over: Any) -> dict[str, Any]:
    prod = {**GAS, "backfill_from": "2026-11-08", "lookback_days": 3, **over}
    return {**REG, "products": [prod]}


def _run(tmp: Path, host: FakeHost, now: datetime = NOW, **kw: Any) -> dict[str, Any]:
    return nfv.refresh(fetch=host, registry=kw.pop("registry", _reg()),
                       vintages=tmp / "v", series=tmp / "s", report=tmp / "r.json",
                       universe={"XNGUSD": {}}, now=now, **kw)


def test_append_only_once_per_issue_and_new_issue_adds_one(tmp_path: Path) -> None:
    gas = _fx("UtilityGas.Heating.20261110.txt")
    host = FakeHost({_url("2026-11-10"): (200, gas)})
    rep = _run(tmp_path, host)
    p = rep["products"]["cpc_dd7_gas_hdd"]
    assert p["status"] == "OK" and p["new_issues"] == 1 and p["instruments"] == ["XNGUSD"]
    store = nfv.store_path("cpc_dd7_gas_hdd", tmp_path / "v")
    n1 = len(nfv.read_vintages(store))
    raw1 = store.read_bytes()
    # a second identical pass adds nothing; the date is done and not refetched
    rep2 = _run(tmp_path, host)
    assert rep2["products"]["cpc_dd7_gas_hdd"]["new_issues"] == 0
    assert store.read_bytes() == raw1
    # a new issue the next day adds exactly one issue, and the earlier bytes are untouched
    host.files[_url("2026-11-11")] = (200, _shift_issue(gas, "20261110", "20261111", bump=3))
    rep3 = _run(tmp_path, host, now=datetime(2026, 11, 11, 18, tzinfo=UTC))
    assert rep3["products"]["cpc_dd7_gas_hdd"]["new_issues"] == 1
    rows = nfv.read_vintages(store)
    assert len(rows) == 2 * n1
    assert store.read_bytes().startswith(raw1)
    assert {r["issue_time_utc"] for r in rows} == {"2026-11-10T00:00:00+00:00",
                                                   "2026-11-11T00:00:00+00:00"}
    first = next(r for r in rows if r["issue_time_utc"].startswith("2026-11-10"))
    assert first["knowable_from_utc"] == "2026-11-10T18:00:00+00:00"
    assert first["source_url"] == _url("2026-11-10") and first["units"]


def test_same_issue_changed_is_counted_never_overwritten(tmp_path: Path) -> None:
    fixed = {**MONTHLY}
    reg = {**REG, "products": [fixed]}
    host = FakeHost({MONTHLY["url"]: (200, _fx("ddforecast.20261015.txt"))})
    _run(tmp_path, host, registry=reg)
    store = nfv.store_path("cpc_dd_monthly", tmp_path / "v")
    before = store.read_bytes()
    host.files[MONTHLY["url"]] = (200, _fx("ddforecast.20261015.txt").replace("704.", "705."))
    later = datetime(2026, 11, 11, 6, tzinfo=UTC)          # past min_refetch_hours
    rep = _run(tmp_path, host, registry=reg, now=later)
    p = rep["products"]["cpc_dd_monthly"]
    assert p["same_issue_changed"] == 1 and p["new_issues"] == 0
    assert store.read_bytes() == before


def test_revision_math_and_pit_series(tmp_path: Path) -> None:
    gas = _fx("UtilityGas.Heating.20261110.txt")
    host = FakeHost({_url("2026-11-10"): (200, gas),
                     _url("2026-11-11"): (200, _shift_issue(gas, "20261110", "20261111", 3))})
    _run(tmp_path, host, now=datetime(2026, 11, 11, 18, tzinfo=UTC))
    rows = nfv.read_vintages(nfv.store_path("cpc_dd7_gas_hdd", tmp_path / "v"))
    revs = nfv.revisions(rows)
    # the day 2026-11-11 for New England: 16 in the first issue, 19 in the second
    r = next(x for x in revs if x["region"] == "new_england" and x["target_kind"] == "day"
             and x["target_start"] == "2026-11-11" and x["prev_issue_time_utc"])
    assert (r["prev_value"], r["value"], r["revision"]) == (16, 19, 3)
    firsts = [x for x in revs if x["prev_issue_time_utc"] is None]
    assert firsts and all(x["revision"] is None for x in firsts)
    # every revision is usable only once both issues were knowable
    assert all(x["available_time"] >= x["issue_time_utc"] for x in revs)

    sp = tmp_path / "s" / "noaa_cpc_dd7_gas_hdd.parquet"
    df = pd.read_parquet(sp)
    for c in ("available_time", "event_time", "source_id", "vintage_id", "retrieval_time"):
        assert c in df.columns
    assert len(df) == 2
    df = df.sort_values("event_time")
    assert pd.isna(df["new_england_hdd_rev"].iloc[0])          # first issue: UNMEASURED
    assert df["new_england_hdd_rev"].iloc[1] == 3
    assert df["conus_hdd_rev"].iloc[1] == 0
    assert df["new_england_hdd_lvl"].tolist() == [154, 157]
    assert df["new_england_hdd_nov"].iloc[1] == 7       # the stub reissue keeps all 7 days

    # the conditioner reads it through its own loader, on its own available_time clock
    from mt5desk.family_exogenous_conditioner import conditioner, series_path
    assert series_path("noaa_cpc_dd7_gas_hdd", tmp_path / "s") == sp
    s = conditioner("noaa_cpc_dd7_gas_hdd", "new_england_hdd_lvl", "delta",
                    root=tmp_path / "s", lag_hours=0)
    assert s is not None and float(s.iloc[-1]) == 3.0


def test_backfilled_older_issue_slots_in_by_issue_time() -> None:
    def rows(issue: str, v: float, kf: str) -> list[dict[str, Any]]:
        return [{"product": "p", "region": "r", "measure": "hdd", "target_kind": "day",
                 "target_start": "2026-01-05", "target_end": "2026-01-05", "value": v,
                 "issue_time_utc": issue, "knowable_from_utc": kf, "vintage_id": issue}]
    # fetched out of order: the 03 issue was backfilled after 04 was held
    revs = nfv.revisions(rows("2026-01-04T00:00:00+00:00", 30, "2026-01-04T15:00:00+00:00")
                         + rows("2026-01-03T00:00:00+00:00", 20, "2026-01-04T00:00:00+00:00"))
    assert [x["revision"] for x in revs] == [None, 10]


def test_robots_refusal_fetches_nothing(tmp_path: Path) -> None:
    host = FakeHost({_url("2026-11-10"): (200, _fx("UtilityGas.Heating.20261110.txt"))},
                    robots=(200, "User-agent: *\nDisallow: /htdocs/degree_days/\n"))
    rep = _run(tmp_path, host)
    p = rep["products"]["cpc_dd7_gas_hdd"]
    assert p["status"] == "ROBOTS_REFUSED" and p["robots_refused"] >= 1
    assert "robots.txt" in p["missed_growth"]
    assert [c for c in host.calls if not c.endswith("robots.txt")] == []
    assert any("cpc_dd7_gas_hdd" in m for m in rep["missed_growth"])


def test_unreadable_robots_is_unmeasured_not_open(tmp_path: Path) -> None:
    host = FakeHost({_url("2026-11-10"): (200, _fx("UtilityGas.Heating.20261110.txt"))},
                    robots=(503, ""))
    rep = _run(tmp_path, host)
    assert rep["products"]["cpc_dd7_gas_hdd"]["status"] == "UNMEASURED"
    assert [c for c in host.calls if not c.endswith("robots.txt")] == []


@pytest.mark.parametrize("code", [401, 403, 429, 451])
def test_hard_stop_is_never_retried(tmp_path: Path, code: int) -> None:
    host = FakeHost({_url("2026-11-10"): (code, "")})
    rep = _run(tmp_path, host)
    p = rep["products"]["cpc_dd7_gas_hdd"]
    assert p["status"] == "HARD_STOP" and p["hard_stop"]["code"] == code
    assert "UNMEASURED" in p["missed_growth"]
    fetched = [c for c in host.calls if not c.endswith("robots.txt")]
    assert fetched == [_url("2026-11-10")]                      # stopped at the first refusal
    # the next pass inside the cooldown does not knock at all
    host.calls.clear()
    rep2 = _run(tmp_path, host)
    assert rep2["products"]["cpc_dd7_gas_hdd"]["status"] == "HARD_STOP"
    assert host.calls == []


def test_instrument_absent_from_universe_is_dropped_and_reported(tmp_path: Path) -> None:
    host = FakeHost({_url("2026-11-10"): (200, _fx("UtilityGas.Heating.20261110.txt"))})
    rep = _run(tmp_path, host, registry=_reg(instruments=["XNGUSD", "NOT_A_SYMBOL"]))
    p = rep["products"]["cpc_dd7_gas_hdd"]
    assert p["instruments"] == ["XNGUSD"] and p["instruments_absent"] == ["NOT_A_SYMBOL"]
    assert "missed_growth_instruments" in p


def test_registry_instruments_exist_in_the_universe() -> None:
    uni = json.loads(nfv.UNIVERSE.read_text("utf-8"))
    for prod in REG["products"]:
        assert prod["format"] in nfv.PARSERS
        assert prod["instruments"] and all(s in uni for s in prod["instruments"]), prod["id"]


def test_store_is_gzip_jsonl(tmp_path: Path) -> None:
    host = FakeHost({_url("2026-11-10"): (200, _fx("UtilityGas.Heating.20261110.txt"))})
    _run(tmp_path, host)
    with gzip.open(nfv.store_path("cpc_dd7_gas_hdd", tmp_path / "v"), "rt") as fh:
        row = json.loads(fh.readline())
    for k in ("issue_time_utc", "knowable_from_utc", "target_start", "target_end", "region",
              "value", "units", "source_url", "product", "vintage_id"):
        assert k in row


# ----------------------------------------------------------------------------- wiring

def test_leg_is_wired_into_the_hourly_cycle_and_a_layer() -> None:
    from libs.research import layers

    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("noaa_forecasts"' in src
    assert '"research/noaa_forecast_vintage.py", "--once"' in src
    assert '"noaa_forecasts": nfv' in src
    assert "noaa_forecasts" in layers.scheduled_legs(ROOT)
    assert layers.LEG_LAYER["noaa_forecasts"] == "information"
    import research.hourly_cycle as hc
    assert "noaa_forecasts" in hc.CORE_LEGS
    assert any("noaa_forecasts" in v for v in hc.LEG_DEPARTMENT.values()) or \
        "noaa_forecasts" in hc.LEG_DEPARTMENT


@pytest.mark.parametrize("code", [404, 410, 400])
def test_an_absent_robots_file_is_any_plain_4xx(tmp_path: Path, code: int) -> None:
    """RFC 9309: 404, 410 and other 4xx (not the hard stops) mean no robots.txt -- fetch."""
    host = FakeHost({_url("2026-11-10"): (200, _fx("UtilityGas.Heating.20261110.txt"))},
                    robots=(code, ""))
    rep = _run(tmp_path, host)
    p = rep["products"]["cpc_dd7_gas_hdd"]
    assert p["status"] == "OK" and p["new_issues"] == 1


def test_a_recent_issue_first_seen_after_its_assumed_lag_is_flagged(tmp_path: Path) -> None:
    gas = _fx("UtilityGas.Heating.20261110.txt")
    on_time = _run(tmp_path / "a", FakeHost({_url("2026-11-10"): (200, gas)}),
                   now=datetime(2026, 11, 10, 18, tzinfo=UTC))
    assert on_time["products"]["cpc_dd7_gas_hdd"]["first_seen_after_lag"] == []
    late = _run(tmp_path / "b", FakeHost({_url("2026-11-10"): (200, gas)}),
                now=datetime(2026, 11, 11, 6, tzinfo=UTC))
    flag = late["products"]["cpc_dd7_gas_hdd"]["first_seen_after_lag"]
    assert [f["issue"] for f in flag] == ["2026-11-10T00:00:00+00:00"]
    assert flag[0]["age_h"] == 30.0 and flag[0]["assumed_lag_h"] == 24.0
