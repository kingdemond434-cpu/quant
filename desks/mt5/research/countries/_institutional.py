"""THE INSTITUTIONAL SCHEMA EVERY COUNTRY PACK CARRIES (principal 2026-09-30 18:12Z: merge the
institutional-footprint civilization into the country packs and region commands; no separate
subsystem).

Every `countries/<code>/pack.py` ends with

    INSTITUTIONAL_FOOTPRINT = institutional_footprint(__name__)

which returns the SAME shape for every department: its jurisdiction, the ten roles it owes
(regulator, exchange, clearing house, central bank, treasury, custodian/settlement, fund filings,
short/position data, derivatives reports, physical market), the atlas rows it holds by canonical
id, one coverage status per frozen source class, and the classes it still owes an answer on.
The data is not typed into 74 files: the rows live in
`desks/mt5/data/source_rosters/institutional_footprint.yaml` and the measured statuses in
`desks/mt5/reports/INSTITUTIONAL_COVERAGE.json`; this function reads both. A pack whose atlas
slice is empty is not an error -- it is a column of UNSEARCHED cells, which is the frontier.

Never raises: a pack must import on a tree where the roster, the report or yaml is absent.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[2]
_ROSTER = _DESK / "data" / "source_rosters" / "institutional_footprint.yaml"
_REPORT = _DESK / "reports" / "INSTITUTIONAL_COVERAGE.json"
_ROWS_CACHE: dict[str, Any] = {"mtime": None, "rows": []}


def _ontology() -> Any:
    for name in ("research.countries.institutional.ontology", "countries.institutional.ontology"):
        try:
            return importlib.import_module(name)
        except ImportError:
            continue
    return None


def _rows() -> list[dict[str, Any]]:
    try:
        m = _ROSTER.stat().st_mtime_ns
    except OSError:
        return []
    if _ROWS_CACHE["mtime"] != m:
        try:
            import yaml
            doc = yaml.safe_load(_ROSTER.read_text("utf-8")) or {}
            _ROWS_CACHE["rows"] = [r for r in doc.get("sources") or [] if isinstance(r, dict)]
        except Exception:
            _ROWS_CACHE["rows"] = []
        _ROWS_CACHE["mtime"] = m
    return list(_ROWS_CACHE["rows"])


def pack_code(module_name: str) -> str:
    """`research.countries.us.pack` / `countries.us.pack` / `us` -> `us`."""
    parts = str(module_name).split(".")
    return parts[-2] if len(parts) >= 2 and parts[-1] == "pack" else parts[-1]


def institutional_footprint(module_name: str) -> dict[str, Any]:
    code = pack_code(module_name)
    onto = _ontology()
    if onto is None:
        return {"pack": code, "status": "UNMEASURED", "why": "the ontology is not importable"}
    jur = onto.JURISDICTION_OF_PACK.get(code, code)
    rows = [r for r in _rows() if str(r.get("jurisdiction")) == jur]
    try:
        grid = (json.loads(_REPORT.read_text("utf-8")).get("grid") or {}).get(jur) or {}
    except (OSError, ValueError):
        grid = {}
    by_class: dict[str, dict[str, Any]] = {}
    for cls in onto.CLASS_IDS:
        ids = [str(r["id"]) for r in rows if r.get("source_class") == cls]
        measured = grid.get(cls)
        if measured:
            st = str(measured)
        elif ids:
            st = "DISCOVERED_NOT_INGESTED"
        elif jur != "global" and cls in onto.GLOBAL_ONLY_CLASSES:
            st = "NOT_RELEVANT"
        else:
            st = onto.UNSEARCHED
        by_class[cls] = {"status": st, "sources": ids}
    roles = {role: [str(r["id"]) for r in rows if role in onto.roles_of(r)]
             for role in onto.JURISDICTION_ROLES}
    return {
        "pack": code, "jurisdiction": jur, "schema": "institutional_footprint/1",
        "sources": [str(r["id"]) for r in rows], "classes": by_class, "roles": roles,
        "role_gaps": sorted(k for k, v in roles.items() if not v),
        "open_classes": sorted(c for c, v in by_class.items()
                               if v["status"] not in onto.CLOSED_STATUSES),
        "status_source": "measured" if grid else "declared (no coverage report on this host)",
        "latent_states": [s["id"] for s in onto.LATENT_STATES],
    }
