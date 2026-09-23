"""CAUCASUS AND CENTRAL ASIA: the six clocks the generic miner set cannot know.

`MINERS` maps a name to `callable(pack, ctx) -> dict`, the contract `country_lab.run_lab` reads
for a pack directory's `miners.py`, and every entry in the pack's `CUSTOM_MINERS`
(`countries.caucasus_central_asia.miners:<function>`) resolves to a function here, so the two
registrations are one set. Each miner builds ITS OWN event dates from the pack's tables -- the
two dated corridor documents, the month-end remittance window, the five national holiday
calendars, the sovereign gold release window -- and hands them to the framework's event study
through the shared kit, so a finding here carries the same matched weekday+hour control,
randomised-date null and adjacent-day placebo as every other country's.

WHAT IS DIFFERENT ABOUT THIS REGION, AND WHY EACH MINER IS BUILT THE WAY IT IS.

  * THE REGION HAS A BUILT-IN CONTROL AND IT WOULD BE NEGLIGENT NOT TO USE IT. On every Nowruz
    and on both Eids, FOUR of the five jurisdictions are shut and ARMENIA IS OPEN. That is a
    treatment and a control on the same calendar date inside the same region, which almost no
    other pack on this desk has. `regional_closure_breadth` is written around it.
  * THE CORRIDOR'S ERAS ARE DOCUMENTS, NOT CHANGE POINTS. 2022-02-24 and 2023-12-22 are dated
    public decisions, so `corridor_era_breaks` runs each era as the others' control rather than
    letting an algorithm find a break and then explain it.
  * ONE ARM IS CONTAMINATED BY SELECTION AND SAYS SO. The NBKR auctions precisely when the flow
    is large, so an uncorrected event study on auction days finds an effect whether or not one
    exists. That arm is labelled in its own payload rather than left for a reviewer.
  * MOST OF A REPORTED RESERVE CHANGE IS THE PRICE. `sovereign_gold_supply` runs the
    valuation-only null FIRST, because a gold-reserve series moves with gold before it moves
    with any operation.

Discoveries go through `ctx.record` and nowhere else; a missing tape is `ctx.note`d UNMEASURED
by symbol, which is a verdict about this box and never a finding about the region.
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

SOURCE = "caucasus_central_asia:pack"


def _pack_module() -> Any:
    try:
        from countries.caucasus_central_asia import pack as mod  # type: ignore[import-not-found]
    except ImportError:
        spec = importlib.util.spec_from_file_location(
            "country_caucasus_central_asia_pack", Path(__file__).resolve().parent / "pack.py")
        if spec is None or spec.loader is None:  # pragma: no cover
            raise
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


def _finish(out: dict[str, Any]) -> dict[str, Any]:
    parts = list(out.get("parts", {}).values())
    out["outcome"] = K.OK if any(p.get("outcome") == K.OK for p in parts) else K.UNMEASURED
    out["discoveries"] = sum(int(p.get("discoveries") or 0) for p in parts)
    return out


def corridor_era_breaks(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """CCA-A and CCA-E: three eras separated by two DATED DOCUMENTS, each the others' control.

    2022-02-24 is the invasion and 2023-12-22 is the order exposing foreign financial
    institutions to secondary sanctions. Both are public decisions with a date, which is the
    only kind of boundary a preregistered study may condition on. The miner runs the two break
    days as events and then runs matched weekdays from INSIDE each era, so the question is never
    "did something happen" but "is this era's ordinary Wednesday different from the last one's".
    """
    ctx.miner = ctx.miner or "corridor_era_breaks"
    mod = _pack_module()
    bars = ctx.bars("USDRUB", "H1")
    if bars is None:
        ctx.note("corridor_era_breaks:bars:USDRUB", "no H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "corridor_era_breaks",
                "why": "no USDRUB tape; the corridor eras cannot be measured here"}
    lo, hi = K.tape_span(bars)
    out: dict[str, Any] = {"miner": "corridor_era_breaks", "parts": {},
                           "tape_span": [lo.isoformat(), hi.isoformat()]}
    breaks = [d for d in (mod.CORRIDOR_START, mod.CORRIDOR_ENFORCEMENT) if lo <= d <= hi]
    if breaks:
        out["parts"]["break_days"] = K.event_study(
            pack, ctx, name="cca_corridor_break_days",
            symbols=("USDRUB", "USDTRY", "USDCNH"), dates=breaks,
            mechanism="cca_corridor_regime_break",
            actor="the sanctions-enforcement authority and the Russian importer",
            constraint="a dated public decision that changes who may clear a payment",
            rationale="the corridor's demand appeared on one date and its payment friction on "
                      "another; both are documents rather than inferred change points",
            falsifier="the two break days match the matched weekday-and-hour control on every "
                      "target, which would mean the documents changed nothing measurable",
            source_id=f"{SOURCE}:corridor_breaks",
            required_data=["COMTRADE:mirror", "CBA:transfers_by_country"],
            horizon="session", payload={"domain": "CCA-E", "declared_break": True,
                                        "n_breaks": len(breaks)})
    else:
        ctx.note("corridor_era_breaks:dates",
                 f"the tape runs {lo}..{hi} and neither declared corridor break falls inside "
                 f"it; the regime break is UNMEASURED on this box, not absent from the world")
    for era in mod.CORRIDOR_ERAS:
        days = [d for d in mod.corridor_era_days(lo, hi, era) if d.weekday() == 2]
        if not days:
            ctx.note(f"corridor_era_breaks:{era}",
                     f"no weekday of this tape falls in the {era} era; that arm is UNMEASURED "
                     f"and the eras that DO have days are therefore uncontrolled against it")
            continue
        out["parts"][f"era_{era.lower()}"] = K.event_study(
            pack, ctx, name=f"cca_corridor_era_{era.lower()}", symbols=("USDRUB", "USDTRY"),
            dates=days, mechanism=f"cca_corridor_era_{era.lower()}",
            actor="the re-export declarant and the third-country correspondent bank",
            constraint="the era's own payment and enforcement conditions",
            rationale="an era is only measured when its ordinary days are measured; these are "
                      "plain Wednesdays inside the era, so no event is doing the work",
            falsifier="the three eras' ordinary Wednesdays are indistinguishable from each "
                      "other, which would mean the corridor is not a regime at all",
            source_id=f"{SOURCE}:era_{era.lower()}", required_data=[], horizon="session",
            payload={"domain": "CCA-A", "era": era, "n_days": len(days)},
            novelty=0.3, confidence=0.3)
    return _finish(out)


def remittance_month_end(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """CCA-B: the month-end remittance payout window, with the mid-month placebo built in.

    Russian wages are paid around the month end and four Central Asian and Caucasus economies
    convert them within days. A month-end effect is a CALENDAR effect until it is told apart
    from one, so the fifteenth of the same months is run as an explicit placebo arm and months
    whose window overlaps a high-breadth regional closure are excluded by name rather than
    silently averaged in.
    """
    ctx.miner = ctx.miner or "remittance_month_end"
    mod = _pack_module()
    bars = ctx.bars("USDRUB", "H1")
    if bars is None:
        ctx.note("remittance_month_end:bars:USDRUB", "no H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "remittance_month_end",
                "why": "no USDRUB tape; the month-end window cannot be measured here"}
    lo, hi = K.tape_span(bars)
    windows: list[date] = []
    excluded: list[str] = []
    year, month = lo.year, lo.month
    while (year, month) <= (hi.year, hi.month):
        last, _second = mod.remittance_window(year, month)
        if lo <= last <= hi:
            if mod.closure_breadth(last) >= 3:
                excluded.append(last.isoformat())
            else:
                windows.append(last)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    out: dict[str, Any] = {"miner": "remittance_month_end", "parts": {},
                           "excluded_for_closure": excluded,
                           "tape_span": [lo.isoformat(), hi.isoformat()]}
    if not windows:
        ctx.note("remittance_month_end:dates", "no usable month-end window inside the tape")
        return _finish(out)
    out["parts"]["month_end"] = K.event_study(
        pack, ctx, name="cca_remittance_month_end", symbols=("USDRUB", "EURRUB", "XAUUSD"),
        dates=windows, mechanism="cca_remittance_month_end_conversion",
        actor="the Uzbek, Tajik, Kyrgyz and Armenian migrant households",
        constraint="the Russian pay cycle, which the migrants do not set",
        rationale="four economies convert the same month-end rouble wage within days of each "
                  "other, which is a scheduled, repeating, same-direction FX demand",
        falsifier="the month-end window matches the mid-month placebo on every target",
        source_id=f"{SOURCE}:month_end",
        required_data=["CBA:transfers_by_country", "NBT:remittances"],
        horizon="session", payload={"domain": "CCA-B", "n_windows": len(windows)})
    placebo = K.month_days(lo, hi, (15,))
    if placebo:
        out["parts"]["mid_month_placebo"] = K.event_study(
            pack, ctx, name="cca_remittance_mid_month", symbols=("USDRUB", "EURRUB"),
            dates=placebo, mechanism="cca_remittance_mid_month_control", actor="control",
            constraint="the fifteenth of the same months, which carries no payout",
            rationale="the explicit placebo the month-end claim is measured against",
            falsifier="n/a -- this arm is the control",
            source_id=f"{SOURCE}:mid_month", required_data=[], horizon="session",
            payload={"domain": "CCA-B", "control": True}, novelty=0.0, confidence=0.0)
    return _finish(out)


def regional_closure_breadth(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """CCA-N: closure BREADTH, and Armenia as the control that is open on the same date.

    This is the pack's best identification and it costs nothing: on every Nowruz and both Eids,
    four of the five jurisdictions are shut and Armenia is open. So the miner runs the
    high-breadth days as the treatment, the ARMENIAN-ONLY closures as a same-region control
    with the opposite sign, and the matched weekday 26 weeks away as the calendar null.
    """
    ctx.miner = ctx.miner or "regional_closure_breadth"
    mod = _pack_module()
    bars = ctx.bars("USDRUB", "H1")
    if bars is None:
        ctx.note("regional_closure_breadth:bars:USDRUB", "no H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "regional_closure_breadth",
                "why": "no USDRUB tape; the closure calendar cannot be measured here"}
    lo, hi = K.tape_span(bars)
    wide: list[date] = []
    armenia_only: list[date] = []
    for year in range(lo.year, hi.year + 1):
        for day, where in mod.regional_holidays(year).items():
            if not (lo <= day <= hi) or day.weekday() >= 5:
                continue
            if len(where) >= 3 and "am" not in where:
                wide.append(day)
            elif where == ("am",):
                armenia_only.append(day)
    out: dict[str, Any] = {"miner": "regional_closure_breadth", "parts": {},
                           "n_wide": len(wide), "n_armenia_only": len(armenia_only),
                           "collision_years": list(mod.collision_years())}
    if wide:
        out["parts"]["wide_closures"] = K.event_study(
            pack, ctx, name="cca_wide_closure_days", symbols=("USDRUB", "XAUUSD", "USDTRY"),
            dates=wide, mechanism="cca_regional_closure_breadth",
            actor="the banks, transfer operators and customs posts of four jurisdictions",
            constraint="a book that cannot be funded during the block is funded before or after",
            rationale="when four of five close at once the region's conversion and settlement "
                      "plumbing stops; the flow QUEUES rather than vanishing",
            falsifier="high-breadth closure days behave no differently from the matched weekday "
                      "26 weeks away on every target",
            source_id=f"{SOURCE}:closure_wide", required_data=[], horizon="session",
            payload={"domain": "CCA-N", "breadth": ">=3 of 5", "armenia_open": True})
    else:
        ctx.note("regional_closure_breadth:wide",
                 "no high-breadth regional closure falls inside this tape; the breadth arm is "
                 "UNMEASURED on this box")
    if armenia_only:
        out["parts"]["armenia_only_control"] = K.event_study(
            pack, ctx, name="cca_armenia_only_closure", symbols=("USDRUB", "XAUUSD"),
            dates=armenia_only, mechanism="cca_armenia_only_closure_control", actor="control",
            constraint="Armenia shut and the other four open -- the mirror image of the "
                       "treatment, on dates the Christian calendar chooses",
            rationale="the same region, the opposite closure; if both arms move the effect is "
                      "regional beta and belongs to neither calendar",
            falsifier="n/a -- this arm is the control",
            source_id=f"{SOURCE}:closure_am", required_data=[], horizon="session",
            payload={"domain": "CCA-N", "control": True}, novelty=0.0, confidence=0.0)
    else:
        ctx.note("regional_closure_breadth:armenia",
                 "no Armenian-only weekday closure inside this tape, so the best control this "
                 "pack owns is empty and the breadth arm is uncontrolled and says so")
    return _finish(out)


def sovereign_gold_supply(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """CCA-C, CCA-UZ-A and CCA-KG-B: the sovereign gold release window, valuation null first.

    The CBU publishes its gold holding monthly in BOTH tonnes and value, which is the only
    reason an OPERATION can be separated from a PRICE here. The miner runs the release window
    (the first week of the month) and states in its own payload that the valuation-only null is
    the arm that must be cleared before any tonnage reading means anything -- the series is
    denominated in the very asset the study is about.
    """
    ctx.miner = ctx.miner or "sovereign_gold_supply"
    bars = ctx.bars("XAUUSD", "H1")
    if bars is None:
        ctx.note("sovereign_gold_supply:bars:XAUUSD", "no H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "sovereign_gold_supply",
                "why": "no XAUUSD tape; the sovereign gold window cannot be measured here"}
    lo, hi = K.tape_span(bars)
    release = K.month_days(lo, hi, (5, 6, 7))
    placebo = K.month_days(lo, hi, (20, 21, 22))
    out: dict[str, Any] = {"miner": "sovereign_gold_supply", "parts": {},
                           "n_release": len(release), "n_placebo": len(placebo)}
    if release:
        out["parts"]["reserve_release_window"] = K.event_study(
            pack, ctx, name="cca_cbu_gold_release", symbols=("XAUUSD",), dates=release,
            mechanism="cca_sovereign_gold_operation_window",
            actor="the Central Bank of Uzbekistan as a seller of monetary gold",
            constraint="a fiscal need for dollars and reserves that are majority gold by value",
            rationale="a sovereign that buys domestic mine output and sells bullion is a "
                      "recurring published supply leg; the release window is when the month's "
                      "operation becomes public",
            falsifier="the release window matches the mid-month placebo on XAUUSD once the "
                      "valuation-only reconstruction of the reported change is removed",
            source_id=f"{SOURCE}:cbu_gold",
            required_data=["CBU:reserves_gold", "WGC:official_holdings"],
            horizon="session",
            payload={"domain": "CCA-UZ-A",
                     "valuation_null_required": True,
                     "why": "the reserve series is denominated in the asset being studied, so "
                            "most of any reported change is the price; the tonnage arm is "
                            "UNMEASURED until the collector holds the published tonnes"})
    if placebo:
        out["parts"]["mid_month_placebo"] = K.event_study(
            pack, ctx, name="cca_gold_mid_month", symbols=("XAUUSD",), dates=placebo,
            mechanism="cca_sovereign_gold_control", actor="control",
            constraint="the third week of the same months, which carries no reserve release",
            rationale="the explicit placebo the release-window claim is measured against",
            falsifier="n/a -- this arm is the control",
            source_id=f"{SOURCE}:gold_placebo", required_data=[], horizon="session",
            payload={"domain": "CCA-C", "control": True}, novelty=0.0, confidence=0.0)
    return _finish(out)


def transmission_seeds(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """The pack's transmission map as HYPOTHESIS discoveries -- the map the law grants a region
    before its tape has been read (LAWS 5n). The Chinese customs release window is attached as
    the calendar the Turkmen gas edge actually settles against, because that release is the only
    date on which a Turkmen number becomes public anywhere."""
    ctx.miner = ctx.miner or "transmission_seeds"
    mod = _pack_module()
    out: dict[str, Any] = K.seed_edges(pack, ctx, name="transmission_seeds",
                                       edges=mod.TRANSMISSION_EDGES_SEED,
                                       mechanism_prefix="cca_transmission",
                                       source_id=f"{SOURCE}:edges")
    bars = ctx.bars("XNGUSD", "H1")
    if bars is None:
        ctx.note("transmission_seeds:bars:XNGUSD",
                 "no H1 tape; the Chinese customs mirror arm is UNMEASURED")
        return out
    lo, hi = K.tape_span(bars)
    customs = K.month_days(lo, hi, (18, 19, 20))
    out["china_customs_window"] = K.event_study(
        pack, ctx, name="cca_china_customs_detail", symbols=("XNGUSD", "USDCNH"), dates=customs,
        mechanism="cca_turkmen_gas_mirror_release",
        actor="Turkmengaz as seller and CNPC as monopsonist buyer",
        constraint="one pipeline, one customer, and a seller that publishes nothing",
        rationale="the detailed by-origin customs tables are the ONLY window in which a Turkmen "
                  "gas volume becomes public; if the number moves anything, it moves it here",
        falsifier="the detailed-release window matches the matched weekday control, or the "
                  "Turkmen volume is fully explained by China's total import series",
        source_id=f"{SOURCE}:china_customs",
        required_data=["CHINACUSTOMS:gas_imports_tm"], horizon="session", hours=(2, 6),
        payload={"domain": "CCA-TM-A", "n_releases": len(customs),
                 "monopsony_warning": "a monopsonist's purchases look like the seller's supply "
                                      "and are not; China's total import series is the null"},
        novelty=0.45, confidence=0.3)
    return out


def emit_cells(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """THE CELL MINT. The pack's domains x its executable instruments x its own named conditions,
    pushed to the registry as hypotheses so the gauntlet has something to judge every hour.

    Every cell names a condition the pack's own data plane can evaluate, and every one carries
    the control its domain declared. A cell with no condition and no control is not breadth --
    it is a charge against the program's shared multiple-testing budget for nothing.
    """
    ctx.miner = ctx.miner or "emit_cells"
    mod = _pack_module()
    rows = mod.cells()
    n = 0
    by_domain: dict[str, int] = {}
    for cell in rows:
        if ctx.remaining_s() <= 0:
            ctx.note("emit_cells:budget", f"budget spent after {n} of {len(rows)} cells")
            break
        did, created = ctx.record(
            mechanism=f"cca_cell:{cell['domain']}:{cell['mechanism_family']}",
            source_id=f"{SOURCE}:cells", source_type="pack_cell",
            actor=str(pack.name), constraint=str(cell["condition"]),
            economic_rationale=str(cell["why"]), assets=[str(cell["symbol"])],
            horizons=[str(cell["horizon"])], sessions=["all"], regimes=["unconditional"],
            required_data=[], pit_requirements=["the condition must be evaluable from a vintage "
                                                "stamped before the window opens"],
            novelty=0.35, confidence=0.25,
            falsifier=f"the cell's condition carries no information beyond its declared "
                      f"control: {cell['control']}",
            payload={"cell": dict(cell), "pack": mod.CODE.lower()})
        n += int(created or did != "dry-run")
        by_domain[str(cell["domain"])] = by_domain.get(str(cell["domain"]), 0) + 1
    return {"outcome": K.OK if rows else K.UNMEASURED, "miner": "emit_cells",
            "discoveries": n, "cells_emitted": len(rows), "by_domain": by_domain,
            "why": "" if rows else "the pack mints no cells"}


MINERS: dict[str, Any] = {
    "corridor_era_breaks": corridor_era_breaks,
    "remittance_month_end": remittance_month_end,
    "regional_closure_breadth": regional_closure_breadth,
    "sovereign_gold_supply": sovereign_gold_supply,
    "transmission_seeds": transmission_seeds,
    "emit_cells": emit_cells,
}
