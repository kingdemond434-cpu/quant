#!/usr/bin/env python3
"""Prove nightly candidate conservation, SLAs, forward truth, and research efficiency.

This is an observer.  It never changes a verdict, certificate, clock, allocation, or order.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = ROOT / "data" / "intelligence" / "midnight_morning_report.json"
TERMINAL = ("RETIRED", "KILL", "QUARANTIN", "DEAD", "REJECT", "PROMOTED")
QUEUE_SLA = timedelta(days=1)
CERT_SLA = timedelta(days=1)


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     delete=False) as handle:
        json.dump(value, handle, indent=1, sort_keys=True, default=str)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _stamp(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _cell_id(row: dict[str, Any]) -> str:
    """The judge's own identity, imported rather than restated -- see reconcile_external_queue.

    A report that names cells by its own spelling reports on cells that do not exist. This one
    tracked `frontier_identity` correctly and would still have missed the chart: a docket row's
    `timeframe` is what tells an M5 cell from the H1 cell of the same symbol and family.
    """
    from desks.mt5.research.frontier_identity import cell_id as _canonical
    return _canonical({"sym": str(row.get("symbol") or row.get("sym") or ""),
                       "family": str(row.get("family") or ""),
                       "timeframe": row.get("timeframe"),
                       "params": dict(row.get("params") or {})})


def _forward_rows(root: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    shadow = root / "desks" / "mt5" / "reports" / "shadow"
    for path in shadow.glob("*shadow_state.json"):
        doc = _read(path, {})
        if not isinstance(doc, dict):
            continue
        candidates = list(doc.items())
        if isinstance(doc.get("sleeves"), dict):
            candidates.extend(doc["sleeves"].items())
        for key, row in candidates:
            if isinstance(row, dict) and "status" in row:
                rows[str(key)] = {**row, "_ledger": path.name}
    return rows


def _failure_clusters(verdicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters: dict[str, list[str]] = defaultdict(list)
    for row in verdicts:
        stages = row.get("stages") or {}
        failed = [name for name, result in stages.items()
                  if isinstance(result, dict) and result.get("passed") is not True]
        cause = failed[0] if failed else str(row.get("downstream_status") or "UNCLASSIFIED")
        if row.get("passed") is not True:
            clusters[cause].append(str(row.get("cell") or "UNKNOWN"))
    return [{"cause": cause, "count": len(cells), "sample_cells": cells[:10]}
            for cause, cells in sorted(clusters.items(), key=lambda item: -len(item[1]))]


def _conservation(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    desk = root / "desks" / "mt5"
    docket = _read(desk / "data" / "hypotheses" / "external_survivors.json", [])
    if isinstance(docket, dict):
        docket = docket.get("survivors", [])
    cells = {_cell_id(row): row for row in docket if isinstance(row, dict)}
    gate = _read(desk / "reports" / "universal_gates_external.json", {})
    verdicts = [row for row in gate.get("verdicts", []) if isinstance(row, dict)]
    by_cell = {str(row.get("cell")): row for row in verdicts if row.get("cell")}
    buckets: Counter[str] = Counter()
    lost: list[str] = []
    for cell in cells:
        row = by_cell.get(cell)
        if row is None:
            buckets["lost"] += 1
            lost.append(cell)
        elif row.get("passed") is True:
            buckets["tested"] += 1
        elif row.get("passed") is False:
            buckets["rejected"] += 1
        elif "DEFERRED" in str(row.get("downstream_status") or ""):
            buckets["queued"] += 1
        else:
            buckets["blocked"] += 1
    discovered = len(cells)
    accounted = sum(buckets[name] for name in ("tested", "queued", "rejected", "blocked"))
    return ({
        "formula": "discovered = tested + queued + rejected + blocked; lost must equal zero",
        "discovered": discovered,
        "tested": buckets["tested"],
        "queued": buckets["queued"],
        "rejected": buckets["rejected"],
        "blocked": buckets["blocked"],
        "accounted": accounted,
        "lost": buckets["lost"],
        "balanced": discovered == accounted and not lost,
        "lost_cells": lost[:100],
        "resumable_deferred": int(gate.get("n_cells_deferred_build_budget") or 0),
        "cell_checkpoint": "content-addressed external_gauntlet series cache by cell+data-day",
    }, verdicts)


def _sla(root: Path, now: datetime, forwards: dict[str, dict[str, Any]]) -> dict[str, Any]:
    desk = root / "desks" / "mt5"
    queue = _read(desk / "data" / "research_queue.json", [])
    queue_rows: list[dict[str, Any]] = []
    active_status = {"PENDING", "QUEUED_CANONICAL_GAUNTLET", "AWAITING_CANONICAL_GAUNTLET"}
    for row in queue if isinstance(queue, list) else []:
        if not isinstance(row, dict) or str(row.get("status") or "") not in active_status:
            continue
        created = _stamp(row.get("created_at"))
        deadline = created + QUEUE_SLA if created else None
        overdue = deadline is None or now > deadline
        queue_rows.append({"id": row.get("id"), "status": row.get("status"),
                           "deadline_at": deadline, "overdue": overdue,
                           "route": row.get("route")})

    cert_doc = _read(desk / "reports" / "UNIVERSAL_SURVIVORS.json", {})
    certs = cert_doc.get("survivors", {}) if isinstance(cert_doc, dict) else {}
    forward_ids: set[str] = set(forwards)
    for row in forwards.values():
        forward_ids.update(str(row.get(name)) for name in ("certificate", "cell") if row.get(name))
        spec = row.get("shadow_spec") or {}
        if isinstance(spec, dict) and spec.get("certificate"):
            forward_ids.add(str(spec["certificate"]))
    cert_rows: list[dict[str, Any]] = []
    for key, row in certs.items() if isinstance(certs, dict) else []:
        gated = _stamp(row.get("gated_at"))
        deadline = gated + CERT_SLA if gated else None
        cell = str(row.get("cell") or "")
        enrolled = str(key) in forward_ids or cell in forward_ids
        cert_rows.append({"certificate": key, "cell": cell, "enrolled": enrolled,
                          "deadline_at": deadline,
                          "overdue": not enrolled and (deadline is None or now > deadline)})
    return {
        "policy": "queued candidates and certificates have a 24h maximum waiting-room SLA",
        "queue_active": len(queue_rows),
        "queue_overdue": sum(bool(row["overdue"]) for row in queue_rows),
        "queue_overdue_rows": [row for row in queue_rows if row["overdue"]][:100],
        "certificates": len(cert_rows),
        "certificates_not_enrolled": sum(not row["enrolled"] for row in cert_rows),
        "certificates_overdue": sum(bool(row["overdue"]) for row in cert_rows),
        "certificate_overdue_rows": [row for row in cert_rows if row["overdue"]][:100],
    }


def _forward_truth(forwards: dict[str, dict[str, Any]], now: datetime) -> dict[str, Any]:
    active = {key: row for key, row in forwards.items()
              if not str(row.get("status") or "").upper().startswith(TERMINAL)}
    native, proxy, stale, unmeasured = [], [], [], []
    for key, row in active.items():
        source = str(row.get("bar_source") or row.get("source") or "")
        last = _stamp(row.get("last_source_bar") or row.get("last_attempt_at")
                      or row.get("updated_at"))
        if row.get("bar_source_stale") is True or last is None or now - last > timedelta(hours=3):
            stale.append(key)
        if "fusion" in source.casefold() or "mt5" in source.casefold():
            native.append(key)
        elif source:
            proxy.append(key)
        else:
            unmeasured.append(key)
    return {
        "active_clocks": len(active),
        "fusion_native": len(native),
        "proxy": len(proxy),
        "source_unmeasured": len(unmeasured),
        "stale": len(stale),
        "stale_keys": stale[:100],
        "rule": ("proxy or stale evidence may accumulate diagnostically but cannot become "
                 "native proof"),
    }


def build(root: Path = ROOT, completion: dict[str, Any] | None = None,
          now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    completion = completion or _read(root / "data" / "intelligence"
                                     / "midnight_completion.json", {})
    conservation, verdicts = _conservation(root)
    forwards = _forward_rows(root)
    stages = completion.get("stages", []) if isinstance(completion, dict) else []
    cpu_hours = sum(float(row.get("cpu_seconds") or 0.0) for row in stages) / 3600.0
    before = completion.get("before", {}) if isinstance(completion, dict) else {}
    after = completion.get("after", {}) if isinstance(completion, dict) else {}
    delta = int(after.get("universal_certificates") or 0) - int(
        before.get("universal_certificates") or 0
    )
    portfolio = _read(root / "desks" / "mt5" / "reports" / "portfolio_evidence.json", {})
    report = {
        "schema_version": 1,
        "generated_at": now.isoformat(),
        "headline": {
            "candidates_discovered": conservation["discovered"],
            "candidates_lost": conservation["lost"],
            "certificates_added": delta,
            "forward_clocks": len(forwards),
            "hard_failures": completion.get("hard_failures", []),
        },
        "candidate_conservation": conservation,
        "sla": _sla(root, now, forwards),
        "rerouting": {
            "canonical_lane": "quant-external-pipeline.service",
            "stalled_cells": conservation["queued"] + conservation["lost"],
            "policy": ("restart the same canonical service while deferred work decreases; "
                       "escalate no-progress or missing-data cells by root cause"),
        },
        "forward_truth": _forward_truth(forwards, now),
        "mechanism_independence": portfolio or {
            "status": "UNMEASURED", "why": "portfolio_evidence has not run"
        },
        "compute_efficiency": {
            "measured_cpu_hours": round(cpu_hours, 6),
            "certificates_added": delta,
            "certificates_per_cpu_hour": (round(delta / cpu_hours, 6) if cpu_hours > 0 else None),
            "stage_rows": [{key: row.get(key) for key in
                            ("name", "cpu_seconds", "certificate_delta", "duration_seconds")}
                           for row in stages],
            "allocation_rule": ("unfinished canonical cells first; among discretionary research "
                                "organs prefer measured certificate yield per CPU-hour"),
        },
        "failure_root_causes": _failure_clusters(verdicts),
        "resource_execution": completion.get("resource_execution", {}),
        "authority": ("REPORT ONLY: no gate, certificate, allocation, promotion, sizing, or "
                      "order authority"),
    }
    _atomic(root / OUT.relative_to(ROOT), report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    report = build(args.root.resolve())
    print(json.dumps(report["headline"], indent=1))
    return 1 if report["candidate_conservation"]["lost"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
