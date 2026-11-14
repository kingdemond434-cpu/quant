"""The flow families and their seeder: COT (legacy/TFF/disaggregated), the tape's signed-tick
imbalance and the opex calendar reach the judge, causally, on synthetic data only."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families_flow as ff  # noqa: E402
from mt5desk import families_orthogonal as fo  # noqa: E402
from mt5desk import families_specialist as fs  # noqa: E402

from research import flow_seeder as fsd  # noqa: E402
from research import specialist_cell as sc  # noqa: E402


def _bars(days: int = 2200, start: str = "2015-01-05", seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=days, tz="UTC")
    idx = pd.DatetimeIndex([d + pd.Timedelta(hours=h) for d in dates for h in range(24)])
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.002, len(idx))))
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.0005,
                         "low": np.minimum(open_, close) * 0.9995, "close": close,
                         "tick_volume": 100}, index=idx)


@pytest.fixture()
def cot_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A TFF file for market `mkt`: weekly Tuesday reports with a random-walk lev-money net."""
    rng = np.random.default_rng(7)
    tuesdays = pd.date_range("2014-01-07", "2023-06-27", freq="W-TUE", tz="UTC")
    lm = np.zeros(len(tuesdays))
    for i in range(1, len(lm)):                              # a stationary AR(1) positioning
        lm[i] = 0.9 * lm[i - 1] + rng.normal(0, 8000)
    df = pd.DataFrame({"report_date": tuesdays, "oi": 400_000.0,
                       "lm_l": lm + 150_000, "lm_s": 100_000.0,
                       "am_l": 1.0, "am_s": 1.0, "dealer_l": 1.0, "dealer_s": 1.0})
    (tmp_path / "cot_tff").mkdir()
    df.to_parquet(tmp_path / "cot_tff" / "mkt.parquet")
    monkeypatch.setattr(ff, "DATA", tmp_path)
    ff._cot_cached.cache_clear()
    return tmp_path


# ------------------------------------------------------------------------------------- COT ---
def test_cot_report_enters_only_after_release_and_flips_for_the_quote_side(cot_store: Path
                                                                           ) -> None:
    d = _bars()
    kw = {"report": "tff", "market": "mkt", "group": "lev_money", "lookback_w": 52, "q": 0.2}
    fade = ff.family_cot_report(d, mode="extreme_fade", **kw)
    follow = ff.family_cot_report(d, mode="extreme_follow", **kw)
    flipped = ff.family_cot_report(d, mode="extreme_fade", sign=-1, **kw)
    assert len(fade) > 60
    usable = set(ff.cot_net_share("tff", "mkt", "lev_money").index)
    for s in fade:
        # every entry sits on or after a report's usable instant: the Monday after a normal
        # Friday release, the Wednesday in a federal-holiday week (market_calendar, MF3)
        assert any(pd.Timedelta(0) <= s.time - u <= pd.Timedelta(days=4) for u in usable)
        assert pd.Timestamp(s.time).dayofweek in (0, 2) and s.wait_bars == 1
    assert [s.side for s in fade] == [-s.side for s in follow]
    assert [s.side for s in fade] == [-s.side for s in flipped]


def test_cot_report_sees_no_future(cot_store: Path) -> None:
    d = _bars()
    kw = {"report": "tff", "market": "mkt", "group": "lev_money", "mode": "change_follow",
          "lookback_w": 52, "z_thr": 1.0}
    base = ff.family_cot_report(d, **kw)
    cut = pd.Timestamp("2019-06-01", tz="UTC")
    p = cot_store / "cot_tff" / "mkt.parquet"
    df = pd.read_parquet(p)
    late = df["report_date"] >= cut
    df.loc[late, "lm_l"] = df.loc[late, "lm_l"][::-1].to_numpy() * 3.0      # rewrite the future
    df.to_parquet(p)
    ff._cot_cached.cache_clear()
    d2 = d.copy()
    d2.loc[d2.index >= cut, "close"] *= 1.5
    after = ff.family_cot_report(d2, **kw)
    early = [(s.time, s.side) for s in base if s.time < cut]
    assert early and early == [(s.time, s.side) for s in after if s.time < cut]


