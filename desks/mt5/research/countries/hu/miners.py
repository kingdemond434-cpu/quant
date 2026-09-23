"""HUNGARY'S OWN MINERS -- the six clocks the generic set cannot know.

`MINERS` maps a name to `callable(pack, ctx) -> dict`, the contract `country_lab.run_lab` reads
for a pack directory's `miners.py`, and every entry in the pack's `CUSTOM_MINERS`
(`countries.hu.miners:<function>`) resolves to a function here, so the two registrations are one
set. Each miner builds ITS OWN event dates from the pack's tables -- the monthly rate decisions,
the two-rate regime's boundaries, the six-cross panel, the AKK auction clock and the DECREED
rest days and working Saturdays -- and hands them to the framework's event study through the
shared kit, so a Hungarian finding carries the same matched-weekday control, randomised-date
null and adjacent-day placebo as every other country's. Discoveries go through `ctx.record` and
nowhere else.
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

SOURCE = "hu:pack"


def _pack_module() -> Any:
    try:
        from countries.hu import pack as mod  # type: ignore[import-not-found]
    except ImportError:
        spec = importlib.util.spec_from_file_location(
            "country_hu_pack", Path(__file__).resolve().parent / "pack.py")
        if spec is None or spec.loader is None:  # pragma: no cover
            raise
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


def mnb_decision_windows(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """HU-A: the monthly rate decision, run SEPARATELY inside and outside the two-rate regime.

    A decision about a base rate that was NOT the effective instrument is not the same event as
    a decision about one that was, and pooling the two is the single most common error in the
    Hungarian literature this pack is written against.
    """
    ctx.miner = ctx.miner or "mnb_decision_windows"
    mod = _pack_module()
    dates = [date.fromisoformat(d) for d in pack.central_bank.decision_dates]
    split = {"single_rate": [d for d in dates if not mod.in_two_rate_regime(d)],
             "two_rate": [d for d in dates if mod.in_two_rate_regime(d)]}
    out: dict[str, Any] = {"miner": "mnb_decision_windows", "legs": {}}
    for label, days in split.items():
        got = K.event_study(
            pack, ctx, name=f"mnb_decision_{label}", symbols=("EURHUF", "USDHUF", "EURPLN"),
            dates=days, mechanism=f"hu_mnb_decision_{label}", actor="the Monetaris Tanacs",
            constraint="a monthly rate-setting meeting on a published calendar -- which is NOT "
                       "the full Hungarian policy event list, because the effective rate was "
                       "set at a daily tender outside it for eleven months",
            rationale="six HUF crosses are quoted here, so a decision's effect can be "
                      "decomposed into the forint's own factor and each funding leg's story "
                      "instead of being attributed to whichever cross was looked at",
            falsifier="the decision window matches the four nearest non-meeting Tuesdays at the "
                      "same LOCAL clock, or matches ECB decision days",
            source_id=f"{SOURCE}:mnb", required_data=["MNB:alapkamat", "decision calendar"],
            horizon="intraday", hours=(12, 15),
            payload={"domain": "HU-A", "regime": label, "n_dates": len(days),
                     "sample_note": "the two regimes are NEVER pooled; each leg reports its own "
                                    "event count"})
        out["legs"][label] = got
    out["outcome"] = next((g.get("outcome") for g in out["legs"].values()
                           if g.get("outcome") != K.UNMEASURED), K.UNMEASURED)
    return out


def two_rate_regime(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """HU-B and HU-C: the 18%-one-day-deposit regime as a dated boundary pair, with the CEE
    peers as the concurrent null. Two boundaries is below any event floor and the miner reports
    that rather than padding the sample: the real object is the distribution either side."""
    ctx.miner = ctx.miner or "two_rate_regime"
    mod = _pack_module()
    bars = ctx.bars("EURHUF", "D1") or ctx.bars("EURHUF", "H1")
    if bars is None:
        ctx.note("two_rate_regime:bars:EURHUF", "no tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "two_rate_regime", "why": "no EURHUF tape"}
    lo, hi = K.tape_span(bars)
    boundaries = [d for d in (mod.TWO_RATE_REGIME["introduced"],
                              mod.TWO_RATE_REGIME["converged"]) if lo <= d <= hi]
    inside = mod.two_rate_days(lo, hi)
    got: dict[str, Any] = K.event_study(
        pack, ctx, name="two_rate_regime", symbols=("EURHUF", "USDHUF", "CHFHUF", "EURPLN"),
        dates=boundaries or inside[:1], mechanism="hu_two_rate_regime_break",
        actor="the MNB money-market desk",
        constraint="an overnight deposit quick tender at 18% above a 13% base rate, decided "
                   "DAILY outside the meeting calendar, from 2022-10-14 to 2023-09-26",
        rationale="for eleven months the real cost of funding a forint short was the tender "
                  "rate; every carry and differential series built on the base rate over that "
                  "window measures a rate nobody could fund at",
        falsifier="the tender rate adds nothing to the base rate in explaining the crosses over "
                  "the window, or the same shift appears in EURPLN and EURCZK -- in which case "
                  "it is regional and not the split",
        source_id=f"{SOURCE}:mnb_tender",
        required_data=["MNB:egynapos_betet", "MNB:alapkamat"],
        horizon="multi_day",
        payload={"domain": "HU-B", "n_boundaries": len(boundaries),
                 "n_days_inside_tape": len(inside),
                 "peak_spread_pp": (float(mod.TWO_RATE_REGIME["peak_rate_pct"])
                                    - float(mod.TWO_RATE_REGIME["base_rate_at_peak_pct"])),
                 "sample_note": "TWO dated boundaries is below the event floor and is reported "
                                "as such; the distributional test is the real object"})
    return got


def six_cross_panel(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """HU-D: the pack's structural advantage. Six simultaneous prices of ONE currency, so a
    common move can be told from a funding leg's own story -- the substitute for a COT report
    that does not exist for the forint.

    It reports which of the six crosses actually have tape on this box, because a panel with a
    missing leg is a different estimator and saying so is the measurement (L1.28a).
    """
    ctx.miner = ctx.miner or "six_cross_panel"
    mod = _pack_module()
    crosses = mod.six_cross_panel()
    present: list[str] = []
    for sym in crosses:
        if ctx.remaining_s() <= 0:
            break
        if ctx.bars(sym, "D1") is not None or ctx.bars(sym, "H1") is not None:
            present.append(sym)
        else:
            ctx.note(f"six_cross_panel:bars:{sym}", "no tape on this box")
    if len(present) < 2:
        return {"outcome": K.UNMEASURED, "miner": "six_cross_panel",
                "why": f"only {len(present)} of {len(crosses)} HUF crosses have tape here",
                "declared": list(crosses), "present": present}
    bars = ctx.bars(present[0], "D1") or ctx.bars(present[0], "H1")
    lo, hi = K.tape_span(bars) if bars is not None else (date(2000, 1, 1), date(2000, 1, 2))
    got: dict[str, Any] = K.event_study(
        pack, ctx, name="six_cross_panel", symbols=tuple(present),
        dates=K.weekday_dates(lo, hi, 2), mechanism="hu_six_cross_common_factor",
        actor="the offshore forint carry account",
        constraint="NO COT SERIES EXISTS FOR HUF; the panel is the substitute and it is only "
                   "informative if the legs are sampled at the same timestamps",
        rationale="a move common to all six crosses is the forint; a move in one is that "
                  "funding leg's own story, and the decomposition is impossible with one cross",
        falsifier="the common factor adds nothing to EURHUF alone, in which case the panel is "
                  "redundant and this pack's structural advantage is imaginary",
        source_id=f"{SOURCE}:panel", required_data=["MNB:arfolyam_EURHUF"],
        horizon="multi_day",
        payload={"domain": "HU-D", "declared_panel": list(crosses), "present": present,
                 "missing": [s for s in crosses if s not in present],
                 "note": "a panel with a missing leg is a DIFFERENT estimator; the missing legs "
                         "are named rather than silently dropped"})
    got["panel"] = {"declared": list(crosses), "present": present}
    return got


def auction_calendar(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """HU-J: the AKK Thursday bond clock, with the matched non-auction weekday placebo beside
    it. Tuesday is deliberately NOT the placebo: it carries the bill auction AND the rate
    decision, which is exactly the collision this domain exists to separate."""
    ctx.miner = ctx.miner or "auction_calendar"
    bars = ctx.bars("EURHUF", "H1") or ctx.bars("EURHUF", "D1")
    if bars is None:
        ctx.note("auction_calendar:bars:EURHUF", "no tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "auction_calendar", "why": "no EURHUF tape"}
    lo, hi = K.tape_span(bars)
    thursdays = K.weekday_dates(lo, hi, 3)
    placebo = K.weekday_dates(lo, hi, 0)
    main: dict[str, Any] = K.event_study(
        pack, ctx, name="auction_calendar", symbols=("EURHUF", "USDHUF"), dates=thursdays,
        mechanism="hu_akk_auction_window", actor="AKK Zrt., the government debt agency",
        constraint="the issuance calendar is published a QUARTER AHEAD, so the timing carries "
                   "no surprise and only the cut-off and the bid-to-cover can",
        rationale="a dated forced-supply event on a currency this broker quotes six ways; the "
                  "retail programme running beside it is what changed who owns the debt",
        falsifier="the Thursday window matches the Monday placebo or the matched weekday "
                  "control, in which case this is a weekday effect and not an auction effect",
        source_id=f"{SOURCE}:akk", required_data=["AKK:auction_yield"],
        horizon="session", hours=(9, 12),
        payload={"domain": "HU-J", "placebo_day": "Monday", "n_thursdays": len(thursdays),
                 "note": "TUESDAY IS NOT THE PLACEBO: it carries the bill auction and the rate "
                         "decision at once. Exact auction dates come from the AKK calendar; "
                         "until that series is on the box the miner uses the Thursday clock "
                         "and SAYS SO"})
    ctrl = K.event_study(
        pack, ctx, name="auction_calendar_placebo", symbols=("EURHUF",), dates=placebo,
        mechanism="hu_akk_auction_placebo", actor="placebo", constraint="none",
        rationale="Monday carries no scheduled auction and no decision; a move here is calendar",
        falsifier="n/a", source_id=f"{SOURCE}:akk_placebo", required_data=[],
        horizon="session", hours=(9, 12), payload={"domain": "HU-J", "placebo": True},
        novelty=0.0, confidence=0.0)
    main["placebo"] = {k: v for k, v in ctrl.items() if k != "readings"}
    return main


def decreed_calendar(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """HU-L and HU-K: the DECREED calendar. Bridge rest days close Budapest while the euro area
    trades; working Saturdays put Hungarian corporates and banks at work when every neighbouring
    market is shut. Neither is computable from any rule -- both are declared per year, and a
    year with no decree in the pack produces no dates at all rather than invented ones."""
    ctx.miner = ctx.miner or "decreed_calendar"
    mod = _pack_module()
    bars = ctx.bars("EURHUF", "H1") or ctx.bars("EURHUF", "D1")
    if bars is None:
        ctx.note("decreed_calendar:bars:EURHUF", "no tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "decreed_calendar", "why": "no EURHUF tape"}
    lo, hi = K.tape_span(bars)
    rest: list[date] = []
    saturdays: list[date] = []
    undeclared: list[int] = []
    for year in range(lo.year, hi.year + 1):
        got_rest = [d for d in mod.bridge_rest_days(year) if lo <= d <= hi]
        got_sat = [d for d in mod.working_saturdays(year) if lo <= d <= hi]
        if not mod.SWAPPED_DAYS.get(year):
            undeclared.append(year)
        rest.extend(got_rest)
        saturdays.extend(got_sat)
    if not rest and not saturdays:
        ctx.note("decreed_calendar:dates",
                 f"no work-schedule decree is declared in this pack for {undeclared}")
        return {"outcome": K.UNMEASURED, "miner": "decreed_calendar",
                "why": "no declared bridge day or working Saturday inside the tape",
                "undeclared_years": undeclared}
    main: dict[str, Any] = K.event_study(
        pack, ctx, name="decreed_rest_days", symbols=("EURHUF", "EUSTX50", "GER40"),
        dates=sorted(rest), mechanism="hu_decreed_rest_day",
        actor="the ministry that issues the annual work-schedule decree",
        constraint="NO RULE COMPUTES THESE; they are gazetted a year ahead and this pack "
                   "carries them declared, with undeclared years left empty",
        rationale="a bridge rest day closes Budapest while the euro area trades, thinning one "
                  "leg of the pair and not the other",
        falsifier="declared rest days match the matched weekday 26 weeks away on every spread "
                  "and range measure",
        source_id=f"{SOURCE}:kozlony", required_data=["SWAPPED_DAYS"],
        horizon="session", hours=(7, 16),
        payload={"domain": "HU-L", "n_rest_days": len(rest), "undeclared_years": undeclared})
    sat = K.event_study(
        pack, ctx, name="working_saturdays", symbols=("EURHUF",), dates=sorted(saturdays),
        mechanism="hu_working_saturday",
        actor="the same decree, on the other side of the swap",
        constraint="an ordinary Saturday is the only honest null for a working Saturday",
        rationale="Hungarian corporates and banks are at work while every neighbouring market "
                  "is shut -- a liquidity state with no European counterpart at all",
        falsifier="working Saturdays are indistinguishable from ordinary Saturdays",
        source_id=f"{SOURCE}:kozlony_sat", required_data=["SWAPPED_DAYS"],
        horizon="session", hours=(7, 16),
        payload={"domain": "HU-L", "n_working_saturdays": len(saturdays)})
    main["working_saturdays"] = {k: v for k, v in sat.items() if k != "readings"}
    return main


def transmission_seeds(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """The pack's transmission map as HYPOTHESIS discoveries -- the map the law grants a region
    before its tape has been read."""
    ctx.miner = ctx.miner or "transmission_seeds"
    mod = _pack_module()
    seeded: dict[str, Any] = K.seed_edges(
        pack, ctx, name="transmission_seeds", edges=mod.TRANSMISSION_EDGES_SEED,
        mechanism_prefix="hu_transmission", source_id=f"{SOURCE}:edges")
    return seeded


MINERS: dict[str, Any] = {
    "mnb_decision_windows": mnb_decision_windows,
    "two_rate_regime": two_rate_regime,
    "six_cross_panel": six_cross_panel,
    "auction_calendar": auction_calendar,
    "decreed_calendar": decreed_calendar,
    "transmission_seeds": transmission_seeds,
}
