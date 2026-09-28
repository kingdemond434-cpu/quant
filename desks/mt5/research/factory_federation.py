"""Factory-surface acquisition, reconstruction, synthesis and handoff under one existing clock.

The external-federation hourly leg calls this organ.  It does not crawl around terms, execute
unknown code, judge alpha, or create a second registry.  Public/authorized acquisitions arrive in
``data/factory_federation/inbox``; every version is content-addressed, acknowledged into the
canonical registry, and either donated to the normal compiler or left with a named blocker.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _path in (str(ROOT), str(DESK), str(DESK / "research")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from libs.research import factory_federation as F  # noqa: E402
from libs.research.lead_schema import EVALUATION_LANES  # noqa: E402

MANIFEST = ROOT / "docs" / "research" / "factory_surfaces_v1.json"
BASE = DESK / "data" / "factory_federation"
INBOX = BASE / "inbox"
PROCESSED = BASE / "processed"
STATE = BASE / "state.json"
DONATIONS = DESK / "data" / "intelligence" / "factory_federation"
REPORT = DESK / "reports" / "FACTORY_FEDERATION.json"
RECEIPTS = BASE / "evaluator_receipts"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str) + "\n", "utf-8")
    os.replace(tmp, path)


def _artifact_bytes(doc: dict[str, Any]) -> bytes:
    payload = doc.get("content") if doc.get("content") is not None else doc.get("text")
    if payload is None:
        payload = {k: v for k, v in doc.items() if k not in {"acquired_at", "retrieval_status"}}
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")


def _disposition(doc: dict[str, Any], surface: F.Surface) -> str:
    named = str(doc.get("disposition") or "").upper()
    if named in F.DISPOSITIONS:
        return named
    if doc.get("family") and doc.get("symbols"):
        return "DIRECT_CANDIDATE"
    if doc.get("external_predictor"):
        return "EXTERNAL_PREDICTOR"
    if doc.get("proxy_for"):
        return "IMPERFECT_PROXY"
    if doc.get("missing_data"):
        return "DATA_BLOCKED"
    if F.access_blocker(surface):
        return "ACCESS_BLOCKED"
    return "RESEARCH_ONLY"


def _candidate(doc: dict[str, Any], surface: F.Surface, vid: str) -> dict[str, Any] | None:
    family, symbols = doc.get("family"), doc.get("symbols")
    if not family or not isinstance(symbols, list) or not symbols:
        return None
    mechanism = str(doc.get("mechanism") or doc.get("mechanism_note") or "").strip()
    falsifier = str(doc.get("falsifier") or "").strip()
    if not mechanism or not falsifier:
        return None
    candidate_id = F.content_hash(f"factory-candidate:{vid}".encode())[:24]
    return {
        "candidate_id": candidate_id, "input_version_id": vid,
        "kind": "hypothesis", "family": str(family),
        "symbols": sorted({str(s).upper() for s in symbols}),
        "text": str(doc.get("rule") or doc.get("claim") or mechanism),
        "mechanism_status": "NAMED", "mechanism_note": mechanism,
        "falsifier": falsifier, "source": f"factory:{surface.factory_id}",
        "url": surface.source_uri, "target_lane": surface.evaluation_lane,
        "source_rule_or_reconstruction": str(doc.get("source_rule_or_reconstruction") or
                                                 "RECONSTRUCTED"),
        "provenance": {"input_version_id": vid, "factory_id": surface.factory_id,
                       "surface_id": surface.surface_id, "content_hash": doc["content_hash"],
                       "authority": "none: universal gauntlet judges"},
    }


def _record_registry(record: dict[str, Any]) -> bool:
    try:
        from libs.moat import registry as R
        conn = R.connect()
        try:
            R.record_discovery(kind="factory_input", origin="EXTERNAL",
                               generator="factory_federation",
                               source_id=f"factory:{record['input_version_id']}",
                               payload=record, conn=conn)
        finally:
            conn.close()
        return True
    except Exception:
        return False


def _register_surface(surface: F.Surface) -> bool:
    """Put the factory surface into the canonical source frontier, never a private queue."""
    try:
        from research import source_frontier
        return source_frontier.register_source(
            f"factory:{surface.key}", url=surface.source_uri, kind=surface.surface_type,
            language=surface.language, country="global", asset_classes=[],
            discovered_from="docs/research/factory_surfaces_v1.json",
            discovered_via="factory_federation",
            status="blocked" if F.access_blocker(surface) else "active",
            licence_note=json.dumps(dict(surface.rights), sort_keys=True),
            meta={"factory_id": surface.factory_id, "surface_id": surface.surface_id,
                  "worker": surface.worker, "evaluation_lane": surface.evaluation_lane})
    except Exception:
        return False


def _components(processed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in processed:
        for i, item in enumerate(row.get("components") or row.get("mechanisms") or []):
            if not isinstance(item, dict):
                continue
            out.append({"factory_id": row["factory_id"],
                        "component_id": str(item.get("component_id") or
                                            f"{row['input_version_id']}:{i}"),
                        "lane": str(item.get("target_lane") or row.get("target_lane") or
                                    "RESEARCH_PROCESS"),
                        "type": str(item.get("type") or item.get("kind") or "mechanism"),
                        "family": item.get("family"), "symbols": item.get("symbols") or [],
                        "content": item})
    return out


def _syntheses(rows: list[dict[str, Any]], *, seen_ids: set[str] | None = None,
               limit: int = 24) -> list[dict[str, Any]]:
    """Type-compatible pairs only; every plan includes baseline, singletons and combination."""
    comps = _components(rows)
    out: list[dict[str, Any]] = []
    seen: set[str] = set(seen_ids or ())
    for i, left in enumerate(comps):
        for right in comps[i + 1:]:
            if left["factory_id"] == right["factory_id"] or left["lane"] != right["lane"]:
                continue
            if left["type"] != right["type"]:
                continue
            plan = F.synthesis_plan((left, right))
            if plan["experiment_id"] in seen:
                continue
            seen.add(plan["experiment_id"])
            plan.update({"target_lane": left["lane"], "component_type": left["type"],
                         "status": "QUEUED_FOR_INDEPENDENT_EVALUATION",
                         "falsifier": "combined result fails to improve its strongest singleton "
                                      "under the same PIT data, cost and evaluation contract"})
            out.append(plan)
            if len(out) >= limit:
                return out
    return out


def run(*, apply: bool = True, budget_s: float = 120.0,
        manifest: Path = MANIFEST, state_path: Path = STATE,
        inbox: Path = INBOX, report: Path = REPORT) -> dict[str, Any]:
    t0 = time.monotonic()
    surfaces = F.load_manifest(_read(manifest, {}))
    by_key = {s.key: s for s in surfaces}
    old = _read(state_path, {})
    state_rows = dict(old.get("surfaces") or {})
    versions = dict(old.get("versions") or {})
    synthesis_seen = set(old.get("synthesis_seen") or [])
    new_versions: list[dict[str, Any]] = []
    donations: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    registered_sources = 0
    pending_moves: list[tuple[Path, Path]] = []
    seen_files: set[str] = set()
    disposed_files: set[str] = set()
    unresolved_files: set[str] = set()

    # Only the evaluator can acknowledge the handoff. Producer-side queueing is never an ACK.
    if RECEIPTS.exists():
        for receipt_path in sorted(RECEIPTS.glob("*.json")):
            receipt = _read(receipt_path, None)
            if not isinstance(receipt, dict):
                continue
            vid = str(receipt.get("input_version_id") or "")
            record = versions.get(vid)
            if not isinstance(record, dict):
                continue
            status = str(receipt.get("status") or "").upper()
            evaluator_id = str(receipt.get("evaluator_id") or "")
            expected = str(record.get("candidate_id") or "")
            if (status in {"RECEIVED", "ACCEPTED", "EVALUATED"} and evaluator_id and
                    str(receipt.get("candidate_id") or "") == expected):
                record.setdefault("consumer_ack", {})["evaluator_handoff"] = True
                record.setdefault("delivery", {})["consumer_acknowledged"] = True
                record["evaluator_receipt"] = receipt
                if status == "EVALUATED" and receipt.get("verdict"):
                    record["consumer_ack"]["eventual_disposition"] = True

    for surface in surfaces:
        prev = dict(state_rows.get(surface.key) or {})
        blocker = F.access_blocker(surface)
        due = datetime.now(tz=UTC) + timedelta(hours=surface.cadence_hours)
        state_rows[surface.key] = {
            "factory_id": surface.factory_id, "surface_id": surface.surface_id,
            "source_uri": surface.source_uri, "surface_type": surface.surface_type,
            "rights_status": dict(surface.rights),
            "access_status": "BLOCKED" if blocker else "READY_FOR_AUTHORIZED_ACQUISITION",
            "unresolved_blockers": (
                [blocker] if blocker
                else (["NO_ACQUIRED_VERSION"] if not prev.get("last_success") else [])
            ),
            "worker_owner": surface.worker, "next_due": due.isoformat(timespec="seconds"),
            "target_lane": surface.evaluation_lane, "last_success": prev.get("last_success"),
            "next_cursor": prev.get("next_cursor"),
            "counts_by_stage": dict(prev.get("counts_by_stage") or {}),
            "resource_costs": dict(prev.get("resource_costs") or {}),
        }
        if apply:
            registered_sources += int(_register_surface(surface))

    for path in sorted(inbox.glob("*.json")) if inbox.exists() else []:
        if time.monotonic() - t0 >= budget_s:
            break
        seen_files.add(path.name)
        doc = _read(path, None)
        if not isinstance(doc, dict):
            rejected.append({"file": path.name, "why": "UNREADABLE_JSON"})
            unresolved_files.add(path.name)
            continue
        key = f"{doc.get('factory_id')}:{doc.get('surface_id')}"
        surface = by_key.get(key)
        if surface is None:
            rejected.append({"file": path.name, "why": "UNREGISTERED_SURFACE"})
            unresolved_files.add(path.name)
            continue
        digest = F.content_hash(_artifact_bytes(doc))
        vid = F.version_id(surface, digest)
        if vid in versions:
            if apply:
                PROCESSED.mkdir(parents=True, exist_ok=True)
                pending_moves.append((path, PROCESSED / path.name))
                disposed_files.add(path.name)
            continue
        doc["content_hash"] = digest
        disposition = _disposition(doc, surface)
        candidate = _candidate(doc, surface, vid)
        blocker = None
        if disposition == "DIRECT_CANDIDATE" and candidate is None:
            blocker = "INCOMPLETE_EXECUTABLE_RECONSTRUCTION"
            disposition = "DATA_BLOCKED" if doc.get("missing_data") else "RESEARCH_ONLY"
        record = {
            "factory_id": surface.factory_id, "surface_id": surface.surface_id,
            "source_uri": surface.source_uri, "artifact_version": str(doc.get("version") or vid),
            "content_hash": digest, "input_version_id": vid,
            "acquisition_time": str(doc.get("acquired_at") or _now()),
            "rights_status": dict(surface.rights), "access_status": "ACQUIRED",
            "data_contract": doc.get("data_contract") or {},
            "directly_published_vs_reconstructed": str(
                doc.get("source_rule_or_reconstruction") or "RECONSTRUCTED"),
            "mechanism_ids": list(doc.get("mechanism_ids") or []),
            "parent_lineages": list(doc.get("parent_lineages") or []),
            "target_lane": surface.evaluation_lane, "executable_mapping": disposition,
            "next_cursor": doc.get("next_cursor"), "worker_owner": surface.worker,
            "next_due": state_rows[key]["next_due"], "produced_experiment_ids": [],
            "consumer_ack": {"registry_intake": False, "evaluator_handoff": False,
                             "eventual_disposition": False},
            "counts_by_stage": {"acquired": 1, "compiled": int(candidate is not None)},
            "resource_costs": doc.get("resource_costs") or {},
            "unresolved_blockers": [blocker] if blocker else [],
            "last_success": _now(), "components": doc.get("components") or
                                                       doc.get("mechanisms") or [],
            "candidate_id": candidate.get("candidate_id") if candidate else None,
            "delivery": {"prepared": candidate is not None, "persisted": False,
                         "submitted": False, "consumer_acknowledged": False},
        }
        if apply:
            record["consumer_ack"]["registry_intake"] = _record_registry(record)
        if candidate is not None:
            donations.append(candidate)
        versions[vid] = record
        new_versions.append(record)
        state_rows[key]["last_success"] = record["last_success"]
        state_rows[key]["next_cursor"] = record["next_cursor"]
        state_rows[key]["unresolved_blockers"] = record["unresolved_blockers"]
        if apply:
            PROCESSED.mkdir(parents=True, exist_ok=True)
            pending_moves.append((path, PROCESSED / path.name))
            disposed_files.add(path.name)

    recent = list(versions.values())[-500:]
    syntheses = _syntheses(recent, seen_ids=synthesis_seen)
    if apply and donations:
        DONATIONS.mkdir(parents=True, exist_ok=True)
        for candidate in donations:
            donation_path = DONATIONS / f"discoveries_{candidate['input_version_id']}.json"
            _atomic(donation_path, [candidate])
            record = versions[candidate["input_version_id"]]
            record["delivery"].update({"persisted": True, "submitted": True,
                                       "outbox_path": str(donation_path)})
            record["produced_experiment_ids"] = [candidate["candidate_id"]]
    if apply:
        for plan in syntheses:
            if _record_registry({"input_version_id": plan["experiment_id"], **plan}):
                plan["registry_ack"] = True
                synthesis_seen.add(plan["experiment_id"])
    counts = {"factories": len({s.factory_id for s in surfaces}), "surfaces": len(surfaces),
              "new_source_registry_rows": registered_sources,
              "versions": len(versions), "new_versions": len(new_versions),
              "donated_cells": len(donations), "synthesis_plans": len(syntheses),
              "blocked_surfaces": sum(bool(r["unresolved_blockers"]) for r in state_rows.values())}
    doc = {"at": _now(), "specification": "FACTORY_FEDERATION_V1_20260927",
           "counts": counts, "surfaces": state_rows, "new_versions": new_versions,
           "syntheses": syntheses, "rejected": rejected,
           "evaluation_lanes": list(EVALUATION_LANES),
           "authority": "research only; no certificate, allocation, promotion or order authority",
           "conservation": {
               "inbox_files_seen": len(seen_files),
               "seen_file_ids": sorted(seen_files),
               "new_version_ids": sorted(r["input_version_id"] for r in new_versions),
               "rejected_files": sorted(r["file"] for r in rejected),
               "durably_disposed_file_ids": sorted(disposed_files),
               "unresolved_file_ids": sorted(unresolved_files),
               "pending_files": sorted(p.name for p in inbox.glob("*.json"))
                                if inbox.exists() else [],
               "silent_loss_file_ids": sorted(seen_files - disposed_files - unresolved_files),
               "silent_loss": len(seen_files - disposed_files - unresolved_files),
               "rule": "independently reconcile observed file IDs to durable state or blocker"
           }}
    if apply:
        # Transactional outbox order: durable candidates + state first, inbox move last. A crash
        # before state replays the same deterministic outbox ID; a crash after state sees the
        # known version and completes only the idempotent move.
        _atomic(state_path, {"at": doc["at"], "surfaces": state_rows, "versions": versions,
                             "synthesis_seen": sorted(synthesis_seen)})
        for source, destination in pending_moves:
            with contextlib.suppress(OSError):
                os.replace(source, destination)
        _atomic(report, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(apply=not a.dry_run, budget_s=a.budget_s)
    print(f"factory federation: {doc['counts']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
