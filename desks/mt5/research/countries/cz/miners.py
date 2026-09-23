"""CZECHIA'S OWN MINERS -- the six clocks the generic set cannot know.

`MINERS` maps a name to `callable(pack, ctx) -> dict`, the contract `country_lab.run_lab` reads
for a pack directory's `miners.py`, and every entry in the pack's `CUSTOM_MINERS`
(`countries.cz.miners:<function>`) resolves to a function here, so the two registrations are one
set. Each miner builds ITS OWN event dates from the pack's tables -- the CNB's fixed 14:30 local
decision minute, the 2013/2017 floor boundaries, the midweek auction clock, the statutory
holiday calendar and the day-ahead power series -- and hands them to the framework's event study
through the shared kit, so a Czech finding carries the same matched-weekday control, randomised-
date null and adjacent-day placebo as every other country's. Discoveries go through `ctx.record`
and nowhere else.
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

SOURCE = "cz:pack"


def _pack_module() -> Any:
    try:
        from countries.cz import pack as mod  # type: ignore[import-not-found]
    except ImportError:
        spec = importlib.util.spec_from_file_location(
            "country_cz_pack", Path(__file__).resolve().parent / "pack.py")
        if spec is None or spec.loader is None:  # pragma: no cover
            raise
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


def cnb_decision_windows(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """CZ-A: the eight-a-year decision at a FIXED 14:30 local minute, run SEPARATELY for the
    two DST regimes -- because the same local minute is 13:30 UTC in winter and 12:30 UTC in
    summer, and a pooled UTC window is two windows averaged into one."""
    ctx.miner = ctx.miner or "cnb_decision_windows"
    mod = _pack_module()
    dates = [date.fromisoformat(d) for d in pack.central_bank.decision_dates]
    winter = [d for d in dates if mod.utc_offset_hours(d) == 1]
    summer = [d for d in dates if mod.utc_offset_hours(d) == 2]
    out: dict[str, Any] = {"miner": "cnb_decision_windows", "legs": {}}
    for label, days, hours in (("cet", winter, (13, 15)), ("cest", summer, (12, 14))):
        got = K.event_study(
            pack, ctx, name=f"cnb_decision_{label}", symbols=("EURCZK", "USDCZK", "EURPLN"),
            dates=days, mechanism=f"cz_cnb_decision_{label}", actor="the bankovni rada CNB",
            constraint="eight scheduled decisions a year, announced at a fixed 14:30 local "
                       "minute, with the vote split published eight days later",
            rationale="the koruna is DIRECTLY EXECUTABLE at this broker, so a Czech policy "
                      "surprise is a cell rather than a proxy -- and the CNB publishes its own "
                      "forecast rate path, so the surprise has a scale",
            falsifier="the decision window matches the four nearest non-meeting Thursdays at "
                      "the same LOCAL clock, or matches ECB decision days, in which case this "
                      "is a weekday effect or a euro event wearing the CNB's hat",
            source_id=f"{SOURCE}:cnb", required_data=["CNB:2T_repo_sazba", "decision calendar"],
            horizon="intraday", hours=hours,
            payload={"domain": "CZ-A", "dst_regime": label, "n_dates": len(days),
                     "sample_note": "the two DST legs are NEVER pooled; each is reported with "
                                    "its own event count"})
        out["legs"][label] = got
    out["outcome"] = next((g.get("outcome") for g in out["legs"].values()
                           if g.get("outcome") != K.UNMEASURED), K.UNMEASURED)
    return out


def floor_regime_break(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """CZ-B: the EUR/CZK floor as a regime BOUNDARY, with the CEE peers as the concurrent null.

    Two dates is far below any event floor and the miner says so rather than padding the sample:
    what it tests is the DISTRIBUTION either side of the boundary, on the koruna and on the two
    neighbours that had no floor at all.
    """
    ctx.miner = ctx.miner or "floor_regime_break"
    mod = _pack_module()
    bars = ctx.bars("EURCZK", "D1") or ctx.bars("EURCZK", "H1")
    if bars is None:
        ctx.note("floor_regime_break:bars:EURCZK", "no tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "floor_regime_break", "why": "no EURCZK tape"}
    lo, hi = K.tape_span(bars)
    boundaries = [d for d in (mod.FLOOR_REGIME["announced"], mod.FLOOR_REGIME["exited"])
                  if lo <= d <= hi]
    inside = mod.floor_era_days(lo, hi)
    got: dict[str, Any] = K.event_study(
        pack, ctx, name="floor_regime_break", symbols=("EURCZK", "EURPLN", "EURHUF"),
        dates=boundaries or inside[:1], mechanism="cz_floor_regime_break",
        actor="the CNB FX desk as the floor's unlimited counterparty",
        constraint="a ONE-SIDED commitment at 27.00 CZK/EUR from 2013-11-07 to 2017-04-06; the "
                   "downside of the EURCZK distribution was administratively removed",
        rationale="every EURCZK volatility, tail, carry and momentum statistic spanning the "
                  "boundary is estimated on two different random variables glued together",
        falsifier="the era's EURCZK distribution matches the surrounding years' once the pin is "
                  "removed, or the same shift appears in EURPLN and EURHUF -- in which case it "
                  "is a regional factor and not the commitment",
        source_id=f"{SOURCE}:floor", required_data=["CNB:kurz_EURCZK", "CNB:reserves"],
        horizon="multi_day", payload={"domain": "CZ-B", "n_boundaries": len(boundaries),
                                      "n_days_inside_tape": len(inside),
                                      "sample_note": "TWO dated boundaries is below the event "
                                                     "floor and is reported as such; the "
                                                     "distributional test is the real object"})
    got["floor_regime"] = {k: str(v) for k, v in mod.FLOOR_REGIME.items()
                           if k in ("level_czk_per_eur", "announced", "exited", "side")}
    return got


def auction_calendar(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """CZ-G: the MF CR midweek auction clock, with the matched non-auction weekday placebo run
    beside it so a midweek effect can be told from a weekday effect."""
    ctx.miner = ctx.miner or "auction_calendar"
    bars = ctx.bars("EURCZK", "H1") or ctx.bars("EURCZK", "D1")
    if bars is None:
        ctx.note("auction_calendar:bars:EURCZK", "no tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "auction_calendar", "why": "no EURCZK tape"}
    lo, hi = K.tape_span(bars)
    midweek = K.weekday_dates(lo, hi, 2)
    placebo = K.weekday_dates(lo, hi, 4)
    main: dict[str, Any] = K.event_study(
        pack, ctx, name="auction_calendar", symbols=("EURCZK", "USDCZK"), dates=midweek,
        mechanism="cz_mfcr_auction_window",
        actor="the Ministry of Finance debt desk",
        constraint="the issuance calendar is published A QUARTER AHEAD, so the timing carries "
                   "no surprise and only the cut-off and the bid-to-cover can",
        rationale="a dated forced-supply event on a currency this broker quotes directly is "
                  "one of the few prospectively testable clocks on the whole desk",
        falsifier="the midweek window matches the Friday placebo or the matched weekday "
                  "control, in which case this is a weekday effect and not an auction effect",
        source_id=f"{SOURCE}:mfcr", required_data=["MFCR:auction_yield"],
        horizon="session", hours=(8, 12),
        payload={"domain": "CZ-G", "placebo_day": "Friday", "n_midweek": len(midweek),
                 "note": "the exact auction dates come from the MF CR calendar; until that "
                         "series is on the box the miner uses the midweek clock and SAYS SO"})
    ctrl = K.event_study(
        pack, ctx, name="auction_calendar_placebo", symbols=("EURCZK",), dates=placebo,
        mechanism="cz_mfcr_auction_placebo", actor="placebo", constraint="none",
        rationale="Friday carries no scheduled auction; a move here is the calendar",
        falsifier="n/a", source_id=f"{SOURCE}:mfcr_placebo", required_data=[],
        horizon="session", hours=(8, 12), payload={"domain": "CZ-G", "placebo": True},
        novelty=0.0, confidence=0.0)
    main["placebo"] = {k: v for k, v in ctrl.items() if k != "readings"}
    return main


def holiday_session_clock(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """CZ-L and CZ-K: the SINGLE-COUNTRY closures -- Czech weekday holidays that are not German
    ones -- against the matched-weekday control. A shared 25 December tells the desk nothing
    about Czechia, which is why the miner filters the calendar before it uses it."""
    ctx.miner = ctx.miner or "holiday_session_clock"
    mod = _pack_module()
    bars = ctx.bars("EURCZK", "H1") or ctx.bars("EURCZK", "D1")
    if bars is None:
        ctx.note("holiday_session_clock:bars:EURCZK", "no tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "holiday_session_clock",
                "why": "no EURCZK tape"}
    lo, hi = K.tape_span(bars)
    solo: list[date] = []
    lost: list[date] = []
    for year in range(lo.year, hi.year + 1):
        solo.extend(d for d in mod.single_country_closures(year) if lo <= d <= hi)
        lost.extend(d for d in mod.lost_weekend_holidays(year) if lo <= d <= hi)
    got: dict[str, Any] = K.event_study(
        pack, ctx, name="holiday_session_clock", symbols=("EURCZK", "EUSTX50", "GER40"),
        dates=sorted(solo), mechanism="cz_single_country_closure",
        actor="the statute (zakon c. 245/2000 Sb.) and the exchange calendar",
        constraint="Czech law grants NO substitute day, so a holiday at the weekend closes "
                   "nothing and the closed-session count varies by up to four days a year",
        rationale="a single-country closure removes the domestic market maker and the local "
                  "corporate flow while the euro-area tape runs, thinning one leg of the pair "
                  "and not the other",
        falsifier="single-country closure days match the matched weekday 26 weeks away on every "
                  "spread and range measure, or German holidays show the same shape",
        source_id=f"{SOURCE}:statute", required_data=["national_holidays"],
        horizon="session", hours=(7, 16),
        payload={"domain": "CZ-L", "n_solo_closures": len(solo),
                 "n_lost_weekend_holidays": len(lost),
                 "note": "LOST weekend holidays are carried as a separate count because they "
                         "close no session at all -- the half of the calendar a naive closed-"
                         "day count invents"})
    return got


def power_outage_fuel(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """CZ-F and CZ-M: the Czech day-ahead power price as a dated lead into the executable fuel
    and smelter legs. The power price itself is not quoted here, so it enters as a SERIES and
    the claim terminates in XNGUSD and XALUSD."""
    ctx.miner = ctx.miner or "power_outage_fuel"
    got: dict[str, Any] = K.series_lead(
        pack, ctx, name="power_outage_fuel", series_name="OTE:DA_price_CZ",
        symbols=("XNGUSD", "XALUSD", "GER40"), mechanism="cz_power_merit_order",
        actor="CEZ and the coupled day-ahead market operator OTE",
        constraint="the Czech zone clears JOINTLY with Germany, Austria, Poland, Slovakia and "
                   "Hungary at a 12:00 local gate, so the price is set in Leipzig as much as "
                   "in Prague and only the SPREAD is Czech",
        rationale="losing a nuclear block moves the Czech marginal plant toward gas, which "
                  "raises the gas call and the smelter's input cost inside a coupled market",
        falsifier="the Czech day-ahead series carries nothing for XNGUSD or XALUSD once the "
                  "German day-ahead price is controlled for",
        source_id=f"{SOURCE}:ote", horizon_days=5,
        payload={"domain": "CZ-F", "spread_note": "the CZ-DE spread is the interconnector's "
                                                  "binding constraint measured directly"})
    return got


def transmission_seeds(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """The pack's transmission map as HYPOTHESIS discoveries -- the map the law grants a region
    before its tape has been read."""
    ctx.miner = ctx.miner or "transmission_seeds"
    mod = _pack_module()
    seeded: dict[str, Any] = K.seed_edges(
        pack, ctx, name="transmission_seeds", edges=mod.TRANSMISSION_EDGES_SEED,
        mechanism_prefix="cz_transmission", source_id=f"{SOURCE}:edges")
    return seeded


MINERS: dict[str, Any] = {
    "cnb_decision_windows": cnb_decision_windows,
    "floor_regime_break": floor_regime_break,
    "auction_calendar": auction_calendar,
    "holiday_session_clock": holiday_session_clock,
    "power_outage_fuel": power_outage_fuel,
    "transmission_seeds": transmission_seeds,
}
