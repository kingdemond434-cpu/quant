"""PAKISTAN'S OWN MINERS -- the five clocks the generic set cannot know.

`MINERS` maps a name to `callable(pack, ctx) -> dict`, the contract `country_lab.run_lab`
reads for a pack directory's `miners.py`, and every entry in the pack's `CUSTOM_MINERS`
(`countries.pk.miners:<function>`) resolves to a function here, so the two registrations are
one set. Each miner builds ITS OWN event dates from the pack's tables (the SBP calendar, the
1st/16th petrol notification, the ANNOUNCED moon-sighting closures, the trade-decision series)
and hands them to the framework's event study through the shared kit, so a Pakistani finding
carries the same matched-weekday control, randomised-date null and adjacent-day placebo as
every other country's. Discoveries go through `ctx.record` and nowhere else.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
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

SOURCE = "pk:pack"


def _pack_module() -> Any:
    try:
        from countries.pk import pack as mod
    except ImportError:
        spec = importlib.util.spec_from_file_location(
            "country_pk_pack", Path(__file__).resolve().parent / "pack.py")
        if spec is None or spec.loader is None:  # pragma: no cover
            raise
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


def sbp_decision_windows(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """PK-A: the SBP's scheduled decisions on the stress-channel instruments, intraday."""
    ctx.miner = ctx.miner or "sbp_decision_windows"
    dates = [date.fromisoformat(d) for d in pack.central_bank.decision_dates]
    return K.event_study(
        pack, ctx, name="sbp_decision_windows", symbols=("USDINR", "XAUUSD", "US500"),
        dates=dates, mechanism="pk_sbp_decision_stress_channel",
        actor="State Bank of Pakistan Monetary Policy Committee",
        constraint="eight scheduled decisions a year on a published calendar; the rupee is "
                   "absent from the broker, so the reaction is read on the regional cross, "
                   "gold and global risk",
        rationale="a rate decision in a programme economy reprices its stress premium; the "
                  "regional cross and gold carry the frontier-stress beta",
        falsifier="the decision-day effect matches the eight nearest non-meeting weekdays or "
                  "the RBI decision-day control",
        source_id=f"{SOURCE}:sbp", required_data=["SBP:policy_rate", "MPC calendar"],
        horizon="intraday", payload={"domain": "PK-A", "n_dates": len(dates)})


