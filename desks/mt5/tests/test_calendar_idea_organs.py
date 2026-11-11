"""B20 session-handoff gaps, B11 non-Western holidays, B13 Treasury auction results.

WHAT THIS PINS, on synthetic bars and recorded rows only (this container reaches no publisher):
  * B20: `overnight_gap_decay` with no `handoff` is the first-bar rule it always was; with one it
    fades the incoming region's own overnight gap at its local cash open, drops a date whose bar
    clock is unmeasured, sees no future, and the replication lane refuses to rebuild it as asia;
  * B11: Lunar New Year rows come from the official GovHK table only, on the Hong Kong local day,
    labelled with their URL; Diwali and Ramadan/Eid with no official row are UNMEASURED by name;
    `event_prefix` narrows `holiday_liquidity` to one region;
  * B13: the FiscalData rows become a stamped series (coupons only, tail = high minus median,
    bid-to-cover surprise against earlier same-term auctions only); robots refusal is UNMEASURED;
    the conditioner's event stance fires once per published value inside its window;
  * the specialist catalogue mints all three with the right sides and culture, every cell is
    buildable, and the fetch is an hourly leg with a budget and a layer.
"""
from __future__ import annotations

import json
import sys
import urllib.robotparser
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK / "scripts"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families_orthogonal as fo  # noqa: E402
from mt5desk import family_exogenous_conditioner as fx  # noqa: E402
from mt5desk import family_forced_flow as ffl  # noqa: E402

from libs.research import bar_clock  # noqa: E402
from research import forced_flow_calendar as C  # noqa: E402
from research import specialist_cell as sc  # noqa: E402
from research import ust_auction_results as uar  # noqa: E402


def _bars(start: str = "2026-01-05", days: int = 60, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=24 * days, freq="h", tz="UTC")
    idx = idx[idx.dayofweek < 5]
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, len(idx))))
    o = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, close) * 1.001,
                         "low": np.minimum(o, close) * 0.999, "close": close}, index=idx)


