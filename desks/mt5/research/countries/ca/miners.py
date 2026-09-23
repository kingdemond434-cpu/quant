"""CANADA'S OWN MINERS -- the five clocks the generic set cannot know.

`MINERS` maps a name to `callable(pack, ctx) -> dict`, the contract `country_lab.run_lab` reads
for a pack directory's `miners.py`, and every entry in the pack's `CUSTOM_MINERS`
(`countries.ca.miners:<function>`) resolves to a function here, so the two registrations are one
set. Each miner builds ITS OWN event dates from the pack's tables (the Bank of Canada's eight
fixed announcement dates, the StatCan release classes and their COLLISION with the BLS, the
Alberta WCS differential and the Mainline apportionment notice, the tariff ledger, and the
Canada/US calendar divergences) and hands them to the framework's event study through the shared
kit, so a Canadian finding carries the same matched-weekday control, randomised-date null and
adjacent-day placebo as every other country's. Discoveries go through `ctx.record` and nowhere
else.

WHY CANADA'S MINERS ARE ABOUT COLLISION AND DIVERGENCE. Canada is the country most likely to be
mistaken for a US beta, and every distinctive thing about its tape is a place where the two
calendars DO NOT line up: the Labour Force Survey lands on the same Friday as the US payroll
about half the time and on its own the rest, the loonie's WTI beta only binds when the WCS
differential is narrow enough for a barrel to reach tidewater, and the TSX and NYSE close on
different days three or four times a year, leaving a one-sided book in USDCAD. A miner that
pools the collision Fridays with the solo Fridays is measuring the United States and filing the
answer under Canada, which is worse than not measuring at all: it spends the programme's shared
trial budget to confirm something the US pack already tested.

EVERY OUTCOME IS A RESULT. A missing tape is `ctx.note`d UNMEASURED by symbol; a series that is
not on this box is named, not skipped; a study with too few events is reported with its counts.
"""
from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterable
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

SOURCE = "ca:pack"


def _pack_module() -> Any:
    try:
        from countries.ca import pack as mod
    except ImportError:
        spec = importlib.util.spec_from_file_location(
            "country_ca_pack", Path(__file__).resolve().parent / "pack.py")
        if spec is None or spec.loader is None:  # pragma: no cover
            raise
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th `weekday` (Monday=0) of a month."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return date(year, month, 1 + offset + 7 * (n - 1))


def nth_weekdays(lo: date, hi: date, weekday: int, n: int,
                 months: Iterable[int] = range(1, 13)) -> list[date]:
    wanted = {int(m) for m in months}
    out: list[date] = []
    for year in range(lo.year, hi.year + 1):
        for month in sorted(wanted):
            day = nth_weekday(year, month, weekday, n)
            if lo <= day <= hi and day.month == month:
                out.append(day)
    return out


def _span(ctx: CL.LabCtx, symbol: str, timeframe: str = "H1") -> tuple[date, date] | None:
    bars = ctx.bars(symbol, timeframe)
    if bars is None:
        return None
    return K.tape_span(bars)


def _fold(parts: dict[str, Any], miner: str) -> dict[str, Any]:
    """One result out of several studies: OK when any part measured, with every part kept."""
    vals = list(parts.values())
    ok = any(p.get("outcome") == K.OK for p in vals)
    return {"miner": miner, "outcome": K.OK if ok else K.UNMEASURED,
            "discoveries": sum(int(p.get("discoveries") or 0) for p in vals),
            "parts": {k: {kk: vv for kk, vv in v.items() if kk != "readings"}
                      for k, v in parts.items()},
            "why": "" if ok else "no part of this miner carried a measurable study"}


