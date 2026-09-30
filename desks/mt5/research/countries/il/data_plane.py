"""ISRAEL DATA PLANE -- the Bank of Israel's documented SDMX API, which needs no key.

Built on the Middle East lane base in `countries.sa.data_plane`. What is Israeli here: an SDMX-JSON
reader (structure and data are separate, observations are addressed by INDEX, and the envelope
moved between 1.0 and 2.0), period ends for SDMX time periods, the key -> series attribution that
drops what it cannot place, and the institutional hedge-gain state that refuses to report on one
leg.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from typing import Any

from countries._declared_data_plane import declared_lanes
from countries._declared_data_plane import report_path as _report_path
from countries.sa import data_plane as _me
from countries.sa.data_plane import (
    MIN_N,
    CatalogueRow,
    MenaLane,
    Observation,
    level_state,
    month_end,
    observe,
)

CODE = "il"
REPORT = _report_path(CODE)
DECLARED = declared_lanes(CODE)

#: DECLARED SDMX v2 data root; verified=False until it returns bytes on this box
_BOI_SDMX = "https://edge.boi.gov.il/FusionEdgeServer/sdmx/v2/data/dataflow/BOI.STATISTICS"


# ------------------------------------------------------------------------------ SDMX-JSON
def _structure(data: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """1.0 puts the structure at `data.structure`; 2.0 at `data.structures[0]`."""
    got = data.get("structure")
    if isinstance(got, Mapping):
        return got
    many = data.get("structures")
    if isinstance(many, list) and many and isinstance(many[0], Mapping):
        return many[0]
    return None


def _ids(dims: Any) -> list[tuple[str, list[str]]]:
    out: list[tuple[str, list[str]]] = []
    for dim in dims if isinstance(dims, list) else []:
        if not isinstance(dim, Mapping):
            continue
        values = [str(v.get("id") if isinstance(v, Mapping) else v)
                  for v in (dim.get("values") or [])]
        out.append((str(dim.get("id") or ""), values))
    return out


def _index(key: str) -> list[int] | None:
    try:
        return [int(part) for part in str(key).split(":")]
    except ValueError:
        return None


def _number(cell: Any) -> float | None:
    raw = cell[0] if isinstance(cell, list) and cell else cell
    if raw is None or isinstance(raw, bool | list | dict):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def parse_sdmx_json(payload: Any) -> list[dict[str, Any]]:
    """[{"key": {dim: value}, "period": ..., "value": ...}], or `[]` for any unreadable envelope.

    Handles the series-keyed layout (`dataSets[0].series["0:1"].observations["3"]`) and the flat
    AllDimensions layout (`dataSets[0].observations["0:1:3"]`) under both envelopes.
    """
    if not isinstance(payload, Mapping):
        return []
    data = payload.get("data") if isinstance(payload.get("data"), Mapping) else payload
    structure = _structure(data)
    sets = data.get("dataSets")
    if structure is None or not isinstance(sets, list) or not sets:
        return []
    dims = structure.get("dimensions") if isinstance(structure, Mapping) else None
    if not isinstance(dims, Mapping):
        return []
    series_dims = _ids(dims.get("series"))
    obs_dims = _ids(dims.get("observation"))
    time_pos = next((i for i, (name, _) in enumerate(obs_dims)
                     if name.upper() in ("TIME_PERIOD", "TIME")), len(obs_dims) - 1)
    rows: list[dict[str, Any]] = []

    def resolve(dims_: list[tuple[str, list[str]]], idx: list[int]) -> dict[str, str] | None:
        if len(idx) != len(dims_):
            return None
        out: dict[str, str] = {}
        for (name, values), i in zip(dims_, idx, strict=True):
            if not 0 <= i < len(values):
                return None
            out[name] = values[i]
        return out

    for ds in sets:
        if not isinstance(ds, Mapping):
            continue
        for skey, block in (ds.get("series") or {}).items():
            sidx = _index(skey)
            key = resolve(series_dims, sidx) if sidx is not None else None
            if key is None or not isinstance(block, Mapping):
                continue
            observations = block.get("observations") or {}
            for okey in sorted(observations, key=lambda k: _index(k) or [0]):
                oidx = _index(okey)
                obs = resolve(obs_dims, oidx) if oidx is not None else None
                value = _number(observations[okey])
                if obs is None or value is None or not obs_dims:
                    continue
                period = obs[obs_dims[time_pos][0]]
                rows.append({"key": dict(key), "period": period, "value": value})
        flat = ds.get("observations")
        if isinstance(flat, Mapping) and not series_dims:
            for okey in sorted(flat, key=lambda k: _index(k) or [0]):
                oidx = _index(okey)
                obs = resolve(obs_dims, oidx) if oidx is not None else None
                value = _number(flat[okey])
                if obs is None or value is None:
                    continue
                name = obs_dims[time_pos][0]
                period = obs.pop(name)
                rows.append({"key": obs, "period": period, "value": value})
    return rows


def sdmx_period_end(period: Any) -> date | None:
    """The LAST day an SDMX time period describes: joining a month to its first day is a
    look-ahead. Day, month (YYYY-MM), quarter (YYYY-Qn), half (YYYY-Sn) and year."""
    text = str(period or "").strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return date.fromisoformat(text)
        if m := re.fullmatch(r"(\d{4})-(\d{2})", text):
            return month_end(int(m.group(1)), int(m.group(2)))
        if m := re.fullmatch(r"(\d{4})-?Q([1-4])", text):
            return month_end(int(m.group(1)), 3 * int(m.group(2)))
        if m := re.fullmatch(r"(\d{4})-?S([12])", text):
            return month_end(int(m.group(1)), 6 * int(m.group(2)))
        if re.fullmatch(r"\d{4}", text):
            return date(int(text), 12, 31)
    except ValueError:
        return None
    return None


# ------------------------------------------------------------------------------ the lane
class BoiLane(MenaLane):
    """The Bank of Israel. Its SDMX API is documented and KEYLESS -- a fact, not a gap."""

    LANE = "boi"
    COUNTRY = "il"
    KEY = ""
    CATALOGUE = (
        CatalogueRow("boi_exchange_rates", "Bank of Israel",
                     "representative exchange rates of the shekel", "daily", "none once fixed",
                     "free, public (Bank of Israel terms)", "1990-01",
                     "the SDMX v2 data endpoint with format=sdmx-json; the representative rate is "
                     "fixed about 15:15 Israel time", 0.2,
                     url=f"{_BOI_SDMX}/EXR/1.0?format=sdmx-json",
                     series=("usdils_representative", "eurils_representative"),
                     aliases=(("usdils_representative", ("ILS_USD", "USD_ILS", "USD",
                                                         "RER_USD_ILS")),
                              ("eurils_representative", ("ILS_EUR", "EUR_ILS", "EUR",
                                                         "RER_EUR_ILS")))),
        CatalogueRow("boi_interest_rates", "Bank of Israel",
                     "the Bank of Israel policy rate", "per decision",
                     "none; a decision is a fact", "free, public (Bank of Israel terms)",
                     "1994-01",
                     "the SDMX rate dataflow for the series and the decision page for the "
                     "announcement time", 0.0, url=f"{_BOI_SDMX}/IR/1.0?format=sdmx-json",
                     series=("boi_policy_rate",),
                     aliases=(("boi_policy_rate", ("BOI_RATE", "MNT_RIB_BOI_D")),)),
        CatalogueRow("boi_reserves", "Bank of Israel", "foreign-exchange reserves (USD)",
                     "monthly", "minor", "free, public (Bank of Israel terms)", "1990-01",
                     "the SDMX reserves dataflow; a reserve change is only interpretable beside "
                     "the Bank's own FX purchases", 7.0,
                     url=f"{_BOI_SDMX}/RES/1.0?format=sdmx-json", series=("fx_reserves_usd",)),
        CatalogueRow("boi_institutional_exposure", "Bank of Israel",
                     "institutional investors' foreign-asset pool and its FX hedge ratio",
                     "monthly", "revised with the next release; vintages kept",
                     "free, public (Bank of Israel terms)", "2010-01",
                     "the Bank's statistics pages and the Capital Market Authority's portfolio "
                     "data", 45.0, url=f"{_BOI_SDMX}/INST/1.0?format=sdmx-json",
                     series=("institutional_hedge_ratio", "institutional_foreign_assets_ils"),
                     vintage="provisional",
                     aliases=(("institutional_hedge_ratio", ("HEDGE_RATIO",)),
                              ("institutional_foreign_assets_ils", ("FOREIGN_ASSETS",)))),
    )

    def series_name(self, key: Mapping[str, Any], row: CatalogueRow) -> str | None:
        """The declared series an SDMX key belongs to, or None. With two or more declared series
        an unknown key is DROPPED -- a wrong attribution is worse than a missing point."""
        codes = {str(v) for v in key.values()}
        for name, aliases in row.aliases:
            if codes & set(aliases):
                return name
        return row.series[0] if len(row.series) == 1 else None

    def parse(self, row: CatalogueRow, payload: Any) -> list[Observation]:
        out: list[Observation] = []
        for rec in parse_sdmx_json(payload):
            name = self.series_name(rec["key"], row)
            day = sdmx_period_end(rec["period"])
            if name is None or day is None:
                continue
            out.append(observe(name, rec["value"], day, lag_days=row.publication_lag_days,
                               vintage=row.vintage, source_id=f"{self.LANE}:{row.dataset_id}",
                               meta={"sdmx_key": dict(rec["key"])}))
        return out

    def hedge_gain_state(self) -> dict[str, Any]:
        """The shekel channel's GAIN: the foreign-asset pool times its hedge ratio. BOTH legs or
        UNMEASURED -- one leg is never a gain of one."""
        ratio = self.known("institutional_hedge_ratio")
        pool = self.known("institutional_foreign_assets_ils")
        missing = [name for name, got in (("institutional_hedge_ratio", ratio),
                                          ("institutional_foreign_assets_ils", pool)) if not got]
        base = {"lane": self.LANE, "name": "hedge_gain_state", "label": "hedge_gain",
                "series": "institutional_foreign_assets_ils * institutional_hedge_ratio / 100"}
        if missing:
            return {**base, "state": _me.UNMEASURED, "missing": missing, "n": 0, "gain": None,
                    "why": f"UNMEASURED: the channel is not conditionable without both legs; "
                           f"missing {', '.join(missing)}"}
        periods = sorted(set(ratio) & set(pool))
        gains = [pool[p] * ratio[p] / 100.0 for p in periods]
        state = level_state(gains, label="hedge_gain", up="HIGH", down="LOW", min_n=MIN_N)
        return {**base, **state, "missing": [], "gain": gains[-1] if gains else None,
                "as_of_period": periods[-1] if periods else None}

    def states(self) -> list[dict[str, Any]]:
        return [self.hedge_gain_state()]


LANES: tuple[type[MenaLane], ...] = (BoiLane,)


def run(**kwargs: Any) -> dict[str, Any]:
    """The Israeli lane through the shared Middle East pass; the miner's registry and report win."""
    kwargs["registry"] = kwargs.get("registry") or LANES
    kwargs["report_default"] = kwargs.get("report_default") or REPORT
    return _me.run(**kwargs)
