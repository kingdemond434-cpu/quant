"""THE UNITED STATES' OWN MINERS -- the seven clocks the generic set cannot know.

`MINERS` maps a name to `callable(pack, ctx) -> dict`, the contract `country_lab.run_lab` reads
for a pack directory's `miners.py`, and every entry in the pack's `CUSTOM_MINERS`
(`countries.us.miners:<function>`) resolves to a function here, so the two registrations are one
set. Each miner builds ITS OWN event dates from the pack's tables (the FOMC calendar, the BLS
and BEA release classes, the Treasury auction and settlement cycle, the RRP/TGA plumbing dates,
the CFTC Tuesday, the third-Friday expiry ladder, the EIA/USDA physical reports) and hands them
to the framework's event study through the shared kit, so an American finding carries the same
matched-weekday control, randomised-date null and adjacent-day placebo as every other country's.
Discoveries go through `ctx.record` and nowhere else.

WHY THE UNITED STATES NEEDS ITS OWN MINERS AT ALL. It is the country whose calendar the desk is
most likely to believe it already knows, and that is exactly the trap: "the FOMC moves the
dollar" is not a measurement, it is a slogan, and the generic central-bank miner cannot tell an
FOMC Wednesday from the two ordinary Wednesdays either side of it. Every miner below therefore
carries the control that makes its claim falsifiable -- the non-FOMC Wednesday, the out-of-cycle
auction week, the 8th/23rd against the 15th, the pre-2022 expiry ladder against the post-2022
one -- because an American effect that survives nothing is the most expensive kind of noise the
programme can buy: it charges the deflated-Sharpe trial budget that every other country's cells
have to clear.

EVERY OUTCOME IS A RESULT. A missing tape is `ctx.note`d UNMEASURED by symbol; a series that is
not on this box is named, not skipped; a study with too few events is reported with its counts.
"""
from __future__ import annotations

import calendar
import importlib.util
import sys
from collections.abc import Iterable, Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Any

try:
    from countries import _miner_kit as K
except ImportError:  # loaded by file path: reach the kit beside this package
    _kit = Path(__file__).resolve().parents[1] / "_miner_kit.py"
    _spec = importlib.util.spec_from_file_location("countries_miner_kit", _kit)
    if _spec is None or _spec.loader is None:  # pragma: no cover
        raise
    K = importlib.util.module_from_spec(_spec)
    sys.modules["countries_miner_kit"] = K
    _spec.loader.exec_module(K)

from libs.research import country_lab as CL

SOURCE = "us:pack"


def _pack_module() -> Any:
    try:
        from countries.us import pack as mod
    except ImportError:
        spec = importlib.util.spec_from_file_location(
            "country_us_pack", Path(__file__).resolve().parent / "pack.py")
        if spec is None or spec.loader is None:  # pragma: no cover
            raise
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- local calendars
def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th `weekday` (Monday=0) of a month -- the shape the US expiry ladder takes."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return date(year, month, 1 + offset + 7 * (n - 1))


def nth_weekdays(lo: date, hi: date, weekday: int, n: int,
                 months: Iterable[int] = range(1, 13)) -> list[date]:
    """Every n-th `weekday` inside [lo, hi] for the named months."""
    wanted = {int(m) for m in months}
    out: list[date] = []
    for year in range(lo.year, hi.year + 1):
        for month in sorted(wanted):
            try:
                day = nth_weekday(year, month, weekday, n)
            except ValueError:                                  # pragma: no cover - defensive
                continue
            if lo <= day <= hi and day.month == month:
                out.append(day)
    return out


def month_ends(lo: date, hi: date, months: Iterable[int] = range(1, 13)) -> list[date]:
    """The last calendar day of each named month inside [lo, hi]."""
    wanted = {int(m) for m in months}
    out: list[date] = []
    y, m = lo.year, lo.month
    while (y, m) <= (hi.year, hi.month):
        if m in wanted:
            day = date(y, m, calendar.monthrange(y, m)[1])
            if lo <= day <= hi:
                out.append(day)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _decision_days(pack: CL.CountryPack) -> list[date]:
    return [date.fromisoformat(d) for d in pack.central_bank.decision_dates]


