"""THE GEOINT FACTORY'S DOOR TO THE DESK'S SENSOR ORGANS: ledger rows and cells, failing closed.

The world sensor's organs -- `libs.research.sensor_contract` (SensorObservation, SensorLedger),
`libs.research.sensor_engines` (write_lake_series, emit_conditioner_cells) and
`libs.data.terms_hold` (the allow-list) -- are the ONE contract and the ONE cell door. This module
does not re-implement any of them. It shapes the factory's numbers into their inputs and calls
them; when an organ is not importable on the running branch (they arrive with the world-sensor
stack, #204/#211, which the live branch did not carry on 2026-10-13), the door reports
ORGAN_ABSENT and does nothing else:

  * observations are still built in the contract's shape and carried in the factory's report,
    so nothing measured is lost, but no ledger row is claimed;
  * NO cell is emitted: the terms gate is the only thing that may clear a source, and a gate that
    cannot be consulted holds (the same rule `terms_hold._fence` applies to its own fence).

Every value is PIT: `event_time` is the acquisition instant, `knowable_at` the S3 LastModified of
the scene's item JSON (``knowable_basis = printed_stamp``) or, when that stamp is absent, the
acquisition plus the DECLARED latency (``declared_lag``); `received_at` is when this desk read it.
"""
from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from typing import Any

UNMEASURED = "UNMEASURED"
SENSOR_ID = "geoint:sentinel2_l2a:tank_fill"
SOURCE_ID = "geoint:sentinel2_l2a"
DATA_SOURCE = "geoint:sentinel2_l2a+mt5:bars"
LICENCE = ("Copernicus Sentinel data (ESA), free, full and open; read from the AWS Open Data "
           "bucket sentinel-cogs (Element 84). Terms basis: desks/mt5/data/terms_clearances.json "
           "key geoint:sentinel2_l2a")


def _organ(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name == name:
            return None
        raise


def observation_row(*, entity: str, metric: str, value: float, event_time: str,
                    knowable_at: str, knowable_basis: str, received_at: str,
                    uncertainty: float | None, raw_pointer: str,
                    attributes: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """One observation in the contract's field names (built through `make` when it exists)."""
    kw: dict[str, Any] = {
        "sensor_id": SENSOR_ID, "source_id": SOURCE_ID, "metric": metric, "entity": entity,
        "dataset_id": "sentinel-2-l2a-cogs", "kind": "state", "sensor_class": "geoint",
        "geography": "US-OK:Cushing", "asset_domain": "crude_oil", "value": value,
        "unit": "fill_fraction_index", "event_time": event_time,
        "publication_time": knowable_at if knowable_basis == "printed_stamp" else UNMEASURED,
        "source_publication_time": (knowable_at if knowable_basis == "printed_stamp"
                                    else UNMEASURED),
        "knowable_at": knowable_at, "knowable_basis": knowable_basis,
        "received_at": received_at, "parse_complete_at": received_at,
        "measurement_uncertainty": uncertainty, "licence": LICENCE,
        "commercial_rights": "Copernicus free, full and open (see terms basis)",
        "raw_pointer": raw_pointer, "attributes": dict(attributes or {})}
    sc = _organ("libs.research.sensor_contract")
    if sc is None:
        return {**kw, "authority": "NONE", "schema": "sensor_observation/1",
                "contract": "ORGAN_ABSENT"}
    obs = sc.make(**kw)
    row = dict(obs.to_row())
    bad = sc.defects(obs)
    row["contract"] = "DEFECTIVE: " + "; ".join(bad) if bad else "ADMITTED"
    return row


def append_ledger(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Append admitted rows to the SensorLedger; ORGAN_ABSENT when the ledger is not here."""
    sc = _organ("libs.research.sensor_contract")
    if sc is None:
        return {"status": "ORGAN_ABSENT", "appended": 0, "rows": len(rows),
                "why": "libs.research.sensor_contract is not on this branch: rows are carried in "
                       "the report, no ledger write is claimed"}
    admitted = [sc.from_row(r) for r in rows if r.get("contract") == "ADMITTED"]
    if not admitted:
        return {"status": "NOTHING_ADMITTED", "appended": 0, "rows": len(rows)}
    try:
        res = sc.SensorLedger().append(admitted)
    except Exception as exc:   # the ledger's own refusal is reported, never swallowed as zero
        return {"status": "ERROR", "appended": 0, "rows": len(rows),
                "why": f"{type(exc).__name__}: {str(exc)[:160]}"}
    return {"status": "APPENDED", "rows": len(rows), "admitted": len(admitted),
            "result": res if isinstance(res, (dict, int, str)) else str(res)[:200]}


def terms(data_source: str = DATA_SOURCE) -> tuple[bool, str]:
    """The terms gate's answer for the source, failing closed when the gate is absent."""
    th = _organ("libs.data.terms_hold")
    if th is None:
        return False, ("HELD_TERMS: libs.data.terms_hold is not on this branch -- a gate that "
                       "cannot be consulted holds every source")
    ok, why = th.gauntlet_terms(data_source)
    return bool(ok), str(why)


def emit_cells(series_id: str, lake_rows: Sequence[Mapping[str, Any]], signals: Sequence[str],
               symbols: Sequence[str], *, judge: bool, judge_why: str, mechanism: str,
               falsifier: str, generator: str = "geoint_tank_fill", dry_run: bool = False,
               data_source: str = DATA_SOURCE) -> dict[str, Any]:
    """Write the lake series and enqueue conditioner cells -- only through the organs, only when
    the ceiling licenses judging AND the terms gate clears the source."""
    ok, why = terms(data_source)
    base = {"series_id": series_id, "data_source": data_source, "signals": list(signals),
            "symbols": list(symbols), "terms_ok": ok, "terms_why": why,
            "ceiling_judge": judge, "ceiling_why": judge_why}
    if not ok:
        return {**base, "status": "HELD_TERMS", "emitted": 0, "created": 0}
    se = _organ("libs.research.sensor_engines")
    if se is None:
        return {**base, "status": "ORGAN_ABSENT", "emitted": 0, "created": 0,
                "why": "libs.research.sensor_engines is not on this branch"}
    if not judge:
        return {**base, "status": "WITHHELD_CEILING", "emitted": 0, "created": 0}
    lake = se.write_lake_series(series_id, list(lake_rows))
    if lake.get("status") != "WRITTEN":
        return {**base, "status": "NO_LAKE_SERIES", "lake": lake, "emitted": 0, "created": 0}
    res = se.emit_conditioner_cells(series_id, list(signals), list(symbols), mechanism=mechanism,
                                    falsifier=falsifier, generator=generator, dry_run=dry_run,
                                    data_source=data_source)
    return {**base, "status": res.get("status") or "EMITTED", "lake": lake, **res}


__all__ = ["DATA_SOURCE", "LICENCE", "SENSOR_ID", "SOURCE_ID", "append_ledger", "emit_cells",
           "observation_row", "terms"]