# --------------------------------------------------------------------------- the five miners
def boc_surprise_vs_bax(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """CA-A: the eight FIXED announcement dates, against the Wednesdays that are not.

    Canada was the first G7 central bank to publish a fixed announcement schedule, which is what
    makes the control clean: the non-announcement Wednesdays are genuinely comparable rather
    than "whenever the governor felt like speaking". The pack asks for the BAX-implied prior;
    that snapshot is not on this box, so the surprise arm runs as a named `series_lead` and
    reads UNMEASURED rather than being replaced with a prior close.
    """
    ctx.miner = ctx.miner or "boc_surprise_vs_bax"
    mod = _pack_module()
    days = [date.fromisoformat(d) for d in pack.central_bank.decision_dates]
    main = K.event_study(
        pack, ctx, name="boc_decision_windows", symbols=("USDCAD", "CA60", "CADJPY"),
        dates=days, mechanism="ca_boc_fixed_announcement_window",
        actor="the Bank of Canada's Governing Council",
        constraint="eight FIXED announcement dates a year at 14:45 UTC (09:45 ET), published a "
                   "year ahead; the Monetary Policy Report lands on four of them",
        rationale="the loonie is a rate-differential currency on a two-day horizon and a crude "
                  "currency on a two-month one; the announcement is where the first dominates",
        falsifier="the announcement Wednesday matches the ordinary Wednesdays two weeks either "
                  "side, or the effect is carried entirely by the four MPR dates",
        source_id=f"{SOURCE}:boc", required_data=["BoC fixed announcement schedule",
                                                  mod.SERIES["CA_POLICY"]],
        horizon="intraday", hours=(14, 17), payload={"domain": "CA-A", "n_dates": len(days)})
    meetings = set(days)
    controls = sorted({d + timedelta(days=off) for d in meetings for off in (-14, 14)}
                      - meetings)
    ctrl = K.event_study(
        pack, ctx, name="boc_wednesday_control", symbols=("USDCAD",), dates=controls,
        mechanism="ca_boc_wednesday_control", actor="control", constraint="none",
        rationale="an ordinary Wednesday two weeks from a fixed date carries no announcement",
        falsifier="n/a", source_id=f"{SOURCE}:boc_control", required_data=[],
        horizon="intraday", hours=(14, 17), payload={"domain": "CA-A", "control": True},
        novelty=0.0, confidence=0.0)
    surprise = K.series_lead(
        pack, ctx, name="boc_bax_surprise", series_name="ME:BAX_implied",
        symbols=("USDCAD", "CA60"), mechanism="ca_boc_surprise_vs_bax",
        actor="the Governing Council against the BAX strip",
        constraint="the strip prices the decision before it lands; only the residual is news",
        rationale="the BAX-implied rate at 09:40 ET is the market's own expectation and the "
                  "only honest prior for a fixed-date decision",
        falsifier="the announcement move is explained by the level rather than the residual",
        source_id=f"{SOURCE}:bax", horizon_days=1, payload={"domain": "CA-A"})
    main["control"] = {k: v for k, v in ctrl.items() if k != "readings"}
    main["surprise"] = {k: v for k, v in surprise.items() if k != "readings"}
    if surprise.get("outcome") == K.UNMEASURED:
        main["verdict_scope"] = ("ANNOUNCEMENT WINDOW ONLY: the BAX-implied snapshot is not on "
                                 "this box, so no surprise-conditioned claim is made")
    return main


def release_collision(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """CA-B: the Labour Force Survey, split by whether the US payroll landed on the same morning.

    The pack's note is explicit -- "splits the LFS sample by NFP coincidence before measuring
    anything" -- and this miner does the split FIRST, because the two samples answer different
    questions. On a collision Friday the Canadian number is read through a dollar that is
    already moving; on a solo Friday it is the only number in the 13:30 UTC window. Pooling them
    measures the United States and files it under Canada.
    """
    ctx.miner = ctx.miner or "release_collision"
    mod = _pack_module()
    span = _span(ctx, "USDCAD")
    if span is None:
        ctx.note("release_collision:bars:USDCAD", "no H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "release_collision", "why": "no USDCAD tape"}
    lo, hi = span
    nfp = set(nth_weekdays(lo, hi, 4, 1))            # the US payroll: first Friday
    lfs_all = set(nth_weekdays(lo, hi, 4, 1)) | set(nth_weekdays(lo, hi, 4, 2))
    collision = sorted(lfs_all & nfp)
    solo = sorted(lfs_all - nfp)
    parts: dict[str, Any] = {}
    parts["lfs_solo"] = K.event_study(
        pack, ctx, name="lfs_solo_friday", symbols=("USDCAD", "CADJPY", "CA60"), dates=solo,
        mechanism="ca_lfs_solo_release_window",
        actor="Statistics Canada's Labour Force Survey",
        constraint="the LFS is released at 13:30 UTC on a Friday; when it does NOT share the "
                   "morning with the US payroll it is the only number in the window",
        rationale="a domestic employment surprise with no competing print is the cleanest "
                  "reading of the loonie's own macro beta",
        falsifier="the solo Fridays match the matched-weekday control, or the effect is the "
                  "same size on the collision Fridays -- which would mean it was never Canadian",
        source_id=f"{SOURCE}:lfs", required_data=[mod.SERIES["CA_LFS"]], horizon="intraday",
        hours=(13, 15), payload={"domain": "CA-B", "arm": "solo", "n_solo": len(solo)})
    parts["lfs_collision"] = K.event_study(
        pack, ctx, name="lfs_collision_friday", symbols=("USDCAD", "CA60"), dates=collision,
        mechanism="ca_lfs_collision_release_window",
        actor="Statistics Canada and the Bureau of Labor Statistics in the same minute",
        constraint="about half the LFS releases share 13:30 UTC with the US Employment "
                   "Situation; the dollar leg of USDCAD is moving on a foreign number",
        rationale="the collision is the state in which the Canadian print is DISCOUNTED; the "
                  "difference between the two arms is the measurement, not a nuisance",
        falsifier="the collision and solo arms are indistinguishable, which would say the "
                  "domestic print never mattered",
        source_id=f"{SOURCE}:lfs_collision", required_data=[mod.SERIES["CA_LFS"]],
        horizon="intraday", hours=(13, 15),
        payload={"domain": "CA-B", "arm": "collision", "n_collision": len(collision)})
    parts["cpi"] = K.event_study(
        pack, ctx, name="statcan_cpi", symbols=("USDCAD", "CA60"),
        dates=K.month_days(lo, hi, (16, 17, 18, 19)),
        mechanism="ca_cpi_release_window",
        actor="Statistics Canada's consumer price programme",
        constraint="the CPI lands at 13:30 UTC around the 16th-19th, after the US print, so "
                   "the Canadian surprise is measured against an already-repriced curve",
        rationale="the inflation print the Governing Council's fixed-date path is conditioned "
                  "on",
        falsifier="the 16th-19th window matches the 4th-7th window of the same months",
        source_id=f"{SOURCE}:cpi", required_data=[mod.SERIES["CA_CPI"]], horizon="intraday",
        hours=(13, 15), payload={"domain": "CA-B", "release": "CPI"})
    parts["cpi_placebo"] = K.event_study(
        pack, ctx, name="statcan_cpi_placebo", symbols=("USDCAD",),
        dates=K.month_days(lo, hi, (4, 5, 6, 7)), mechanism="ca_cpi_placebo", actor="placebo",
        constraint="none", rationale="the 4th-7th carry no StatCan CPI", falsifier="n/a",
        source_id=f"{SOURCE}:cpi_placebo", required_data=[], horizon="intraday", hours=(13, 15),
        payload={"domain": "CA-B", "placebo": True}, novelty=0.0, confidence=0.0)
    out = _fold(parts, "release_collision")
    out["split"] = {"n_collision": len(collision), "n_solo": len(solo),
                    "why": "the split is made BEFORE any measurement, which is the whole point "
                           "of this miner"}
    return out


def wcs_takeaway(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """CA-C: the loonie's crude beta, CONDITIONED on whether the barrel can reach tidewater.

    The Western Canadian Select differential is not a price, it is a CONSTRAINT: when takeaway
    capacity is short the differential blows out, Alberta's barrel stops tracking WTI and the
    currency's crude beta collapses. The apportionment notice is the administered evidence that
    the pipe is full. Both arrive as dated series; when they are not on this box the miner says
    so by name and measures nothing it cannot see.
    """
    ctx.miner = ctx.miner or "wcs_takeaway"
    mod = _pack_module()
    parts: dict[str, Any] = {}
    parts["wcs_differential"] = K.series_lead(
        pack, ctx, name="wcs_diff_lead", series_name=mod.SERIES["CA_WCS_DIFF"],
        symbols=("USDCAD", "XTIUSD"), mechanism="ca_wcs_differential_gates_crude_beta",
        actor="Alberta producers who must sell into a constrained pipe",
        constraint="a producer with no takeaway capacity is a price taker at whatever the rail "
                   "bid is; the differential IS the constraint, priced",
        rationale="the currency's WTI beta is a function of how much of the WTI price the "
                  "domestic barrel actually receives",
        falsifier="the loonie's crude beta is the same in a wide-differential and a "
                  "narrow-differential regime",
        source_id=f"{SOURCE}:wcs", horizon_days=10, payload={"domain": "CA-C"})
    parts["apportionment"] = K.series_lead(
        pack, ctx, name="mainline_apportionment_lead",
        series_name=mod.SERIES["CA_APPORTIONMENT"], symbols=("USDCAD", "XTIUSD"),
        mechanism="ca_mainline_apportionment_as_capacity_signal",
        actor="Enbridge as the administered allocator of Mainline capacity",
        constraint="apportionment is announced monthly and is a MEASURED statement that "
                   "nominations exceeded capacity",
        rationale="an administered rationing percentage is a published, dated capacity "
                  "constraint -- the rarest kind of honest supply signal",
        falsifier="apportionment carries no information for the differential or the currency "
                  "beyond the differential itself",
        source_id=f"{SOURCE}:apportionment", horizon_days=20, payload={"domain": "CA-C"})
    parts["bcpi"] = K.series_lead(
        pack, ctx, name="bcpi_lead", series_name=mod.SERIES["CA_BCPI"],
        symbols=("USDCAD", "CA60"), mechanism="ca_commodity_price_index_terms_of_trade",
        actor="the Bank of Canada's own commodity price index as the terms-of-trade proxy",
        constraint="the BCPI is the basket the Bank itself cites when it explains the currency",
        rationale="the terms-of-trade channel is the loonie's textbook mechanism and deserves "
                  "to be measured rather than assumed",
        falsifier="the BCPI carries no forward information once WTI alone is conditioned on",
        source_id=f"{SOURCE}:bcpi", horizon_days=20, payload={"domain": "CA-C"})
    return _fold(parts, "wcs_takeaway")


def tariff_event_ledger(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """CA-D: tariff ANNOUNCEMENT dates and tariff EFFECTIVE dates as two separate samples.

    The pack's note insists they are separate events and it is right: the announcement is news
    and the effective date is a cash-flow change that everyone has known about for weeks. A
    study that pools them is measuring two different mechanisms with one estimator. The ledger
    itself lives in the pack (`ACCESS_CONSTRAINTS` names the Federal Register as its ground);
    when no dated ledger is on this box the miner says so and falls back to the WEEKLY policy
    window the ledger is published in, labelled as the coarser instrument it is.
    """
    ctx.miner = ctx.miner or "tariff_event_ledger"
    mod = _pack_module()
    rows = getattr(mod, "TARIFF_LEDGER", None)
    announced: list[date] = []
    effective: list[date] = []
    if isinstance(rows, dict):
        for iso, row in rows.items():
            try:
                day = date.fromisoformat(str(iso))
            except ValueError:
                continue
            (effective if "effective" in str(row).lower() else announced).append(day)
    if not announced and not effective:
        ctx.note("tariff_event_ledger", "no dated tariff ledger in the pack on this box; the "
                                        "announcement/effective split cannot be made and no "
                                        "pooled verdict is offered in its place")
        return {"outcome": K.UNMEASURED, "miner": "tariff_event_ledger",
                "why": "no dated tariff ledger", "n_announced": 0, "n_effective": 0}
    parts: dict[str, Any] = {}
    if announced:
        parts["announcement"] = K.event_study(
            pack, ctx, name="tariff_announcement", symbols=("USDCAD", "CA60", "XALUSD"),
            dates=announced, mechanism="ca_tariff_announcement_news",
            actor="the US executive as the setter of Section 232/301 tariffs on Canadian goods",
            constraint="an announcement is unscheduled and repriced in minutes",
            rationale="a tariff on the largest bilateral trade relationship in the world is a "
                      "terms-of-trade shock to the smaller partner",
            falsifier="the announcement days match the matched-weekday control",
            source_id=f"{SOURCE}:tariff_ann", required_data=["Federal Register ledger"],
            horizon="intraday", payload={"domain": "CA-D", "arm": "announcement"})
    if effective:
        parts["effective"] = K.event_study(
            pack, ctx, name="tariff_effective", symbols=("USDCAD", "CA60"), dates=effective,
            mechanism="ca_tariff_effective_date_cash_flow",
            actor="importers whose duty liability changes at midnight on the effective date",
            constraint="the effective date is known weeks ahead, so the NEWS is already in the "
                       "price and only the flow is left",
            rationale="if anything happens on a fully anticipated date it is a flow effect, "
                      "which is a different mechanism from the announcement",
            falsifier="the effective days are indistinguishable from the matched control, "
                      "which is the expected result and would be a clean negative",
            source_id=f"{SOURCE}:tariff_eff", required_data=["Federal Register ledger"],
            horizon="session", payload={"domain": "CA-D", "arm": "effective"})
    out = _fold(parts, "tariff_event_ledger")
    out["n_announced"], out["n_effective"] = len(announced), len(effective)
    return out


def calendar_divergence(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """CA-E / CA-F: the days one side of the border is shut and the other is open.

    Victoria Day, Canada Day, the Civic Holiday and Thanksgiving-in-October close the TSX while
    New York trades; Martin Luther King Day, Presidents' Day, Memorial Day, Juneteenth, 4 July
    and US Thanksgiving do the reverse. On either kind of day USDCAD has ONE side of its
    liquidity, which is a microstructure state with a published calendar -- the pack carries the
    dates in `CALENDAR_DIVERGENCES` and this miner reads them rather than retyping them.
    """
    ctx.miner = ctx.miner or "calendar_divergence"
    mod = _pack_module()
    table = getattr(mod, "CALENDAR_DIVERGENCES", {}) or {}
    ca_closed: list[date] = []
    us_closed: list[date] = []
    for iso, label in dict(table).items():
        try:
            day = date.fromisoformat(str(iso))
        except ValueError:
            continue
        text = str(label).lower()
        if "tsx" in text and "closed" in text:
            ca_closed.append(day)
        elif "nyse" in text or "us " in text or "new york" in text:
            us_closed.append(day)
        else:
            ca_closed.append(day)
    parts: dict[str, Any] = {}
    if ca_closed:
        parts["canada_closed"] = K.event_study(
            pack, ctx, name="tsx_closed_nyse_open", symbols=("USDCAD", "CADJPY"),
            dates=ca_closed, mechanism="ca_one_sided_book_tsx_closed",
            actor="the market makers who are the only side quoting the loonie that day",
            constraint="the Toronto book is shut and the New York one is not; a Canadian "
                       "hedge cannot be laid off domestically until the next session",
            rationale="a one-sided book is a measurable liquidity state with a statutory "
                      "calendar, not a guess about participation",
            falsifier="the divergent closures match the matched-weekday control, or the effect "
                      "is the same on days BOTH markets are open",
            source_id=f"{SOURCE}:div_ca", required_data=["the divergence table"],
            horizon="session", payload={"domain": "CA-E", "arm": "TSX closed"})
    if us_closed:
        parts["us_closed"] = K.event_study(
            pack, ctx, name="nyse_closed_tsx_open", symbols=("USDCAD", "CA60"),
            dates=us_closed, mechanism="ca_one_sided_book_nyse_closed",
            actor="Toronto trading into a shut New York",
            constraint="the dollar leg has no domestic liquidity; the TSX trades a US-priced "
                       "commodity complex with no US market to price it",
            rationale="the mirror image of the first arm, and the control that tells a "
                      "liquidity mechanism from a Canadian one",
            falsifier="the two arms are indistinguishable, which would say the direction of "
                      "the closure does not matter",
            source_id=f"{SOURCE}:div_us", required_data=["the divergence table"],
            horizon="session", payload={"domain": "CA-E", "arm": "NYSE closed"})
    span = _span(ctx, "USDCAD")
    if span is not None:
        lo, hi = span
        parts["thursday_roll"] = K.event_study(
            pack, ctx, name="thursday_value_date_roll", symbols=("USDCAD",),
            dates=K.weekday_dates(lo, hi, 3), mechanism="ca_thursday_spot_value_roll",
            actor="the spot book rolling value date over a weekend or a divergent holiday",
            constraint="T+1 settlement means Thursday's value date is the one that can land on "
                       "a day one of the two countries is shut",
            rationale="the roll is a dated, mechanical funding decision, not a view",
            falsifier="Thursday matches the other four weekdays in the same weeks",
            source_id=f"{SOURCE}:roll", required_data=["settlement conventions"],
            horizon="session", payload={"domain": "CA-F"})
    else:
        ctx.note("calendar_divergence:bars:USDCAD", "no H1 tape on this box")
    if not parts:
        return {"outcome": K.UNMEASURED, "miner": "calendar_divergence",
                "why": "the divergence table is empty and no tape is on this box"}
    out = _fold(parts, "calendar_divergence")
    out["n_ca_closed"], out["n_us_closed"] = len(ca_closed), len(us_closed)
    return out


def transmission_seeds(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """The pack's transmission map as HYPOTHESIS discoveries -- the map the law grants a region
    before any tape has been read (LAWS 5n)."""
    ctx.miner = ctx.miner or "transmission_seeds"
    mod = _pack_module()
    return K.seed_edges(pack, ctx, name="transmission_seeds",
                        edges=mod.TRANSMISSION_EDGES_SEED,
                        mechanism_prefix="ca_transmission", source_id=f"{SOURCE}:edges")


MINERS: dict[str, Any] = {
    "boc_surprise_vs_bax": boc_surprise_vs_bax,
    "release_collision": release_collision,
    "wcs_takeaway": wcs_takeaway,
    "tariff_event_ledger": tariff_event_ledger,
    "calendar_divergence": calendar_divergence,
    "transmission_seeds": transmission_seeds,
}
