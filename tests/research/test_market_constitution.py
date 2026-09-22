"""The market constitution: PIT rule states, the KRX VI machine, the calendar, the flags."""
from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.research import country_lab as lab  # noqa: E402
from libs.research import market_constitution as mc  # noqa: E402

JST = ZoneInfo("Asia/Tokyo")
KST = ZoneInfo("Asia/Seoul")
CST = ZoneInfo("Asia/Shanghai")
V = mc.builtin_venues()
TODAY = date(2026, 9, 22)


def _tse(iso: str, cls: str = "equity_cash") -> mc.VenueRuleState:
    return mc.state_at(V["TSE"], datetime.fromisoformat(iso).replace(tzinfo=JST), cls)


def _krx(iso: str) -> mc.VenueRuleState:
    return mc.state_at(V["KRX"], datetime.fromisoformat(iso).replace(tzinfo=KST), "equity_cash")


def _sse(iso: str) -> mc.VenueRuleState:
    return mc.state_at(V["SSE_SZSE"], datetime.fromisoformat(iso).replace(tzinfo=CST), "a_share")


def _cffex(iso: str) -> mc.VenueRuleState:
    return mc.state_at(V["CFFEX"], datetime.fromisoformat(iso).replace(tzinfo=CST),
                       "index_futures")


def test_tse_1526_is_pre_closing_after_november_2024_and_not_before() -> None:
    after = _tse("2025-03-05T15:26")                       # a Wednesday, a trading day
    assert after.session_state == "PRE_CLOSING" and after.auction_state == "CLOSING_ITAYOSE"
    assert after.window == "closing_auction"
    before = _tse("2024-03-05T15:26")
    assert before.session_state == "CLOSED"                # the cash market closed at 15:00
    assert _tse("2024-03-05T14:58").session_state == "CONTINUOUS"
    assert _tse("2024-11-04T15:26").session_state == "CLOSED"       # last day of the old regime
    assert _tse("2024-11-05T15:26").session_state == "PRE_CLOSING"  # first day of the new one
    assert after.rule_version != before.rule_version
    assert "2024-11-05" in after.rule_version and "2019-07-16" in before.rule_version


def test_tse_lunch_holiday_weekend_and_the_futures_clock() -> None:
    assert _tse("2025-03-05T11:45").session_state == "LUNCH"
    assert _tse("2025-01-01T10:00").session_state == "HOLIDAY"
    assert _tse("2025-03-08T10:00").session_state == "WEEKEND"
    assert _tse("2025-03-05T02:00", "index_futures").session_state == "NIGHT_SESSION"
    assert _tse("2025-03-05T15:40", "index_futures").session_state == "CONTINUOUS"
    assert _tse("2024-03-05T15:40", "index_futures").session_state == "CLOSED"


def test_tse_daily_price_limit_table_and_band_state() -> None:
    assert mc.tse_daily_price_limit(99) == 30 and mc.tse_daily_price_limit(1000) == 300
    assert mc.tse_daily_price_limit(4999) == 700 and mc.tse_daily_price_limit(5000) == 1000
    at = datetime(2025, 3, 5, 10, 0, tzinfo=JST)
    up = mc.state_at(V["TSE"], at, "equity_cash", observed={"price": 1300, "reference": 1000})
    assert up.price_band == "LIMIT_UP"
    ok = mc.state_at(V["TSE"], at, "equity_cash", observed={"price": 1100, "reference": 1000})
    assert ok.price_band == "WITHIN_LIMITS"
    assert _tse("2025-03-05T10:00").price_band == "UNOBSERVED"


def test_krx_vi_transitions() -> None:
    t0 = datetime(2025, 3, 5, 1, 0, tzinfo=UTC)
    s1 = mc.krx_vi_step(mc.VIState(), t0, price=103.0, dynamic_ref=100.0, static_ref=100.0)
    assert s1.state == "VI_CALL" and s1.trigger == "dynamic"
    assert datetime.fromisoformat(s1.until) == t0 + timedelta(seconds=mc.KRX_VI_SECONDS)
    s2 = mc.krx_vi_step(s1, t0 + timedelta(seconds=60), 110.0, 100.0, 100.0)
    assert s2 == s1                                         # a call in progress is never re-armed
    s3 = mc.krx_vi_step(s1, t0 + timedelta(seconds=120), 101.0, 100.0, 100.0)
    assert s3.state == "NONE"
    s4 = mc.krx_vi_step(mc.VIState(), t0, price=111.0, dynamic_ref=110.0, static_ref=100.0)
    assert s4.state == "VI_CALL" and s4.trigger == "static"
    assert mc.krx_vi_step(mc.VIState(), t0, 101.0, 100.0, 100.0).state == "NONE"
    during = mc.state_at(V["KRX"], t0 + timedelta(seconds=30), "equity_cash",
                         observed={"vi_until": s1.until})
    assert during.session_state == "CONTINUOUS" and during.auction_state == "VI_CALL"
    after = mc.state_at(V["KRX"], t0 + timedelta(seconds=130), "equity_cash",
                        observed={"vi_until": s1.until})
    assert after.auction_state == "NONE"