def test_cot_report_refuses_what_it_cannot_read(cot_store: Path) -> None:
    d = _bars(300)
    assert ff.family_cot_report(d, report="tff", market="absent", group="lev_money") == []
    assert ff.family_cot_report(d, report="tff", market="mkt", group="noncomm") == []
    assert ff.family_cot_report(d, report="nope", market="mkt", group="lev_money") == []
    assert ff.family_cot_report(d, report="tff", market="../x", group="lev_money") == []


def test_cot_positioning_has_an_in_tree_fallback_lagged_and_signed(tmp_path: Path,
                                                                    monkeypatch: pytest.MonkeyPatch
                                                                    ) -> None:
    from mt5desk import data as mdata

    from research import orthogonal_sweep as osw
    tuesdays = pd.date_range("2020-01-07", periods=80, freq="W-TUE", tz="UTC")
    pd.DataFrame({"report_date": tuesdays, "noncomm_positions_long_all": 10.0,
                  "noncomm_positions_short_all": 4.0}).to_parquet(tmp_path / "jpy.parquet")
    monkeypatch.setattr(mdata, "_COT", tmp_path)
    got = osw._cot_frame_in_tree("USDJPY")
    from mt5desk.market_calendar import cot_usable_index
    assert got is not None and got.index.equals(cot_usable_index(tuesdays))
    lag = got.index - tuesdays
    assert set(lag) <= {pd.Timedelta(days=6), pd.Timedelta(days=8)} and pd.Timedelta(days=8) in set(lag)
    assert (got["net"] == -6.0).all()                     # long yen futures = short USDJPY
    assert osw._cot_frame_in_tree("NOPE") is None


def test_the_raw_cot_families_are_buildable_by_the_sealed_gauntlets_own_branch() -> None:
    from research import gauntlet_buildability as gb
    supplied = gb.supplied_families()
    assert {"cot_net_fade", "cot_change_fade", "cot_change_momentum",
            "cot_comm_follow"} <= supplied
    for fam in ("cot_net_fade", "cot_comm_follow", "cot_report", "expiry_gamma"):
        assert gb.cell_verdict(fam, {})[0] == gb.BUILDABLE
    assert gb.information_class("cot_report") == gb.EXOGENOUS
    assert gb.information_class("expiry_gamma") == gb.PRICE_ONLY


# ---------------------------------------------------------------------------- expiry gamma ---
def test_third_friday_and_the_expiry_sets() -> None:
    assert ff.third_friday(2026, 3) == date(2026, 3, 20)
    assert ff.third_friday(2026, 11) == date(2026, 11, 20)
    assert ff.third_friday(2024, 11) == date(2024, 11, 15)
    lo, hi = date(2026, 1, 1), date(2026, 12, 31)
    quad = ff.expiry_days(lo, hi, "quad", 0, 0)
    monthly = ff.expiry_days(lo, hi, "monthly", 0, 0)
    assert len(quad) == 4 and len(monthly) == 8 and not quad & monthly
    assert ff.expiry_days(lo, hi, "all", 1, 1) == {ff.add_weekdays(ff.third_friday(2026, m), 1)
                                                    for m in range(1, 13)}
    assert ff.add_weekdays(date(2026, 3, 20), -4) == date(2026, 3, 16)


