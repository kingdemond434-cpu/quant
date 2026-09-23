"""BANGLADESH'S OWN MINERS -- the Thursday week-end, the circulars, the export print, the
gazetted holiday eves and the transmission map.

`MINERS` maps a name to `callable(pack, ctx) -> dict`, the contract `country_lab.run_lab` reads;
every `CUSTOM_MINERS` entry in the pack (`countries.bd.miners:<function>`) resolves here. Each
miner builds its own event dates from the pack's tables and hands them to the framework's event
study through the shared kit, so a Bangladeshi finding carries the same controls as every
other country's. Discoveries go through `ctx.record` and nowhere else.
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

from libs.research import country_lab as CL  # noqa: E402

SOURCE = "bd:pack"


def _pack_module() -> Any:
    try:
        from countries.bd import pack as mod
    except ImportError:
        spec = importlib.util.spec_from_file_location(
            "country_bd_pack", Path(__file__).resolve().parent / "pack.py")
        if spec is None or spec.loader is None:  # pragma: no cover
            raise
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


def bb_circular_windows(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """BD-A / BD-B: the statements, the repo circulars and the two regime announcements."""
    ctx.miner = ctx.miner or "bb_circular_windows"
    dates = [date.fromisoformat(d) for d in pack.central_bank.decision_dates]
    return K.event_study(
        pack, ctx, name="bb_circular_windows", symbols=("USDINR", "XAUUSD", "COTTON"),
        dates=dates, mechanism="bd_bangladesh_bank_circular_reaction",
        actor="Bangladesh Bank (the Governor and the monetary policy committee)",
        constraint="two statements a year and circulars with immediate effect; the taka is "
                   "absent, so the reaction is read on the regional cross, gold and cotton",
        rationale="a rate or regime circular in a crawling-peg economy reprices its stress "
                  "premium and the dollar supply its importers face",
        falsifier="the circular-day effect matches the eight nearest non-announcement banking "
                  "days or the RBI decision-day control",
        source_id=f"{SOURCE}:bb", required_data=["BB:repo_rate", "BB circular archive"],
        horizon="intraday", payload={"domain": "BD-A", "n_dates": len(dates),
                                     "regime_dates": ["2024-05-08", "2025-05-14"]})


def thursday_week_end(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """BD-K: the last trading day of the Sunday-Thursday week, against Friday as the placebo
    (the day the Bangladeshi market is closed while the global one is open)."""
    ctx.miner = ctx.miner or "thursday_week_end"
    bars = ctx.bars("XAUUSD", "H1")
    if bars is None:
        ctx.note("thursday_week_end:bars:XAUUSD", "no H1 tape on this box")
        return {"outcome": K.UNMEASURED, "miner": "thursday_week_end", "why": "no XAUUSD tape"}
    lo, hi = K.tape_span(bars)
    thursdays = K.weekday_dates(lo, hi, 3)
    fridays = K.weekday_dates(lo, hi, 4)
    main = K.event_study(
        pack, ctx, name="thursday_week_end", symbols=("XAUUSD", "USDINR"), dates=thursdays,
        mechanism="bd_thursday_week_end_liquidity",
        actor="the Bangladeshi banks and the DSE closing for the Friday-Saturday weekend",
        constraint="the week ends on Thursday 08:30 UTC; Friday is closed",
        rationale="the week-end squaring of a South Asian liquidity pool lands on Thursday "
                  "afternoon, not Friday; the Friday placebo tells the two apart",
        falsifier="the Thursday-afternoon window matches the Friday window on the same "
                  "instruments (the global weekend effect, not the Bangladeshi one)",
        source_id=f"{SOURCE}:weekend", required_data=["the holiday rule"], horizon="session",
        hours=(6, 9), payload={"domain": "BD-K", "weekend": "Friday-Saturday"})
    ctrl = K.event_study(
        pack, ctx, name="friday_placebo", symbols=("XAUUSD",), dates=fridays,
        mechanism="bd_friday_placebo", actor="placebo", constraint="none",
        rationale="Friday is the global week-end and the Bangladeshi closed day",
        falsifier="n/a", source_id=f"{SOURCE}:weekend_placebo", required_data=[],
        horizon="session", hours=(6, 9), payload={"domain": "BD-K", "placebo": True},
        novelty=0.0, confidence=0.0)
    main["placebo"] = {k: v for k, v in ctrl.items() if k != "readings"}
    return main


def export_print_and_cotton(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """BD-D / BD-E: the EPB release days on COTTON and the export/import series lead-lag."""
    ctx.miner = ctx.miner or "export_print_and_cotton"
    results: dict[str, Any] = {"miner": "export_print_and_cotton", "parts": {}}
    bars = ctx.bars("COTTON", "H1")
    if bars is not None:
        lo, hi = K.tape_span(bars)
        results["parts"]["epb_release_days"] = K.event_study(
            pack, ctx, name="epb_release_days", symbols=("COTTON", "EURUSD"),
            dates=K.month_days(lo, hi, (3, 4, 5)), mechanism="bd_epb_export_print_reaction",
            actor="the Export Promotion Bureau and the BGMEA", constraint="the print lands in "
                                                                          "the first week",
            rationale="the world's largest cotton importer's export figure sets the next "
                      "quarter's import need", falsifier="the release days match the same "
            "weekdays in non-release weeks", source_id=f"{SOURCE}:epb",
            required_data=["EPB:exports"], horizon="session", payload={"domain": "BD-D"})
    else:
        ctx.note("export_print_and_cotton:bars:COTTON", "no H1 tape on this box")
    results["parts"]["export_lead"] = K.series_lead(
        pack, ctx, name="epb_export_lead", series_name="EPB:exports", symbols=("COTTON",),
        mechanism="bd_export_print_cotton_lead", actor="BGMEA/BKMEA exporters",
        constraint="the buyers' order calendar", rationale="the export print leads the cotton "
        "import need by a quarter", falsifier="no information beyond US and EU retail sales",
        source_id=f"{SOURCE}:epb", horizon_days=20, payload={"domain": "BD-D"})
    results["parts"]["import_lead"] = K.series_lead(
        pack, ctx, name="usda_import_lead", series_name="USDA:bd_cotton_imports",
        symbols=("COTTON",), mechanism="bd_cotton_import_swing", actor="BTMA spinning mills",
        constraint="the LC regime", rationale="a revision to the largest importer's line is a "
        "demand step ICE reads", falsifier="revisions carry no information against the "
        "randomised-release null", source_id=f"{SOURCE}:usda", horizon_days=10,
        payload={"domain": "BD-E"})
    parts = results["parts"].values()
    results["outcome"] = K.OK if any(p.get("outcome") == K.OK for p in parts) else K.UNMEASURED
    results["discoveries"] = sum(int(p.get("discoveries") or 0) for p in parts)
    return results


def gazetted_holiday_eves(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """BD-K / BD-C: the eve of every GAZETTED closure; PROJECTED rows are the placebo."""
    ctx.miner = ctx.miner or "gazetted_holiday_eves"
    mod = _pack_module()
    gazetted: list[date] = []
    projected: list[date] = []
    for rows in mod.LUNAR_AND_RELIGIOUS.values():
        for day, _name, status in rows:
            (gazetted if status == "GAZETTED" else projected).append(day)
    out = K.event_study(
        pack, ctx, name="gazetted_holiday_eves", symbols=("XAUUSD", "USDINR"),
        dates=K.shift(gazetted, -1), mechanism="bd_gazetted_holiday_eve_liquidity",
        actor="the Cabinet Division's gazette and the banks it closes",
        constraint="only GAZETTED closures are the sample; projected rows are the placebo",
        rationale="the eve of a Bangladeshi bank closure carries the Eid cash and gold demand "
                  "and the loss of a South Asian liquidity pool the next day",
        falsifier="the gazetted eves match the projected-but-not-holiday eves or the matched "
                  "weekday control",
        source_id=f"{SOURCE}:gazette", required_data=["gazetted holiday rows"],
        horizon="overnight", payload={"domain": "BD-K", "n_gazetted": len(gazetted),
                                      "n_projected": len(projected)})
    out["projected_dates"] = [d.isoformat() for d in projected]
    return out


def transmission_seeds(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    ctx.miner = ctx.miner or "transmission_seeds"
    mod = _pack_module()
    return K.seed_edges(pack, ctx, name="transmission_seeds", edges=mod.TRANSMISSION_EDGES_SEED,
                        mechanism_prefix="bd_transmission", source_id=f"{SOURCE}:edges")


MINERS: dict[str, Any] = {
    "bb_circular_windows": bb_circular_windows,
    "thursday_week_end": thursday_week_end,
    "export_print_and_cotton": export_print_and_cotton,
    "gazetted_holiday_eves": gazetted_holiday_eves,
    "transmission_seeds": transmission_seeds,
}
