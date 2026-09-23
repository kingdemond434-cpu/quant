"""MOROCCO'S OWN MINERS -- the six clocks the generic set cannot know.

`MINERS` maps a name to `callable(pack, ctx) -> dict`, the contract `country_lab.run_lab` reads
for a pack directory's `miners.py`, and every entry in the pack's `CUSTOM_MINERS`
(`countries.ma.miners:<function>`) resolves to a function here, so the two registrations are one
set. Each miner builds ITS OWN event dates from the pack's tables -- the quarterly Conseil
calendar, the band-widening decrees, the Tuesday 7-day advance tender, the soft-wheat duty
decrees and the declared Ramadan UTC+0 windows -- and hands them to the framework's event study
through the shared kit, so a Moroccan finding carries the same matched-weekday control,
randomised-date null and adjacent-day placebo as every other country's. Discoveries go through
`ctx.record` and nowhere else.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path
from typing import Any

try:
    from countries import _miner_kit as K  # type: ignore[import-not-found]
except ImportError:  # loaded by file path: reach the kit beside this package
    _kit = Path(__file__).resolve().parents[1] / "_miner_kit.py"
    _spec = importlib.util.spec_from_file_location("countries_miner_kit", _kit)
    if _spec is None or _spec.loader is None:  # pragma: no cover
        raise
    K = importlib.util.module_from_spec(_spec)
    sys.modules["countries_miner_kit"] = K
    _spec.loader.exec_module(K)

from libs.research import country_lab as CL

SOURCE = "ma:pack"
#: The band-widening and basket decrees: four dated regime breaks and the whole of MA-B's
#: history. Four is below the framework's event floor and the miner says so rather than
#: padding the sample with days that carried no decree.
BAND_DECREES: tuple[str, ...] = ("2015-04-13", "2017-06-15", "2018-01-15", "2020-03-09")


def _pack_module() -> Any:
    try:
        from countries.ma import pack as mod  # type: ignore[import-not-found]
    except ImportError:
        spec = importlib.util.spec_from_file_location(
            "country_ma_pack", Path(__file__).resolve().parent / "pack.py")
        if spec is None or spec.loader is None:  # pragma: no cover
            raise
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


def bam_conseil_windows(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """MA-A: the four-a-year Conseil decisions, intraday, on the legs a bounded currency leaves
    open -- the euro leg of the basket, gold, and the European indices that hold the parents."""
    ctx.miner = ctx.miner or "bam_conseil_windows"
    dates = [date.fromisoformat(d) for d in pack.central_bank.decision_dates]
    got: dict[str, Any] = K.event_study(
        pack, ctx, name="bam_conseil_windows", symbols=("EURUSD", "XAUUSD", "E35", "FRA40"),
        dates=dates, mechanism="ma_conseil_decision_channel",
        actor="the Conseil de Bank Al-Maghrib",
        constraint="FOUR scheduled decisions a year on a published calendar; the dirham cannot "
                   "move more than its band allows, so the reaction is read on the basket's "
                   "euro leg, on gold and on the European indices",
        rationale="a decision in a band regime cannot move the currency itself, so whatever it "
                  "carries must appear on the legs the band leaves free",
        falsifier="the decision-day effect matches the four nearest non-meeting Tuesdays or the "
                  "same window on ECB decision days",
        source_id=f"{SOURCE}:bkam", required_data=["BAM:taux_directeur", "Conseil calendar"],
        horizon="intraday", hours=(14, 17),
        payload={"domain": "MA-A", "n_dates": len(dates),
                 "sample_note": "four meetings a year is a third of a normal central bank's "
                                "sample and is reported, never padded"})
    return got


def basket_band_pressure(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """MA-B: the 60/40 basket. The daily reference rate against the euro leg as a lead-lag, and
    the four basket/band decrees as regime breaks -- the second part is deliberately tiny and
    reports POORLY_MEASURED rather than pretending a four-event study is a verdict."""
    ctx.miner = ctx.miner or "basket_band_pressure"
    results: dict[str, Any] = {"miner": "basket_band_pressure", "parts": {}}
    results["parts"]["reference_rate_lead"] = K.series_lead(
        pack, ctx, name="bam_reference_rate_lead", series_name="BAM:reference_rate",
        symbols=("EURUSD", "USDX"), mechanism="ma_basket_reference_rate_lead",
        actor="the Bank Al-Maghrib FX desk as the band's counterparty",
        constraint="the rate is fixed off a 60% EUR / 40% USD basket inside a +/-5% band, so "
                   "where it sits INSIDE the band is the only free information it carries",
        rationale="a managed rate that is pressed toward an edge is a flow imbalance the "
                  "official sector must absorb; the basket makes EURUSD the readable leg",
        falsifier="the reference-rate series carries no information for EURUSD beyond what a "
                  "block-shuffled copy of the same series carries",
        source_id=f"{SOURCE}:bkam_fx", horizon_days=10,
        payload={"domain": "MA-B", "basket": "60% EUR / 40% USD since 2015-04-13"})
    results["parts"]["band_regime_breaks"] = K.event_study(
        pack, ctx, name="ma_band_decrees", symbols=("EURUSD", "USDX"),
        dates=[date.fromisoformat(d) for d in BAND_DECREES],
        mechanism="ma_band_widening_regime_break",
        actor="the government, which owns the exchange-rate regime, and Bank Al-Maghrib, which "
              "defends it",
        constraint="the band widened on 2018-01-15 and 2020-03-09 after the basket was "
                   "reweighted on 2015-04-13; the 2017-06 launch was postponed after a "
                   "speculative episode",
        rationale="a widening changes the arithmetic of every dirham-to-euro mapping, so a study "
                  "that pools across one is measuring two different functions",
        falsifier="the decree windows match the matched-weekday control, which for a sample this "
                  "small is the expected outcome and is recorded as such",
        source_id=f"{SOURCE}:band", required_data=["the band decrees"], horizon="session",
        payload={"domain": "MA-B", "n_decrees": len(BAND_DECREES),
                 "sample_note": "four events is below the framework's floor: POORLY_MEASURED is "
                                "the honest verdict here and the pack refuses to pad it"},
        novelty=0.5, confidence=0.3)
    parts = results["parts"].values()
    results["outcome"] = K.OK if any(p.get("outcome") == K.OK for p in parts) else K.UNMEASURED
    results["discoveries"] = sum(int(p.get("discoveries") or 0) for p in parts)
    return results


def advance_tender_week(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """MA-C: the Tuesday 7-day advance tender as the operational stance between two quarterly
    Conseils, with the Thursday placebo run alongside so a Tuesday effect can be told from a
    weekday effect."""
    ctx.miner = ctx.miner or "advance_tender_week"
    bars = ctx.bars("EURUSD", "H1")
    if bars is None:
        ctx.note("advance_tender_week:bars:EURUSD", "no H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "advance_tender_week",
                "why": "no EURUSD tape"}
    lo, hi = K.tape_span(bars)
    tuesdays = K.weekday_dates(lo, hi, 1)
    thursdays = K.weekday_dates(lo, hi, 3)
    main: dict[str, Any] = K.event_study(
        pack, ctx, name="advance_tender_week", symbols=("EURUSD",), dates=tuesdays,
        mechanism="ma_weekly_advance_tender",
        actor="Bank Al-Maghrib refinancing a structural banking liquidity deficit",
        constraint="the allotment is announced every Tuesday and settled Wednesday; the same "
                   "Tuesday carries the Direction du Tresor's bill auction",
        rationale="with only four decisions a year the weekly allotment IS the policy stance; a "
                  "deficit funded by the central bank is the cereal and energy import bill "
                  "arriving as a money-market fact",
        falsifier="the Tuesday window matches the Thursday placebo or the matched weekday "
                  "control, in which case this is a weekday effect and not a tender effect",
        source_id=f"{SOURCE}:bkam_mm", required_data=["BAM:liquidity_deficit"],
        horizon="session", hours=(8, 11),
        payload={"domain": "MA-C", "placebo_day": "Thursday", "n_tuesdays": len(tuesdays)})
    ctrl = K.event_study(
        pack, ctx, name="advance_tender_placebo", symbols=("EURUSD",), dates=thursdays,
        mechanism="ma_weekly_advance_tender_placebo", actor="placebo", constraint="none",
        rationale="Thursday carries no tender and no bill auction; a move here is the calendar",
        falsifier="n/a", source_id=f"{SOURCE}:bkam_mm_placebo", required_data=[],
        horizon="session", hours=(8, 11), payload={"domain": "MA-C", "placebo": True},
        novelty=0.0, confidence=0.0)
    main["placebo"] = {k: v for k, v in ctrl.items() if k != "readings"}
    return main


def cereal_duty_switch(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """MA-F: the soft-wheat customs duty switched on and off by decree, with the out-of-season
    boundary placebo. The decree rows are PRESS_REPORTED, which the payload carries so nothing
    compiled here can be promoted before a Bulletin Officiel number is attached to it."""
    ctx.miner = ctx.miner or "cereal_duty_switch"
    mod = _pack_module()
    bars = ctx.bars("WHEAT", "H1") or ctx.bars("WHEAT", "D1")
    if bars is None:
        ctx.note("cereal_duty_switch:bars:WHEAT", "no tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "cereal_duty_switch", "why": "no WHEAT tape"}
    lo, hi = K.tape_span(bars)
    decrees = [d for d in mod.duty_switch_dates() if lo <= d <= hi]
    boundary = mod.campaign_boundary_days(lo, hi)
    used, why = (decrees, "PRESS_REPORTED decree dates") if len(decrees) >= 6 else (
        sorted(set(decrees) | set(boundary)), "decrees plus the marketing-year boundary days, "
        "because the recorded decree sample alone is below the event floor")
    placebo = [d for d in K.month_days(lo, hi, (1,))
               if d.month not in mod.CAMPAIGN_BOUNDARY_MONTHS]
    main: dict[str, Any] = K.event_study(
        pack, ctx, name="cereal_duty_switch", symbols=("WHEAT", "CORN"), dates=used,
        mechanism="ma_soft_wheat_duty_decree",
        actor="ADII and the Ministry of Agriculture as the tariff switch",
        constraint="the duty is restored to protect the May-June harvest and suspended for the "
                   "October-November import season; the subsidised flour price never moves",
        rationale="a suspension opens a 5-7 mt import window on French and Black Sea wheat and a "
                  "restoration closes it; the decision is administered and dated, not a price "
                  "response",
        falsifier="the decree windows match the SAME boundary days in years with no decree, or "
                  "the out-of-season first-of-month placebo",
        source_id=f"{SOURCE}:bo_duty", required_data=["BO:decrets_douane", "ONICL:imports"],
        horizon="session",
        payload={"domain": "MA-F", "dates_used": why, "n_decrees": len(decrees),
                 "evidence_label": "PRESS_REPORTED -- no cell compiled here may be promoted "
                                   "until a Bulletin Officiel number is attached"})
    ctrl = K.event_study(
        pack, ctx, name="cereal_duty_placebo", symbols=("WHEAT",), dates=placebo,
        mechanism="ma_soft_wheat_duty_placebo", actor="placebo", constraint="none",
        rationale="the first of a month outside the marketing-year boundary carries no decree",
        falsifier="n/a", source_id=f"{SOURCE}:bo_duty_placebo", required_data=[],
        horizon="session", payload={"domain": "MA-F", "placebo": True},
        novelty=0.0, confidence=0.0)
    main["placebo"] = {k: v for k, v in ctrl.items() if k != "readings"}
    main["boundary_days"] = len(boundary)
    return main


def ramadan_clock_shift(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """MA-L: Morocco's own session mechanism. Inside the declared Ramadan window the country is
    on UTC+0, so the whole local day -- the bourse open, the reference-rate publication -- is one
    hour LATER in UTC. The control is the SAME UTC hour on matched weekdays 26 weeks away, which
    is the only way to tell a clock shift from a season."""
    ctx.miner = ctx.miner or "ramadan_clock_shift"
    mod = _pack_module()
    bars = ctx.bars("EURUSD", "H1")
    if bars is None:
        ctx.note("ramadan_clock_shift:bars:EURUSD", "no H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "ramadan_clock_shift", "why": "no EURUSD tape"}
    lo, hi = K.tape_span(bars)
    gmt_days = mod.gmt_window_weekdays(lo, hi)
    if not gmt_days:
        ctx.note("ramadan_clock_shift:window", "no declared UTC+0 window inside the tape span")
        return {"outcome": K.UNMEASURED, "miner": "ramadan_clock_shift",
                "why": "the tape does not reach a declared Ramadan clock window"}
    main: dict[str, Any] = K.event_study(
        pack, ctx, name="ramadan_clock_shift", symbols=("EURUSD", "XAUUSD", "E35"),
        dates=gmt_days, mechanism="ma_ramadan_utc0_session_shift",
        actor="the Ministry of Habous and the government that decree the return to UTC+0",
        constraint="from the Sunday before Ramadan at 03:00 to the Sunday after Aid al-Fitr at "
                   "02:00 the country keeps UTC+0 instead of UTC+1, so every local hour lands "
                   "one hour later in UTC",
        rationale="the Moroccan session and the reference-rate publication move into the 09:00 "
                  "UTC band that is otherwise the European mid-morning; a session study that "
                  "pools these weeks averages two different hours of the global day",
        falsifier="the same UTC hour band on matched weekdays 26 weeks away behaves identically, "
                  "or the Turkish and Egyptian Ramadan weeks -- the fast WITHOUT the clock "
                  "change -- show the same signature",
        source_id=f"{SOURCE}:clock", required_data=["RAMADAN_CLOCK"], horizon="session",
        hours=(9, 11),
        payload={"domain": "MA-L", "n_gmt_weekdays": len(gmt_days),
                 "windows": {y: [w[0].isoformat(), w[1].isoformat(), w[2]]
                             for y, w in mod.RAMADAN_CLOCK.items()}})
    ctrl = K.event_study(
        pack, ctx, name="ramadan_clock_control", symbols=("EURUSD",),
        dates=K.shift(gmt_days, 182), mechanism="ma_ramadan_utc0_matched_control",
        actor="control", constraint="none",
        rationale="the same weekdays 26 weeks away, when Morocco is on UTC+1 and the same UTC "
                  "hour is the Moroccan mid-morning rather than the open",
        falsifier="n/a", source_id=f"{SOURCE}:clock_control", required_data=[],
        horizon="session", hours=(9, 11), payload={"domain": "MA-L", "control": True},
        novelty=0.0, confidence=0.0)
    main["matched_control"] = {k: v for k, v in ctrl.items() if k != "readings"}
    return main


def transmission_seeds(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """The pack's transmission map as HYPOTHESIS discoveries -- the map the law grants a region
    before its tape has been read."""
    ctx.miner = ctx.miner or "transmission_seeds"
    mod = _pack_module()
    seeded: dict[str, Any] = K.seed_edges(
        pack, ctx, name="transmission_seeds", edges=mod.TRANSMISSION_EDGES_SEED,
        mechanism_prefix="ma_transmission", source_id=f"{SOURCE}:edges")
    return seeded


MINERS: dict[str, Any] = {
    "bam_conseil_windows": bam_conseil_windows,
    "basket_band_pressure": basket_band_pressure,
    "advance_tender_week": advance_tender_week,
    "cereal_duty_switch": cereal_duty_switch,
    "ramadan_clock_shift": ramadan_clock_shift,
    "transmission_seeds": transmission_seeds,
}
