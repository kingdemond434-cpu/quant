# ruff: noqa: E501 -- fixtures reproduce the publishers' own long header lines
"""Global flow: parsers read the publishers' documented layouts, series are PIT-stamped after the
observation, refusals hard-stop, offline passes read only what is held, and every gap is named."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import global_flow as gf  # noqa: E402


def _snb(n: int = 40) -> str:
    lines = ['"CubeId";"snbgwdzid"', '"PublishingDate";"2026-11-02 09:00"', "",
             '"Date";"D0";"Value"']
    for i, d in enumerate(pd.date_range("2026-01-02", periods=n, freq="W-FRI")):
        lines.append(f'"{d.date()}";"GB";"{450000 + 100 * i}"')
        lines.append(f'"{d.date()}";"T0";"{470000 + 120 * i}"')
    return "\n".join(lines)


def _gld(n: int = 40) -> str:
    head = ("Date, GLD Close, LBMA Gold Price, NAV, Daily Share Volume,"
            " Total Net Asset Value Ounces in the Trust, Total Net Asset Value Tonnes in the Trust")
    rows = ["SPDR Gold Trust archive", head]
    for i, d in enumerate(pd.bdate_range("2026-01-02", periods=n)):
        rows.append(f"{d.strftime('%d-%b-%Y')},200.1,2000,199.9,{1000 + i},"
                    f"\"28,000,000\",{870.5 + 0.3 * i}")
    rows.append("01-Jan-2026,HOLIDAY,,,,,")
    return "\n".join(rows)


_NSE = """Participant wise Open Interest (no. of contracts) in Equity Derivatives as on Oct 30, 2026
Client Type,Future Index Long,Future Index Short,Future Stock Long,Future Stock Short\t,Option Index Call Long,Option Index Put Long,Option Index Call Short,Option Index Put Short,Option Stock Call Long,Option Stock Put Long,Option Stock Call Short,Option Stock Put Short,Total Long Contracts\t,Total Short Contracts
Client,300000,100000,2000000,500000,4000000,3000000,3500000,3800000,1,1,1,1,1,1
DII,50000,150000,100000,2500000,10,10,0,0,1,1,1,1,1,1
FII,100000,300000,1500000,1200000,500000,900000,400000,700000,1,1,1,1,1,1
Pro,80000,80000,300000,200000,2000000,2000000,2600000,2000000,1,1,1,1,1,1
TOTAL,530000,630000,3900000,4400000,1,1,1,1,1,1,1,1,1,1
"""


_MOF = """Weekly report,,,,,,
(100 million yen),Japanese investors' net purchases of foreign securities,,,Foreign investors' net purchases of Japanese securities,,
Week,Equity,Long-term,Short-term,Equity,Long-term,Short-term
2026.10.18~10.24,"1,200","-3,400",50,"2,300",-800,"1,000"
2026.10.25~10.31,-500,"4,100",-20,-900,600,-300
2026.12.27~1.2,10,20,30,40,50,60
"""


def test_snb_pivots_by_member():
    df = gf.parse_snb_cube(_snb())
    assert list(df.columns) == ["sight_gb", "sight_t0"]
    assert len(df) == 40 and df.index.is_monotonic_increasing


def test_gld_reads_tonnes_and_skips_holidays():
    df = gf.parse_gld_archive(_gld())
    assert len(df) == 40
    assert df["tonnes"].iloc[0] == pytest.approx(870.5)
    assert "share_volume" in df.columns


def test_nse_classes_and_retail_vs_fii():
    row = gf.parse_nse_participant_oi(_NSE)
    assert row["client_fi_net"] == pytest.approx((300000 - 100000) / 400000)
    assert row["fii_fi_net"] == pytest.approx((100000 - 300000) / 400000)
    assert row["client_minus_fii_fi"] == pytest.approx(1.0)
    assert "total_fi_net" not in row
    bull, bear = 4000000 + 3800000, 3000000 + 3500000
    assert row["client_opt_tilt"] == pytest.approx((bull - bear) / (bull + bear))


def test_nse_unknown_layout_reads_nothing():
    assert gf.parse_nse_participant_oi("garbage\n1,2,3") == {}


def test_mof_weekly_rows_and_year_wrap():
    df = gf.parse_mof_weekly(_MOF)
    assert list(df.index) == [pd.Timestamp("2026-10-24"), pd.Timestamp("2026-10-31"),
                              pd.Timestamp("2027-01-02")]
    assert df.loc["2026-10-24", "jp_out_ltdebt"] == -3400
    assert df.loc["2026-10-24", "net_yen_flow"] == pytest.approx((2300 - 800) - (1200 - 3400))


@pytest.fixture()
def tmp_raw(tmp_path, monkeypatch):
    monkeypatch.setattr(gf, "RAW", tmp_path / "raw")
    return tmp_path


def _reg(**over):
    src = {"id": "gld_holdings", "class": "etf", "region": "US", "adapter": "gld_archive",
           "url": "https://example.test/gld.csv", "avail_lag_days": 1, "avail_hour_utc": 6,
           "targets": ["XAUUSD"], "log_change_cols": ["tonnes"], **over}
    gap = {"id": "x_gap", "class": "retail", "region": "KR", "adapter": "none",
           "blocked_by": "reason"}
    return {"sources": [src, gap], "already_live": [{"id": "cot", "class": "institutional"}]}


def test_collect_stamps_after_observation(tmp_raw):
    notes: list = []
    built, frames = gf.collect(get=lambda url, **k: _gld(), state={}, notes=notes,
                               get_text=None, now=datetime(2026, 3, 1, tzinfo=UTC),
                               registry=_reg())
    f = frames["flow_gld_holdings"]
    assert built["flow_gld_holdings"]["kind"] == "flow_etf"
    ev = pd.to_datetime(f["event_time"], utc=True)
    av = pd.to_datetime(f["available_time"], utc=True)
    assert (av > ev).all()
    assert "tonnes_logchg" in f.columns and "tonnes_chg" in f.columns


def test_hard_stop_is_recorded_and_not_retried(tmp_raw):
    calls = []

    def refuse(url, **k):
        calls.append(url)
        raise gf.HardStop(403, url)
    state: dict = {}
    gf.collect(get=refuse, state=state, notes=[], registry=_reg())
    assert "gf_gld_holdings" in state["hard_stops"]
    gf.collect(get=refuse, state=state, notes=[], registry=_reg())
    assert len(calls) == 1


def test_offline_reads_only_held(tmp_raw):
    notes: list = []
    built, _ = gf.collect(get=None, state={}, notes=notes, registry=_reg())
    assert built == {} and notes[0]["status"] == "UNMEASURED"
    gf.collect(get=lambda url, **k: _gld(), state={}, notes=[], registry=_reg())
    built, _ = gf.collect(get=None, state={}, notes=[], registry=_reg())
    assert "flow_gld_holdings" in built


def test_nse_walks_days_and_remembers_holidays(tmp_raw):
    asked = []

    def get(url, **k):
        asked.append(url)
        if "31102026" in url:
            raise gf.Missing(url)
        return _NSE
    src = {"id": "nse_part_oi", "class": "retail", "adapter": "nse_daily",
           "url": "https://example.test/fao_participant_oi_{ddmmyyyy}.csv", "targets": ["USDINR"]}
    state: dict = {}
    gf.collect(get=get, state=state, notes=[], registry={"sources": [src]},
               now=datetime(2026, 11, 3, tzinfo=UTC))
    assert len(asked) == gf.NSE_DAYS_PER_PASS
    assert "2026-10-31" not in state["global_flow_nse_seen"]          # a Saturday: never asked
    first = len(asked)
    gf.collect(get=get, state=state, notes=[], registry={"sources": [src]},
               now=datetime(2026, 11, 3, tzinfo=UTC))
    assert not set(asked[first:]) & set(asked[:first])                # nothing asked twice


def test_shipped_registry_is_valid_and_gaps_are_named():
    reg = json.loads(gf.REGISTRY.read_text(encoding="utf-8"))
    for s in reg["sources"]:
        assert s["class"] in set(reg["player_classes"]), s["id"]
        assert s.get("region") in set(reg["regions"]), s["id"]
        if s["adapter"] == "none":
            assert s.get("blocked_by"), s["id"]
        else:
            assert s["adapter"] in {*gf.PARSERS, "nse_daily", "cb_hazard", "session_window"}, s["id"]
            assert s["targets"] and s.get("why")
    cov = gf.coverage(reg)
    assert cov["n_gaps"] == sum(1 for s in reg["sources"] if s["adapter"] == "none")
    universe = json.loads((DESK / "data" / "universe" / "universe.json").read_text())
    for s in reg["sources"]:
        for t in s.get("targets") or []:
            assert t in universe, (s["id"], t)


def test_grid_names_unsearched_cells():
    reg = {"player_classes": ["retail", "cta"], "regions": ["US", "JP"],
           "sources": [{"id": "a", "class": "retail", "region": "US", "adapter": "x"},
                       {"id": "b", "class": "cta", "region": "JP", "adapter": "none"}]}
    cov = gf.coverage(reg)
    assert sorted(cov["unsearched"]) == ["cta|US", "retail|JP"]
    assert cov["grid_cells"] == 4 and cov["grid_covered"] == 2


def test_first_seen_floors_recent_rows_and_keeps_backfill():
    idx = pd.Series(pd.to_datetime(["2026-01-03", "2026-10-31"]))
    rule = pd.Series(pd.to_datetime(["2026-01-08", "2026-11-05"], utc=True))
    state: dict = {}
    now = datetime(2026, 11, 6, 2, 0, tzinfo=UTC)          # late release: seen after the rule
    at = gf.first_seen_floor("mof_weekly", idx, rule, state, now)
    assert at.iloc[0] == rule.iloc[0]                       # back-fill keeps the rule time
    assert at.iloc[1] == pd.Timestamp(now)                  # recent row: never before first seen
    later = gf.first_seen_floor("mof_weekly", idx, rule, state, datetime(2026, 12, 1, tzinfo=UTC))
    assert later.iloc[1] == pd.Timestamp(now)               # the stamp never moves


def test_robots_disallow_is_a_label_not_a_stop(tmp_raw):
    notes: list = []
    built, _ = gf.collect(get=lambda url, **k: _gld(), state={}, notes=notes,
                          get_text=lambda url: "User-agent: *\nDisallow: /", registry=_reg())
    assert built["flow_gld_holdings"]["access_label"] == "PUBLIC_WITH_TERMS"
    assert any(n.get("access_label") == "PUBLIC_WITH_TERMS" for n in notes)


def test_intervention_hazard_is_causal_and_signed():
    idx = pd.date_range("2024-01-01", periods=400, freq="D")
    rng = np.random.default_rng(3)
    px = pd.Series(150 * np.exp(np.cumsum(rng.normal(0, 0.004, 400))), index=idx)
    px.iloc[-10:] = px.iloc[-11] * np.exp(np.linspace(0.01, 0.06, 10))   # a fast weak-side run
    h = gf.intervention_hazard(px, +1.0)
    assert h["ext252"].iloc[-1] == pytest.approx(1.0)
    assert h["speed5"].iloc[-1] > 2 and h["hazard"].iloc[-1] > 0.9
    cut = gf.intervention_hazard(px.iloc[:300], +1.0)
    pd.testing.assert_frame_equal(cut, h.iloc[:300])                   # no future leaks back
    mirrored = gf.intervention_hazard(px, -1.0)
    assert mirrored["ext252"].iloc[-1] == pytest.approx(-1.0)


def test_cb_hazard_runs_offline_from_desk_bars(tmp_raw):
    idx = pd.date_range("2024-01-01", periods=24 * 300, freq="h", tz="UTC")
    rng = np.random.default_rng(5)
    h1 = pd.DataFrame({"close": 150 * np.exp(np.cumsum(rng.normal(0, 0.001, len(idx))))},
                      index=idx)
    src = {"id": "cb_hazard_usdjpy", "class": "central_bank", "adapter": "cb_hazard",
           "pairs": [{"symbol": "USDJPY", "weak_side": 1}], "targets": ["USDJPY"],
           "avail_lag_days": 1, "avail_hour_utc": 0}
    _, frames = gf.collect(get=None, state={}, notes=[], registry={"sources": [src]},
                               bars=lambda s: h1 if s == "USDJPY" else None,
                               now=datetime(2024, 11, 1, tzinfo=UTC))
    f = frames["flow_cb_hazard_usdjpy"]
    assert "usdjpy_hazard" in f.columns
    assert (pd.to_datetime(f["available_time"], utc=True)
            > pd.to_datetime(f["event_time"], utc=True)).all()


def _h1(start: str, days: int, seed: int = 7) -> pd.DataFrame:
    """Broker-stamped H1 bars (New York + 7 h under a UTC label), weekends included."""
    idx = pd.date_range(start, periods=24 * days, freq="h", tz="UTC")
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.001, len(idx))))
    return pd.DataFrame({"open": np.r_[100.0, close[:-1]], "close": close,
                         "tick_volume": rng.integers(50, 500, len(idx)).astype(float)},
                        index=idx)


@pytest.mark.parametrize("start", ["2024-01-08", "2024-07-08"])      # US winter and summer
def test_session_window_reads_the_markets_own_clock(start):
    from libs.regime import session_clock
    h1 = _h1(start, 30)
    w = gf.session_window(h1, "Asia/Shanghai", 21, 2)
    # Beijing has no DST: 21:00-02:00 there is 13:00-18:00 UTC on every date, whichever
    # offset the broker stamp carries that week.
    assert set(w["win_close_utc"].dt.hour) == {18}
    last = w.index[-1]
    utc = session_clock.server_to_utc(h1.index).tz_localize(None)
    inside = (utc >= last + pd.Timedelta(hours=13)) & (utc < last + pd.Timedelta(hours=18))
    assert inside.sum() == 5
    seg = h1[inside]
    assert w["win_ret"].iloc[-1] == pytest.approx(
        np.log(seg["close"].iloc[-1] / seg["open"].iloc[0]))
    assert 0 < w["win_path_share"].iloc[-1] < 1 and 0 < w["win_vol_share"].iloc[-1] < 1


def test_session_window_follows_local_dst_and_is_causal():
    h1 = _h1("2024-01-08", 300)
    w = gf.session_window(h1, "Europe/London", 15, 16)
    hours = w["win_close_utc"].dt.hour
    assert set(hours[w.index < "2024-03-25"]) == {16}        # GMT: 16:00 London = 16:00 UTC
    assert set(hours[(w.index > "2024-04-07") & (w.index < "2024-10-20")]) == {15}    # BST
    cut = gf.session_window(h1.iloc[: 24 * 200], "Europe/London", 15, 16)
    both = cut.index.intersection(w.index)
    pd.testing.assert_frame_equal(cut.loc[both], w.loc[both])     # later bars change nothing


def test_session_window_source_is_stamped_after_the_window_closes(tmp_raw):
    h1 = _h1("2024-01-08", 200)
    src = {"id": "cn_night_session", "class": "retail", "adapter": "session_window",
           "tz": "Asia/Shanghai", "start_hour": 21, "end_hour": 2, "symbols": ["XAUUSD", "NOPE"],
           "targets": ["XAUUSD"], "avail_lag_days": 0, "avail_hour_utc": 19}
    notes: list = []
    _, frames = gf.collect(get=None, state={}, notes=notes, registry={"sources": [src]},
                           bars=lambda s: h1 if s == "XAUUSD" else None,
                           now=datetime(2024, 11, 1, tzinfo=UTC))
    f = frames["flow_cn_night_session"]
    assert {"xauusd_win_ret", "xauusd_win_path_share", "xauusd_win_vol_share"} <= set(f.columns)
    assert not any("win_close_utc" in c for c in f.columns)
    lead = pd.to_datetime(f["available_time"], utc=True) - pd.to_datetime(f["event_time"], utc=True)
    assert (lead >= pd.Timedelta(hours=19)).all()            # the window closed at 18:00 UTC
    assert {"source": "cn_night_session", "symbol": "NOPE", "status": "NO_BARS"} in notes


def test_shipped_session_windows_are_stamped_after_their_close():
    from zoneinfo import ZoneInfo
    reg = json.loads(gf.REGISTRY.read_text(encoding="utf-8"))
    rows = [s for s in reg["sources"] if s["adapter"] == "session_window"]
    assert {s["id"] for s in rows} >= {"cn_night_session"}
    for s in rows:
        assert s["avail_lag_days"] == 0
        for day in ("2024-01-15", "2024-07-15"):                  # both DST states
            end = datetime.fromisoformat(f"{day}T{int(s['end_hour']):02d}:00").replace(
                tzinfo=ZoneInfo(s["tz"])).astimezone(UTC)
            assert s["avail_hour_utc"] > end.hour, s["id"]
