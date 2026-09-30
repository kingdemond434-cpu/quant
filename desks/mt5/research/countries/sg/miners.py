"""Singapore's nine native miners.

Every function is the callable named by ``pack.CUSTOM_MINERS``. Price studies reuse the country
lab's matched controls; macro legs require PIT-certified series and say UNMEASURED when absent.
Nothing here grants a certificate or capital.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path
from typing import Any, Iterable

try:
    from countries import _miner_kit as K
except ImportError:
    path = Path(__file__).resolve().parents[1] / "_miner_kit.py"
    spec = importlib.util.spec_from_file_location("countries_miner_kit_sg", path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise
    K = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = K
    spec.loader.exec_module(K)

from libs.research import country_lab as CL
from research.countries.sg import pack as P

SOURCE = "sg:pack"


def _fold(name: str, parts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ok = any(row.get("outcome") == K.OK for row in parts.values())
    return {"miner": name, "outcome": K.OK if ok else K.UNMEASURED,
            "discoveries": sum(int(row.get("discoveries") or 0) for row in parts.values()),
            "parts": {key: {k: v for k, v in row.items() if k != "readings"}
                      for key, row in parts.items()},
            "why": "" if ok else "no arm carried a measurable study"}


def _dates(rows: Iterable[dict[str, Any]], predicate=lambda row: True) -> list[date]:
    return [date.fromisoformat(str(row["date"])) for row in rows if predicate(row)]


def _series(pack: CL.CountryPack, ctx: CL.LabCtx, *, name: str, candidates: tuple[str, ...],
            symbols: tuple[str, ...], mechanism: str, rationale: str, falsifier: str,
            horizon: int = 5) -> dict[str, Any]:
    selected = next((key for key in candidates if ctx.series(key) is not None), "")
    if not selected:
        for key in candidates:
            ctx.note(f"{name}:series", f"{key}: no PIT-certified acquired series")
        return {"miner": name, "outcome": K.UNMEASURED, "discoveries": 0,
                "why": "required PIT series absent", "required_series": list(candidates)}
    return K.series_lead(pack, ctx, name=name, series_name=selected, symbols=symbols,
                         mechanism=mechanism, actor="Singapore's forced institutional flows",
                         constraint="the input is usable only from its publication timestamp",
                         rationale=rationale, falsifier=falsifier, source_id=f"{SOURCE}:{name}",
                         horizon_days=horizon, payload={"domain": name, "series": selected})


def synthetic_neer(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """Calibrate the executable SGD basket against the official weekly S$NEER series."""
    return _series(
        pack, ctx, name="synthetic_neer",
        candidates=("MAS weekly S$NEER index", "S$NEER", "SG_NEER"),
        symbols=("USDSGD", "EURSGD", "GBPSGD", "AUDSGD", "NZDSGD", "CHFSGD", "SGDJPY"),
        mechanism="sg_synthetic_neer_calibration",
        rationale="MAS targets the trade-weighted basket, so common movement across SGD crosses "
                  "contains the latent policy state a single pair cannot identify",
        falsifier="a random-weight basket forecasts the official index as well as the SGD basket",
        horizon=5)


def mps_event_study(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    """Scheduled/off-cycle and slope/re-centring policy actions are never pooled."""
    groups = {
        "off_cycle": _dates(P.BAND_STATE, lambda r: "OFF-CYCLE" in str(r.get("action"))),
        "recentre": _dates(P.BAND_STATE, lambda r: "re-cent" in str(r.get("centre", "")).lower()),
        "slope_only": _dates(P.BAND_STATE, lambda r: "unchanged" not in str(r.get("slope", ""))
                             and "re-cent" not in str(r.get("centre", "")).lower()),
    }
    parts = {}
    for arm, days in groups.items():
        parts[arm] = K.event_study(
            pack, ctx, name=f"mps_{arm}", symbols=("USDSGD", "EURSGD", "SGDJPY", "AUDSGD"),
            dates=days, mechanism=f"sg_mps_{arm}", actor="Monetary Authority of Singapore",
            constraint=f"{arm} changes the S$NEER target, not a policy rate",
            rationale="a change to the basket's slope or centre reprices every SGD cross together",
            falsifier="USDHKD shows the same matched-date response, or only USDSGD moves",
            source_id=f"{SOURCE}:mps:{arm}", required_data=["MAS policy statement archive"],
            horizon="session", hours=(0, 10), payload={"domain": "SG-A", "arm": arm})
    return _fold("mps_event_study", parts)


def band_edge(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    return _series(
        pack, ctx, name="band_edge", candidates=("MAS weekly S$NEER index", "S$NEER", "SG_NEER"),
        symbols=("USDSGD", "AUDSGD", "GBPSGD"), mechanism="sg_neer_band_edge_reversion",
        rationale="MAS resists movements near the undisclosed band edge, creating asymmetric "
                  "basket reversion conditional on estimated position",
        falsifier="edge-state reversion is indistinguishable from middle-of-band reversion",
        horizon=10)


def regional_fixing(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    # The canonical calendar miner compares the declared 03:00 fixing window across own and
    # other currencies, including the USDSGD deliverable-currency placebo.
    out = CL.generic_calendar_settlement(pack, ctx)
    return {"miner": "regional_fixing", **out, "domain": "SG-F",
            "control": "USDSGD in the same window"}


def sgx_expiry(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    bars = ctx.bars("JPN225", "H1")
    if bars is None:
        ctx.note("sgx_expiry:bars:JPN225", "no H1 tape")
        return {"miner": "sgx_expiry", "outcome": K.UNMEASURED, "why": "no JPN225 tape"}
    lo, hi = K.tape_span(bars)
    dates = []
    for year in range(lo.year, hi.year + 1):
        for month in (3, 6, 9, 12):
            first = date(year, month, 1)
            day = first.replace(day=1 + ((4 - first.weekday()) % 7) + 7)  # second Friday
            if lo <= day <= hi:
                dates.append(day)
    return K.event_study(
        pack, ctx, name="sgx_nikkei_sq", symbols=("JPN225", "USDJPY"), dates=dates,
        mechanism="sg_sgx_nikkei_special_quotation", actor="SGX/Osaka index hedgers",
        constraint="the quarterly SQ uses constituent opening prices on the second Friday",
        rationale="the opening-price settlement concentrates hedge completion into one auction",
        falsifier="the third Friday shows the same effect", source_id=f"{SOURCE}:sgx_sq",
        required_data=["SGX Nikkei expiry calendar"], horizon="session", hours=(0, 4),
        payload={"domain": "SG-G", "placebo": "third Friday"})


def moc_window(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    readings = []
    for symbol in ("XBRUSD", "XTIUSD"):
        bars = ctx.bars(symbol, "M15") or ctx.bars(symbol, "H1")
        if bars is None:
            ctx.note(f"moc_window:bars:{symbol}", "no M15 or H1 tape")
            continue
        row = CL.window_effect(bars, "08:00", "08:30", eras=CL.era_masks(pack, CL.bar_days(bars)))
        row["symbol"] = symbol
        readings.append(row)
    measured = [row for row in readings if row.get("verdict") == "MEASURED"]
    return {"miner": "moc_window", "outcome": K.OK if measured else K.UNMEASURED,
            "discoveries": 0, "measured": len(measured), "readings": measured,
            "control": "the two adjacent half-hours", "domain": "SG-H",
            "why": "" if measured else "no oil tape measured the window"}


def nodx_nowcast(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    return _series(
        pack, ctx, name="nodx_nowcast",
        candidates=("Singapore non-oil domestic exports (NODX)", "SG_NODX", "NODX"),
        symbols=("USDSGD", "USDKRW", "USDCNH", "AUDUSD"), mechanism="sg_nodx_trade_nowcast",
        rationale="electronics NODX is an early monthly read on the Asian trade cycle",
        falsifier="Korean 20-day exports absorb the signal or Chinese-New-Year timing explains it",
        horizon=20)


def reserve_intervention(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    return _series(
        pack, ctx, name="reserve_intervention",
        candidates=("MAS official foreign reserves", "SG_RESERVES", "official reserves"),
        symbols=("USDSGD", "SGDJPY", "USDX"), mechanism="sg_reserve_intervention_flow",
        rationale="reserve changes net of valuation proxy intervention used to hold the FX band",
        falsifier="the valuation-only counterfactual explains the full reserve change",
        horizon=20)


def holiday_liquidity(pack: CL.CountryPack, ctx: CL.LabCtx) -> dict[str, Any]:
    out = CL.generic_holiday_liquidity(pack, ctx)
    return {"miner": "holiday_liquidity", **out, "domain": "SG-K",
            "saturday_exception": "gazetted Saturday holidays create no market closure"}


MINERS = {
    "synthetic_neer": synthetic_neer, "mps_event_study": mps_event_study,
    "band_edge": band_edge, "regional_fixing": regional_fixing, "sgx_expiry": sgx_expiry,
    "moc_window": moc_window, "nodx_nowcast": nodx_nowcast,
    "reserve_intervention": reserve_intervention, "holiday_liquidity": holiday_liquidity,
}