def test_expiry_gamma_fires_only_on_its_window_and_sees_no_future() -> None:
    d = _bars(1500, start="2019-01-07")
    sigs = ff.family_expiry_gamma(d, expiry="quad", day_from=-4, day_to=0,
                                  decision_hour=16, direction="follow")
    days = ff.expiry_days(date(2019, 1, 1), date(2025, 12, 31), "quad", -4, 0)
    assert sigs and all(pd.Timestamp(s.time).date() in days for s in sigs)
    assert all(pd.Timestamp(s.time).hour == 16 for s in sigs)
    cut = pd.Timestamp("2021-07-01", tz="UTC")
    d2 = d.copy()
    d2.loc[d2.index >= cut, "close"] *= 0.5
    again = ff.family_expiry_gamma(d2, expiry="quad", day_from=-4, day_to=0,
                                   decision_hour=16, direction="follow")
    assert ([(s.time, s.side) for s in sigs if s.time < cut]
            == [(s.time, s.side) for s in again if s.time < cut])
    post = ff.family_expiry_gamma(d, expiry="all", day_from=0, day_to=0, direction="long",
                                  era="post_2022")
    assert post and all(pd.Timestamp(s.time).date() >= ff.ERA_SPLIT and s.side == 1
                        for s in post)
    assert ff.family_expiry_gamma(d, expiry="weekly") == []


def test_strike_pin_trades_toward_the_grid_only_before_comex_gold_expiry() -> None:
    assert ff.comex_gold_option_expiry(2026, 11) == date(2026, 11, 24)   # Nov 30 Mon - 4
    assert ff.comex_gold_option_expiry(2026, 1) == date(2026, 1, 27)     # 4th last bd of Jan
    d = _bars(1500, start="2019-01-07") * 20.0                           # ~2000: a $25 grid
    pin = ff.family_strike_pin(d, day_from=-3, day_to=0, mode="pin", max_frac=0.5)
    unpin = ff.family_strike_pin(d, day_from=-3, day_to=0, mode="unpin", max_frac=0.5)
    assert pin and [s.side for s in pin] == [-s.side for s in unpin]
    for s in pin:
        day = pd.Timestamp(s.time).date()
        e = ff.comex_gold_option_expiry(day.year, day.month)
        assert day in {ff.add_weekdays(e, k) for k in range(-3, 1)}
        px = float(d.loc[s.time, "close"])
        assert s.side == (1 if round(px / 25) * 25 > px else -1)
    cut = pd.Timestamp("2021-07-01", tz="UTC")
    d2 = d.copy()
    d2.loc[d2.index >= cut, "close"] *= 0.5
    again = ff.family_strike_pin(d2, day_from=-3, day_to=0, mode="pin", max_frac=0.5)
    assert ([(s.time, s.side) for s in pin if s.time < cut]
            == [(s.time, s.side) for s in again if s.time < cut])
    assert ff.family_strike_pin(d, grid=0) == [] and ff.family_strike_pin(d, mode="x") == []


# ------------------------------------------------------------------------- the tick tape ---
@pytest.fixture()
def tape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> pd.DataFrame:
    """Silver days for XAUUSD whose ticks lean up in hours 10-11 of every day."""
    rng = np.random.default_rng(3)
    d = _bars(40, start="2026-09-07")
    root = tmp_path / "ticks"
    (root / "XAUUSD").mkdir(parents=True)
    for day in pd.bdate_range("2026-09-07", periods=40, tz="UTC"):
        ts = day + pd.to_timedelta(np.sort(rng.uniform(0, 86_400, 6000)), unit="s")
        drift = np.where(np.isin(ts.hour, (10, 11)), 0.004, 0.0)
        mid = 100 + np.cumsum(rng.normal(0, 0.01, len(ts)) + drift)
        pd.DataFrame({"ts": ts, "bid": mid - 0.01, "ask": mid + 0.01}).to_parquet(
            root / "XAUUSD" / f"{day.date().isoformat()}.parquet")
    monkeypatch.setattr(ff, "TAPE_SILVER", root)
    ff._tape_flow_cached.cache_clear()
    return d