def test_krx_short_states_and_closing_call_by_date() -> None:
    assert _krx("2024-01-10T10:00").short_state == "BANNED"
    assert _krx("2022-01-12T10:00").short_state == "PARTIAL_BAN"
    assert _krx("2025-06-11T10:00").short_state == "UPTICK_RULE"
    assert _krx("2025-06-11T15:25").session_state == "CLOSING_CALL"
    assert _krx("2015-06-10T15:25").session_state == "CLOSED"        # a 15:00 close before 2016
    over = mc.state_at(V["KRX"], datetime(2025, 6, 11, 1, 0, tzinfo=UTC), "equity_cash",
                       observed={"overheated": True})
    assert over.short_state == "OVERHEATED_DESIGNATED"


def test_china_regimes_by_date() -> None:
    assert _sse("2022-06-15T10:00").hft_regime == "UNREGULATED"
    assert _sse("2024-06-12T10:00").hft_regime == "REPORTING"
    assert _sse("2025-08-13T10:00").hft_regime == "REPORTING_WITH_THRESHOLDS"
    assert _sse("2025-08-13T10:00").settlement_state == "T+1_LOCKED"
    assert _sse("2025-08-13T14:58").session_state == "CLOSING_CALL"
    assert _sse("2017-08-16T14:58").session_state == "CONTINUOUS"
    assert _cffex("2016-06-15T10:00").fee_regime == "CFFEX_2015_CURBS"
    assert _cffex("2020-06-17T10:00").fee_regime == "STANDARD"
    assert _cffex("2026-03-11T10:00").fee_regime == "CFFEX_HFT_DIFFERENTIATED"


def test_fusion_clock_and_the_rollover_rule_is_verified_from_the_repo() -> None:
    assert mc.state_at(V["FUSION"], datetime(2025, 8, 9, 10, 0, tzinfo=UTC),
                       "forex").session_state == "WEEKEND"
    mid = mc.state_at(V["FUSION"], datetime(2025, 8, 6, 10, 0, tzinfo=UTC), "forex")
    assert mid.session_state == "CONTINUOUS" and mid.settlement_state == "CFD_ROLLOVER"
    roll = next(r for r in V["FUSION"].rules if r.kind == "rollover")
    assert roll.spec["rollover_hour_utc"] == 21 and roll.spec["triple_swap_weekday"] == 2
    assert roll.source.verified == mc.VERIFIED and "engine.py" in roll.source.citation
    close = next(r for r in V["FUSION"].rules if r.kind == "desk_close")
    assert close.spec["close_utc"] == "19:30" and close.source.verified == mc.VERIFIED


def test_rule_change_appears_in_the_calendar_with_its_mechanism() -> None:
    cal = mc.rule_change_calendar()
    by_id = {c.change_id: c for c in cal}
    tse = by_id["tse_closing_auction_2024"]
    assert tse.date == "2024-11-05" and tse.mechanism and tse.experiment
    assert tse.control_symbols == ("HK50",) and not tse.prospective
    assert by_id["tse_random_close_2027"].prospective
    assert by_id["tse_random_close_2027"].date == "2027-10-12"
    vi = by_id["krx_vi_activations"]
    assert vi.affected_symbols == () and "UNMEASURED" in vi.experiment
    assert all(c.mechanism and c.source.citation for c in cal)
    assert [c.date for c in cal] == sorted(c.date for c in cal)
    row = next(r for r in V["TSE"].rules if r.rule_id == "tse.session.2024_closing_auction")
    assert row.effective_from == tse.date                   # the calendar and the rule agree


def test_unverified_rows_say_so_everywhere() -> None:
    for v in V.values():
        for r in v.rules:
            assert r.source.verified in mc.VERIFY_STATES and r.source.citation
    reading = mc.unverified_rules(V.values())
    assert reading and all(x["citation"] for x in reading)
    st = _tse("2025-03-05T15:26")
    assert "tse.session.2024_closing_auction" in st.unverified   # until the JPX notice is read
    assert st.as_row()["unverified"]
    fx = mc.state_at(V["FUSION"], datetime(2025, 8, 6, 10, 0, tzinfo=UTC), "forex")
    assert "fusion.rollover.swap" not in fx.unverified and "fusion.session.fx" in fx.unverified
    with pytest.raises(ValueError):
        mc.Source(citation="x", verified="TRUST_ME")