def petrol_fortnight_clock(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """PK-D: the fortnightly petrol notification as an administered pass-through, with the
    8th/23rd placebo run alongside so an 'effect' on Brent can be told from the calendar."""
    ctx.miner = ctx.miner or "petrol_fortnight_clock"
    bars = ctx.bars("XBRUSD", "H1")
    if bars is None:
        ctx.note("petrol_fortnight_clock:bars:XBRUSD", "no H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "petrol_fortnight_clock",
                "why": "no XBRUSD tape"}
    lo, hi = K.tape_span(bars)
    events = K.month_days(lo, hi, (1, 16))
    placebo = K.month_days(lo, hi, (8, 23))
    main = K.event_study(
        pack, ctx, name="petrol_fortnight_clock", symbols=("XBRUSD", "XTIUSD"), dates=events,
        mechanism="pk_petrol_notification_pass_through",
        actor="the Finance Division and OGRA as the fortnightly petrol price setter",
        constraint="prices are notified the evening before the 1st and the 16th and take "
                   "effect at midnight Karachi",
        rationale="an INPUT-direction mechanism: Brent and the rupee pass into the domestic "
                  "price; an outward effect on crude is not expected and is measured honestly",
        falsifier="the notification-day window matches the 8th/23rd placebo or the matched "
                  "weekday control",
        source_id=f"{SOURCE}:ogra", required_data=["OGRA:petrol"], horizon="session",
        hours=(18, 21), payload={"domain": "PK-D", "placebo_days": "8th and 23rd"})
    ctrl = K.event_study(
        pack, ctx, name="petrol_fortnight_placebo", symbols=("XBRUSD",), dates=placebo,
        mechanism="pk_petrol_notification_placebo", actor="placebo", constraint="none",
        rationale="the 8th/23rd carry no notification; a move here is the calendar, not OGRA",
        falsifier="n/a", source_id=f"{SOURCE}:ogra_placebo", required_data=[],
        horizon="session", hours=(18, 21), payload={"domain": "PK-D", "placebo": True},
        novelty=0.0, confidence=0.0)
    main["placebo"] = {k: v for k, v in ctrl.items() if k != "readings"}
    return main


def moon_sighting_holidays(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """PK-L / PK-E: the ANNOUNCED closures only; the PROJECTED rows are the placebo."""
    ctx.miner = ctx.miner or "moon_sighting_holidays"
    mod = _pack_module()
    announced: list[date] = []
    projected: list[date] = []
    for year, rows in mod.LUNAR_HOLIDAYS.items():
        for day, _name, status in rows:
            (announced if status == "ANNOUNCED" else projected).append(day)
        _ = year
    out = K.event_study(
        pack, ctx, name="moon_sighting_holidays", symbols=("XAUUSD", "USDINR"),
        dates=K.shift(announced, -1), mechanism="pk_announced_holiday_eve_liquidity",
        actor="the Central Ruet-e-Hilal Committee and the banks it closes",
        constraint="the closed day is fixed the evening before; only ANNOUNCED dates are the "
                   "sample",
        rationale="the eve of a Pakistani bank closure carries the Eid cash and gold demand and "
                  "the loss of one South Asian liquidity pool the next day",
        falsifier="the announced eves match the projected-but-not-holiday eves or the matched "
                  "weekday control",
        source_id=f"{SOURCE}:ruet", required_data=["announced holiday rows"],
        horizon="overnight", payload={"domain": "PK-L", "n_announced": len(announced),
                                      "n_projected": len(projected)})
    out["projected_dates"] = [d.isoformat() for d in projected]
    return out


def softs_trade_transmission(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """PK-F / PK-G: the cotton arrivals count against COTTON and the tender series against
    WHEAT/SUGAR where the series are on the box; the fortnightly arrivals release days as an
    event study regardless."""
    ctx.miner = ctx.miner or "softs_trade_transmission"
    results: dict[str, Any] = {"miner": "softs_trade_transmission", "parts": {}}
    results["parts"]["arrivals_lead"] = K.series_lead(
        pack, ctx, name="pcga_arrivals_lead", series_name="PCGA:arrivals", symbols=("COTTON",),
        mechanism="pk_cotton_arrivals_import_swing",
        actor="APTMA textile mills as cotton importers",
        constraint="a short domestic crop must be replaced with imported lint",
        rationale="arrivals below the prior year raise Pakistan's import need, which reaches ICE "
                  "cotton through the season's contracts",
        falsifier="the arrivals shortfall carries no information for COTTON beyond the Indian "
                  "CCI arrivals in the same fortnights", source_id=f"{SOURCE}:pcga",
        horizon_days=10, payload={"domain": "PK-F"})
    bars = ctx.bars("COTTON", "H1")
    if bars is not None:
        lo, hi = K.tape_span(bars)
        season = [d for d in K.month_days(lo, hi, (1, 16)) if d.month in (9, 10, 11, 12, 1, 2)]
        results["parts"]["arrivals_release_days"] = K.event_study(
            pack, ctx, name="pcga_release_days", symbols=("COTTON",), dates=season,
            mechanism="pk_cotton_arrivals_release_reaction",
            actor="the Pakistan Cotton Ginners Association", constraint="the fortnightly count "
                                                                        "in season",
            rationale="the release day of a counted physical flow", falsifier="the release "
            "days match the same days out of season", source_id=f"{SOURCE}:pcga",
            required_data=["PCGA:arrivals"], horizon="session",
            payload={"domain": "PK-F"})
    else:
        ctx.note("softs_trade_transmission:bars:COTTON", "no H1 tape on this box")
    results["parts"]["tender_lead"] = K.series_lead(
        pack, ctx, name="tcp_tender_lead", series_name="TCP:wheat_tenders",
        symbols=("WHEAT",), mechanism="pk_wheat_tender_demand",
        actor="the Trading Corporation of Pakistan", constraint="the harvest shortfall",
        rationale="a state import tender is Black Sea demand the CBOT export basis reads",
        falsifier="tender windows match the GASC control and the matched weekday control",
        source_id=f"{SOURCE}:tcp", horizon_days=5, payload={"domain": "PK-G"})
    parts = results["parts"].values()
    results["outcome"] = K.OK if any(p.get("outcome") == K.OK for p in parts) else K.UNMEASURED
    results["discoveries"] = sum(int(p.get("discoveries") or 0) for p in parts)
    return results


def transmission_seeds(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """The pack's transmission map as HYPOTHESIS discoveries -- the map the law grants a
    region before its tape has been read."""
    ctx.miner = ctx.miner or "transmission_seeds"
    mod = _pack_module()
    return K.seed_edges(pack, ctx, name="transmission_seeds", edges=mod.TRANSMISSION_EDGES_SEED,
                        mechanism_prefix="pk_transmission", source_id=f"{SOURCE}:edges")


MINERS: dict[str, Any] = {
    "sbp_decision_windows": sbp_decision_windows,
    "petrol_fortnight_clock": petrol_fortnight_clock,
    "moon_sighting_holidays": moon_sighting_holidays,
    "softs_trade_transmission": softs_trade_transmission,
    "transmission_seeds": transmission_seeds,
}