def test_tape_flow_is_a_bounded_per_bar_imbalance_never_forward_filled(tape: pd.DataFrame
                                                                       ) -> None:
    flow = ff.tape_flow_for(tape, "XAUUSD")
    assert flow is not None and flow.notna().sum() > 500
    assert float(flow.abs().max()) <= 1.0
    hourly = flow.groupby(flow.index.hour).mean()
    assert hourly.loc[10] > hourly.drop([10, 11]).max()
    gap = tape.copy()
    extra = pd.Timestamp("2027-01-04", tz="UTC")
    gap.loc[extra] = gap.iloc[-1]
    assert np.isnan(ff.tape_flow_for(gap.sort_index(), "XAUUSD").loc[extra])
    assert ff.tape_flow_for(tape, "NOPE") is None
    assert ff.tape_flow_for(tape, "../XAUUSD") is None


def test_orderflow_imbalance_loads_the_whole_tape_itself(tape: pd.DataFrame) -> None:
    sigs = fo.family_orderflow_imbalance(tape, flow=None, symbol="XAUUSD",
                                         flow_source="tape_signed_ticks", lookback=24, z_in=1.5)
    assert sigs and all(s.tag == "orderflow_imbalance" and s.wait_bars == 1 for s in sigs)
    # older than the thirty newest silver days: only a whole-tape read can reach these
    assert any(pd.Timestamp(s.time) < tape.index[10 * 24] for s in sigs)
    # the caller's flow is ignored on this source, and a missing symbol refuses
    junk = pd.Series(1.0, index=tape.index)
    assert [s.time for s in fo.family_orderflow_imbalance(
        tape, flow=junk, symbol="XAUUSD", flow_source="tape_signed_ticks", lookback=24,
        z_in=1.5)] == [s.time for s in sigs]
    assert fo.family_orderflow_imbalance(tape, flow=None, flow_source="tape_signed_ticks") == []
    assert fo.family_orderflow_imbalance(tape, flow=junk, flow_source="bogus") == []
    # the supplied contract every existing cell was judged on is unchanged
    assert fo.family_orderflow_imbalance(tape, flow=None) == []


# ------------------------------------------------------------------------------ the seeder ---
def test_registered_where_the_gauntlet_and_the_registries_look() -> None:
    from libs.research.alpha_clusters import classify_family
    from research import axis_registry
    from research import orthogonal_sweep as osw
    for name in ("cot_report", "expiry_gamma", "strike_pin"):
        assert fo.ORTHOGONAL_FAMILIES[name] is fs.SPECIALIST_FAMILIES[name]
        assert name in fo.FAMILY_INPUTS and name in axis_registry.FAMILY_TABLE
        assert name in osw.NOT_SOURCED_HERE
    assert classify_family("cot_report") == "positioning_flow"
    assert classify_family("expiry_gamma") == "fixing_roll_calendar"


def test_the_grid_is_gold_indices_majors_and_never_exotic() -> None:
    from research import universe_policy as up
    cells = fsd.plan()
    assert cells
    for c in cells:
        assert "exotic" not in str(up.asset_class_of(c["symbol"]) or "").lower()
        assert c["bucket"] in ("gold", "index", "major")
    fams = {c["family"] for c in cells}
    assert {"cot_report", "cot_net_fade", "cot_positioning", "expiry_gamma",
            "strike_pin"} <= fams
    reports = {c["params"].get("report") for c in cells if c["family"] == "cot_report"}
    assert {"legacy", "tff", "disagg"} <= reports
    assert all(c["symbol"] != "EURZAR" for c in cells)