def _identity_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bars stamped in true UTC: the measured offset is zero for this test only."""
    monkeypatch.setattr(bar_clock, "to_bar_time", lambda when, *a, **k: (when, "CONVERTED", ""))


def _first_bar_reference(df: pd.DataFrame, gap_atr: float = 0.75, atr_n: int = 20,
                         stop_atr: float = 1.5, rr: float = 1.0, ttl_bars: int = 8) -> list:
    """The pre-B20 body, copied verbatim in logic: the default path must still be exactly this."""
    d = fo._h1(df)
    atr = fo._atr(d, atr_n).to_numpy()
    day = pd.Series(d.index.date, index=d.index)
    first = (day != day.shift(1)).to_numpy()
    out = []
    for i in range(atr_n, len(d) - 1):
        a = float(atr[i])
        if not first[i] or not np.isfinite(a) or a <= 0:
            continue
        gap = float(d["open"].iloc[i]) - float(d["close"].iloc[i - 1])
        if abs(gap) < gap_atr * a:
            continue
        side = -1 if gap > 0 else 1
        px = float(d["open"].iloc[i])
        out.append((d.index[i], side, px - side * stop_atr * a, px + side * abs(gap) * rr))
    return out


# ---------------------------------------------------------------------------------- B20 ---
def test_default_gap_decay_is_unchanged_and_handoff_is_opt_in():
    df = _bars()
    # plant overnight gaps so the default rule fires
    df.loc[df.index.hour == 0, "open"] *= 1.01
    got = [(s.time, s.side, s.stop, s.target) for s in fo.family_overnight_gap_decay(df)]
    assert got == _first_bar_reference(df) and got
    assert [s.tag for s in fo.family_overnight_gap_decay(df, handoff="")] == \
        ["overnight_gap_decay"] * len(got)
    assert fo.family_overnight_gap_decay(df, handoff="no_such_handoff") == []


@pytest.mark.parametrize("handoff,zone,open_hm", [("asia_europe", "Europe/London", (8, 0)),
                                                  ("europe_us", "America/New_York", (9, 30))])
def test_handoff_fades_the_regions_own_overnight_gap(monkeypatch, handoff, zone, open_hm):
    _identity_clock(monkeypatch)
    df = _bars(start="2026-01-05", days=40)
    day = date(2026, 2, 3)                                  # a Tuesday, winter in both zones
    open_utc = pd.Timestamp(datetime(day.year, day.month, day.day, *open_hm,
                                     tzinfo=ZoneInfo(zone))).tz_convert("UTC")
    bar_k = df.index[df.index.searchsorted(open_utc, side="right") - 1]
    # lift every bar from the region's previous close up to and including the open bar
    prev_close = pd.Timestamp(datetime(2026, 2, 2, *fo.HANDOFF_WINDOWS[handoff][2],
                                       tzinfo=ZoneInfo(zone))).tz_convert("UTC")
    lift = (df.index >= prev_close) & (df.index <= bar_k)
    for c in ("open", "high", "low", "close"):
        df.loc[lift, c] = df.loc[lift, c] * 1.03
    sigs = fo.family_overnight_gap_decay(df, handoff=handoff)
    hit = [s for s in sigs if s.time == bar_k]
    assert len(hit) == 1 and hit[0].side == -1             # faded back down
    assert hit[0].tag == f"overnight_gap_decay.{handoff}" and hit[0].wait_bars == 1
    assert hit[0].target < hit[0].stop
    # one decision per business day at most
    assert len({s.time.date() for s in sigs}) == len(sigs)


def test_handoff_drops_dates_whose_bar_clock_is_unmeasured(monkeypatch):
    monkeypatch.setattr(bar_clock, "to_bar_time", lambda when, *a, **k: (None, "UNMEASURED", ""))
    df = _bars()
    df["open"] = df["open"] * np.where(np.arange(len(df)) % 24 == 8, 1.02, 1.0)
    assert fo.family_overnight_gap_decay(df, handoff="asia_europe") == []


def test_handoff_sees_no_future(monkeypatch):
    _identity_clock(monkeypatch)
    df = _bars(days=80, seed=3)
    cut = df.index[len(df) // 2]
    later = df.copy()
    m = later.index >= cut
    later.loc[m, ["open", "high", "low", "close"]] *= 1.07
    before = [(s.time, s.side, round(s.stop, 9), round(s.target, 9))
              for s in fo.family_overnight_gap_decay(df, handoff="europe_us", gap_atr=0.3)
              if s.time < cut - pd.Timedelta(hours=1)]
    after = [(s.time, s.side, round(s.stop, 9), round(s.target, 9))
             for s in fo.family_overnight_gap_decay(later, handoff="europe_us", gap_atr=0.3)
             if s.time < cut - pd.Timedelta(hours=1)]
    assert before == after and before


def test_replication_refuses_to_rebuild_a_handoff_cell_as_the_first_bar_rule():
    from research import replication_civilization as rc
    p, why = rc.resolve_spec("overnight_gap_decay", {"handoff": "asia_europe"}, None, None)
    assert p is None and "handoff" in why
    p, why = rc.resolve_spec("overnight_gap_decay", {"gap_atr": 0.5}, "asia", None)
    assert p is not None and why == "ok"


# ---------------------------------------------------------------------------------- B11 ---
def test_lunar_new_year_rows_are_official_local_day_and_labelled():
    rows = [e for e in C.events(date(2026, 1, 1), date(2027, 12, 31))
            if e.name.startswith("hk_lny_holiday_")]
    assert {e.date for e in rows} == {date(2026, 2, 17), date(2026, 2, 18), date(2026, 2, 19),
                                      date(2027, 2, 6), date(2027, 2, 8), date(2027, 2, 9)}
    first = next(e for e in rows if e.date == date(2026, 2, 17))
    assert first.kind == "holiday_liquidity"
    assert first.window_start_utc == datetime(2026, 2, 16, 16, 0, tzinfo=ZoneInfo("UTC"))
    assert "https://www.gov.hk/en/about/abouthk/holiday/2026.htm" in first.source_rule
    assert set(first.instruments) <= set(C._registry())
    assert "HK50" in first.instruments and "USDCNH" in first.instruments
    # no LNY row is invented for a year GovHK was not read for
    assert not [e for e in C.events(date(2025, 1, 1), date(2025, 12, 31))
                if e.name.startswith("hk_lny_")]


def test_diwali_and_eid_without_official_rows_are_unmeasured_by_name():
    gap = C.unmeasured_holidays(date(2025, 1, 1), date(2027, 12, 31))
    assert gap["in_diwali"]["missing_years"] == [2025, 2026, 2027]
    assert gap["gulf_eid"]["missing_years"] == [2025, 2026, 2027]
    assert gap["hk_lny"]["missing_years"] == [2025]
    assert not [e for e in C.events(date(2025, 1, 1), date(2027, 12, 31))
                if e.name.startswith(("in_diwali", "gulf_eid"))]
    payload = C.build(today=date(2026, 11, 11))
    assert "in_diwali" in payload["unmeasured"]["holiday_years"]


def test_event_prefix_narrows_holiday_liquidity_to_one_region(monkeypatch, tmp_path):
    monkeypatch.setattr(ffl, "CALENDAR_PATH", tmp_path / "absent.json")
    idx = pd.date_range("2026-01-02", "2026-03-31", freq="h", tz="UTC")
    rng = np.random.default_rng(5)
    close = 7.8 * np.exp(np.cumsum(rng.normal(0, 0.001, len(idx))))
    o = np.r_[close[0], close[:-1]]
    df = pd.DataFrame({"open": o, "high": np.maximum(o, close), "low": np.minimum(o, close),
                       "close": close}, index=idx)
    narrow = ffl.family_forced_flow(df, event_kind="holiday_liquidity", symbol="USDHKD",
                                    mode="pre_flow", event_prefix="hk_lny_holiday_")
    broad = ffl.family_forced_flow(df, event_kind="holiday_liquidity", symbol="USDHKD",
                                   mode="pre_flow")
    assert narrow and len(broad) > len(narrow)
    assert {s.time.date() for s in narrow} <= {date(2026, 2, 16), date(2026, 2, 17),
                                               date(2026, 2, 18)}


# ---------------------------------------------------------------------------------- B13 ---
def _api_row(cusip, day, term, hy, med, btc, stype="Note", close="01:00 PM", **kw):
    return {"cusip": cusip, "auction_date": day, "security_term": term, "security_type": stype,
            "high_yield": hy, "avg_med_yield": med, "bid_to_cover_ratio": btc,
            "closing_time_comp": close, **kw}


ROWS = [
    _api_row("A1", "2026-01-06", "3-Year", "3.500", "3.450", "2.60"),
    _api_row("A2", "2026-02-03", "3-Year", "3.600", "3.560", "2.40"),
    _api_row("A3", "2026-03-03", "3-Year", "3.550", "3.540", "2.80"),
    _api_row("A4", "2026-04-07", "3-Year", "3.700", "3.640", "2.20"),
    _api_row("B1", "2026-04-08", "10-Year", "4.200", "4.150", "2.50"),
    _api_row("T1", "2026-04-09", "26-Week", "4.000", "3.990", "3.10", stype="Bill"),
    _api_row("P1", "2026-04-10", "5-Year TIPS", "1.900", "1.850", "2.40", tips="Yes"),
    _api_row("N1", "2026-05-12", "10-Year", "null", "null", "null"),      # announced only
    _api_row("C1", "2026-04-14", "7-Year", "4.000", "3.980", "2.55", close=""),
]


def test_normalise_keeps_coupons_stamps_honestly_and_trails_only_the_past():
    rows, counts = uar.normalise(ROWS, datetime(2026, 11, 11, tzinfo=ZoneInfo("UTC")))
    assert [r["cusip"] for r in rows] == ["A1", "A2", "A3", "A4", "B1", "C1"]
    assert counts["not_coupon"] == 2 and counts["no_result_yet"] == 1
    assert counts["close_time_fallback"] == 1
    a4 = next(r for r in rows if r["cusip"] == "A4")
    assert a4["tail_bp"] == pytest.approx(6.0)
    assert a4["btc_surprise"] == pytest.approx(2.20 - (2.60 + 2.40 + 2.80) / 3)
    assert a4["available_time"] == "2026-04-07T17:30:00+00:00"   # 13:00 EDT + 30 min
    assert [r["btc_surprise"] for r in rows if r["security_term"] == "3-Year"][:3] == [None] * 3
    assert next(r for r in rows if r["cusip"] == "B1")["btc_surprise"] is None
    c1 = next(r for r in rows if r["cusip"] == "C1")
    assert c1["available_time"] == "2026-04-14T21:30:00+00:00"   # 17:00 EDT fallback + 30


def _paths(monkeypatch, tmp_path):
    monkeypatch.setattr(uar, "SERIES", tmp_path / "series" / "ust_auction_results.csv")
    monkeypatch.setattr(uar, "RAW", tmp_path / "raw" / "auctions.json")
    monkeypatch.setattr(uar, "OUT", tmp_path / "UST_AUCTION_RESULTS.json")


def test_run_writes_the_series_the_conditioner_reads(monkeypatch, tmp_path):
    _paths(monkeypatch, tmp_path)
    monkeypatch.setattr(uar.time, "sleep", lambda s: None)
    calls = []

    def get(url):
        calls.append(url)
        return json.dumps({"data": ROWS, "meta": {"total-pages": 1}}).encode(), "HTTP 200"
    doc = uar.run(get=get, now=datetime(2026, 11, 11, tzinfo=ZoneInfo("UTC")))
    assert doc["status"] == "MEASURED" and doc["coupon_results"] == 6 and len(calls) == 1
    assert doc["columns"]["tail_bp"]["tail_kind"] == "high_minus_median"
    frame = pd.read_csv(uar.SERIES)
    assert {"available_time", "tail_bp", "btc_surprise"} <= set(frame.columns)
    s = fx.conditioner("ust_auction_results", "tail_bp", "raw", lag_hours=12,
                       root=uar.SERIES.parent)
    assert s is not None and len(s) == 6
    assert s.index[0] == pd.Timestamp("2026-01-07T06:30:00Z")     # 13:30 EST + 12 h lag
    again = uar.run(get=get, now=datetime(2026, 11, 11, 1, tzinfo=ZoneInfo("UTC")))
    assert again["fetch"]["status"] == "NOT_DUE" and len(calls) == 1
    assert again["coupon_results"] == 6                            # rebuilt from the raw store


def test_robots_refusal_is_unmeasured_and_writes_no_series(monkeypatch, tmp_path):
    from research import index_discovery as idx
    _paths(monkeypatch, tmp_path)
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(["User-agent: *", "Disallow: /services"])
    monkeypatch.setattr(idx, "_ROBOTS", {"https://api.fiscaldata.treasury.gov": rp})
    opened = []
    monkeypatch.setattr(uar.urllib.request, "urlopen", lambda *a, **k: opened.append(a))
    doc = uar.run(now=datetime(2026, 11, 11, tzinfo=ZoneInfo("UTC")))
    assert doc["status"] == "UNMEASURED" and "REFUSED" in str(doc["fetch"].get("why"))
    assert not opened and not uar.SERIES.exists()


def test_event_stance_fires_once_per_value_inside_its_window(tmp_path):
    n = 60
    stamps = pd.date_range("2025-06-02 17:30", periods=n, freq="7D", tz="UTC")
    vals = np.r_[np.zeros(n - 3), [5.0, -5.0, 0.0]]
    vals[: n - 3] = np.random.default_rng(1).normal(0, 0.1, n - 3)
    pd.DataFrame({"available_time": stamps.astype(str), "tail_bp": vals}).to_csv(
        tmp_path / "ust_auction_results.csv", index=False)
    idx = pd.date_range(pd.Timestamp("2025-05-01", tz="UTC"), stamps[-1] + pd.Timedelta(days=5),
                        freq="h")
    close = 100 + np.sin(np.arange(len(idx)) / 10.0)
    o = np.r_[close[0], close[:-1]]
    df = pd.DataFrame({"open": o, "high": np.maximum(o, close) + 0.1,
                       "low": np.minimum(o, close) - 0.1, "close": close}, index=idx)
    kw = {"source": "ust_auction_results", "signal": "tail_bp", "transform": "level_z",
          "threshold": 2.0, "lag_hours": 12, "series_root": tmp_path, "side_when_high": -1}
    ev = fx.family_exogenous_conditioner(df, event_window_hours=12, **kw)
    assert [s.side for s in ev] == [-1, 1]
    assert ev[0].time == stamps[-3] + pd.Timedelta(hours=12) and ev[0].wait_bars == 1
    standing = fx.family_exogenous_conditioner(df, **kw)            # default: unchanged mode
    assert len(standing) > len(ev)


# ------------------------------------------------------------------------- the catalogue ---
def test_catalogue_mints_all_three_buildable_with_their_priors():
    from research.gauntlet_buildability import BUILDABLE, cell_verdict
    cells = sc.plan({"fx": ["EURUSD", "USDJPY", "USDHKD"], "indices": ["US500", "HK50",
                                                                       "JPN225"]})
    by = {(c["symbol"], c["mechanism"]): c for c in cells}
    assert {(c["symbol"], c["params"]["handoff"]) for c in cells
            if c["mechanism"] == "session_handoff_gap"} == {
        (s, h) for s in ("EURUSD", "USDJPY", "USDHKD", "US500", "HK50", "JPN225")
        for h in ("asia_europe", "europe_us")}
    assert all(c["family"] == "overnight_gap_decay" for c in cells
               if c["mechanism"] == "session_handoff_gap")
    assert ("USDHKD", "lunar_new_year_liquidity") in by
    assert ("HK50", "lunar_new_year_liquidity") in by
    assert ("JPN225", "golden_week_liquidity") in by and ("USDJPY", "golden_week_liquidity") in by
    assert ("EURUSD", "lunar_new_year_liquidity") not in by
    assert by[("HK50", "lunar_new_year_liquidity")]["source_culture"] == "CN"
    assert by[("JPN225", "golden_week_liquidity")]["source_culture"] == "JP"
    sides = {(c["symbol"], c["params"]["signal"]): c["params"]["side_when_high"]
             for c in cells if c["mechanism"] == "ust_auction_result"}
    assert sides == {("US500", "tail_bp"): -1, ("US500", "btc_surprise"): 1,
                     ("USDJPY", "tail_bp"): 1, ("USDJPY", "btc_surprise"): -1,
                     ("EURUSD", "tail_bp"): -1, ("EURUSD", "btc_surprise"): 1}
    assert not [c for c in cells if c["mechanism"] == "ust_auction_result"
                and c["symbol"] in ("USDHKD", "HK50")]
    new = [c for c in cells if c["mechanism"] in ("session_handoff_gap", "ust_auction_result",
                                                  "lunar_new_year_liquidity",
                                                  "golden_week_liquidity")]
    assert {cell_verdict(c["family"], c["params"])[0] for c in new} == {BUILDABLE}
    assert all(c["prior"] for c in new)
    idents = [sc.identity(c["symbol"], c["family"], c["params"]) for c in new]
    assert len(idents) == len(set(idents))                      # no duplicate hypothesis


def test_the_fetch_is_an_hourly_leg_with_a_budget_and_a_layer():
    from libs.research.layers import LEG_LAYER
    from research import hourly_cycle as hc
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    for leg in ("ust_auction_results", "specialist_cell", "forced_flow_calendar"):
        assert f'_costed("{leg}"' in src
        assert leg in hc.LEG_BUDGET_SEC or leg == "forced_flow_calendar"
        assert leg in LEG_LAYER
