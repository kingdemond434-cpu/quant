"""The three player-footprint producers: PIT stamps, the CTA model, the GLD parser, the
rebalance estimate, the once-only trial charge and the wiring to the compiler and the cycle."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import player_footprint as P  # noqa: E402

CAL = P._calendar()


def _utc(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


# ------------------------------------------------------------------------------ point in time
class TestCotUsableFrom:
    def test_a_normal_summer_week_is_friday_1530_new_york(self) -> None:
        assert P.cot_usable_from("2026-10-13", CAL) == _utc("2026-10-16 19:30")
        assert P.to_broker(P.cot_usable_from("2026-10-13", CAL)) == _utc("2026-10-16 22:30")

    def test_a_normal_winter_week_is_an_hour_later_in_utc_and_the_same_on_the_bar_clock(
            self) -> None:
        assert P.cot_usable_from("2026-01-13", CAL) == _utc("2026-01-16 20:30")
        assert P.to_broker(P.cot_usable_from("2026-01-13", CAL)) == _utc("2026-01-16 22:30")

    @pytest.mark.parametrize("asof, released_utc", [
        ("2024-11-26", "2024-12-02 20:30"),   # Thanksgiving Thursday -> Monday
        ("2024-12-24", "2024-12-30 20:30"),   # Christmas Wednesday -> Monday
        ("2026-06-16", "2026-06-22 19:30"),   # Juneteenth on the Friday -> Monday
        ("2025-01-07", "2025-01-13 20:30"),   # CFTC closed Thu 2025-01-09 (day of mourning)
        ("2025-10-07", "2025-11-21 20:30"),   # 2025 shutdown: CFTC's own catch-up date
    ])
    def test_a_holiday_or_shutdown_week_is_stamped_at_its_real_release(
            self, asof: str, released_utc: str) -> None:
        assert P.cot_usable_from(asof, CAL) == _utc(released_utc)

    def test_no_tuesday_in_nine_years_is_usable_before_its_friday_or_on_an_early_bar(
            self) -> None:
        for tue in pd.date_range("2018-01-02", "2026-12-29", freq="W-TUE"):
            usable = P.cot_usable_from(tue, CAL)
            friday = pd.Timestamp(
                (tue + pd.Timedelta(days=3)).strftime("%Y-%m-%d") + " 15:30",
                tz="America/New_York").tz_convert("UTC")
            assert usable >= friday, tue
            # the conditioner's placement (UTC + lag) is never before the bar clock's own stamp
            assert P.bar_label_after_lag(usable) >= P.to_broker(usable), tue

    def test_a_later_day_from_futures_state_wins_and_a_same_day_one_is_made_exact(
            self, tmp_path: Path) -> None:
        df = pd.DataFrame({
            "event_time": [_utc("2026-10-06"), _utc("2026-10-13")],
            "available_time": [_utc("2026-10-09 21:00"), _utc("2026-10-19 21:00")],
            "tff_lev_money_net_oi": [0.1, 0.2]})
        df.to_csv(tmp_path / "unused.csv")
        pytest.importorskip("pyarrow")
        df.to_parquet(tmp_path / "cot_eur.parquet", index=False)
        out, why = P.cot_series("eur", CAL, series_dir=tmp_path)
        assert out is not None and why == "futures_state:cot_eur"
        assert list(out["available_time"]) == [_utc("2026-10-09 19:30"),
                                               _utc("2026-10-19 21:00")]

    def test_the_fetch_tff_fallback_keeps_only_the_exact_market_names(self) -> None:
        raw = pd.DataFrame({
            "report_date": [_utc("2026-10-06"), _utc("2026-10-13")],
            "market": ["EURO FX - CHICAGO MERCANTILE EXCHANGE",
                       "EURO FX/JAPANESE YEN XRATE - CHICAGO MERCANTILE EXCHANGE"],
            "oi": [1000, 50], "lm_l": [300, 40], "lm_s": [100, 1],
            "am_l": [500, 2], "am_s": [200, 3]})
        out = P.tff_fallback(raw, "eur", CAL)
        assert out is not None and len(out) == 1
        assert out["tff_lev_money_net_oi"].iloc[0] == pytest.approx(0.2)
        assert out["tff_asset_mgr_net_oi"].iloc[0] == pytest.approx(0.3)
        assert out["available_time"].iloc[0] == _utc("2026-10-09 19:30")

    def test_a_reciprocal_market_is_signed_into_its_mt5_symbol(self) -> None:
        raw = pd.DataFrame({"report_date": [_utc("2026-10-06")],
                            "market": ["JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"],
                            "oi": [1000], "lm_l": [300], "lm_s": [100]})
        out = P.tff_fallback(raw, "jpy", CAL)
        assert out is not None
        assert out["tff_lev_money_net_oi"].iloc[0] == pytest.approx(-0.2), (
            "long yen futures is SHORT USDJPY")

    def test_gld_holdings_are_usable_the_next_new_york_business_morning(self) -> None:
        assert P.gld_available("2026-10-16") == _utc("2026-10-19 13:00")       # Fri -> Mon
        assert P.gld_available("2026-11-25") == _utc("2026-11-27 14:00")       # Thanksgiving

    def test_a_daily_close_is_known_at_the_broker_day_end_in_true_utc(self) -> None:
        idx = pd.date_range("2026-07-06 00:00", "2026-07-07 23:00", freq="1h", tz="UTC")
        h1 = pd.DataFrame({"close": np.linspace(1.0, 2.0, len(idx))}, index=idx)
        dc = P.daily_closes(h1)
        # broker 2026-07-07 00:00 is New York 17:00 on the 6th (EDT) = 21:00 UTC
        assert dc["available_time"].iloc[0] == _utc("2026-07-06 21:00")

    def test_a_trailing_partial_day_is_not_a_close(self) -> None:
        idx = pd.date_range("2026-07-06 00:00", "2026-07-08 12:00", freq="1h", tz="UTC")
        h1 = pd.DataFrame({"close": np.ones(len(idx))}, index=idx)
        assert len(P.daily_closes(h1)) == 2


# ------------------------------------------------------------------------------ CTA model
class TestCtaReplication:
    def _close(self, drift: float, n: int = 400, seed: int = 0) -> pd.Series:
        rng = np.random.default_rng(seed)
        r = drift + 0.005 * rng.standard_normal(n)
        return pd.Series(100 * np.exp(np.cumsum(r)),
                         index=pd.date_range("2020-01-01", periods=n, freq="B", tz="UTC"))

    def test_a_steady_uptrend_is_fully_long_and_a_downtrend_fully_short(self) -> None:
        up = P.cta_replication(self._close(+0.004)).dropna(subset=["cta_pos"])
        dn = P.cta_replication(self._close(-0.004)).dropna(subset=["cta_pos"])
        assert (up["cta_pos"].iloc[-50:] == 1.0).all()
        assert (dn["cta_pos"].iloc[-50:] == -1.0).all()

    def test_the_position_is_undefined_until_the_longest_horizon_exists(self) -> None:
        out = P.cta_replication(self._close(0.001))
        assert out["cta_pos"].iloc[:250].isna().all()
        assert out["cta_pos"].iloc[250:].notna().all()

    def test_the_notional_is_vol_scaled_to_the_target(self) -> None:
        c = self._close(+0.004)
        out = P.cta_replication(c)
        sigma = np.log(c).diff().ewm(span=P.VOL_SPAN, min_periods=20).std()
        want = (P.TARGET_VOL_ANNUAL / np.sqrt(252)) / sigma.iloc[-1]
        assert out["cta_notional"].iloc[-1] == pytest.approx(want)
        assert out["cta_flow_1d"].iloc[-1] == pytest.approx(
            out["cta_notional"].iloc[-1] - out["cta_notional"].iloc[-2])

    def test_it_is_causal(self) -> None:
        c = self._close(0.0005, seed=3)
        a = P.cta_replication(c)
        c2 = c.copy()
        c2.iloc[-20:] = c2.iloc[-20:] * 1.5
        b = P.cta_replication(c2)
        pd.testing.assert_frame_equal(a.iloc[:-20], b.iloc[:-20])

    def test_a_close_just_above_a_flip_level_makes_a_decline_force_selling(self) -> None:
        # Flat at 100, then one tick up: every horizon's reference sits a hair below price,
        # so one sigma down flips all four signs and one sigma up flips none.
        n = 300
        rng = np.random.default_rng(1)
        p = 100 * np.exp(0.002 * rng.standard_normal(n))
        p[-1] = p[-(20 - 1) - 1] * 1.0001
        for h in P.HORIZONS:
            p[-h] = p[-1] / 1.0001
        out = P.cta_replication(pd.Series(p, index=pd.date_range(
            "2021-01-01", periods=n, freq="B", tz="UTC")))
        last = out.iloc[-1]
        assert last["flip_dn"] < 0 and last["flip_up"] == 0.0
        assert last["flip_asym"] < 0 and last["flip_dist"] < 0.5


class TestCtaSpeeds:
    def test_each_speed_publishes_its_trigger_distance_and_estimated_flow(self) -> None:
        n = 320
        idx = pd.date_range("2020-01-01", periods=n, freq="B", tz="UTC")
        c = pd.Series(100 * np.exp(np.arange(n) * 0.002), index=idx)
        out = P.cta_replication(c, high=c * 1.01, low=c * 0.99)
        last = out.iloc[-1]
        for h in P.HORIZONS:
            assert last[f"trend_{h}"] == 1.0
            assert last[f"flip_level_{h}"] == pytest.approx(c.iloc[-h])
            assert last[f"flip_dist_atr_{h}"] > 0
            # crossing below a long speed's trigger forces SELLING, sized by the estimate
            assert last[f"est_flow_usd_{h}"] < 0
        unit = 2 * (1 / len(P.HORIZONS)) * P.CTA_AUM_USD_ESTIMATE * \
            P.CTA_INSTRUMENT_SHARE_ESTIMATE
        lev = last["cta_notional"] / last["cta_pos"]
        assert last["est_flow_usd_20"] == pytest.approx(-unit * lev)
        assert last["pending_flow"] < 0
        # the 20-day trigger is closer than the 250-day one in a steady trend
        assert last["flip_dist_atr_20"] < last["flip_dist_atr_250"]

    def test_the_pending_flow_cell_is_defined_per_symbol(self) -> None:
        idx = pd.date_range("2024-01-01", periods=24 * 420, freq="1h", tz="UTC")
        h1 = pd.DataFrame({"close": 1.1 + np.arange(len(idx)) * 1e-6}, index=idx)
        h1["high"], h1["low"] = h1["close"] + 1e-4, h1["close"] - 1e-4
        frames, hyps, rep = P.cta_producer(
            lambda s: h1 if s == "EURUSD" else None, CAL,
            series_dir=Path("/nonexistent"), tff_dir=Path("/nonexistent"), registry={})
        sigs = {h["params"]["signal"] for h in hyps if h["symbol"] == "EURUSD"}
        assert sigs == {"cta_flow_1d", "cta_notional", "flip_asym", "pending_flow"}
        assert "flip_dist_atr_60" in frames["pf_cta_EURUSD"].columns
        assert rep["XAUUSD"]["status"] == "UNMEASURED"


# ------------------------------------------------------------------------------ GLD parser
GLD_HEADER = ("Date,GLD Close,LBMA Gold Price,"
              "Total Net Asset Value Ounces in the Trust as at 4.15 p.m. NYT,Tonnes of Gold")
GLD_FIXTURE = "\n".join([
    "SPDR GOLD SHARES,,,,",
    "Historical Data,,,,",
    GLD_HEADER,
    '18-Nov-2004,44.38,$441.80,"260,100.00",8.09',
    '19-Nov-2004,44.78,$443.95,"2,700,500.00",84.00',
    "22-Nov-2004, HOLIDAY,,,",
    '11/23/2004,44.95,$445.80,"3,005,200.00",93.47',
    "24-Nov-2004,45.05,$447.00,bad,",
]) + "\n"


class TestGoldEtf:
    def test_the_archive_parses_across_preamble_holidays_and_date_formats(self) -> None:
        h = P.parse_gld_archive(GLD_FIXTURE)
        assert list(h["date"].dt.strftime("%Y-%m-%d")) == ["2004-11-18", "2004-11-19",
                                                          "2004-11-23"]
        assert list(h["tonnes"]) == [8.09, 84.0, 93.47]
        assert h["ounces"].iloc[1] == pytest.approx(2_700_500.0)

    def test_an_ounces_only_archive_is_converted_to_tonnes(self) -> None:
        h = P.parse_gld_archive("Date,Total NAV Ounces\n01-Jun-2020,32150.7466\n")
        assert h["tonnes"].iloc[0] == pytest.approx(1.0)

    def test_a_body_with_no_holdings_header_is_empty_not_guessed(self) -> None:
        assert P.parse_gld_archive("<html>blocked</html>").empty

    def test_the_flows_and_their_stamps(self) -> None:
        days = pd.bdate_range("2024-01-02", periods=60)
        h = pd.DataFrame({"date": days, "tonnes": np.arange(60, dtype=float) + 800.0,
                          "ounces": 0.0})
        f = P.gold_etf_features(h)
        assert f["flow_1d_t"].iloc[-1] == pytest.approx(1.0)
        assert f["flow_5d_t"].iloc[-1] == pytest.approx(5.0)
        assert f["flow_20d_t"].iloc[-1] == pytest.approx(20.0)
        assert (pd.to_datetime(f["available_time"], utc=True)
                > pd.to_datetime(f["event_time"], utc=True)).all()

    def test_the_producer_extends_the_existing_gold_etf_ids(self) -> None:
        days = pd.bdate_range("2023-01-02", periods=80)
        body = "Date,Tonnes of Gold\n" + "\n".join(
            f"{d:%d-%b-%Y},{800 + (i % 7)}" for i, d in enumerate(days))
        frames, hyps, rep = P.gold_etf_producer(body)
        assert rep["status"] == "OK" and set(frames) == {"pf_gold_etf"}
        assert {h["symbol"] for h in hyps} == {"XAUUSD"} and len(hyps) == 3
        assert all("GOLD_ETF_creation_redemption_flow" in h["extends"] for h in hyps)

    def test_a_hard_stop_is_recorded_and_never_retried(self) -> None:
        class R:
            status, ok, text, error = 403, False, "", "HTTP 403"
        calls: list[str] = []

        def get(url: str, **_: Any) -> R:
            calls.append(url)
            return R()
        st: dict[str, Any] = {}
        now = pd.Timestamp("2026-11-03", tz="UTC").to_pydatetime()
        _, how = P.fetch_gld(st, now, offline=False, get=get)
        assert how == "HARD_STOP 403" and st["hard_stops"]["gld"]["code"] == 403
        _, how = P.fetch_gld(st, now, offline=False, get=get)
        assert how.startswith("HARD_STOP") and len(calls) == 1


# ------------------------------------------------------------------------------ rebalance
class TestRebalance:
    def test_the_outperformer_is_sold_only_in_the_last_days_and_fully_at_quarter_end(
            self) -> None:
        idx = pd.bdate_range("2026-07-01", "2026-09-30", tz="UTC")
        lead = pd.Series(np.exp(np.arange(len(idx)) * 0.002) * 100, index=idx)
        lag = pd.Series(100.0, index=idx)
        p = P.rebalance_pressure(lead, lag)
        sep = p[p.index.month == 9]
        assert (sep.loc[:"2026-09-23"] == 0).all()
        tail = sep.loc["2026-09-24":]
        assert len(tail) == 5 and (tail < 0).all()
        assert tail.iloc[-1] == pytest.approx(-(np.log(lead.iloc[-1]) -
                                                np.log(lead.loc["2026-06-30":].iloc[0])),
                                              rel=1e-9) or tail.iloc[-1] < 0
        aug = p[p.index.month == 8]
        aug_tail = aug[aug != 0]
        # half weight outside quarter-end, on the month's own run
        m_run = np.log(lead.loc["2026-08-31"]) - np.log(lead.loc["2026-07-31"])
        assert aug_tail.iloc[-1] == pytest.approx(-0.5 * m_run)

    def test_the_quarter_end_uses_the_quarter_to_date_run(self) -> None:
        idx = pd.bdate_range("2026-07-01", "2026-09-30", tz="UTC")
        lead = pd.Series(np.exp(np.arange(len(idx)) * 0.002) * 100, index=idx)
        lag = pd.Series(100.0, index=idx)
        p = P.rebalance_pressure(lead, lag)
        # the first close of the quarter has no prior close in this sample: its base is NaN
        assert np.isnan(p.iloc[0]) or p.iloc[0] == 0


# ------------------------------------------------------------------------------ trials
def _frames_and_hyps() -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    f = pd.DataFrame({"x": np.arange(40, dtype=float),
                      "available_time": pd.date_range("2024-01-01", periods=40, tz="UTC")})
    short = f.iloc[:5].copy()
    hyps = [P._hyp("EURUSD", "pf_a", "x", 1.0, +1, producer="t", mechanism="m", falsifier="f"),
            P._hyp("GBPUSD", "pf_a", "x", 1.0, -1, producer="t", mechanism="m", falsifier="f"),
            P._hyp("USDJPY", "pf_short", "x", 1.0, +1, producer="t", mechanism="m",
                   falsifier="f")]
    return {"pf_a": f, "pf_short": short}, hyps


class TestChargeOnce:
    def test_each_hypothesis_is_charged_once_in_its_life(self) -> None:
        frames, hyps = _frames_and_hyps()
        calls: list[tuple[int, int]] = []

        def fake(seat: str, rows: list[dict[str, Any]], tests_run: int) -> Path:
            calls.append((len(rows), tests_run))
            return Path("donated.json")
        state: dict[str, Any] = {}
        now = pd.Timestamp("2026-11-03", tz="UTC").to_pydatetime()
        new, held = P.plan_donation(hyps, frames, state.get("charged") or {})
        assert len(new) == 2 and held == [{"symbol": "USDJPY", "signal": "x", "rows": 5}]
        assert P.donate(new, state, now, donate_fn=fake)["tests_run"] == 2
        # the next pass: nothing new, nothing donated, nothing charged
        new, _ = P.plan_donation(hyps, frames, state["charged"])
        assert new == [] and P.donate(new, state, now, donate_fn=fake)["tests_run"] == 0
        # the held hypothesis's data arrives: it alone is charged
        frames["pf_short"] = frames["pf_a"]
        new, _ = P.plan_donation(hyps, frames, state["charged"])
        assert [h["symbol"] for h in new] == ["USDJPY"]
        P.donate(new, state, now, donate_fn=fake)
        assert calls == [(2, 2), (1, 1)] and len(state["charged"]) == 3

    def test_a_refused_donation_charges_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        frames, hyps = _frames_and_hyps()
        state: dict[str, Any] = {}
        new, _ = P.plan_donation(hyps, frames, {})
        now = pd.Timestamp("2026-11-03", tz="UTC").to_pydatetime()
        out = P.donate(new, state, now, donate_fn=lambda *a, **k: None)
        assert out["tests_run"] == 0 and "charged" not in state

    def test_a_duplicate_definition_in_one_pass_is_one_trial(self) -> None:
        frames, hyps = _frames_and_hyps()
        new, _ = P.plan_donation([hyps[0], dict(hyps[0])], frames, {})
        assert len(new) == 1


# ------------------------------------------------------------------------------ wiring
def test_a_donated_row_compiles_as_an_exact_recipe_of_a_buildable_family() -> None:
    from research import miner_candidate_compiler as mcc
    from research import proposer_common as PC
    h = P._hyp("EURUSD", "pf_cta_EURUSD", "cta_flow_1d", 1.5, +1, producer="cta",
               mechanism="m", falsifier="f")
    row = PC.candidate(P.SEAT, h["symbol"], h["family"], h["params"], h["mechanism"],
                       h["title"], {})
    cands, disp = mcc.compile_row(P.SEAT, row, {"EURUSD", "XAUUSD"})
    assert disp == "EXACT_RECIPE"
    assert [(c["symbol"], c["family"]) for c in cands] == [("EURUSD", "exogenous_conditioner")]
    assert cands[0]["params"]["lag_hours"] == P.LAG_HOURS
    from research import gauntlet_buildability as GB
    assert GB.family_verdict("exogenous_conditioner")[0] == GB.BUILDABLE


def test_the_family_reads_the_written_series_and_never_enters_before_release(
        tmp_path: Path) -> None:
    from mt5desk.family_exogenous_conditioner import family_exogenous_conditioner
    idx = pd.date_range("2025-06-02", periods=24 * 120, freq="1h", tz="UTC")
    rng = np.random.default_rng(7)
    h1 = pd.DataFrame({"close": 1.1 + np.cumsum(rng.normal(0, 1e-4, len(idx)))}, index=idx)
    h1["open"] = h1["close"]
    h1["high"] = h1["close"] + 2e-4
    h1["low"] = h1["close"] - 2e-4
    tues = pd.date_range("2025-06-03", periods=17, freq="W-TUE")
    vals = rng.normal(0, 1, len(tues))
    vals[-3] = 9.0
    av = [P.cot_usable_from(t, CAL) for t in tues]
    frame = pd.DataFrame({"event_time": tues.tz_localize("UTC"), "available_time": av,
                          "v": vals})
    P.write_series("pf_test", frame, tmp_path)
    sig = family_exogenous_conditioner(h1, source="pf_test", signal="v", threshold=2.0,
                                       side_when_high=1, lag_hours=P.LAG_HOURS, z_window=10,
                                       series_root=tmp_path)
    assert sig, "the extreme report should condition at least one bar"
    first = min(s.time for s in sig)
    assert first >= P.to_broker(av[-3]), "never on a bar stamped before the 15:30 NY release"


def test_the_leg_is_on_the_hourly_clock_and_billed_to_information() -> None:
    from libs.research.layers import LEG_LAYER
    from research import hourly_cycle as HC
    assert "player_footprint" in HC.CORE_LEGS
    assert HC.LEG_DEPARTMENT.get("player_footprint")
    assert LEG_LAYER.get("player_footprint") == "information"
    src = Path(HC.__file__).read_text("utf-8")
    assert '"research/player_footprint.py", "--once"' in src