def test_floor_donation_weekly_remeasure_and_no_message_text(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch
                                                            ) -> None:
    monkeypatch.setattr(fsd, "STATE", tmp_path / "state.json")
    cells = [{"bucket": "gold", "symbol": "XAUUSD", "family": "cot_report",
              "mechanism": f"cot_report.tff.lev_money.m{i}",
              "params": {"report": "tff", "market": "x", "group": "lev_money", "q": q}}
             for i, q in enumerate((0.1, 0.2, 0.3))]
    calls: list[dict[str, Any]] = []

    def fake_measure(sym: str, fam: str, params: dict, meta: dict) -> dict:
        calls.append(params)
        if params["q"] == 0.3:
            return {"built": False, "why": "input load failed: OSError: C:\\secret\\leak 42"}
        lb = 80 if params["q"] == 0.1 else 10
        return {"built": True, "signal_days": lb, "trade_days_lb": lb}

    donated: list[list[dict]] = []
    monkeypatch.setattr(sc, "measure", fake_measure)
    monkeypatch.setattr(sc, "_meta", lambda: {})
    from research import proposer_common as pc
    monkeypatch.setattr(pc, "donate", lambda src, rows, n: donated.append(rows) or tmp_path)
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(donated[-1])})
    rep = fsd.seed(budget_s=60, cells=cells)
    assert rep["candidates_this_pass"] == 1 and len(donated[0]) == 1
    assert donated[0][0]["source"] == "flow_seeder"
    assert "leak" not in str(rep) and "OSError" in str(rep["input_gaps"])
    assert rep["trial_charge_this_pass"]["n_raw"] == 3
    rep2 = fsd.seed(budget_s=60, cells=cells)
    assert len(calls) == 3 and rep2["candidates_this_pass"] == 0


def test_cot_freshness_says_stale(cot_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fsd, "COT_MAP", (("index", ("US500",), (("tff", "mkt", 1),
                                                                 ("tff", "gone", 1))),))
    got = fsd.cot_freshness(date(2026, 11, 13))
    assert got["tff/mkt"]["status"] == "STALE" and got["tff/mkt"]["last_report"] == "2023-06-27"
    assert got["tff/gone"]["status"] == "UNMEASURED"


def test_the_hourly_cycle_runs_it_with_a_layer_and_a_budget() -> None:
    from libs.research.attribution import NON_REGIONAL_NAMES
    from libs.research.layers import LEG_LAYER
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"research/flow_seeder.py", "--once", "--budget-s", "600"' in src
    assert '"flow_seeder": flws' in src and '"flow_seeder": 700' in src
    assert LEG_LAYER["flow_seeder"] == "prediction" and "flow_seeder" in NON_REGIONAL_NAMES


def test_the_sealed_build_cell_builds_every_flow_cell(tape: pd.DataFrame) -> None:
    """Through the SEALED builder itself (its `h1_override`), no input branch added."""
    sys.path.insert(0, str(DESK / "scripts"))
    import external_gauntlet as eg
    cases = [("XAUUSD", "orderflow_imbalance", tape,
              {"symbol": "XAUUSD", "flow_source": "tape_signed_ticks", "lookback": 24,
               "z_in": 1.5}),
             ("US500", "expiry_gamma", _bars(800, start="2019-01-07"),
              {"expiry": "all", "day_from": -4, "day_to": 0, "direction": "long"}),
             ("XAUUSD", "strike_pin", _bars(800, start="2019-01-07") * 20.0, {"mode": "pin"})]
    for sym, fam, bars, params in cases:
        cell = eg.build_cell(sym, fam, params, {}, h1_override=bars)
        assert cell is not None and len(cell.get("sigs") or []) > 0, fam


# ------------------------------------------------------- Auditor HOLD on #845 (2026-11-13) ---
def test_cot_is_never_read_before_a_holiday_week_release() -> None:
    """MF3: Veterans Day (Mon 2024-11-11) moved the release to Monday 15:30 ET, so the report as
    of Tue 2024-11-12 is not usable on Monday 2024-11-18 00:00 -- only from Wednesday."""
    from mt5desk.market_calendar import cot_usable_at
    assert cot_usable_at(date(2024, 11, 5)) == pd.Timestamp("2024-11-11", tz="UTC")
    assert cot_usable_at(date(2024, 11, 12)) == pd.Timestamp("2024-11-20", tz="UTC")
    assert cot_usable_at(date(2024, 12, 24)) == pd.Timestamp("2025-01-01", tz="UTC")
    for d in (date(2013, 10, 8), date(2019, 1, 15), date(2025, 10, 14)):
        assert cot_usable_at(d) is None                 # shutdown-delayed: dropped, not guessed


