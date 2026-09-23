"""THE PACIFIC'S OWN MINERS -- five clocks the generic set cannot know.

`MINERS` maps a name to `callable(pack, ctx) -> dict`, the contract `country_lab.run_lab` reads
for a pack directory's `miners.py`, and every entry in the pack's `CUSTOM_MINERS`
(`countries.pacific.miners:<function>`) resolves to a function here, so the two registrations
are one set. Each miner builds ITS OWN event dates from the pack's tables -- the PNG LNG
nomination window and the declared outage rows, the New Caledonia and Solomon nickel disruption
rows, the June-December Fiji crushing season, the week-open bars on the earliest-opening ground
on earth -- and hands them to the framework's event study through the shared kit, so a Pacific
finding carries the same matched-weekday control, randomised-date null and adjacent-day placebo
as every other country's.

THREE THINGS THIS REGION FORCES ON EVERY MINER HERE.

  1. EVERY STUDY CARRIES ITS OWN PLACEBO. The Pacific's event samples are SMALL -- four dated
     LNG interruptions, five nickel ones -- so a matched-weekday control alone is not enough to
     tell an effect from the calendar. Each miner below runs an explicit no-event arm on the
     same instrument: the mid-month days that carry no cargo nomination, the matched
     non-disruption days in the same months, the out-of-season months, the Tuesday open.

  2. THE STATUS COLUMN TRAVELS WITH THE DATE. The pack's disruption rows are labelled RECORDED
     (the day is hard and public) or REPORTED (the month is certain, the day comes from press
     reporting). Both are used, the counts of each are carried in every payload, and a reading
     that depends on REPORTED rows says so -- pooling them silently is the defect this column
     exists to prevent.

  3. THE WEAK LEG IS NAMED. JKM, the JCC index and the LME book are absent from this box, so a
     PNG LNG reading on Henry Hub and a nickel reading on a broker CFD are declared weak-proxy
     readings in their own rationale and falsifier, not in a footnote somebody may not read.

Discoveries go through `ctx.record` and nowhere else.
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

SOURCE = "pacific:pack"


def _pack_module() -> Any:
    """The pack module beside this one, however this file was loaded."""
    try:
        from countries.pacific import pack as mod  # type: ignore[import-not-found]
    except ImportError:
        spec = importlib.util.spec_from_file_location(
            "country_pacific_pack", Path(__file__).resolve().parent / "pack.py")
        if spec is None or spec.loader is None:  # pragma: no cover
            raise
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


def _rows(table: Any, lo: date, hi: date) -> tuple[list[date], dict[str, int]]:
    """The dated rows of a disruption table that fall inside the tape, with the RECORDED /
    REPORTED split counted. The split is carried into every payload: a reading that rests on
    press-dated rows is a different claim from one that rests on gazetted ones."""
    days: list[date] = []
    counts = {"RECORDED": 0, "REPORTED": 0}
    for iso, _what, status in table:
        try:
            day = date.fromisoformat(str(iso))
        except ValueError:  # pragma: no cover -- a malformed row is a pack defect
            continue
        if lo <= day <= hi:
            days.append(day)
            counts[str(status)] = counts.get(str(status), 0) + 1
    return days, counts


def png_lng_loading_clock(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """PAC-PNG-C: ONE PLANT, ONE BERTH, TWO ARMS.

    Arm one is the monthly cargo NOMINATION window -- the opening five business days in which
    the following month's lifting programme is fixed -- against the mid-month days that carry no
    nomination. Arm two is the declared OUTAGE rows: the 2018 Highlands earthquake, the 2024
    state of emergency and the Mulitaka landslide. The gas leg on this box is Henry Hub, which
    is a weak proxy for an Asian cargo, and both arms say so in their own rationale.
    """
    ctx.miner = ctx.miner or "png_lng_loading_clock"
    mod = _pack_module()
    bars = ctx.bars("XNGUSD", "H1")
    if bars is None:
        ctx.note("png_lng_loading_clock:bars:XNGUSD", "no H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "png_lng_loading_clock",
                "why": "no XNGUSD tape"}
    lo, hi = K.tape_span(bars)
    events = K.month_days(lo, hi, mod.LNG_NOMINATION_DAYS)
    placebo = K.month_days(lo, hi, mod.LNG_PLACEBO_DAYS)
    outages, split = _rows(mod.LNG_DISRUPTIONS, lo, hi)
    out: dict[str, Any] = K.event_study(
        pack, ctx, name="png_lng_loading_clock", symbols=("XNGUSD", "XBRUSD"), dates=events,
        mechanism="pacific_png_lng_nomination_window",
        actor="ExxonMobil PNG as the PNG LNG operator and its Asian term buyers",
        constraint="the following month's lifting programme is fixed in the opening business "
                   "days and the plant loads at a single marine terminal at Caution Bay",
        rationale="a short nomination is a forward physical-supply signal the term buyers act "
                  "on; the leg the desk can quote is Henry Hub, which is a WEAK PROXY for an "
                  "Asian cargo, and this reading is never promoted above HYPOTHESIS on it alone",
        falsifier="the nomination window matches the mid-month placebo or the matched-weekday "
                  "control, which is the honest expectation for a scheduling event that is not "
                  "publicly disclosed",
        source_id=f"{SOURCE}:png_lng", required_data=["PNG LNG lifting programme"],
        horizon="session", hours=(22, 23),
        payload={"domain": "PAC-PNG-C", "placebo_days": list(mod.LNG_PLACEBO_DAYS),
                 "weak_proxy": "XNGUSD is Henry Hub; JKM and JCC are absent from this box"})
    ctrl: dict[str, Any] = K.event_study(
        pack, ctx, name="png_lng_nomination_placebo", symbols=("XNGUSD",), dates=placebo,
        mechanism="pacific_png_lng_nomination_placebo", actor="placebo", constraint="none",
        rationale="the 12th to the 16th carry no nomination; a move here is the calendar",
        falsifier="n/a", source_id=f"{SOURCE}:png_lng_placebo", required_data=[],
        horizon="session", hours=(22, 23),
        payload={"domain": "PAC-PNG-C", "placebo": True}, novelty=0.0, confidence=0.0)
    out["placebo"] = {k: v for k, v in ctrl.items() if k != "readings"}
    if outages:
        out["outages"] = K.event_study(
            pack, ctx, name="png_lng_outage_dates", symbols=("XNGUSD", "XBRUSD"), dates=outages,
            mechanism="pacific_png_lng_unplanned_outage",
            actor="ExxonMobil PNG, and the guria, landslide or state of emergency that stopped it",
            constraint="one train complex and one berth, with highlands infrastructure exposed "
                       "to earthquakes and roadblocks; the sample is FOUR dated interruptions",
            rationale="8-9 mtpa of Asian supply stops at once and the term buyers must replace "
                      "the cargo from the spot market",
            falsifier="the outage windows match the matched-weekday control and the no-outage "
                      "months -- the expected result if Atlantic-basin gas does not read a "
                      "Pacific outage, which this miner records rather than hides",
            source_id=f"{SOURCE}:png_lng_outage",
            required_data=["LNG_DISRUPTIONS rows with their RECORDED/REPORTED status"],
            horizon="overnight",
            payload={"domain": "PAC-PNG-C", "status_split": split, "n_outages": len(outages)})
    else:
        ctx.note("png_lng_loading_clock:outages", "no declared outage falls inside this tape")
    return out


def nickel_supply_shock(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """PAC-NC-A / PAC-SB-A: the New Caledonia and Solomon nickel disruption dates on XNIUSD.

    The framework supplies the matched-weekday control; this miner adds the placebo the region
    actually needs -- MATCHED NON-DISRUPTION DAYS drawn from the same calendar months of the
    same years, so a 'May 2024 effect' can be told from 'the riots'. The whole point is that an
    Indonesian NPI surplus may have made a tenth-of-world-reserves producer price-irrelevant,
    and either answer is a finding.
    """
    ctx.miner = ctx.miner or "nickel_supply_shock"
    mod = _pack_module()
    bars = ctx.bars("XNIUSD", "H1")
    if bars is None:
        ctx.note("nickel_supply_shock:bars:XNIUSD", "no H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "nickel_supply_shock", "why": "no XNIUSD tape"}
    lo, hi = K.tape_span(bars)
    events, split = _rows(mod.NICKEL_DISRUPTIONS, lo, hi)
    if not events:
        ctx.note("nickel_supply_shock:dates", "no declared disruption falls inside this tape")
        return {"outcome": K.UNMEASURED, "miner": "nickel_supply_shock",
                "why": "no disruption date inside the tape span"}
    months = sorted({d.month for d in events})
    hit = {d.isoformat() for d in events}
    placebo = [d for d in K.month_days(lo, hi, (7, 8, 9, 21, 22, 23))
               if d.month in months and d.isoformat() not in hit]
    out: dict[str, Any] = K.event_study(
        pack, ctx, name="nickel_supply_shock", symbols=("XNIUSD", "XCUUSD"), dates=events,
        mechanism="pacific_new_caledonia_nickel_disruption",
        actor="Societe Le Nickel, Koniambo Nickel and Prony Resources, and the roadblocks that "
              "cut the rouleurs from the mines",
        constraint="every tonne of ore moves by truck; a roadblock stops haulage before any "
                   "plant decision is taken, and the sample is FIVE dated interruptions",
        rationale="a producer holding roughly a tenth of world nickel reserves loses haulage "
                  "and smelting at once; XNIUSD is a broker CFD on the LME leg and not the LME "
                  "book, which is stated here and not in a footnote",
        falsifier="the disruption dates match BOTH the matched-weekday control and the "
                  "no-disruption placebo drawn from the same months, which would say the "
                  "Indonesian surplus has made this producer price-irrelevant",
        source_id=f"{SOURCE}:nc_nickel",
        required_data=["NICKEL_DISRUPTIONS rows with their RECORDED/REPORTED status"],
        horizon="overnight",
        payload={"domain": "PAC-NC-A", "status_split": split, "n_events": len(events),
                 "months_sampled": months})
    if placebo:
        ctrl: dict[str, Any] = K.event_study(
            pack, ctx, name="nickel_no_disruption_placebo", symbols=("XNIUSD",), dates=placebo,
            mechanism="pacific_nickel_no_disruption_placebo", actor="placebo",
            constraint="none", rationale="the same months, the same instrument, no disruption",
            falsifier="n/a", source_id=f"{SOURCE}:nc_nickel_placebo", required_data=[],
            horizon="overnight", payload={"domain": "PAC-NC-A", "placebo": True},
            novelty=0.0, confidence=0.0)
        out["placebo"] = {k: v for k, v in ctrl.items() if k != "readings"}
    else:
        ctx.note("nickel_supply_shock:placebo", "no matched non-disruption day could be built")
    return out


def fiji_crush_season(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """PAC-FJ-B: the June-December Fiji crushing season on SUGARRAW and SUGAR.

    The design IS the placebo: the mills cannot crush outside the season, so the January-May
    months are a real no-treatment arm on the same instrument rather than a gap in the sample.
    Fiji makes a fraction of a per cent of world sugar, so the honest expectation is no outward
    effect, and the out-of-season arm is what makes that answer readable instead of assumed.
    """
    ctx.miner = ctx.miner or "fiji_crush_season"
    mod = _pack_module()
    bars = ctx.bars("SUGARRAW", "H1") or ctx.bars("SUGAR", "H1")
    if bars is None:
        ctx.note("fiji_crush_season:bars:SUGARRAW", "no H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "fiji_crush_season", "why": "no sugar tape"}
    lo, hi = K.tape_span(bars)
    weekly = K.month_days(lo, hi, (1, 8, 15, 22))
    events = [d for d in weekly if d.month in mod.CRUSH_MONTHS]
    placebo = [d for d in weekly if d.month in mod.OUT_OF_SEASON_MONTHS]
    out: dict[str, Any] = K.event_study(
        pack, ctx, name="fiji_crush_season", symbols=("SUGARRAW", "SUGAR"), dates=events,
        mechanism="pacific_fiji_crushing_season_supply",
        actor="the Fiji Sugar Corporation and the cane growers of Viti Levu and Vanua Levu",
        constraint="cane ripens on a calendar; the Lautoka, Rarawai and Labasa mills crush only "
                   "between June and December and the weekly crush table is published through it",
        rationale="150-200kt of raw sugar reaches the world market in season and none outside "
                  "it; the mechanism is TIMING rather than size, which is why it is measured as "
                  "a seasonal event study and not as a supply shock",
        falsifier="the in-season windows match the OUT-OF-SEASON months and the matched-weekday "
                  "control, which is the expected result for a producer this small and is "
                  "recorded as the finding rather than dressed up",
        source_id=f"{SOURCE}:fsc", required_data=["FSC:crush_weekly"], horizon="session",
        hours=(20, 23),
        payload={"domain": "PAC-FJ-B", "season_months": list(mod.CRUSH_MONTHS),
                 "n_in_season": len(events)})
    ctrl: dict[str, Any] = K.event_study(
        pack, ctx, name="fiji_out_of_season_placebo", symbols=("SUGARRAW",), dates=placebo,
        mechanism="pacific_fiji_out_of_season_placebo", actor="placebo",
        constraint="the mills are shut from January to May",
        rationale="the same weekly grid on the same instrument with no Fijian crush at all",
        falsifier="n/a", source_id=f"{SOURCE}:fsc_placebo", required_data=[],
        horizon="session", hours=(20, 23),
        payload={"domain": "PAC-FJ-B", "placebo": True,
                 "placebo_months": list(mod.OUT_OF_SEASON_MONTHS)},
        novelty=0.0, confidence=0.0)
    out["placebo"] = {k: v for k, v in ctrl.items() if k != "readings"}
    return out


def dateline_monday_open(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """PAC-REG-C: the week-open gap, read from the earliest-opening ground on earth.

    Samoa and Tonga sit at UTC+13 and Fiji at UTC+12, so Apia reaches 08:00 on Monday about
    three hours before the FX week opens in Wellington and Sydney. Anything that happened in the
    Pacific over the weekend -- a cyclone landfall, a mine or LNG stoppage, a state of emergency,
    a currency notice -- has been public and acted on by Pacific institutions for hours before
    the first quote exists. THE EVENT IS THEREFORE THE SUNDAY BAR, 21:00-23:00 UTC, which is the
    week's first bars; the PLACEBO is the Monday bar in the SAME UTC HOURS, a mid-week open with
    no weekend behind it. This is the one mechanism in the pack that needs no Pacific statistic.
    """
    ctx.miner = ctx.miner or "dateline_monday_open"
    symbols = ("AUDUSD", "NZDUSD", "AUDNZD")
    bars = ctx.bars("AUDUSD", "H1")
    if bars is None:
        ctx.note("dateline_monday_open:bars:AUDUSD", "no H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "dateline_monday_open", "why": "no AUDUSD tape"}
    lo, hi = K.tape_span(bars)
    week_open = K.weekday_dates(lo, hi, 6)      # Sundays: the 21:00 UTC bars open the week
    midweek = K.weekday_dates(lo, hi, 0)        # Mondays: the same hours, no weekend gap
    out: dict[str, Any] = K.event_study(
        pack, ctx, name="dateline_monday_open", symbols=symbols, dates=week_open,
        mechanism="pacific_dateline_week_open_gap",
        actor="the Pacific institutions -- banks, ports, disaster offices, central banks -- "
              "already open in Apia, Nuku'alofa and Suva before any FX market is",
        constraint="the region spans UTC+10 to UTC+13 and Samoa and Tokelau crossed the "
                   "dateline at the end of 29 December 2011, so Monday begins here first and "
                   "no quote exists for the first two to three hours of it",
        rationale="a weekend Pacific event is public and being acted on before the tape opens, "
                  "so the week's first bars carry information that the Friday close could not",
        falsifier="the week-open bars match the TUESDAY-open placebo in the same UTC hours and "
                  "the matched weekday-and-hour control, in which case the gap is the ordinary "
                  "weekend gap every market has and owes nothing to the dateline",
        source_id=f"{SOURCE}:dateline", required_data=["the tape's own weekly boundary"],
        horizon="session", hours=(21, 23),
        payload={"domain": "PAC-REG-C", "window_utc": "21:00-23:00 on the Sunday bar",
                 "n_weeks": len(week_open)})
    ctrl: dict[str, Any] = K.event_study(
        pack, ctx, name="dateline_midweek_placebo", symbols=("AUDUSD", "AUDNZD"), dates=midweek,
        mechanism="pacific_dateline_midweek_placebo", actor="placebo",
        constraint="the same UTC hours on a Monday, which opens Tuesday in Sydney",
        rationale="a mid-week open with no weekend and no Pacific head start behind it",
        falsifier="n/a", source_id=f"{SOURCE}:dateline_placebo", required_data=[],
        horizon="session", hours=(21, 23),
        payload={"domain": "PAC-REG-C", "placebo": True}, novelty=0.0, confidence=0.0)
    out["placebo"] = {k: v for k, v in ctrl.items() if k != "readings"}
    return out


def transmission_seeds(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """The pack's transmission map as HYPOTHESIS discoveries -- the map the law grants a region
    before its tape has been read (LAWS 5n)."""
    ctx.miner = ctx.miner or "transmission_seeds"
    mod = _pack_module()
    out: dict[str, Any] = K.seed_edges(
        pack, ctx, name="transmission_seeds", edges=mod.TRANSMISSION_EDGES_SEED,
        mechanism_prefix="pacific_transmission", source_id=f"{SOURCE}:edges")
    return out


MINERS: dict[str, Any] = {
    "png_lng_loading_clock": png_lng_loading_clock,
    "nickel_supply_shock": nickel_supply_shock,
    "fiji_crush_season": fiji_crush_season,
    "dateline_monday_open": dateline_monday_open,
    "transmission_seeds": transmission_seeds,
}
