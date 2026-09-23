"""SRI LANKA'S OWN MINERS -- the five clocks the generic set cannot know.

`MINERS` maps a name to `callable(pack, ctx) -> dict`, the contract `country_lab.run_lab` reads
for a pack directory's `miners.py`, and every entry in the pack's `CUSTOM_MINERS`
(`countries.lk.miners:<function>`) resolves to a function here, so the two registrations are one
set. Each miner builds ITS OWN event dates from the pack's tables -- the four VERIFIED Monetary
Policy Review days, the gazetted full-moon Poya closures, the Tuesday Colombo Tea Auction, the
month-end CPC fuel revision -- and hands them to the framework's event study through the shared
kit, so a Sri Lankan finding carries the same matched-weekday control, randomised-date null and
adjacent-day placebo as every other country's. Discoveries go through `ctx.record` and nowhere
else.

THREE OF THE FIVE EXPECT A NULL AND SAY SO. Sri Lanka is a small, price-taking island: the fuel
formula is an INPUT-direction mechanism, the tea auction has no contract anywhere on this broker,
and the transmission seeds are hypotheses by construction. Each of those miners carries its
placebo or its declared-weak label in the payload, so a reading that comes back empty is a
measurement and not a failure (L1.28a).
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from datetime import date
from pathlib import Path
from typing import Any

from libs.research import country_lab as CL

SOURCE = "lk:pack"


def _load_by_path(name: str, filename: str, parents: int) -> Any:
    """One module beside this package, loaded by file path. Used only when this file was itself
    loaded by path and `countries` is therefore not an importable package name."""
    target = Path(__file__).resolve().parents[parents] / filename
    spec = importlib.util.spec_from_file_location(name, target)
    if spec is None or spec.loader is None:  # pragma: no cover -- an unreadable sibling file
        raise ImportError(f"{name}: nothing loadable at {target}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_kit() -> Any:
    try:
        return importlib.import_module("countries._miner_kit")
    except ImportError:
        return _load_by_path("countries_miner_kit", "_miner_kit.py", 1)


def _pack_module() -> Any:
    try:
        return importlib.import_module("countries.lk.pack")
    except ImportError:
        return _load_by_path("country_lk_pack", "pack.py", 0)


#: The shared event study, series lead-lag, seed and calendar builders.
K: Any = _load_kit()


def cbsl_policy_windows(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """LK-A: the Monetary Policy Review on the frontier-stress instruments, intraday.

    The 07:30 Colombo release is 02:00 UTC, in the European pre-open, so the study is an INTRADAY
    one on the hours around it. Only the VERIFIED review dates are the sample; the REPORTED ones
    the desk has not read off a CBSL release run as a separate, labelled arm and are never pooled
    -- the same announced/projected discipline the Poya miner uses.
    """
    ctx.miner = ctx.miner or "cbsl_policy_windows"
    mod = _pack_module()
    verified = [date.fromisoformat(d) for d in pack.central_bank.decision_dates]
    reported = [date.fromisoformat(d) for d in mod.REPORTED_DECISION_DATES]
    out: dict[str, Any] = K.event_study(
        pack, ctx, name="cbsl_policy_windows", symbols=("USDINR", "XAUUSD", "UST10Y"),
        dates=verified, mechanism="lk_cbsl_review_stress_channel",
        actor="Central Bank of Sri Lanka Monetary Policy Board",
        constraint="eight scheduled reviews a year on a pre-announced calendar, released at "
                   "07:30 Colombo; the rupee is absent from the broker, so the reaction is read "
                   "on the regional cross, gold and the frontier rate",
        rationale="a rate decision in a freshly restructured frontier sovereign reprices its "
                  "stress premium; the regional cross, gold and the ten-year carry that beta "
                  "while LKR itself cannot be traded here",
        falsifier="the review-day effect matches the eight nearest non-review weekdays or the "
                  "RBI decision-day control, in which case it is South Asia and not the CBSL",
        source_id=f"{SOURCE}:cbsl", required_data=["CBSL:opr", "Monetary Policy Review calendar"],
        horizon="intraday", hours=(1, 4),
        payload={"domain": "LK-A", "n_verified": len(verified),
                 "rate_series_break": "SDFR/SLFR before the OPR transition, OPR after: the two "
                                      "are never spliced"})
    arm: dict[str, Any] = K.event_study(
        pack, ctx, name="cbsl_policy_windows_reported", symbols=("USDINR",), dates=reported,
        mechanism="lk_cbsl_review_reported_dates", actor="reported-date arm",
        constraint="dates the desk believes are review days and has NOT read off a release",
        rationale="the eight-a-year rule and the four verified rows disagree; this arm makes the "
                  "gap measurable instead of absent",
        falsifier="n/a -- this arm is a measurement of the calendar gap, not a claim",
        source_id=f"{SOURCE}:cbsl_reported", required_data=[], horizon="intraday", hours=(1, 4),
        payload={"domain": "LK-A", "status": "REPORTED_UNVERIFIED"},
        novelty=0.0, confidence=0.0)
    out["reported_arm"] = {k: v for k, v in arm.items() if k != "readings"}
    return out


def poya_closure_eves(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """LK-L / LK-H: the eve of every gazetted full-moon Poya closure.

    Sri Lanka is the only country in the desk's book whose cash market shuts on a LUNAR MONTHLY
    schedule. The placebo is what makes it a mechanism rather than an astronomy result: the
    full-moon-ADJACENT weekdays that were NOT closures (four days before and three days after
    each Poya) run alongside, so 'the market was shut tomorrow' can be told from 'it was near a
    full moon'. Only ANNOUNCED rows are the sample; the PROJECTED 2026 rows join the placebo.
    """
    ctx.miner = ctx.miner or "poya_closure_eves"
    mod = _pack_module()
    announced: list[date] = []
    projected: list[date] = []
    for _year, rows in mod.POYA_DAYS.items():
        for day, _name, status in rows:
            (announced if status == "ANNOUNCED" else projected).append(day)
    closed = set(announced) | set(projected)
    adjacent = [d for d in K.shift(announced, -4) + K.shift(announced, 3)
                if d not in closed and d.weekday() < 5]
    out: dict[str, Any] = K.event_study(
        pack, ctx, name="poya_closure_eves", symbols=("XAUUSD", "USDINR"),
        dates=[d for d in K.shift(announced, -1) if d.weekday() < 5],
        mechanism="lk_poya_closure_eve_liquidity",
        actor="the Buddhist calendar and the banks and exchange it closes",
        constraint="every full moon is a statutory public holiday; the closure is monthly, the "
                   "date moves with the moon, and there is no weekend substitution",
        rationale="the eve of a Sri Lankan closure carries the day's settlement into one session "
                  "and removes a South Asian liquidity pool the next; the festival Poyas "
                  "(Vesak, Poson) also carry the jewellery and pawning demand of LK-H",
        falsifier="the announced eves match the full-moon-ADJACENT open weekdays or the matched "
                  "weekday control, in which case the mechanism is the lunar month and not the "
                  "closure",
        source_id=f"{SOURCE}:poya", required_data=["the gazetted Poya rows"],
        horizon="overnight",
        payload={"domain": "LK-L", "n_announced": len(announced),
                 "n_projected": len(projected)})
    placebo: dict[str, Any] = K.event_study(
        pack, ctx, name="poya_full_moon_placebo", symbols=("XAUUSD",), dates=adjacent,
        mechanism="lk_poya_adjacent_placebo", actor="placebo", constraint="none",
        rationale="these weekdays are near a full moon and are NOT closures; a move here is the "
                  "moon or the calendar, never the Poya holiday",
        falsifier="n/a", source_id=f"{SOURCE}:poya_placebo", required_data=[],
        horizon="overnight", payload={"domain": "LK-L", "placebo": True},
        novelty=0.0, confidence=0.0)
    out["placebo"] = {k: v for k, v in placebo.items() if k != "readings"}
    out["projected_dates"] = [d.isoformat() for d in sorted(projected)]
    return out


def tea_auction_week(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """LK-F: the weekly Colombo Tea Auction, declared weak on every leg.

    There is NO tea contract on this broker, so this miner does two honest things and claims
    nothing else: it runs the Tuesday sale day as an event study on the only auctioned-beverage
    softs the box quotes, and it runs the Tea Board's export-volume series against them as a
    lead-lag. Both are labelled WEAK_PROXY in the payload, and the non-sale weekdays are the
    control the falsifier names.
    """
    ctx.miner = ctx.miner or "tea_auction_week"
    results: dict[str, Any] = {"miner": "tea_auction_week", "parts": {}}
    bars = ctx.bars("COFROB", "H1")
    if bars is None:
        ctx.note("tea_auction_week:bars:COFROB", "no H1 tape on this box")
    else:
        lo, hi = K.tape_span(bars)
        results["parts"]["sale_days"] = K.event_study(
            pack, ctx, name="tea_auction_sale_days", symbols=("COFROB", "COFARA"),
            dates=K.weekday_dates(lo, hi, 1), mechanism="lk_colombo_tea_auction_sale_day",
            actor="the Colombo Tea Traders Association and the broking houses",
            constraint="the sale sits every Tuesday and continues Wednesday; the catalogued "
                       "quantity is public days ahead and the price is not",
            rationale="the weekly clearing of essentially all Ceylon tea is a dated supply-and-"
                      "demand event in the world beverage complex; the executable reach here is "
                      "the auctioned-beverage substitutes and it is WEAK by construction",
            falsifier="the Tuesday sale-day window matches the same weekdays in weeks with no "
                      "Colombo sale, or the Mombasa auction days carry the same move",
            source_id=f"{SOURCE}:cta", required_data=["CTA:auction_average"],
            horizon="session", hours=(3, 12),
            payload={"domain": "LK-F", "leg_strength": "WEAK_PROXY",
                     "absent_instrument": "no tea contract exists in the broker universe"})
    results["parts"]["export_lead"] = K.series_lead(
        pack, ctx, name="tea_export_volume_lead", series_name="CBSL:tea_export_volume",
        symbols=("COFROB", "COFARA"), mechanism="lk_tea_export_volume_supply",
        actor="the Sri Lanka Tea Board and the estates",
        constraint="the crop cannot be warehoused and the 2021-22 fertiliser ban removed the "
                   "yield outright",
        rationale="a policy-induced collapse in the largest orthodox black-tea exporter's volume "
                  "withdraws supply the beverage complex must price somewhere",
        falsifier="the export-volume series carries no information for the beverage complex "
                  "beyond Kenyan production and the Brazilian coffee cycle in the same months",
        source_id=f"{SOURCE}:teaboard", horizon_days=20,
        payload={"domain": "LK-F", "leg_strength": "WEAK_PROXY"})
    parts = list(results["parts"].values())
    results["outcome"] = K.OK if any(p.get("outcome") == K.OK for p in parts) else K.UNMEASURED
    results["discoveries"] = sum(int(p.get("discoveries") or 0) for p in parts)
    return results


def fuel_formula_month(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """LK-E: the month-end CPC revision as an administered pass-through, with the 15th placebo.

    `K.month_days(lo, hi, (31,))` lands on the LAST day of every month by the kit's own
    contract, which is exactly the revision date. The honest expectation is that an island this
    small moves nothing in crude; the placebo runs alongside so 'an effect' on Brent can be told
    from the turn of the month.
    """
    ctx.miner = ctx.miner or "fuel_formula_month"
    bars = ctx.bars("XBRUSD", "H1")
    if bars is None:
        ctx.note("fuel_formula_month:bars:XBRUSD", "no H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "fuel_formula_month", "why": "no XBRUSD tape"}
    lo, hi = K.tape_span(bars)
    events = K.month_days(lo, hi, (31,))
    placebo_days = K.month_days(lo, hi, (15,))
    main: dict[str, Any] = K.event_study(
        pack, ctx, name="fuel_formula_month", symbols=("XBRUSD", "XTIUSD"), dates=events,
        mechanism="lk_cpc_fuel_formula_pass_through",
        actor="Ceylon Petroleum Corporation and the Ministry of Energy as the price setter",
        constraint="the cost-reflective formula is applied on the last day of the month and the "
                   "new price runs from midnight Colombo (about 15:00 UTC)",
        rationale="an INPUT-direction mechanism: Brent and the rupee pass into the domestic "
                  "price on a published clock; an outward effect on crude is not expected from "
                  "an importer this size and is measured honestly rather than assumed away",
        falsifier="the revision-day window matches the 15th placebo or the matched "
                  "weekday-and-hour control",
        source_id=f"{SOURCE}:cpc", required_data=["CPC:retail_price"], horizon="session",
        hours=(13, 19),
        payload={"domain": "LK-E", "placebo_days": "the 15th of each month",
                 "direction": "INPUT_EXPECTED_NULL"})
    ctrl: dict[str, Any] = K.event_study(
        pack, ctx, name="fuel_formula_placebo", symbols=("XBRUSD",), dates=placebo_days,
        mechanism="lk_cpc_fuel_formula_placebo", actor="placebo", constraint="none",
        rationale="the 15th carries no revision; a move here is the calendar, not the formula",
        falsifier="n/a", source_id=f"{SOURCE}:cpc_placebo", required_data=[],
        horizon="session", hours=(13, 19), payload={"domain": "LK-E", "placebo": True},
        novelty=0.0, confidence=0.0)
    main["placebo"] = {k: v for k, v in ctrl.items() if k != "readings"}
    return main


def transmission_seeds(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """The pack's transmission map as HYPOTHESIS discoveries -- the map the law grants a region
    before its tape has been read."""
    ctx.miner = ctx.miner or "transmission_seeds"
    mod = _pack_module()
    out: dict[str, Any] = K.seed_edges(
        pack, ctx, name="transmission_seeds", edges=mod.TRANSMISSION_EDGES_SEED,
        mechanism_prefix="lk_transmission", source_id=f"{SOURCE}:edges")
    return out


MINERS: dict[str, Any] = {
    "cbsl_policy_windows": cbsl_policy_windows,
    "poya_closure_eves": poya_closure_eves,
    "tea_auction_week": tea_auction_week,
    "fuel_formula_month": fuel_formula_month,
    "transmission_seeds": transmission_seeds,
}
