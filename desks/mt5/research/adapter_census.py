#!/usr/bin/env python3
"""ADAPTER CENSUS -- one row per federated adapter: what class of work it does, through which
contract, on which clock, how many cells it donated, how many of those were judged, or the
measured reason it cannot work here (hourly leg `adapter_census`).

WHY (audit 2026-11-13). Twenty-five of ~141 adapters only checked that a package imported and fed
no cell, and nothing measured that: the sandbox roster said "runs here" for a probe that donated
nothing. This census is the measurement, and it fails loud in its own report -- an adapter that
still only probes is listed under `probe_only` by name, which is a defect (III.16), never a
quiet row.

CLASSES
    a  data source       a DataHub contract (libs/data/datahub_adapters.py) on a clock; cells
                         are counted by the lake series their params name
    b  research engine   a hypothesis generator donating through the sandbox runner (cells are
                         the registry candidates whose generator is `sandbox:<system>`), or an
                         independent verifier whose work is a report (lean, nautilus ->
                         reports/ENGINE_REPLICAS.json)
    c  cannot work here  a measured VERDICT_REASON (licence, terms, uninstallable, non-MT5)

An adapter module declares its class with CENSUS_CLASS (and CONTRACTS, CLOCK, VERDICT_REASON,
ROLE); one that declares nothing is derived from what it does -- a numpy rebuild
(RUNS_WITHOUT_LIBRARY) or a library engine is class b on the sandbox runner's clock, a module
whose packet carries only an `api_probe` is PROBE_ONLY. Absent artifacts are UNMEASURED, never
zero (L1.28a). Published reasons are exception TYPE NAMES only.

ARTIFACT `reports/ADAPTER_CENSUS.json`.

    python desks/mt5/research/adapter_census.py --once
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import json
import logging
import os
import pkgutil
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_LOG = logging.getLogger(__name__)

OUT = DESK / "reports" / "ADAPTER_CENSUS.json"
SANDBOX_REPORT = DESK / "reports" / "SANDBOX_RUNNER.json"
FREE_STACK_YIELD = DESK / "reports" / "FREE_STACK_YIELD.json"
ADAPTER_DATA = DESK / "reports" / "ADAPTER_DATA.json"
ENGINE_REPLICAS = DESK / "reports" / "ENGINE_REPLICAS.json"
REGISTRY = ROOT / "data" / "alpha_registry.sqlite"
UNMEASURED = "UNMEASURED"
SANDBOX_CLOCK = "hourly_cycle:sandbox_runner"
CLASSES = {"a": "data_source", "b": "research_engine", "c": "cannot_work_here"}


def _json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def adapter_rows() -> list[dict[str, Any]]:
    """Every adapter module's declared (or derived) registry row."""
    from libs.research import adapters as A
    rows = []
    for info in sorted(pkgutil.iter_modules(A.__path__), key=lambda i: i.name):
        if info.name.startswith("_"):
            continue
        try:
            m = importlib.import_module(f"{A.__name__}.{info.name}")
        except Exception as exc:  # noqa: BLE001
            rows.append({"name": info.name, "class": UNMEASURED,
                         "reason": f"adapter import failed: {type(exc).__name__}"})
            continue
        try:
            src = inspect.getsource(m)
        except (OSError, TypeError):
            src = ""
        declared = str(getattr(m, "CENSUS_CLASS", "") or "")
        rebuilt = bool(getattr(m, "RUNS_WITHOUT_LIBRARY", False))
        probe_only = ("api_probe(" in src and not rebuilt and not declared)
        spec = A.SPECS.get(str(getattr(m, "SYSTEM", info.name)))
        note = spec.note if spec else ""
        if declared:
            cls = declared
        elif probe_only:
            cls = "PROBE_ONLY"
        elif "REJECTED_WITH_EVIDENCE" in note and not rebuilt:
            cls = "c"
        else:
            cls = "b"
        reason = str(getattr(m, "VERDICT_REASON", "") or "")
        if cls == "c" and not reason:
            reason = note or "declared cannot-work without a reason"
        rows.append({
            "name": str(getattr(m, "SYSTEM", info.name)), "module": info.name,
            "class": cls, "class_name": CLASSES.get(cls, cls),
            "capability_family": str(getattr(m, "CAPABILITY_FAMILY", "")),
            "role": str(getattr(m, "ROLE", "") or ("REBUILT method (numpy, in-process)"
                                                    if rebuilt else "")),
            "contracts": list(getattr(m, "CONTRACTS", ()) or ()),
            "clock": str(getattr(m, "CLOCK", "") or (SANDBOX_CLOCK if cls == "b" else "")),
            "rebuilt_in_process": rebuilt,
            "generator": str(getattr(m, "ROUTED_TO", "") or
                             f"sandbox:{getattr(m, 'SYSTEM', info.name)}"),
            "reason": reason,
        })
    return rows


