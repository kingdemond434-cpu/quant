"""THE BLACK SEA PACK'S OWN MINERS -- the eight clocks the generic set cannot know.

`MINERS` maps a name to `callable(pack, ctx) -> dict`, the contract `country_lab.run_lab` reads
for a pack directory's `miners.py`, and every entry in the pack's `CUSTOM_MINERS`
(`countries.black_sea.miners:<function>`) resolves to a function here, so the two registrations
are one set. Each miner builds ITS OWN event dates from the pack's tables -- the eight Black Sea
Grain Initiative announcements, the five corridor regimes, the five import-ban events, the two
hryvnia switch dates, the four published basket eras, the potash route closure and the two
national holiday calendars -- and hands them to the framework's event study through the shared
kit, so a Ukrainian or Belarusian finding carries the same matched-weekday control, randomised-
date null and adjacent-day placebo as every other country's. Discoveries go through `ctx.record`
and nowhere else.

TWO THINGS THESE MINERS REFUSE TO DO. They never pool two corridor regimes or two hryvnia eras
into one sample -- a fixed exchange rate is not a price and a negotiated corridor is not a
defended one. And they never compile a cell on the LICENSED potash or FOB assessments: those are
registered `machine_use_allowed=false` in the pack and the crops and the published tonnage are
what is actually measured.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, date, datetime, timedelta
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

SOURCE = "black_sea:pack"


def _pack_module() -> Any:
    try:
        from countries.black_sea import pack as mod  # type: ignore[import-not-found]
    except ImportError:
        spec = importlib.util.spec_from_file_location(
            "country_black_sea_pack", Path(__file__).resolve().parent / "pack.py")
        if spec is None or spec.loader is None:  # pragma: no cover
            raise
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


def bsgi_event_windows(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """UA-A: the eight dated Black Sea Grain Initiative announcements, intraday, on the three
    crops the corridor actually moved. Eight events is a small sample and the payload says so
    rather than padding it with days on which nothing was announced."""
    ctx.miner = ctx.miner or "bsgi_event_windows"
    mod = _pack_module()
    dates = mod.bsgi_event_dates("SETTLED")
    main: dict[str, Any] = K.event_study(
        pack, ctx, name="bsgi_event_windows", symbols=("WHEAT", "CORN", "SOYBEAN"),
        dates=dates, mechanism="black_sea_bsgi_announcement",
        actor="the Joint Coordination Centre and the four participating parties",
        constraint="unanimity -- any party could halt the corridor and one did; the Initiative "
                   "ran on 120-day and then 60-day terms and ended on 2023-07-17",
        rationale="an announced halt to the only corridor moving roughly 33 mt of grain is an "
                  "immediate, unambiguous supply shock with a known minute; a resumption is the "
                  "same shock with the sign reversed",
        falsifier="the announcement windows carry no abnormal WHEAT or CORN move beyond the "
                  "matched weekday-plus-hour control, which would be a major negative result "
                  "because these are the best-dated grain-supply announcements of the decade",
        source_id=f"{SOURCE}:jcc", required_data=["JCC:vessel_table", "BSGI_EVENTS"],
        horizon="intraday", hours=(12, 18),
        payload={"domain": "UA-A", "n_dates": len(dates),
                 "sample_note": "EIGHT EVENTS. Small by construction and reported, never "
                                "padded; each one is unambiguous, timestamped and unrepeatable"})
    ctrl: dict[str, Any] = K.event_study(
        pack, ctx, name="bsgi_event_control", symbols=("WHEAT", "CORN"),
        dates=K.shift(dates, 364), mechanism="black_sea_bsgi_matched_control",
        actor="control", constraint="none",
        rationale="the same weekdays one year away, when no Initiative announcement landed",
        falsifier="n/a", source_id=f"{SOURCE}:jcc_control", required_data=[],
        horizon="intraday", hours=(12, 18),
        payload={"domain": "UA-A", "control": True}, novelty=0.0, confidence=0.0)
    main["matched_control"] = {k: v for k, v in ctrl.items() if k != "readings"}
    return main


def corridor_regime_split(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """UA-B and XX-A: each declared corridor regime measured against the others on the same two
    instruments. The country is its own control across its own route changes, which is the only
    control a single-corridor mechanism can honestly have."""
    ctx.miner = ctx.miner or "corridor_regime_split"
    mod = _pack_module()
    boundaries = [lo for lo, _hi, name, _why in mod.CORRIDOR_ERAS if name != "PREWAR"]
    got: dict[str, Any] = K.event_study(
        pack, ctx, name="corridor_regime_split", symbols=("WHEAT", "CORN"),
        dates=boundaries, mechanism="black_sea_corridor_regime_break",
        actor="the Ukrainian Navy, the ports authority and the war-risk market",
        constraint="the route is physical: a regime change is a change in which vessels can "
                   "lawfully and insurably sail, not a change in price expectations",
        rationale="four dated route changes in eighteen months, each of which altered the "
                  "physical export capacity of a tenth of the world wheat trade",
        falsifier="the regime boundaries are indistinguishable from the matched weekday control "
                  "and from the Romanian export pace over the same weeks",
        source_id=f"{SOURCE}:corridor",
        required_data=["CORRIDOR_ERAS", "MINAGRO:export_tonnage", "USPA:throughput"],
        horizon="multi_day", hours=None,
        payload={"domain": "UA-B", "n_regimes": len(mod.CORRIDOR_ERAS),
                 "regimes": [name for _lo, _hi, name, _why in mod.CORRIDOR_ERAS],
                 "never_pooled": "a negotiated corridor and a defended one are different "
                                 "physical regimes that happen to move the same cargo"})
    return got


def import_ban_events(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """UA-C: the five dated 2023 neighbour-ban and EU-restriction events. The prediction is an
    intra-EU BASIS effect, so the zloty pair is run beside the crops and carries the test."""
    ctx.miner = ctx.miner or "import_ban_events"
    mod = _pack_module()
    dates = mod.import_ban_dates()
    got: dict[str, Any] = K.event_study(
        pack, ctx, name="import_ban_events", symbols=("WHEAT", "CORN", "EURPLN"),
        dates=dates, mechanism="black_sea_import_ban_redirection",
        actor="the European Commission and the five frontline member states",
        constraint="farmer politics against single-market rules; a national ban can precede the "
                   "EU act by about a fortnight and can outlive it",
        rationale="closing five land markets to the same tonnage REDIRECTS rather than destroys "
                  "it, so the effect is an intra-EU basis and a CEE political-risk event before "
                  "it is a flat-price one",
        falsifier="the ban announcement windows carry no abnormal EURPLN behaviour and no "
                  "measurable redirection in the DG AGRI weekly licence data",
        source_id=f"{SOURCE}:bans",
        required_data=["IMPORT_BAN_EVENTS", "DGAGRI:cereals_dashboard"],
        horizon="multi_day", hours=None,
        payload={"domain": "UA-C", "n_dates": len(dates),
                 "evidence_label": "PRESS_REPORTED",
                 "promotion_block": "every row is PRESS_REPORTED and carries no act number, so "
                                    "this miner may mint hypotheses and nothing compiled on it "
                                    "is promoted until an Official Journal citation is attached"})
    return got


def uah_regime_break(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """UA-D: the two hryvnia switch dates as regime breaks on the Polish crosses and the euro.

    The FIXED eras are declared untradable as volatility samples and the payload says which
    windows those are, so a downstream study refuses them rather than averaging a constant.
    """
    ctx.miner = ctx.miner or "uah_regime_break"
    mod = _pack_module()
    switches = [lo for lo, _hi, name, _rate in mod.UAH_ERAS if name != "FLOATING_MANAGED"]
    fixed = [(lo.isoformat(), hi.isoformat(), name, rate)
             for lo, hi, name, rate in mod.UAH_ERAS if rate is not None]
    got: dict[str, Any] = K.event_study(
        pack, ctx, name="uah_regime_break", symbols=("EURPLN", "USDPLN", "EURUSD"),
        dates=switches, mechanism="black_sea_uah_regime_break",
        actor="the Board of the National Bank of Ukraine",
        constraint="reserves that are a function of external disbursements rather than exports, "
                   "and capital controls that cannot be lifted without testing the rate",
        rationale="Poland carries Ukrainian risk in its currency more than any other quoted "
                  "market, so a Ukrainian exchange-rate regime break is a zloty event when it "
                  "cannot be a hryvnia one",
        falsifier="the switch dates carry no abnormal EURPLN move beyond the NBP's own calendar "
                  "and the global risk tape",
        source_id=f"{SOURCE}:nbu", required_data=["UAH_ERAS", "NBU:kurs"],
        horizon="multi_day", hours=None,
        payload={"domain": "UA-D", "n_switches": len(switches), "fixed_eras": fixed,
                 "refusal": "a fixed number is not a price: any volatility or beta computed on "
                            "the official hryvnia series inside a FIXED era measures the fix"})
    return got


def byn_basket_residual(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """BY-D: the published-basket era boundaries on the rouble legs the basket itself names.

    The arithmetic basket-implied move is the part the NBRB already announced; the interesting
    object is what is left over, and this miner reports the declared weights so the residual can
    be computed by whoever holds the BYN series rather than re-estimated from prices.
    """
    ctx.miner = ctx.miner or "byn_basket_residual"
    mod = _pack_module()
    boundaries = [lo for lo, _hi, _w, _st in mod.BASKET_ERAS][1:]
    weights = [{"from": lo.isoformat(), "to": hi.isoformat(), "weights": w, "status": st}
               for lo, hi, w, st in mod.BASKET_ERAS]
    got: dict[str, Any] = K.event_study(
        pack, ctx, name="byn_basket_residual", symbols=("USDRUB", "EURRUB"),
        dates=boundaries, mechanism="black_sea_byn_basket_recomposition",
        actor="the Board of the National Bank of the Republic of Belarus",
        constraint="a basket whose largest published weight is the rouble, which ties "
                   "Belarusian monetary conditions to Russian ones by announced arithmetic",
        rationale="the weights are PUBLISHED, so the implied rouble beta is arithmetic and a "
                  "recomposition is a dated change to a known coefficient rather than an "
                  "inferred break",
        falsifier="the basket residual carries no information about the following days' USDRUB "
                  "path, in which case the NBRB is a pure follower and the pack records it",
        source_id=f"{SOURCE}:nbrb",
        required_data=["BASKET_ERAS", "NBRB:kurs_kosh", "NBRB:basket_weights"],
        horizon="multi_day", hours=None,
        payload={"domain": "BY-D", "declared_weights": weights,
                 "implied_rub_beta_today": mod.implied_rub_beta(datetime.now(tz=UTC).date()),
                 "note": "the rare case where a managed currency's coefficients are published; "
                         "most such studies begin by estimating what this bank announces"})
    return got


def potash_route_break(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """BY-A and BY-B: the dated potash measures and the Lithuanian transit termination, run on
    the crops whose acreage economics the nutrient cost reaches. An INPUT claim on a one-to-two
    quarter horizon -- never a claim that Minsk moves Chicago."""
    ctx.miner = ctx.miner or "potash_route_break"
    dates = [date(2021, 6, 24), date(2021, 8, 9), date(2021, 12, 8), date(2022, 2, 1),
             date(2022, 4, 1)]
    got: dict[str, Any] = K.event_study(
        pack, ctx, name="potash_route_break", symbols=("CORN", "WHEAT", "SOYBEAN"),
        dates=dates, mechanism="black_sea_potash_route_closure",
        actor="Belaruskali, the Belarusian Potash Company and Belarusian Railway",
        constraint="the farmer's affordability, not the producer's cost; a potash mine cannot "
                   "be idled cheaply, so the constraint is the ROUTE and not the output",
        rationale="removing roughly a fifth of world potash supply from its normal route raises "
                  "the delivered nutrient cost, and an unaffordable nutrient cuts applied rates "
                  "and shifts acreage toward the crops that need less of it",
        falsifier="seasons with a large potash-affordability move show no change in USDA's "
                  "applied-rate or acreage estimates, which breaks the mechanism at its first "
                  "link",
        source_id=f"{SOURCE}:potash",
        required_data=["BELSTAT:trade", "COMTRADE:mirror", "USDA PSD applied rates"],
        horizon="multi_day", hours=None,
        payload={"domain": "BY-A", "n_dates": len(dates),
                 "direction": "INPUT cost into the NEXT crop's acreage, declared",
                 "licensed_absence": "the potash assessment itself is machine_use_allowed=false "
                                     "and is never fetched; tonnage and the crops carry the test",
                 "other_nutrient_control": "phosphate affordability over the same seasons, "
                                           "which is the `ma` pack's ground"})
    return got


def calendar_asymmetry(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """XX-C: the days exactly ONE of the two countries is closed, with the joint closures run as
    the placebo. Both halves of the asymmetry are measured -- a Ukrainian-only closure and a
    Belarusian-only closure are different objects and the pack refuses to average them."""
    ctx.miner = ctx.miner or "calendar_asymmetry"
    mod = _pack_module()
    years = tuple(int(y) for y in mod.HOLIDAYS_RULE["years"])
    span = tuple(range(min(years) - 4, max(years) + 1))
    asym = [d for y in span for d in mod.asymmetric_closure_days(y) if d.weekday() < 5]
    joint = [d for y in span for d in mod.joint_closure_days(y) if d.weekday() < 5]
    main: dict[str, Any] = K.event_study(
        pack, ctx, name="calendar_asymmetry", symbols=("EURPLN", "EURUSD", "USDRUB"),
        dates=asym, mechanism="black_sea_asymmetric_closure",
        actor="the Verkhovna Rada and the Belarusian Council of Ministers",
        constraint="Ukraine rewrote its statutory calendar in 2023 and Belarus did not, so the "
                   "two countries' closed days now coincide far less than they did",
        rationale="a day on which exactly one of the two stops reporting and trading is a day "
                  "half this plane's physical data stops, which is a liquidity and information "
                  "effect with no price cause at all",
        falsifier="asymmetric closure days are indistinguishable from the same weekday in the "
                  "adjacent weeks, in which case the calendar carries no measurable "
                  "microstructure and the pack records that",
        source_id=f"{SOURCE}:calendar",
        required_data=["market_holidays", "asymmetric_closure_days"],
        horizon="session", hours=(7, 12),
        payload={"domain": "XX-C", "n_asymmetric": len(asym), "n_joint": len(joint),
                 "calendar_break": "Law No. 3258-IX of 2023-07-14"})
    ctrl: dict[str, Any] = K.event_study(
        pack, ctx, name="calendar_joint_placebo", symbols=("EURPLN", "EURUSD"),
        dates=joint, mechanism="black_sea_joint_closure_placebo",
        actor="control", constraint="none",
        rationale="the days BOTH countries are closed, which since 2023 are very few",
        falsifier="n/a", source_id=f"{SOURCE}:calendar_placebo", required_data=[],
        horizon="session", hours=(7, 12),
        payload={"domain": "XX-C", "control": True}, novelty=0.0, confidence=0.0)
    main["joint_placebo"] = {k: v for k, v in ctrl.items() if k != "readings"}
    return main


def transmission_seeds(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """The pack's transmission map as HYPOTHESIS discoveries -- the map the law grants a region
    before its tape has been read (LAWS 5n)."""
    ctx.miner = ctx.miner or "transmission_seeds"
    mod = _pack_module()
    seeded: dict[str, Any] = K.seed_edges(
        pack, ctx, name="transmission_seeds", edges=mod.TRANSMISSION_EDGES_SEED,
        mechanism_prefix="black_sea_transmission", source_id=f"{SOURCE}:edges")
    return seeded


def clock_divergence_window(start: date, end: date) -> list[date]:
    """Every weekday inside [start, end] on which Kyiv and Minsk sit on DIFFERENT UTC offsets.

    Exposed here because it is the sample a session-microstructure study needs and because it is
    cheap to get wrong: Kyiv keeps EU summer time and Minsk has been fixed UTC+3 since 2014.
    """
    mod = _pack_module()
    out: list[date] = []
    day = start
    while day <= end:
        if day.weekday() < 5 and mod.utc_offset_hours("ua", day) != mod.utc_offset_hours("by",
                                                                                         day):
            out.append(day)
        day += timedelta(days=1)
    return out


MINERS: dict[str, Any] = {
    "bsgi_event_windows": bsgi_event_windows,
    "corridor_regime_split": corridor_regime_split,
    "import_ban_events": import_ban_events,
    "uah_regime_break": uah_regime_break,
    "byn_basket_residual": byn_basket_residual,
    "potash_route_break": potash_route_break,
    "calendar_asymmetry": calendar_asymmetry,
    "transmission_seeds": transmission_seeds,
}