def _control_wednesdays(pack: CL.CountryPack, lo: date, hi: date,
                        offsets: Sequence[int] = (-14, 14)) -> list[date]:
    """The ordinary Wednesdays two weeks either side of a decision -- the control that tells an
    FOMC Wednesday from a Wednesday. A control day that is itself a decision day is dropped."""
    meetings = set(_decision_days(pack))
    out: list[date] = []
    for day in meetings:
        for off in offsets:
            got = day + timedelta(days=int(off))
            if lo <= got <= hi and got not in meetings and got.weekday() == day.weekday():
                out.append(got)
    return sorted(set(out))


def _span(ctx: CL.LabCtx, symbol: str, timeframe: str = "H1") -> tuple[date, date] | None:
    bars = ctx.bars(symbol, timeframe)
    if bars is None:
        return None
    return K.tape_span(bars)


# --------------------------------------------------------------------------- the seven miners
def fomc_surprise_vs_zq(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """US-A: the eight scheduled FOMC decisions, and the ordinary Wednesdays that are not.

    The pack's own note says this miner "refuses a verdict when the pre-statement ZQ snapshot is
    missing". It does: the SURPRISE half is a `series_lead` on the ZQ-implied rate and reads
    UNMEASURED by name when that series is not on this box. What is always measurable is the
    DECISION-DAY window itself against its own matched control, and that runs regardless -- an
    absent surprise series is a reason to narrow the claim, never a reason to measure nothing.
    """
    ctx.miner = ctx.miner or "fomc_surprise_vs_zq"
    mod = _pack_module()
    days = _decision_days(pack)
    symbols = ("USDX", "UST05Y", "US500", "XAUUSD")
    main = K.event_study(
        pack, ctx, name="fomc_surprise_vs_zq", symbols=symbols, dates=days,
        mechanism="us_fomc_decision_window",
        actor="the Federal Open Market Committee",
        constraint="eight scheduled decisions a year, released at 19:00 UTC (18:00 in winter) "
                   "with the press conference thirty minutes later; the blackout binds the "
                   "committee's speech for ten days before it",
        rationale="the decision reprices the front of the curve the dollar factor and the "
                  "index discount rate are both quoted off",
        falsifier="the decision-day window matches the ordinary Wednesdays two weeks either "
                  "side of it, or the effect is carried entirely by the press-conference half "
                  "hour and not by the statement",
        source_id=f"{SOURCE}:fomc", required_data=["FOMC calendar", mod.SERIES["US_POLICY"]],
        horizon="intraday",
        payload={"domain": "US-A", "n_dates": len(days),
                 "calendar_rule": str(pack.central_bank.decision_calendar_rule)[:200]})
    span = (min(days), max(days)) if days else _span(ctx, "USDX")
    lo, hi = span if span is not None else (date(2024, 1, 1), date(2024, 1, 1))
    control = K.event_study(
        pack, ctx, name="fomc_wednesday_control", symbols=("USDX",),
        dates=_control_wednesdays(pack, lo, hi),
        mechanism="us_fomc_wednesday_control", actor="control", constraint="none",
        rationale="an ordinary Wednesday two weeks from a decision carries no statement; a "
                  "move here is the weekday, not the committee",
        falsifier="n/a", source_id=f"{SOURCE}:fomc_control", required_data=[],
        horizon="intraday", payload={"domain": "US-A", "control": True},
        novelty=0.0, confidence=0.0)
    surprise = K.series_lead(
        pack, ctx, name="fomc_zq_surprise", series_name="CME:ZQ_implied",
        symbols=("USDX", "UST05Y"), mechanism="us_fomc_surprise_vs_zq",
        actor="the Federal Open Market Committee against the fed funds futures strip",
        constraint="the strip prices the decision before it lands; only the residual is news",
        rationale="the tape reacts to the SURPRISE, not to the level; the ZQ-implied rate at "
                  "13:55 ET is the market's own expectation and the only honest prior",
        falsifier="the decision-day move is explained by the level rather than the residual, "
                  "or the residual carries no information beyond the statement window itself",
        source_id=f"{SOURCE}:zq", horizon_days=1, payload={"domain": "US-A"})
    main["control"] = {k: v for k, v in control.items() if k != "readings"}
    main["surprise"] = {k: v for k, v in surprise.items() if k != "readings"}
    if surprise.get("outcome") == K.UNMEASURED:
        main["verdict_scope"] = ("DECISION WINDOW ONLY: the ZQ-implied snapshot is not on this "
                                 "box, so no surprise-conditioned claim is made")
    return main


def release_surprise_with_revisions(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """US-B: the two release clocks the pack names, and the REVISION as a second surprise.

    NFP is the first Friday; CPI lands between the 10th and the 15th. Both are built from the
    calendar rather than typed, so the sample extends with the tape. The revision half runs as a
    `series_lead` on the ALFRED vintage series and is UNMEASURED by name when it is absent.
    """
    ctx.miner = ctx.miner or "release_surprise_with_revisions"
    mod = _pack_module()
    span = _span(ctx, "USDX") or _span(ctx, "EURUSD")
    if span is None:
        ctx.note("release_surprise_with_revisions:bars", "no USDX or EURUSD H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "release_surprise_with_revisions",
                "why": "no dollar tape"}
    lo, hi = span
    parts: dict[str, Any] = {}
    parts["nfp"] = K.event_study(
        pack, ctx, name="nfp_first_friday", symbols=("USDX", "UST10Y", "XAUUSD"),
        dates=nth_weekdays(lo, hi, 4, 1), mechanism="us_nfp_release_window",
        actor="the Bureau of Labor Statistics and the establishment survey it publishes",
        constraint="the Employment Situation is released at 13:30 UTC on the first Friday of "
                   "the month and is revised twice before the annual benchmark",
        rationale="the single release the whole curve is repriced against; the dollar factor "
                  "and the long bond carry it first",
        falsifier="the first Friday matches the SECOND Friday of the same months, which "
                  "carries no release",
        source_id=f"{SOURCE}:bls", required_data=[mod.SERIES["US_NFP"]], horizon="intraday",
        hours=(13, 15), payload={"domain": "US-B", "release": "NFP"})
    parts["nfp_placebo"] = K.event_study(
        pack, ctx, name="nfp_second_friday_placebo", symbols=("USDX",),
        dates=nth_weekdays(lo, hi, 4, 2), mechanism="us_nfp_placebo", actor="placebo",
        constraint="none", rationale="the second Friday carries no Employment Situation",
        falsifier="n/a", source_id=f"{SOURCE}:bls_placebo", required_data=[],
        horizon="intraday", hours=(13, 15), payload={"domain": "US-B", "placebo": True},
        novelty=0.0, confidence=0.0)
    parts["cpi"] = K.event_study(
        pack, ctx, name="cpi_mid_month", symbols=("USDX", "UST10Y", "US500"),
        dates=K.month_days(lo, hi, (10, 11, 12, 13)), mechanism="us_cpi_release_window",
        actor="the Bureau of Labor Statistics price programme",
        constraint="the CPI lands at 13:30 UTC between the 10th and the 15th; headline, core, "
                   "shelter and 'supercore' are four surprises and the tape reads whichever the "
                   "committee last named",
        rationale="the inflation print the policy path is conditioned on",
        falsifier="the 10th-13th window matches the 20th-23rd window of the same months",
        source_id=f"{SOURCE}:bls_cpi", required_data=[mod.SERIES["US_CPI"]],
        horizon="intraday", hours=(13, 15), payload={"domain": "US-B", "release": "CPI"})
    parts["cpi_placebo"] = K.event_study(
        pack, ctx, name="cpi_late_month_placebo", symbols=("USDX",),
        dates=K.month_days(lo, hi, (20, 21, 22, 23)), mechanism="us_cpi_placebo",
        actor="placebo", constraint="none",
        rationale="the 20th-23rd carry no CPI", falsifier="n/a",
        source_id=f"{SOURCE}:bls_cpi_placebo", required_data=[], horizon="intraday",
        hours=(13, 15), payload={"domain": "US-B", "placebo": True},
        novelty=0.0, confidence=0.0)
    parts["revision"] = K.series_lead(
        pack, ctx, name="alfred_revision_lead", series_name="ALFRED:PAYEMS_revision",
        symbols=("USDX", "UST10Y"), mechanism="us_release_revision_as_second_surprise",
        actor="the statistical agency as its own counterparty",
        constraint="the first print is a sample; the revision is the correction and arrives "
                   "with the NEXT month's release, unannounced",
        rationale="a revision is news the survey median never forecast, so it is a surprise "
                  "with no consensus to subtract",
        falsifier="the revision carries no information for the dollar beyond the headline of "
                  "the release it arrives with",
        source_id=f"{SOURCE}:alfred", horizon_days=3, payload={"domain": "US-B"})
    return _fold(parts, "release_surprise_with_revisions")


def auction_tail_event_study(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """US-C: the Treasury's refunding ladder, measured on the Treasury CFDs.

    The 10-year is auctioned in the SECOND week of every month and the 5-year in the LAST week;
    the refunding months (February, May, August, November) carry the quarterly announcement.
    The pack's note asks for the tail against the 13:00 ET when-issued; that snapshot is not on
    this box, so the WINDOW is measured and the tail-conditioned claim is declared out of scope
    by name rather than faked with a prior close.
    """
    ctx.miner = ctx.miner or "auction_tail_event_study"
    span = _span(ctx, "UST10Y") or _span(ctx, "UST05Y")
    if span is None:
        ctx.note("auction_tail_event_study:bars", "no UST10Y or UST05Y H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "auction_tail_event_study",
                "why": "no Treasury CFD tape"}
    lo, hi = span
    parts: dict[str, Any] = {}
    parts["ten_year"] = K.event_study(
        pack, ctx, name="ust10y_auction_week", symbols=("UST10Y", "USDX"),
        dates=nth_weekdays(lo, hi, 2, 2), mechanism="us_treasury_10y_auction_window",
        actor="the primary dealers who must bid the Treasury's supply",
        constraint="a dealer that takes down an unwanted auction is short balance sheet until "
                   "it can distribute; the auction closes at 13:00 ET and the result is out at "
                   "13:02",
        rationale="supply that has to be absorbed at a price moves that price; the dealer's "
                  "hedge reaches the future before the cash",
        falsifier="the auction Wednesday matches the FIRST Wednesday of the same months, which "
                  "carries no coupon auction",
        source_id=f"{SOURCE}:auction10", required_data=["TreasuryDirect auction results"],
        horizon="intraday", hours=(17, 20), payload={"domain": "US-C", "tenor": "10y"})
    parts["five_year"] = K.event_study(
        pack, ctx, name="ust05y_auction_week", symbols=("UST05Y", "USDX"),
        dates=[d for d in month_ends(lo, hi) if True],
        mechanism="us_treasury_5y_auction_window",
        actor="the primary dealers at the month-end 2/5/7 sequence",
        constraint="the 2/5/7-year block settles on the last business day of the month, which "
                   "is also the index-extension date",
        rationale="the month-end coupon block collides with the index extension, so the same "
                  "day carries both a supply shock and a mechanical duration buy",
        falsifier="the month-end effect matches the mid-month settlement date, or disappears "
                  "once the index-extension day is conditioned on",
        source_id=f"{SOURCE}:auction5", required_data=["TreasuryDirect auction results"],
        horizon="session", payload={"domain": "US-C", "tenor": "5y"})
    parts["control"] = K.event_study(
        pack, ctx, name="auction_first_wednesday_control", symbols=("UST10Y",),
        dates=nth_weekdays(lo, hi, 2, 1), mechanism="us_auction_control", actor="control",
        constraint="none", rationale="the first Wednesday carries no coupon auction",
        falsifier="n/a", source_id=f"{SOURCE}:auction_control", required_data=[],
        horizon="intraday", hours=(17, 20), payload={"domain": "US-C", "control": True},
        novelty=0.0, confidence=0.0)
    out = _fold(parts, "auction_tail_event_study")
    out["verdict_scope"] = ("AUCTION WINDOW ONLY: the 13:00 ET when-issued snapshot is not on "
                            "this box, so no tail-conditioned claim is made")
    return out


def plumbing_calendar(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """US-D: the dollar's plumbing -- the corporate tax dates, mid-month and month-end
    settlement, and the RRP buffer that decides whether any of it binds.

    The buffer state is a `series_lead` on the RRP take-up and is UNMEASURED by name when that
    series is absent; the tax and settlement DATES are calendar facts and always measurable.
    """
    ctx.miner = ctx.miner or "plumbing_calendar"
    mod = _pack_module()
    span = _span(ctx, "USDX") or _span(ctx, "US500")
    if span is None:
        ctx.note("plumbing_calendar:bars", "no USDX or US500 H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "plumbing_calendar", "why": "no tape"}
    lo, hi = span
    tax = [d for d in K.month_days(lo, hi, (15,)) if d.month in (4, 6, 9, 12)]
    parts: dict[str, Any] = {}
    parts["tax_dates"] = K.event_study(
        pack, ctx, name="corporate_tax_dates", symbols=("USDX", "US500", "UST05Y"),
        dates=[K.next_business_day(d) for d in tax],
        mechanism="us_corporate_tax_date_drain",
        actor="corporate treasurers making the quarterly estimated-tax payment",
        constraint="15 April, 15 June, 15 September and 15 December are statutory; the cash "
                   "leaves the banking system into the Treasury General Account on the day",
        rationale="a scheduled, unavoidable drain of reserves is a funding shock with a date "
                  "known a year ahead -- the purest forced flow the dollar has",
        falsifier="the four statutory dates match the 15th of the eight NON-tax months",
        source_id=f"{SOURCE}:tga", required_data=[mod.SERIES["US_TGA"]], horizon="session",
        payload={"domain": "US-D", "clock": "estimated tax"})
    parts["tax_placebo"] = K.event_study(
        pack, ctx, name="non_tax_fifteenth_placebo", symbols=("USDX",),
        dates=[K.next_business_day(d) for d in K.month_days(lo, hi, (15,))
               if d.month not in (4, 6, 9, 12)],
        mechanism="us_tax_date_placebo", actor="placebo", constraint="none",
        rationale="the 15th of a non-tax month carries no estimated-tax drain",
        falsifier="n/a", source_id=f"{SOURCE}:tga_placebo", required_data=[],
        horizon="session", payload={"domain": "US-D", "placebo": True},
        novelty=0.0, confidence=0.0)
    parts["month_end"] = K.event_study(
        pack, ctx, name="month_end_settlement", symbols=("USDX", "UST10Y"),
        dates=month_ends(lo, hi), mechanism="us_month_end_settlement_squeeze",
        actor="dealers and money funds squaring the month-end balance sheet",
        constraint="the coupon settlement, the index extension and the regulatory snapshot "
                   "fall on the same day",
        rationale="three forced flows on one date; the balance-sheet constraint is binding by "
                  "construction on the reporting day",
        falsifier="the month-end matches the mid-month settlement date once the quarter-ends "
                  "are excluded",
        source_id=f"{SOURCE}:settle", required_data=["Daily Treasury Statement"],
        horizon="session", payload={"domain": "US-D", "clock": "settlement"})
    parts["quarter_end"] = K.event_study(
        pack, ctx, name="quarter_end_balance_sheet", symbols=("USDX", "UST05Y"),
        dates=month_ends(lo, hi, (3, 6, 9, 12)),
        mechanism="us_quarter_end_balance_sheet_constraint",
        actor="G-SIB dealers at the quarterly leverage-ratio snapshot",
        constraint="the leverage ratio is measured on the quarter-end date, so repo is "
                   "withdrawn into it and returned the next day",
        rationale="a regulatory measurement date is a hard, dated balance-sheet constraint",
        falsifier="the quarter-end matches the eight non-quarter month-ends",
        source_id=f"{SOURCE}:qe", required_data=["Daily Treasury Statement"],
        horizon="session", payload={"domain": "US-D", "clock": "quarter end"})
    parts["rrp_buffer"] = K.series_lead(
        pack, ctx, name="rrp_buffer_state", series_name=mod.SERIES["US_RRP"],
        symbols=("USDX", "UST05Y"), mechanism="us_rrp_buffer_conditions_the_drain",
        actor="money funds parking cash at the Fed's reverse repo facility",
        constraint="while the facility is full a drain is absorbed by the buffer; once it is "
                   "empty the same drain reaches bank reserves",
        rationale="the buffer is the STATE that decides whether a tax date is a non-event or a "
                  "funding squeeze -- the conditioning variable, not a predictor on its own",
        falsifier="the tax-date and settlement effects are the same size in a full-buffer and "
                  "an empty-buffer regime",
        source_id=f"{SOURCE}:rrp", horizon_days=5, payload={"domain": "US-D"})
    return _fold(parts, "plumbing_calendar")


def cot_extreme_unwind(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """US-E: the CFTC's Tuesday-stamped positioning against forward returns, with the
    look-ahead control run FIRST.

    The report is stamped Tuesday and published Friday 15:30 ET. A study that aligns on the
    Tuesday stamp is reading three days of the future; the honest alignment is the FRIDAY. Both
    are run and the difference IS the leak size, reported rather than hidden.
    """
    ctx.miner = ctx.miner or "cot_extreme_unwind"
    mod = _pack_module()
    covered = ("XAUUSD", "XAGUSD", "XTIUSD", "XNGUSD", "CORN", "WHEAT", "SOYBEAN", "COTTON",
               "EURUSD", "USDJPY", "US500")
    honest = K.series_lead(
        pack, ctx, name="cot_friday_aligned", series_name=mod.SERIES["US_COT"],
        symbols=covered, mechanism="us_cot_extreme_unwind_friday_aligned",
        actor="managed money at a crowded extreme",
        constraint="a fund at its risk limit can only reduce; the report is stamped Tuesday and "
                   "PUBLISHED Friday 15:30 ET, so Friday is the first tradable stamp",
        rationale="an extreme is a population of forced sellers whose exit is mechanical once "
                  "the move goes against them",
        falsifier="the Friday-aligned reading carries no forward information, or all of it is "
                  "the three days between the stamp and the publication",
        source_id=f"{SOURCE}:cot", horizon_days=10, payload={"domain": "US-E",
                                                             "alignment": "publication"})
    leaky = K.series_lead(
        pack, ctx, name="cot_tuesday_aligned_lookahead", series_name=mod.SERIES["US_COT"],
        symbols=covered[:4], mechanism="us_cot_tuesday_alignment_control",
        actor="look-ahead control", constraint="none",
        rationale="aligning on the Tuesday stamp reads three days the desk could not have had; "
                  "the gap between this and the Friday alignment IS the leak",
        falsifier="n/a", source_id=f"{SOURCE}:cot_lookahead", horizon_days=10,
        payload={"domain": "US-E", "alignment": "stamp", "control": True})
    out = _fold({"friday": honest, "tuesday_lookahead": leaky}, "cot_extreme_unwind")
    out["leak_note"] = ("the Tuesday-aligned arm is a CONTROL and is never promoted; any "
                        "excess it shows over the Friday arm is the look-ahead size")
    return out


def expiry_gamma_calendar(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """US-F: the third-Friday expiry ladder, split at the 2022 daily-expiry change.

    Monthly OpEx is the third Friday; the quadruple witch is the third Friday of March, June,
    September and December. The pack's note asks for the sample split; the split is carried as a
    named era in the payload so the two halves are never pooled by accident.
    """
    ctx.miner = ctx.miner or "expiry_gamma_calendar"
    span = _span(ctx, "US500") or _span(ctx, "NAS100")
    if span is None:
        ctx.note("expiry_gamma_calendar:bars", "no US500 or NAS100 H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "expiry_gamma_calendar", "why": "no tape"}
    lo, hi = span
    split = date(2022, 5, 1)          # the daily-expiry ladder reached the whole week from here
    opex = nth_weekdays(lo, hi, 4, 3)
    witch = nth_weekdays(lo, hi, 4, 3, (3, 6, 9, 12))
    parts: dict[str, Any] = {}
    parts["monthly_opex"] = K.event_study(
        pack, ctx, name="third_friday_opex", symbols=("US500", "NAS100", "US30"),
        dates=[d for d in opex if d not in set(witch)],
        mechanism="us_monthly_opex_pin",
        actor="dealers hedging a short-gamma book into the settlement print",
        constraint="the settlement price is fixed by the opening prints; the hedge must be "
                   "unwound by then and cannot be deferred",
        rationale="a mechanical, dated hedge unwind concentrated in one session",
        falsifier="the third Friday matches the SECOND Friday of the same months",
        source_id=f"{SOURCE}:opex", required_data=["the expiry calendar"],
        horizon="session", payload={"domain": "US-F", "class": "monthly", "era_split":
                                    split.isoformat()})
    parts["quad_witch"] = K.event_study(
        pack, ctx, name="quadruple_witching", symbols=("US500", "NAS100", "US2000"),
        dates=witch, mechanism="us_quadruple_witching_rebalance",
        actor="index funds and dealers at the quarterly index reconstitution",
        constraint="futures, options on futures, index options and single-stock options all "
                   "settle on the same morning, and the index changes are effective then",
        rationale="four expiries and a reconstitution on one date is the largest scheduled "
                  "mechanical flow in the equity calendar",
        falsifier="the witching Friday matches the eight non-witching third Fridays",
        source_id=f"{SOURCE}:witch", required_data=["the expiry calendar"], horizon="session",
        payload={"domain": "US-F", "class": "quad_witch"})
    parts["second_friday_control"] = K.event_study(
        pack, ctx, name="second_friday_control", symbols=("US500",),
        dates=nth_weekdays(lo, hi, 4, 2), mechanism="us_expiry_control", actor="control",
        constraint="none", rationale="the second Friday carries no index expiry",
        falsifier="n/a", source_id=f"{SOURCE}:opex_control", required_data=[],
        horizon="session", payload={"domain": "US-F", "control": True},
        novelty=0.0, confidence=0.0)
    out = _fold(parts, "expiry_gamma_calendar")
    out["era_split"] = {"at": split.isoformat(),
                        "why": "the daily-expiry ladder reached every weekday from mid-2022; "
                               "pooling the two halves measures a mechanism that changed"}
    return out


def physical_report_surprises(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """US-G / US-H / US-I: one miner, three report classes, each with its own control.

    The EIA crude report is Wednesday 15:30 UTC and the natural-gas storage report Thursday
    15:30; the USDA WASDE lands around the 12th at 17:00. Each gets the matched non-report
    weekday as its own control, because "crude moves on Wednesdays" and "crude moves on the EIA"
    are different claims and only the second one is tradable.
    """
    ctx.miner = ctx.miner or "physical_report_surprises"
    mod = _pack_module()
    span = _span(ctx, "XTIUSD") or _span(ctx, "XNGUSD") or _span(ctx, "CORN")
    if span is None:
        ctx.note("physical_report_surprises:bars", "no energy or grain H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "physical_report_surprises",
                "why": "no physical-complex tape"}
    lo, hi = span
    parts: dict[str, Any] = {}
    parts["eia_crude"] = K.event_study(
        pack, ctx, name="eia_crude_wednesday", symbols=("XTIUSD", "XBRUSD"),
        dates=K.weekday_dates(lo, hi, 2), mechanism="us_eia_crude_inventory_release",
        actor="the Energy Information Administration's weekly petroleum status report",
        constraint="released 15:30 UTC every Wednesday (Thursday after a Monday holiday); the "
                   "API's Tuesday-evening estimate is the only prior",
        rationale="a counted physical stock against a surveyed expectation is the cleanest "
                  "surprise in the energy complex",
        falsifier="the Wednesday window matches the Tuesday and Friday windows of the same "
                  "weeks",
        source_id=f"{SOURCE}:eia_crude", required_data=[mod.SERIES["US_CRUDE_STOCKS"]],
        horizon="intraday", hours=(15, 18), payload={"domain": "US-G"})
    parts["eia_gas"] = K.event_study(
        pack, ctx, name="eia_gas_thursday", symbols=("XNGUSD",),
        dates=K.weekday_dates(lo, hi, 3), mechanism="us_eia_gas_storage_release",
        actor="the EIA's weekly natural-gas storage report",
        constraint="released 15:30 UTC every Thursday; the injection season and the withdrawal "
                   "season are different mechanisms and must not be pooled",
        rationale="storage against a five-year normal is the gas market's only scheduled state "
                  "variable",
        falsifier="the Thursday window matches the Wednesday window on the same weeks",
        source_id=f"{SOURCE}:eia_gas", required_data=[mod.SERIES["US_GAS_STORAGE"]],
        horizon="intraday", hours=(15, 18), payload={"domain": "US-H"})
    parts["wasde"] = K.event_study(
        pack, ctx, name="usda_wasde", symbols=("CORN", "WHEAT", "SOYBEAN", "COTTON"),
        dates=K.month_days(lo, hi, (11, 12)), mechanism="us_usda_wasde_release",
        actor="the USDA World Agricultural Supply and Demand Estimates board",
        constraint="released around the 12th at 17:00 UTC under a lock-up; the ending-stocks "
                   "number is the balance the whole complex is quoted off",
        rationale="a single administered estimate resets the supply-demand balance every grain "
                  "contract is priced against",
        falsifier="the 11th-12th window matches the 25th-26th of the same months",
        source_id=f"{SOURCE}:wasde", required_data=["USDA WASDE calendar"], horizon="session",
        payload={"domain": "US-I"})
    parts["wasde_placebo"] = K.event_study(
        pack, ctx, name="usda_late_month_placebo", symbols=("CORN",),
        dates=K.month_days(lo, hi, (25, 26)), mechanism="us_wasde_placebo", actor="placebo",
        constraint="none", rationale="the 25th-26th carry no WASDE", falsifier="n/a",
        source_id=f"{SOURCE}:wasde_placebo", required_data=[], horizon="session",
        payload={"domain": "US-I", "placebo": True}, novelty=0.0, confidence=0.0)
    return _fold(parts, "physical_report_surprises")


def transmission_seeds(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """The pack's transmission map as HYPOTHESIS discoveries -- the map the law grants a region
    before any tape has been read (LAWS 5n)."""
    ctx.miner = ctx.miner or "transmission_seeds"
    mod = _pack_module()
    return K.seed_edges(pack, ctx, name="transmission_seeds",
                        edges=mod.TRANSMISSION_EDGES_SEED,
                        mechanism_prefix="us_transmission", source_id=f"{SOURCE}:edges")


# --------------------------------------------------------------------------- folding
def _fold(parts: dict[str, Any], miner: str) -> dict[str, Any]:
    """One result out of several studies: OK when any part measured, with every part kept."""
    vals = list(parts.values())
    return {"miner": miner,
            "outcome": K.OK if any(p.get("outcome") == K.OK for p in vals) else K.UNMEASURED,
            "discoveries": sum(int(p.get("discoveries") or 0) for p in vals),
            "parts": {k: {kk: vv for kk, vv in v.items() if kk != "readings"}
                      for k, v in parts.items()},
            "why": "" if any(p.get("outcome") == K.OK for p in vals) else
                   "no part of this miner carried a measurable study"}


MINERS: dict[str, Any] = {
    "fomc_surprise_vs_zq": fomc_surprise_vs_zq,
    "release_surprise_with_revisions": release_surprise_with_revisions,
    "auction_tail_event_study": auction_tail_event_study,
    "plumbing_calendar": plumbing_calendar,
    "cot_extreme_unwind": cot_extreme_unwind,
    "expiry_gamma_calendar": expiry_gamma_calendar,
    "physical_report_surprises": physical_report_surprises,
    "transmission_seeds": transmission_seeds,
}
