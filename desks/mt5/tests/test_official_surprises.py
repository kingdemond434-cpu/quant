"""Official-data surprises: point-in-time stamps, honest access, catalogue-first ids, no lookahead.

WHAT THIS PINS, on synthetic inputs only (no network):
  * release instants are the scheduled local time plus grace in UTC, DST-correct; a holiday in the
    release week moves the stamp LATER, never earlier; exact calendar dates and shutdown windows win;
  * a surprise is never scored against itself (truncating the future changes no past z);
  * EIA's baseline is the 5-year same-week mean and needs all five years;
  * net liquidity = WALCL - TGA - RRP in $bn on Wednesdays, released Thursday 16:30 ET;
  * robots is read before any data request and a disallow stops it; 403 is a hard stop in state;
  * a series id / commodity code is used only when the source's catalogue returns it;
  * a missing key is NEEDS_KEY and no note ever carries a key value;
  * TIC's state lasts release day + 1 week and then reads 0;
  * the CIP proxy is the mid swap-implied differential minus the cash differential;
  * futures_state mints the outputs as exogenous_conditioner cells.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import futures_state as fs  # noqa: E402
from research import official_surprises as osx  # noqa: E402


@pytest.fixture(autouse=True)
def _tmp_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(osx, "RAW", tmp_path / "raw")
    monkeypatch.setattr(fs, "CALENDAR_BACKFILL", tmp_path / "cal")
    for k in ("EIA_API_KEY", "EIA_KEY", "FRED_API_KEY", "FRED_KEY", "USDA_FAS_API_KEY",
              "DATA_GOV_API_KEY"):
        monkeypatch.delenv(k, raising=False)


class FakeNet:
    """URL -> body. Records every URL asked, so a test can prove what was NOT requested."""

    def __init__(self, pages: dict[str, Any], robots: str = "", refuse: dict[str, int] | None
                 = None):
        self.pages, self.robots, self.refuse = pages, robots, refuse or {}
        self.asked: list[str] = []

    def __call__(self, url: str, headers: Any) -> str:
        self.asked.append(url)
        if url.endswith("/robots.txt"):
            return self.robots
        for frag, code in self.refuse.items():
            if frag in url:
                raise fs.HardStop(code, url)
        for frag, body in self.pages.items():
            if frag in url:
                return body if isinstance(body, str) else json.dumps(body)
        raise fs.FetchError(404, url, "HTTP 404")


# ------------------------------------------------------------------------------ clocks

def test_release_instant_is_local_time_plus_grace_in_utc_both_dst_regimes() -> None:
    days = pd.Series(pd.to_datetime(["2026-01-15", "2026-07-16"]))   # Thursdays
    t = osx.release_instant(days, "10:30", "America/New_York")
    assert t.iloc[0] == pd.Timestamp("2026-01-15 15:35", tz="UTC")       # EST
    assert t.iloc[1] == pd.Timestamp("2026-07-16 14:35", tz="UTC")       # EDT


def test_holiday_week_moves_the_release_later_never_earlier() -> None:
    # Thanksgiving 2026 is Thursday 26 Nov: the Thursday release cannot be on the holiday
    t = osx.release_instant(pd.Series([pd.Timestamp("2026-11-26")]), "10:30",
                            "America/New_York")
    assert t.iloc[0].date().isoformat() == "2026-11-27"
    # Labor Day Monday 7 Sep 2026 sits in the week: Thursday 10 Sep -> Friday 11 Sep
    t = osx.release_instant(pd.Series([pd.Timestamp("2026-09-10")]), "08:30",
                            "America/New_York")
    assert t.iloc[0].date().isoformat() == "2026-09-11"


def test_exact_calendar_and_shutdown_window_win() -> None:
    cal = {"releases": {"2025-10-09": "2025-11-20"},
           "windows": [{"from": "2025-10-01", "to": "2025-11-12", "not_before": "2025-11-14"}]}
    t = osx.release_instant(pd.Series(pd.to_datetime(["2025-10-09", "2025-10-16"])), "10:30",
                            "America/New_York", cal)
    assert t.iloc[0].date().isoformat() == "2025-11-20"
    assert t.iloc[1].date().isoformat() == "2025-11-14"


# ------------------------------------------------------------------------------ features

def test_surprise_z_never_sees_itself_or_the_future() -> None:
    rng = np.random.default_rng(3)
    a = pd.Series(rng.normal(size=120))
    full = osx.surprise_frame(a, pd.Series(0.0, index=a.index))
    cut = osx.surprise_frame(a.iloc[:80], pd.Series(0.0, index=a.index[:80]))
    pd.testing.assert_frame_equal(full.iloc[:80], cut)
    # a huge value at i must not shrink its own z (it is excluded from its baseline)
    a2 = a.copy()
    a2.iloc[100] = 50.0
    z = osx.surprise_frame(a2, pd.Series(0.0, index=a.index))["surprise_z"]
    assert z.iloc[100] > 10


def test_trailing_baselines_exclude_the_release() -> None:
    x = pd.Series([1.0, 2.0, 3.0, 4.0, 100.0])
    assert osx.trailing_mean(x, 4).iloc[4] == pytest.approx(2.5)
    assert osx.trailing_median(x, 3).iloc[4] == pytest.approx(3.0)


def test_eia_baseline_is_the_five_year_same_week_mean_and_needs_all_five() -> None:
    weeks = pd.Series(pd.date_range("2015-01-02", "2026-12-31", freq="W-FRI"))
    chg = pd.Series(weeks.dt.year.astype(float))            # each year's change = its year
    base = osx.same_week_5y_mean(weeks, chg)
    i = int(weeks[weeks == pd.Timestamp("2024-03-01")].index[0])
    assert base.iloc[i] == pytest.approx(np.mean([2019, 2020, 2021, 2022, 2023]))
    assert np.isnan(base.iloc[10])                          # 2015: no five prior years


def test_net_liquidity_units_and_wednesday_frame() -> None:
    d = pd.date_range("2024-01-01", periods=70, freq="D")
    df = pd.DataFrame({"date": d, "WALCL": np.where(d.weekday == 2, 8_000_000.0, np.nan),
                       "WTREGEN": np.where(d.weekday == 2, 700.0, np.nan),
                       "RRPONTSYD": 500.0})
    w = osx.net_liquidity(df, {"WALCL": 0.001, "WTREGEN": 1.0, "RRPONTSYD": 1.0})
    assert (pd.to_datetime(w["week"]).dt.weekday == 2).all()
    assert w["net_liq_bn"].iloc[0] == pytest.approx(8000 - 700 - 500)


# ------------------------------------------------------------------------------ access

def _storage(n: int = 400) -> list[dict[str, Any]]:
    weeks = pd.date_range("2018-01-05", periods=n, freq="W-FRI")
    rng = np.random.default_rng(1)
    stock = 2000 + np.cumsum(rng.normal(0, 50, n))
    return [{"period": w.date().isoformat(), "value": float(v)} for w, v in zip(weeks, stock,
                                                                                strict=True)]


EIA_ROW = {"id": "eia_storage", "adapter": "eia_storage", "terms": "OPEN",
           "key_env": ["EIA_API_KEY"], "route": "natural-gas/stor/wkly",
           "series": "NW2_EPG0_SWO_R48_BCF", "at": "10:30", "tz": "America/New_York",
           "targets": ["XNGUSD"]}


def test_eia_end_to_end_catalogue_first_then_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EIA_API_KEY", "SECRETKEY123")
    net = FakeNet({"/facet/series": {"response": {"facets": [{"id": "NW2_EPG0_SWO_R48_BCF"}]}},
                   "/data/": {"response": {"data": _storage()}}})
    notes: list[dict[str, Any]] = []
    outs = osx.collect(text=net, state={}, notes=notes, registry={"rows": [EIA_ROW]})
    assert [o[0] for o in outs] == ["os_eia_storage"]
    oid, frame, meta = outs[0]
    assert {"surprise", "surprise_z", "available_time", "event_time"} <= set(frame.columns)
    # available strictly after the Friday week end (Thursday 10:30 ET + grace)
    assert (frame["available_time"] > frame["event_time"] + pd.Timedelta(days=6)).all()
    assert meta["targets"] == ["XNGUSD"]
    assert (fs.CALENDAR_BACKFILL / "backfill_os_eia_storage.jsonl.gz").exists()
    assert "SECRETKEY123" not in json.dumps(notes)


def test_series_absent_from_catalogue_is_unmeasured_and_never_fetched(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EIA_API_KEY", "k")
    net = FakeNet({"/facet/series": {"response": {"facets": [{"id": "OTHER"}]}},
                   "/data/": {"response": {"data": _storage()}}})
    notes: list[dict[str, Any]] = []
    outs = osx.collect(text=net, state={}, notes=notes, registry={"rows": [EIA_ROW]})
    assert outs == []
    assert not any("/data/" in u for u in net.asked)
    assert any(n.get("why") == "series id not in the route's catalogue" for n in notes)


def test_robots_disallow_stops_every_data_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EIA_API_KEY", "k")
    net = FakeNet({"/facet/series": {}}, robots="User-agent: *\nDisallow: /")
    notes: list[dict[str, Any]] = []
    osx.collect(text=net, state={}, notes=notes, registry={"rows": [EIA_ROW]})
    assert all(u.endswith("/robots.txt") for u in net.asked)
    assert any(n.get("why") == "robots disallows" for n in notes)


def test_403_is_a_hard_stop_recorded_in_state_and_not_retried(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EIA_API_KEY", "k")
    net = FakeNet({}, refuse={"api.eia.gov/v2": 403})
    state: dict[str, Any] = {}
    osx.collect(text=net, state=state, notes=[], registry={"rows": [EIA_ROW]})
    assert state["hard_stops"]["eia_storage"]["code"] == 403
    n = len(net.asked)
    osx.collect(text=net, state=state, notes=[], registry={"rows": [EIA_ROW]})
    assert len(net.asked) == n


def test_missing_key_is_needs_key_and_held_raw_still_serves(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EIA_API_KEY", "k")
    net = FakeNet({"/facet/series": {"response": {"facets": [{"id": "NW2_EPG0_SWO_R48_BCF"}]}},
                   "/data/": {"response": {"data": _storage()}}})
    osx.collect(text=net, state={}, notes=[], registry={"rows": [EIA_ROW]})
    monkeypatch.delenv("EIA_API_KEY")
    notes: list[dict[str, Any]] = []
    outs = osx.collect(text=net, state={}, notes=notes, registry={"rows": [EIA_ROW]})
    assert any(n.get("status") == "NEEDS_KEY" for n in notes)
    assert [o[0] for o in outs] == ["os_eia_storage"]


def test_terms_not_open_is_never_fetched() -> None:
    net = FakeNet({})
    notes: list[dict[str, Any]] = []
    osx.collect(text=net, state={}, notes=notes,
                registry={"rows": [{**EIA_ROW, "terms": "TO_CONFIRM"}]})
    assert net.asked == []
    assert any("terms" in str(n.get("why")) for n in notes)


def test_redact_hides_keys() -> None:
    u = osx._redact("https://x.org/a?api_key=SECRET&series_id=WALCL")
    assert "SECRET" not in u and "WALCL" in u


# ------------------------------------------------------------------------------ USDA

USDA_ROW = {"id": "usda_esr", "adapter": "usda_esr", "terms": "OPEN",
            "key_env": ["USDA_FAS_API_KEY"], "api_base": "https://apps.fas.usda.gov/OpenData/api",
            "field": "currentMYNetSales", "first_market_year": 2023, "baseline_weeks": 4,
            "at": "08:30", "tz": "America/New_York",
            "commodities": [{"id": "corn", "name_pattern": "^\\s*corn\\s*$", "targets": ["CORN"]},
                            {"id": "wheat", "name_pattern": "wheat", "targets": ["WHEAT"]}]}


def _esr_year(my: int) -> list[dict[str, Any]]:
    weeks = pd.date_range(f"{my - 1}-09-07", periods=52, freq="W-THU")
    rng = np.random.default_rng(my)
    out = []
    for w in weeks:
        for country in ("JAPAN", "MEXICO"):
            out.append({"weekEndingDate": w.isoformat(), "countryCode": country,
                        "currentMYNetSales": float(rng.integers(0, 900_000))})
    return out


def test_usda_codes_come_from_the_catalogue_and_ambiguity_is_unmeasured(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USDA_FAS_API_KEY", "k")
    cat = [{"commodityCode": 401, "commodityName": "Corn"},
           {"commodityCode": 107, "commodityName": "All Wheat"},
           {"commodityCode": 101, "commodityName": "Wheat - HRW"}]
    pages: dict[str, Any] = {"/esr/commodities": cat}
    for my in range(2023, 2028):
        pages[f"/commodityCode/401/allCountries/marketYear/{my}"] = _esr_year(my)
    net = FakeNet(pages)
    notes: list[dict[str, Any]] = []
    outs = osx.collect(text=net, state={}, notes=notes, registry={"rows": [USDA_ROW]},
                       now=datetime(2026, 11, 13, tzinfo=UTC))
    assert [o[0] for o in outs] == ["os_usda_esr_corn"]
    assert not any("/commodityCode/107/" in u or "/commodityCode/101/" in u for u in net.asked)
    assert any(n.get("source") == "usda_esr_wheat" and "matched 2" in n.get("why", "")
               for n in notes)
    f = outs[0][1]
    assert f["event_time"].dt.weekday.eq(3).all()
    assert (f["available_time"] - f["event_time"] >= pd.Timedelta(days=7)).all()


# ------------------------------------------------------------------------------ TIC

def test_tic_parse_finds_the_column_by_header() -> None:
    body = "Country,Gross Purchases,Net Foreign Purchases of Long-term Securities\n" + "\n".join(
        f"{y}-{m:02d},1,{y * 10 + m}" for y in range(2020, 2024) for m in range(1, 13))
    d = osx.tic_parse(body, osx.fs._read(osx.REGISTRY, {})["rows"][5]["column_pattern"])
    assert len(d) == 48 and d["value"].iloc[0] == 20201
    assert osx.tic_parse("a,b\n2020-01,1", "net purchases").empty


def test_tic_state_lasts_one_week_then_reads_zero() -> None:
    a = pd.Series(pd.to_datetime(["2026-01-20", "2026-02-18"], utc=True))
    f = pd.DataFrame({"surprise": [1.0, 2.0], "surprise_z": [2.5, -3.0]})
    feat, avail, ev = osx.windowed_state(f, a, pd.Series(pd.to_datetime(["2025-11-30",
                                                                          "2025-12-31"])),
                                         "surprise_z", 7)
    assert list(feat["surprise_z_wk"]) == [2.5, 0.0, -3.0, 0.0]
    assert avail.iloc[1] == a.iloc[0] + pd.Timedelta(days=7)
    assert np.isnan(feat["surprise_z"].iloc[1])


def test_tic_find_file_matches_link_text() -> None:
    html = '<a href="/x/a.txt">Other</a><a href="/data/s1.csv">Net Purchases of Long-Term ' \
           'Securities</a>'
    assert osx.tic_find_file(html, "net purchases.*long[- ]term", "https://t.gov/i.html") \
        == "https://t.gov/data/s1.csv"


# ------------------------------------------------------------------------------ CIP, rinban

def test_swap_implied_differential_math() -> None:
    # 1 point/night at 5 digits on 1.10000 = 0.00001/1.1*365*100 = 0.3318 %/yr
    assert osx.swap_implied_diff(1.0, 1.1, 5, "long") == pytest.approx(0.33182, rel=1e-4)
    assert osx.swap_implied_diff(1.0, 1.1, 5, "short") == pytest.approx(-0.33182, rel=1e-4)


def test_cip_basis_is_mid_implied_minus_cash() -> None:
    days = pd.date_range("2026-01-01", periods=60, freq="D", tz="UTC")
    swaps = pd.DataFrame({"time": days + pd.Timedelta(hours=8), "symbol": "EURUSD",
                          "swap_long": -3.0, "swap_short": 1.0, "swap_mode": "points",
                          "digits": 5, "price": 1.0})
    cash = pd.DataFrame({"diff": [-1.5] * 60, "available_time": days - pd.Timedelta(days=1)})
    row = {"id": "cip", "adapter": "cip_basis", "terms": "OPEN",
           "pairs": [{"symbol": "EURUSD", "cash": "fred_rdiff_on_eurusd"}], "targets": []}
    outs = osx.collect(text=None, state={}, notes=[], registry={"rows": [row]},
                       frames={"fred_rdiff_on_eurusd": cash}, swaps=swaps)
    f = outs[0][1]
    implied = (osx.swap_implied_diff(-3, 1, 5, "long") + osx.swap_implied_diff(1, 1, 5,
                                                                              "short")) / 2
    assert f["basis_pct"].iloc[-1] == pytest.approx(implied + 1.5)
    assert outs[0][2]["targets"] == ["EURUSD"]


def test_rinban_size_vs_plan_and_cover() -> None:
    ops = osx.rinban_parse([{"date": "2026-11-02", "offered": 400, "planned": 500, "bids": 1200},
                            {"date": "2026-11-02", "offered": 300, "planned": 300, "bids": 600}])
    assert ops["size_vs_plan"].iloc[0] == pytest.approx((-0.2 + 0.0) / 2)
    assert ops["cover"].iloc[0] == pytest.approx((3.0 + 2.0) / 2)


# ------------------------------------------------------------------------------ wiring

def test_registry_rows_all_have_an_adapter_targets_and_no_key_values() -> None:
    reg = fs._read(osx.REGISTRY, {})
    universe = json.loads((_DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    for r in reg["rows"]:
        assert r["adapter"] in osx.ADAPTERS
        ts = list(r.get("targets") or []) + [t for c in r.get("commodities") or []
                                               for t in c["targets"]]
        assert ts and all(t in universe for t in ts), r["id"]
        assert not any(k for k in r if "key" in k and k != "key_env")


def test_futures_state_mints_official_outputs_as_conditioner_cells(
        monkeypatch: pytest.MonkeyPatch) -> None:
    frame = fs.stamped(pd.DataFrame({"surprise": np.arange(40.0), "surprise_z": np.sin(np.arange(40.0))}),
                       pd.Series(pd.date_range("2024-01-04", periods=40, freq="7D", tz="UTC")),
                       "os_x", pd.Series(pd.date_range("2024-01-01", periods=40, freq="7D")))
    monkeypatch.setattr(osx, "collect", lambda **k: [("os_x", frame, {"targets": ["XNGUSD"],
                                                                     "kind": "k"})])
    built, frames, _ = fs.build_market_series({}, get=None, state={}, bars=lambda s: None)
    assert "os_x" in built
    seen: list[dict[str, Any]] = []
    fs.mint(built, frames, frozenset({"XNGUSD"}), {}, dry_run=False,
            enqueue=lambda **k: (seen.append(k), ("id", True))[1])
    assert seen and all(k["family"] == "exogenous_conditioner" for k in seen)
    assert {k["params"]["signal"] for k in seen} == {"surprise", "surprise_z"}