def test_comex_gold_and_third_friday_respect_the_exchange_calendar() -> None:
    from mt5desk.families_flow import comex_gold_option_expiry, third_friday
    assert comex_gold_option_expiry(2025, 7) == date(2025, 7, 28)       # SF1: Aug-25 options
    assert third_friday(2026, 6) == date(2026, 6, 18)                   # SF2: Juneteenth Friday
    assert third_friday(2025, 4) == date(2025, 4, 17)                   # Good Friday 2025-04-18
    assert third_friday(2026, 3) == date(2026, 3, 20)


def test_no_exception_message_reaches_state_or_report() -> None:
    """MF4: the sealed builder's `BLOCKED_DATA: ...: OSError: <box path>` keeps its type only."""
    why = fsd.safe_why("BLOCKED_DATA: raw COT for XAUUSD: OSError: [Errno 2] C:\\opt\\quant\\x")
    assert why == "BLOCKED_DATA: raw COT for XAUUSD: OSError" and "opt" not in why


def test_the_zcache_cot_path_follows_the_release_calendar(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """The VPS zcache path used a flat Friday+3; it now reaches the same instant as the in-tree
    path: Monday after release, Wednesday in a holiday week, shutdown reports dropped."""
    from research import orthogonal_sweep as osw
    days = pd.date_range("2018-06-05", "2019-12-31", freq="D")
    tuesdays = days[days.dayofweek == 1]
    daily = pd.Series(np.arange(len(tuesdays), dtype=float), index=tuesdays).reindex(days).ffill()
    (tmp_path / "data").mkdir()
    daily.rename("USDJPY").to_frame().to_parquet(tmp_path / "data" / "cot_zcache.parquet")
    monkeypatch.setattr(osw, "BASE", tmp_path / "a" / "b")
    osw._cot_frame.cache_clear()
    try:
        got = osw._cot_frame("USDJPY")
    finally:
        osw._cot_frame.cache_clear()
    assert got is not None and got.index.notna().all()
    from mt5desk.market_calendar import cot_usable_at
    for when, value in got["net"].items():
        assert cot_usable_at(tuesdays[int(value)]) == when
    assert set(got.index.dayofweek) <= {0, 2} and 2 in set(got.index.dayofweek)
    shutdown = (got.index >= pd.Timestamp("2018-12-20", tz="UTC")) & (
        got.index < pd.Timestamp("2019-03-06", tz="UTC"))
    assert not shutdown.any()


def test_a_slipped_cot_release_is_bound_by_when_it_was_seen(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    """Global data 2026-11-13: availability is bound by release_seen_utc, never by report date
    plus a lag, when the refresher saw the release later than the calendar says."""
    tuesdays = pd.date_range("2026-09-01", periods=10, freq="W-TUE", tz="UTC")
    seen = [pd.NaT] * 10
    seen[-1] = pd.Timestamp("2026-11-19T14:05:00Z")          # Nov 3 report seen 16 days late
    seen[-2] = pd.Timestamp("2026-10-30T20:31:00Z")          # on time: the calendar stands
    table = pd.DataFrame({"report_date": tuesdays, "release_seen_utc": seen})
    from mt5desk.market_calendar import cot_usable_index
    got = ff.cot_usable_from(table)
    cal = cot_usable_index(tuesdays)
    assert got[-1] == pd.Timestamp("2026-11-20T00:00:00Z")
    assert got[-2] == cal[-2] and list(got[:-1]) == list(cal[:-1])
    assert ff.cot_usable_from(table.drop(columns="release_seen_utc")).equals(cal)


def test_vix_positioning_conditions_the_us_indices() -> None:
    pairs = {(sym, rep, mkt, sign) for _b, aliases, reps in fsd.COT_MAP
             for sym in aliases[:1] for rep, mkt, sign in reps}
    for sym in ("US500", "NAS100"):
        assert {(sym, "legacy", "vix", -1), (sym, "tff", "vix", -1)} <= pairs
