"""CENTRAL EUROPE AND THE BALKANS: the five clocks the generic miner set cannot know.

`MINERS` maps a name to `callable(pack, ctx) -> dict`, the contract `country_lab.run_lab` reads
for a pack directory's `miners.py`, and every entry in the pack's `CUSTOM_MINERS`
(`countries.cee_balkans.miners:<function>`) resolves to a function here, so the two
registrations are one set. Each miner builds ITS OWN event dates from the pack's tables -- the
CNB's eight Bank Board days, the MNB's twelve Monetary Council days, the two declared koruna
floor dates, the quick-tender era bounds, and the two Easter computations -- and hands them to
the framework's event study through the shared kit, so a CEE finding carries the same matched
weekday+hour control, randomised-date null and adjacent-day placebo as every other country's.
Discoveries go through `ctx.record` and nowhere else.

WHAT IS DIFFERENT ABOUT THIS REGION, AND WHY EACH MINER IS BUILT THE WAY IT IS. The single
commonest way to get central Europe wrong is to pool it. The CNB and the MNB do not decide on
the same days, the koruna traded inside a hard floor for three and a half years while the forint
never did, the forint's effective policy rate for eleven months of 2022-23 was set by an
instrument the Monetary Council did not vote on, and three of the eight jurisdictions here keep
a different Easter from the other five. So every miner in this file runs its samples SEPARATELY
and hands each one the other's dates as a control: the question is never "did something happen",
it is "did something happen HERE that did not happen in the country next door on the same day".
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

SOURCE = "cee_balkans:pack"

#: The koruna's exchange-rate commitment, declared rather than inferred. Both ends are public
#: decisions with a date, which is what makes CEE-CZ-B a regime break and not a change point
#: somebody's algorithm found.
FLOOR_START = date(2013, 11, 7)
FLOOR_END = date(2017, 4, 6)

#: The Hungarian two-rate era: a one-day deposit quick tender at 18% run beside a 13% base rate.
QUICK_TENDER_START = date(2022, 10, 14)
QUICK_TENDER_END = date(2023, 9, 26)


def _pack_module() -> Any:
    try:
        from countries.cee_balkans import pack as mod  # type: ignore[import-not-found]
    except ImportError:
        spec = importlib.util.spec_from_file_location(
            "country_cee_balkans_pack", Path(__file__).resolve().parent / "pack.py")
        if spec is None or spec.loader is None:  # pragma: no cover
            raise
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


def _days(values: Any) -> list[date]:
    return [date.fromisoformat(str(d)) for d in values]


def cnb_mnb_decision_windows(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """CEE-CZ-A and CEE-HU-A: TWO central banks, TWO samples, each the other's control.

    The CNB decides eight times a year at 14:30 Prague and the MNB twelve times at 14:00
    Budapest, in the same time zone one hour apart. Pooling them would measure "a CEE bank
    decided"; running them separately and then crossing them -- CNB dates on the forint, MNB
    dates on the koruna -- measures whether the reaction is the country's or the region's.
    """
    ctx.miner = ctx.miner or "cnb_mnb_decision_windows"
    mod = _pack_module()
    cnb = _days(pack.central_bank.decision_dates)
    mnb = _days(mod.MNB["decision_dates"])
    forecast = set(_days(mod.CENTRAL_BANK["forecast_meetings"]))
    out: dict[str, Any] = {"miner": "cnb_mnb_decision_windows", "parts": {}}

    out["parts"]["cnb_on_koruna"] = K.event_study(
        pack, ctx, name="cnb_decision_koruna", symbols=("EURCZK", "USDCZK"), dates=cnb,
        mechanism="cee_cz_cnb_decision_against_published_path",
        actor="the Czech National Bank Bank Board",
        constraint="eight scheduled meetings a year announced at 14:30 Prague, four of them "
                   "forecast meetings that publish the bank's own implied rate path",
        rationale="a surprise measured against a PUBLISHED path is a different quantity from a "
                  "surprise against a survey, and the koruna reprices on the path revision as "
                  "well as on the rate",
        falsifier="the decision-day window matches the eight nearest non-meeting weekdays, or "
                  "matches the MNB's own decision days on the same cross",
        source_id=f"{SOURCE}:cnb", required_data=["CNB:repo_2w", "CNB:implied_path"],
        horizon="intraday", hours=(12, 15),
        payload={"domain": "CEE-CZ-A", "n_dates": len(cnb),
                 "n_forecast_meetings": len(forecast & set(cnb))})

    out["parts"]["mnb_on_forint"] = K.event_study(
        pack, ctx, name="mnb_decision_forint", symbols=("EURHUF", "USDHUF", "CHFHUF"),
        dates=mnb, mechanism="cee_hu_mnb_decision_asymmetric_reaction",
        actor="the Magyar Nemzeti Bank Monetary Council",
        constraint="twelve rate-setting meetings a year published at 14:00 Budapest",
        rationale="the forint's reaction to its own central bank is asymmetric, because the "
                  "holders being disappointed by a dovish surprise are leveraged carry positions",
        falsifier="the MNB decision-day window on EURHUF matches the CNB decision-day window on "
                  "the same cross -- a Hungarian decision that moves the forint no more than a "
                  "Czech one does is CEE beta and not Hungarian policy",
        source_id=f"{SOURCE}:mnb", required_data=["MNB:base_rate"], horizon="intraday",
        hours=(11, 15), payload={"domain": "CEE-HU-A", "n_dates": len(mnb)})

    out["parts"]["cross_country_control"] = K.event_study(
        pack, ctx, name="cnb_dates_on_forint_control", symbols=("EURHUF",), dates=cnb,
        mechanism="cee_cross_country_policy_control", actor="control",
        constraint="the CNB's dates on the forint, where no Hungarian decision was taken",
        rationale="if the forint moves on Czech decision days as much as on its own, the "
                  "reaction is regional and neither bank is the actor",
        falsifier="n/a -- this arm is the control",
        source_id=f"{SOURCE}:cnb_control", required_data=[], horizon="intraday", hours=(12, 15),
        payload={"domain": "CEE-CZ-A", "control": True}, novelty=0.0, confidence=0.0)

    parts = list(out["parts"].values())
    out["outcome"] = K.OK if any(p.get("outcome") == K.OK for p in parts) else K.UNMEASURED
    out["discoveries"] = sum(int(p.get("discoveries") or 0) for p in parts)
    return out


def czk_floor_regime_break(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """CEE-CZ-B: the two declared koruna-floor dates, with the PRE-FLOOR window as the control.

    A regime break is only a measurement if the period before it is measured too. This miner
    therefore runs three samples on the same instrument: the two break days, a set of matched
    weekdays drawn from inside the commitment (where the distribution is truncated), and the
    same weekdays from before it. A tape that does not reach 2013 makes the historical arms
    UNMEASURED BY NAME -- which is a verdict about this box, not a finding about the koruna.
    """
    ctx.miner = ctx.miner or "czk_floor_regime_break"
    bars = ctx.bars("EURCZK", "H1")
    if bars is None:
        ctx.note("czk_floor_regime_break:bars:EURCZK", "no H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "czk_floor_regime_break",
                "why": "no EURCZK tape; the floor break cannot be measured here"}
    lo, hi = K.tape_span(bars)
    breaks = [d for d in (FLOOR_START, FLOOR_END) if lo <= d <= hi]
    inside = list(K.weekday_dates(max(lo, FLOOR_START), min(hi, FLOOR_END), 2))
    before = list(K.weekday_dates(lo, min(hi, FLOOR_START), 2))
    out: dict[str, Any] = {"miner": "czk_floor_regime_break", "parts": {},
                           "tape_span": [lo.isoformat(), hi.isoformat()],
                           "floor": [FLOOR_START.isoformat(), FLOOR_END.isoformat()]}
    if not breaks:
        ctx.note("czk_floor_regime_break:dates",
                 f"the tape runs {lo}..{hi} and neither declared break date falls inside it; "
                 f"the regime break is UNMEASURED on this box, not absent from the world")
    else:
        out["parts"]["break_days"] = K.event_study(
            pack, ctx, name="czk_floor_break_days", symbols=("EURCZK", "USDCZK"), dates=breaks,
            mechanism="cee_cz_exchange_rate_commitment_break",
            actor="the CNB's FX desk under the exchange-rate commitment",
            constraint="an unlimited one-sided offer to sell koruna at 27.00 while it stood, "
                       "and nothing at all the day after it was withdrawn",
            rationale="a truncated distribution releases three and a half years of suppressed "
                      "adjustment on the exit day",
            falsifier="the break days match the matched weekday control, which would mean the "
                      "commitment never bound",
            source_id=f"{SOURCE}:cnb_floor", required_data=["CNB:fx_intervention"],
            horizon="session", payload={"domain": "CEE-CZ-B", "declared_break": True})
    if inside:
        out["parts"]["inside_commitment"] = K.event_study(
            pack, ctx, name="czk_inside_commitment", symbols=("EURCZK",), dates=inside,
            mechanism="cee_cz_floored_distribution",
            actor="the CNB's FX desk", constraint="EUR/CZK could not trade below 27.00",
            rationale="the floored sample is the regime, measured on ordinary Wednesdays so "
                      "that no event is doing the work",
            falsifier="the floored Wednesdays are indistinguishable from the pre-floor ones",
            source_id=f"{SOURCE}:cnb_floor_inside", required_data=[], horizon="session",
            payload={"domain": "CEE-CZ-B", "sample": "inside"}, novelty=0.3, confidence=0.3)
    if before:
        out["parts"]["pre_floor_control"] = K.event_study(
            pack, ctx, name="czk_pre_floor_control", symbols=("EURCZK",), dates=before,
            mechanism="cee_cz_pre_floor_control", actor="control",
            constraint="the same weekday, before the commitment existed",
            rationale="the explicit pre-period the break is measured against",
            falsifier="n/a -- this arm is the control",
            source_id=f"{SOURCE}:cnb_pre_floor", required_data=[], horizon="session",
            payload={"domain": "CEE-CZ-B", "control": True}, novelty=0.0, confidence=0.0)
    else:
        ctx.note("czk_floor_regime_break:control",
                 "the tape does not reach 2013-11-07, so the pre-floor control sample is empty "
                 "and every reading inside the commitment is uncontrolled and says so")
    parts = list(out["parts"].values())
    out["outcome"] = K.OK if any(p.get("outcome") == K.OK for p in parts) else K.UNMEASURED
    out["discoveries"] = sum(int(p.get("discoveries") or 0) for p in parts)
    return out


def mnb_quick_tender_era(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """CEE-HU-B: the two-rate era measured against the SAME instrument outside it.

    From 2022-10-14 to 2023-09-26 the forint's effective policy rate was the one-day deposit
    quick tender at 18%, not the 13% base rate the Monetary Council voted on. The claim is that
    the reaction function changed shape, and the control that can falsify it is the same cross,
    the same broker and the same Council dates ELEVEN MONTHS EARLIER OR LATER. A peer country is
    the weaker control and is run beside it, never instead of it.
    """
    ctx.miner = ctx.miner or "mnb_quick_tender_era"
    mod = _pack_module()
    mnb = _days(mod.MNB["decision_dates"])
    in_era = [d for d in mnb if QUICK_TENDER_START <= d <= QUICK_TENDER_END]
    out_era = [d for d in mnb if not (QUICK_TENDER_START <= d <= QUICK_TENDER_END)]
    out: dict[str, Any] = {"miner": "mnb_quick_tender_era", "parts": {},
                           "era": [QUICK_TENDER_START.isoformat(), QUICK_TENDER_END.isoformat()],
                           "n_in_era": len(in_era), "n_out_era": len(out_era)}
    if in_era:
        out["parts"]["council_inside_era"] = K.event_study(
            pack, ctx, name="mnb_council_inside_quick_tender", symbols=("EURHUF", "CHFHUF"),
            dates=in_era, mechanism="cee_hu_two_rate_regime_council_reaction",
            actor="the MNB Monetary Council while the quick-tender desk set the effective rate",
            constraint="the base rate was held at 13% while the one-day deposit cleared at 18%",
            rationale="if the tender was the real instrument, the Council's own dates should "
                      "carry LESS reaction inside the era than outside it",
            falsifier="the Council dates react identically inside and outside the era, which "
                      "would mean the two-rate regime changed no reaction function at all",
            source_id=f"{SOURCE}:mnb_tender", required_data=["MNB:one_day_deposit"],
            horizon="intraday", hours=(11, 15),
            payload={"domain": "CEE-HU-B", "sample": "two_rate_era"})
    else:
        ctx.note("mnb_quick_tender_era:dates",
                 "no Monetary Council date in the pack's table falls inside the quick-tender "
                 "era; the era arm is UNMEASURED and the comparison cannot be made")
    if out_era:
        out["parts"]["council_outside_era"] = K.event_study(
            pack, ctx, name="mnb_council_outside_quick_tender", symbols=("EURHUF", "CHFHUF"),
            dates=out_era, mechanism="cee_hu_single_rate_council_reaction",
            actor="the MNB Monetary Council in a single-rate regime",
            constraint="the base rate is the only policy rate",
            rationale="the same country, the same cross and the same committee, with one rate "
                      "instead of two -- the cleanest control this pack owns",
            falsifier="n/a -- this arm is the control the era arm is measured against",
            source_id=f"{SOURCE}:mnb_single", required_data=["MNB:base_rate"],
            horizon="intraday", hours=(11, 15),
            payload={"domain": "CEE-HU-B", "sample": "single_rate"}, novelty=0.2,
            confidence=0.3)
    out["parts"]["tender_rate_lead"] = K.series_lead(
        pack, ctx, name="mnb_one_day_deposit_lead", series_name="MNB:one_day_deposit",
        symbols=("EURHUF", "CHFHUF"), mechanism="cee_hu_effective_rate_lead",
        actor="the MNB's one-day deposit quick-tender desk",
        constraint="the tender rate cleared forint overnight liquidity for eleven months",
        rationale="the GAP between the tender rate and the base rate is the regime; the forint "
                  "should track the effective rate and not the voted one",
        falsifier="the one-day deposit series carries no information for EURHUF beyond the base "
                  "rate over the same days",
        source_id=f"{SOURCE}:mnb_tender_series", horizon_days=3,
        payload={"domain": "CEE-HU-B"})
    out["parts"]["chf_legacy_lead"] = K.series_lead(
        pack, ctx, name="cee_chf_legacy_lead", series_name="ECB:chf_loan_stock",
        symbols=("CHFHUF",), mechanism="cee_xx_chf_mortgage_political_reflex",
        actor="the CHF-mortgage households and the banks that lent to them",
        constraint="household solvency is a political limit, so a franc move produces law",
        rationale="the residual franc exposure is the size of the reflex CHFHUF carries over "
                  "and above the EURCHF x EURHUF arithmetic",
        falsifier="CHFHUF carries no residual over the synthetic cross once the stock is "
                  "controlled for, in which case the reflex is a story",
        source_id=f"{SOURCE}:chf_stock", horizon_days=20, payload={"domain": "CEE-XX-A"})
    parts = list(out["parts"].values())
    out["outcome"] = K.OK if any(p.get("outcome") == K.OK for p in parts) else K.UNMEASURED
    out["discoveries"] = sum(int(p.get("discoveries") or 0) for p in parts)
    return out


def orthodox_vs_western_easter(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """CEE-XX-B: the divergence weeks, with the COINCIDING years as the placebo.

    Romania, Bulgaria and Serbia keep the Julian Easter; Czechia, Hungary, Croatia, Slovakia and
    Slovenia keep the Gregorian one. In a divergence year that produces weekdays on which three
    banking systems are shut and five are open, and the mirror image a week or five weeks away.
    In a coinciding year (2025) the Easter half of the sample vanishes -- which is the placebo,
    and it is arithmetic rather than a choice.
    """
    ctx.miner = ctx.miner or "orthodox_vs_western_easter"
    mod = _pack_module()
    bars = ctx.bars("EURHUF", "H1")
    if bars is None:
        ctx.note("orthodox_vs_western_easter:bars:EURHUF", "no H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "orthodox_vs_western_easter",
                "why": "no EURHUF tape"}
    lo, hi = K.tape_span(bars)
    years = range(lo.year, hi.year + 1)
    east: list[date] = []
    west: list[date] = []
    placebo_years: list[int] = []
    for year in years:
        if mod.easter_divergence_days(year) == 0:
            placebo_years.append(year)
        east += [d for d in mod.orthodox_only_days(year) if lo <= d <= hi]
        west += [d for d in mod.western_only_days(year) if lo <= d <= hi]
    out: dict[str, Any] = {"miner": "orthodox_vs_western_easter", "parts": {},
                           "n_orthodox_only": len(east), "n_western_only": len(west),
                           "coinciding_years": placebo_years}
    if east:
        out["parts"]["orthodox_only"] = K.event_study(
            pack, ctx, name="cee_orthodox_only_closures", symbols=("EURHUF", "EURCZK",
                                                                   "EUSTX50"),
            dates=east, mechanism="cee_xx_orthodox_closure_asymmetry",
            actor="the Romanian, Bulgarian and Serbian banking systems and their statutes",
            constraint="three of the eight jurisdictions here keep the Julian computus and are "
                       "shut on days the other five trade",
            rationale="a weekday on which part of the region's banking system is absent is a "
                      "liquidity event with a date knowable years ahead",
            falsifier="the orthodox-only weekdays match the matched weekday control, or match "
                      "the same seasonal position in a COINCIDING year where no asymmetry exists",
            source_id=f"{SOURCE}:orthodox_calendar",
            required_data=["orthodox_only_days"], horizon="session",
            payload={"domain": "CEE-XX-B", "rite": "orthodox"})
    if west:
        out["parts"]["western_only"] = K.event_study(
            pack, ctx, name="cee_western_only_closures", symbols=("EURHUF", "EURCZK"),
            dates=west, mechanism="cee_xx_western_closure_asymmetry",
            actor="the Czech, Hungarian, Croatian, Slovak and Slovene statutes",
            constraint="the mirror image of the same calendar split",
            rationale="both halves of an asymmetry must be run; one half alone is a one-sided "
                      "study that cannot tell a closure effect from a seasonal",
            falsifier="the western-only weekdays match the matched weekday control",
            source_id=f"{SOURCE}:western_calendar", required_data=["western_only_days"],
            horizon="session", payload={"domain": "CEE-XX-B", "rite": "western"})
    eves = [d for d in K.shift(east, -1) if lo <= d <= hi]
    if eves:
        out["parts"]["closure_eves"] = K.event_study(
            pack, ctx, name="cee_orthodox_closure_eves", symbols=("EURHUF",), dates=eves,
            mechanism="cee_xx_closure_eve_positioning",
            actor="the banks squaring before a national closure",
            constraint="a book that cannot be funded tomorrow is squared today",
            rationale="the eve of a one-country closure carries the squaring flow; the closure "
                      "day itself carries the absence",
            falsifier="the eves match the closure days themselves, which would mean the effect "
                      "is the week and not the closure",
            source_id=f"{SOURCE}:closure_eves", required_data=[], horizon="overnight",
            payload={"domain": "CEE-XX-B", "sample": "eve"}, novelty=0.4, confidence=0.35)
    if not placebo_years:
        ctx.note("orthodox_vs_western_easter:placebo",
                 f"the tape {lo}..{hi} contains no year in which the two Easters coincide, so "
                 f"the placebo arm is UNMEASURED; the next coinciding years are 2025 and 2028")
    parts = list(out["parts"].values())
    out["outcome"] = K.OK if any(p.get("outcome") == K.OK for p in parts) else K.UNMEASURED
    out["discoveries"] = sum(int(p.get("discoveries") or 0) for p in parts)
    return out


def transmission_seeds(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """The pack's transmission map as HYPOTHESIS discoveries -- the map the law grants a region
    before its tape has been read. The month-end fixing days are attached as the calendar the
    grain, gas and index edges actually settle against."""
    ctx.miner = ctx.miner or "transmission_seeds"
    mod = _pack_module()
    out: dict[str, Any] = K.seed_edges(pack, ctx, name="transmission_seeds",
                                       edges=mod.TRANSMISSION_EDGES_SEED,
                                       mechanism_prefix="cee_balkans_transmission",
                                       source_id=f"{SOURCE}:edges")
    bars = ctx.bars("EURHUF", "H1")
    if bars is None:
        ctx.note("transmission_seeds:bars:EURHUF", "no H1 tape; the month-end arm is UNMEASURED")
        return out
    lo, hi = K.tape_span(bars)
    month_ends = K.month_days(lo, hi, (28, 29, 30, 31))
    out["month_end_rebalance"] = K.event_study(
        pack, ctx, name="cee_month_end_fix", symbols=("EURHUF", "EURCZK"), dates=month_ends,
        mechanism="cee_month_end_index_rebalance",
        actor="the EM funds that rebalance the CEE crosses at the 16:00 London fix",
        constraint="the benchmark is struck on the last business day and the tracking error is "
                   "measured against it",
        rationale="the region's largest scheduled flow is a fixing flow, not a policy flow",
        falsifier="the month-end fixing window matches the same window on the fifteenth of the "
                  "month, which carries no rebalance",
        source_id=f"{SOURCE}:month_end", required_data=[], horizon="session", hours=(14, 17),
        payload={"domain": "CEE-HU-D", "n_month_ends": len(month_ends)},
        novelty=0.35, confidence=0.35)
    return out


MINERS: dict[str, Any] = {
    "cnb_mnb_decision_windows": cnb_mnb_decision_windows,
    "czk_floor_regime_break": czk_floor_regime_break,
    "mnb_quick_tender_era": mnb_quick_tender_era,
    "orthodox_vs_western_easter": orthodox_vs_western_easter,
    "transmission_seeds": transmission_seeds,
}
