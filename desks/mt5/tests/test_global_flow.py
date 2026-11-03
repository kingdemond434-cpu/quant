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


def _cboe(spot: float = 5000.0) -> str:
    opts = []
    for k in range(4500, 5501, 50):
        opts.append({"option": f"SPX261120C0{k}000", "gamma": 0.001, "open_interest": 1000,
                     "volume": 10})
        opts.append({"option": f"SPX261120P0{k}000", "gamma": 0.002 if k < 4900 else 0.0005,
                     "open_interest": 1500, "volume": 20})
    return json.dumps({"timestamp": "2026-11-03 16:15:00",
                       "data": {"current_price": spot, "options": opts}})


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


def test_cboe_gamma_sign_and_ratios():
    snap = gf.parse_cboe_chain(_cboe())
    assert snap["spot"] == 5000.0
    assert snap["pc_oi"] == pytest.approx(1.5)
    assert snap["pc_vol"] == pytest.approx(2.0)
    assert np.isfinite(snap["gex_bn"]) and np.isfinite(snap["gex_near_bn"])
    assert snap["gex_bn"] < 0           # heavy put gamma below spot: dealers short gamma


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
            assert s["adapter"] in {*gf.PARSERS, "nse_daily", "cboe_snapshot"}, s["id"]
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