def test_stamp_matches_state_at() -> None:
    times = [datetime(2024, 11, 4, 6, 26) + timedelta(hours=h) for h in range(72)]
    cols = mc.stamp(V["TSE"], times, "equity_cash")
    assert len(cols["session_state"]) == 72 and set(cols) == set(mc.STAMP_COLUMNS)
    for i, ts in enumerate(times):
        s = mc.state_at(V["TSE"], ts, "equity_cash")
        assert cols["session_state"][i] == s.session_state
        assert cols["rule_version"][i] == s.rule_version
        assert cols["n_unverified"][i] == len(s.unverified)
    assert cols["session_state"][0] == "CLOSED" and cols["session_state"][24] == "PRE_CLOSING"


def test_venue_from_pack_rows_consumes_country_lab_types() -> None:
    ex = lab.Exchange(name="Korea Exchange (KRX)", index_symbols=(), expiry_rule="2nd Thursday",
                      expiry_dates=("2025-03-13",), open_utc="00:00", close_utc="06:30")
    win = lab.SessionWindow(name="closing call", start_utc="06:20", end_utc="06:30")
    hol = lab.HolidayRule(dates=("2025-03-03",), fixed_md=("01-01",), weekly_closed=(5, 6))
    sett = lab.SettlementRule(name="kr_customs_20day_print", kind="day_of_month", days=(21,))
    venues = mc.venue_from_pack_rows("kr", [ex], [win], hol, [sett], mt5_symbols=("USDKRW",))
    assert len(venues) == 1
    v = venues[0]
    assert v.venue_id.startswith("KR:") and v.mt5_symbols == ("USDKRW",)
    assert v.holidays == frozenset({"2025-03-03"})
    assert {"session", "expiry", "settlement_convention"} <= {r.kind for r in v.rules}
    assert all(r.source.citation.endswith("countries/kr/pack.py") for r in v.rules)
    assert mc.state_at(v, datetime(2025, 3, 4, 3, 0)).session_state == "CONTINUOUS"
    assert mc.state_at(v, datetime(2025, 3, 4, 6, 25)).window == "closing_call"
    assert mc.state_at(v, datetime(2025, 3, 3, 3, 0)).session_state == "HOLIDAY"
    assert mc.state_at(v, datetime(2025, 1, 1, 3, 0)).session_state == "HOLIDAY"


def _tape(seed: int, start: str, days: int, effect_from: str | None = None,
          window_hour: int = 6, boost: float = 4.0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    t0 = np.datetime64(start, "h")
    times = np.arange(t0, t0 + np.timedelta64(days * 24, "h"),
                      np.timedelta64(1, "h")).astype("datetime64[ns]")
    r = rng.normal(0, 1e-3, times.size)
    if effect_from is not None:
        hours = (times.astype("datetime64[h]") - times.astype("datetime64[D]")).astype(int)
        r[(times >= np.datetime64(effect_from)) & (hours == window_hour)] *= boost
    return times, np.exp(np.cumsum(r)) * 100.0


def test_rule_change_effect_sees_an_injected_effect_and_not_a_null() -> None:
    ta, ca = _tape(1, "2023-01-02", 1100, effect_from="2024-11-05")
    tc, cc = _tape(2, "2023-01-02", 1100)
    w = ("06:00", "07:00")
    hit = mc.rule_change_effect(ta, ca, tc, cc, "2024-11-05", w, today=TODAY)
    assert hit["verdict"] == "MEASURED" and hit["did"] > 0 and hit["p_placebo"] <= 0.05
    assert hit["n_placebo"] >= mc.MIN_PLACEBOS and hit["post_affected"] > hit["pre_affected"]
    tn, cn = _tape(3, "2023-01-02", 1100)
    null = mc.rule_change_effect(tn, cn, tc, cc, "2024-11-05", w, today=TODAY)
    assert null["verdict"] == "MEASURED" and null["p_placebo"] > 0.05
    early = mc.rule_change_effect(ta, ca, tc, cc, "2015-09-07", w, today=TODAY)
    assert early["verdict"] == "UNMEASURED" and "outside the tape" in early["why"]
    assert early["tape"]["first"] == "2023-01-02"
    future = mc.rule_change_effect(ta, ca, tc, cc, "2027-10-12", w, today=TODAY)
    assert future["verdict"] == "PROSPECTIVE"
    short = mc.rule_change_effect(ta[:24 * 60], ca[:24 * 60], tc, cc, "2023-02-15", w,
                                  today=TODAY)
    assert short["verdict"] == "POORLY_MEASURED"


def test_placebo_dates_avoid_the_true_change_and_the_edges() -> None:
    days = np.arange(np.datetime64("2023-01-02"), np.datetime64("2026-01-06"))
    change = np.datetime64("2024-11-05")
    ps = mc.placebo_dates(days, change, 120, 120, 10)
    assert ps.size >= mc.MIN_PLACEBOS and change not in ps
    idx, true_idx = np.searchsorted(days, ps), np.searchsorted(days, change)
    assert (np.abs(idx - true_idx) >= 240).all()
    assert idx.min() >= 120 and idx.max() < days.size - 120
    assert mc.placebo_dates(days[:100], change, 120, 120).size == 0
