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


def _untestable_families(root: Path) -> dict[str, str]:
    """Families the gauntlet MEASURED as producing zero judgeable cells.

    THIS MIRRORS `miner_candidate_compiler.structurally_untestable_families()` AND MUST KEEP
    MIRRORING IT. The rule is that family's: the last sweep produced at least five verdicts for
    it and EVERY one was `unmeasured` -- built, and under the 60 trading days the gates need.

    It is re-derived rather than imported because this report runs on checkouts where the desk
    package is not importable, and because the compiler's copy resolves its own BASE path while
    this one must answer for an arbitrary root (the tests pass a tmp_path). That duplication is
    a real cost and it has already been paid once: the first version of this function keyed on
    the CELL ID and on `passed`, while the compiler keys on the `family` FIELD and on
    `unmeasured`. Same intent, different inputs, and it silently returned {} against a live
    report -- which is precisely the failure L0312 records about two implementations of one
    measurement. If the rule changes, change it in both, and the test below is what notices.
    """
    gate = _read(root / "desks" / "mt5" / "reports" / "universal_gates_external.json", {})
    per_fam: dict[str, list[int]] = {}
    for v in gate.get("verdicts", []) or []:
        if not isinstance(v, dict):
            continue
        fam = str(v.get("family") or "?")
        n_all, n_unm = per_fam.setdefault(fam, [0, 0])
        per_fam[fam] = [n_all + 1, n_unm + (1 if v.get("unmeasured") else 0)]
    return {fam: f"last sweep built {n} cell(s), judged 0 -- parameters need DEEPENING"
            for fam, (n, unm) in per_fam.items() if n >= 5 and unm == n}


def _conservation(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    desk = root / "desks" / "mt5"
    docket = _read(desk / "data" / "hypotheses" / "external_survivors.json", [])
    if isinstance(docket, dict):
        docket = docket.get("survivors", [])
    cells = {_cell_id(row): row for row in docket if isinstance(row, dict)}
    gate = _read(desk / "reports" / "universal_gates_external.json", {})
    verdicts = [row for row in gate.get("verdicts", []) if isinstance(row, dict)]
    by_cell = {str(row.get("cell")): row for row in verdicts if row.get("cell")}
    # A CELL ROUTED TO DEEPENING IS ACCOUNTED FOR, NOT LOST (fixed 2026-09-14).
    #
    # `lost` meant "the docket holds this cell and the gauntlet published no verdict for it", and
    # for most cells that is exactly right. But the compiler DELIBERATELY withholds whole families
    # from judgement: `structurally_untestable_families()` measures which families built cells and
    # judged none of them -- every cell under the 60 trading days the gates need -- and routes
    # them to the deepening queue instead. Its own docstring says "Routing them to the DEEPENING
    # queue is not a rejection: it is the statement that these parameterizations need widening
    # before any gate can rule".
    #
    # So the desk's most careful piece of routing arrived here as its most alarming number. All 13
    # reported lost were `lvc_asia_london` at one parameter hash across 13 symbols -- one family,
    # one parameterization, every instance. Random attrition does not look like that, and the
    # shape was the clue that nothing had been dropped at all.
    #
    # THE POINT IS NOT TO MAKE THE NUMBER ZERO. A cell withheld from judgement and a cell that
    # fell out of the ledger are different events that a conservation check exists to tell apart,
    # and they were rendering identically (WS-005). `deepening` is now its own bucket with its own
    # cells named, so `lost` means what it says: unaccounted, and still a hard failure at one.
    untestable = _untestable_families(root)
    # A CELL THE SWEEP HAS NOT REACHED YET IS PENDING, NOT LOST (fixed 2026-09-14).
    #
    # `lost` meant "in the docket, no verdict row", which silently counted every candidate the
    # hourly sweep had not got to. Measured tonight: docket 22,131 against 6,447 judged, so the
    # check reported 15,525 LOST -- a number that says nothing about conservation and everything
    # about throughput. It also grows every time the desk adds candidates, so proposing new work
    # made the provenance check look like it was haemorrhaging.
    #
    # `gauntlet_seen_cells.json` is the record that separates them: it holds every cell id this
    # desk has EVER judged. A cell in that set with no verdict row today was judged and its
    # verdict has gone -- that is a genuine conservation failure and still fails at one. A cell
    # never in it has simply not been built yet.
    #
    # THE POINT IS NOT A SMALLER NUMBER. It is that `lost` should mean "the ledger dropped
    # something" and nothing else, or the one alarm that would catch a real loss is permanently
    # swamped by the backlog.
    # THE CURRENT REPORT IS ONE SWEEP, NOT THE RECORD (second correction, 2026-09-14).
    #
    # `universal_gates_external.json` is OVERWRITTEN every sweep: it holds this hour's verdicts and
    # no history. So "in the docket, judged once, no verdict row today" describes almost every cell
    # the desk has ever ruled -- 14,698 of them -- and calling those LOST was the same mistake as
    # calling the backlog lost, one layer down.
    #
    # `gate_verdict_index.json` is the persistent per-cell record the gauntlet appends on change,
    # written precisely because the report was being thrown away once an hour. A cell there HAS a
    # standing verdict whether or not this hour re-judged it.
    #
    # LOST NOW MEANS WHAT IT SAYS: judged at some point (`gauntlet_seen_cells`) and holding no
    # verdict anywhere -- not in this sweep, not in the index. That is a record the ledger dropped,
    # and it is the only thing a conservation check should ever fail on.
    seen_doc = _read(desk / "data" / "hypotheses" / "gauntlet_seen_cells.json", {})
    seen = set(seen_doc) if isinstance(seen_doc, dict) else set(seen_doc or ())
    index_doc = _read(desk / "data" / "hypotheses" / "gate_verdict_index.json", {})
    indexed = set(index_doc) if isinstance(index_doc, dict) else set(index_doc or ())
    buckets: Counter[str] = Counter()
    lost: list[str] = []
    deepening: list[str] = []
    for cell in cells:
        row = by_cell.get(cell)
        if row is None:
            fam = cell.split(".")[1] if "." in cell else ""
            if fam in untestable:
                buckets["deepening"] += 1
                deepening.append(cell)
            elif cell in indexed:
                # A standing verdict exists in the persistent index; this sweep simply did not
                # re-judge it. Accounted for, and not re-tested every hour by design.
                buckets["rejected"] += 1
            elif cell in seen:
                buckets["lost"] += 1
                lost.append(cell)
            else:
                buckets["pending"] += 1
        elif row.get("passed") is True:
            buckets["tested"] += 1
        elif row.get("passed") is False:
            buckets["rejected"] += 1
        elif "DEFERRED" in str(row.get("downstream_status") or ""):
            buckets["queued"] += 1
        else:
            buckets["blocked"] += 1
    discovered = len(cells)
    accounted = sum(buckets[name] for name in
                    ("tested", "queued", "rejected", "blocked", "deepening", "pending"))
    return ({
        "formula": ("discovered = tested + queued + rejected + blocked + deepening + "
                    "pending; lost must equal zero"),
        "discovered": discovered,
        "tested": buckets["tested"],
        "queued": buckets["queued"],
        "rejected": buckets["rejected"],
        "blocked": buckets["blocked"],
        "accounted": accounted,
        "lost": buckets["lost"],
        "balanced": discovered == accounted and not lost,
        "lost_cells": lost[:100],
        "deepening": buckets["deepening"],
        "pending": buckets["pending"],
        "deepening_cells": deepening[:100],
        "deepening_families": untestable,
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