def registry_counts(path: Path = REGISTRY, series: tuple[str, ...] = ()) -> dict[str, Any]:
    """Cells per generator and per lake series: donated, judged, survived. Read-only."""
    if not path.exists():
        return {"status": UNMEASURED, "why": "registry absent on this host"}
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=20)
    except sqlite3.Error as exc:
        return {"status": UNMEASURED, "why": type(exc).__name__}
    out: dict[str, Any] = {"status": "MEASURED", "by_generator": {}, "by_series": {}}
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(research_candidates)")}
        judged = "judged_at IS NOT NULL" if "judged_at" in cols else "0"
        surv = "COALESCE(survived, 0) = 1" if "survived" in cols else "0"
        if "generator" in cols:
            q = (f"SELECT generator, COUNT(*), SUM({judged}), SUM({surv}) FROM "
                 "research_candidates WHERE generator LIKE 'sandbox:%' OR generator = "
                 "'adapter_data' GROUP BY generator")
            for g, n, j, s in con.execute(q):
                out["by_generator"][str(g)] = {"cells": int(n or 0), "judged": int(j or 0),
                                               "survived": int(s or 0)}
        for sid in series:
            like = f'%"source": "{sid}%'
            n, j, s = con.execute(
                f"SELECT COUNT(*), SUM({judged}), SUM({surv}) FROM research_candidates "
                "WHERE params_json LIKE ?", (like,)).fetchone()
            out["by_series"][sid] = {"cells": int(n or 0), "judged": int(j or 0),
                                     "survived": int(s or 0)}
    except sqlite3.Error as exc:
        return {"status": UNMEASURED, "why": type(exc).__name__}
    finally:
        con.close()
    return out


def _data_status(name: str, contracts: list[str]) -> dict[str, Any]:
    """The collector's own measurement of a data adapter's feed."""
    from libs.data.datahub_adapters import CONTRACTS
    rows = [c for c in CONTRACTS if c.name in contracts]
    out: dict[str, Any] = {}
    fsy = _json(FREE_STACK_YIELD)
    ad = _json(ADAPTER_DATA)
    for c in rows:
        if c.yield_source:
            per = ((fsy or {}).get("per_source") or {}).get(c.yield_source) \
                if isinstance(fsy, dict) else None
            out[c.name] = ({"feed_status": per.get("status"), "obs_total": per.get("obs_total"),
                            "last_success": per.get("last_success")}
                           if isinstance(per, dict) else {"feed_status": UNMEASURED})
        else:
            acc = (ad or {}).get("access") if isinstance(ad, dict) else None
            out[c.name] = ({"feed_status": acc.get("status"),
                            "series": (ad or {}).get("series")}
                           if isinstance(acc, dict) else {"feed_status": UNMEASURED})
    return out


def build(registry_path: Path = REGISTRY) -> dict[str, Any]:
    from libs.data.datahub_adapters import CONTRACTS
    rows = adapter_rows()
    series = tuple(c.series for c in CONTRACTS)
    counts = registry_counts(registry_path, series)
    sbr = _json(SANDBOX_REPORT)
    roi = (sbr or {}).get("roi") if isinstance(sbr, dict) else None
    er = _json(ENGINE_REPLICAS)
    by_contract = {c.name: c for c in CONTRACTS}
    for r in rows:
        name = r["name"]
        cells: Any = UNMEASURED
        if counts.get("status") == "MEASURED":
            if r["class"] == "a":
                agg = {"cells": 0, "judged": 0, "survived": 0}
                for cn in r["contracts"]:
                    c = by_contract.get(cn)
                    got = counts["by_series"].get(c.series) if c else None
                    for k in agg:
                        agg[k] += int((got or {}).get(k, 0))
                if "oecd.cli" in r["contracts"]:
                    got = counts["by_generator"].get("adapter_data") or {}
                    agg = {k: max(agg[k], int(got.get(k, 0))) for k in agg}
                cells = agg
            else:
                cells = counts["by_generator"].get(str(r.get("generator")),
                                                   {"cells": 0, "judged": 0, "survived": 0})
        r["cells_donated"] = cells["cells"] if isinstance(cells, dict) else UNMEASURED
        r["judged"] = cells["judged"] if isinstance(cells, dict) else UNMEASURED
        r["survived"] = cells["survived"] if isinstance(cells, dict) else UNMEASURED
        last = (roi or {}).get(name) if isinstance(roi, dict) else None
        r["sandbox_last_status"] = (last or {}).get("last_status") or UNMEASURED
        if r["class"] == "a":
            r["feed"] = _data_status(name, r["contracts"])
        if name in ("lean", "nautilus"):
            eng = {"lean": "lean_gap", "nautilus": "nautilus_path"}[name]
            e = ((er or {}).get("engines") or {}).get(eng) if isinstance(er, dict) else None
            r["verifier"] = ({"certificates": e.get("certificates"),
                              "total_delta_sum_r": e.get("total_delta_sum_r"),
                              "flattered_by_contract": e.get("flattered_by_contract")}
                             if isinstance(e, dict) else UNMEASURED)
    by_class: dict[str, int] = {}
    for r in rows:
        by_class[r["class"]] = by_class.get(r["class"], 0) + 1
    probe_only = sorted(r["name"] for r in rows if r["class"] == "PROBE_ONLY")
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "n_adapters": len(rows), "by_class": by_class,
        "probe_only": probe_only,
        "status": "DEFECT" if probe_only else "MEASURED",
        "registry": {k: v for k, v in counts.items() if k in ("status", "why")},
        "classes": CLASSES,
        "rows": rows,
        "rule": ("every adapter does real work (a contract on a clock, or donated cells) or "
                 "carries a measured reason; an import probe that does neither is a DEFECT and "
                 "is named in probe_only"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.parse_args(argv)
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    try:
        os.replace(tmp, OUT)
    except PermissionError:
        OUT.unlink(missing_ok=True)
        os.replace(tmp, OUT)
    print(json.dumps({"n": doc["n_adapters"], "by_class": doc["by_class"],
                      "probe_only": doc["probe_only"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
