"""THE EVIDENCE ROUTER -- every source the desk holds walks the five-stage pipeline, hourly.

LAWS 5e. `libs/research/access_classifier.py` is the law as a pure function; this is the organ
that actually applies it to the desk's own record, which is the difference between a rule and a
rule that has happened. Until it ran, the registry's `sources` table carried url, kind, language
and country and NOT ONE FIELD saying whether the desk may lawfully consume what it had collected
-- so the question was answered ad hoc, per crawler, in prose, and never written down.

WHAT ONE PASS DOES:

    DISCOVER          every row of the registry's `sources` table, plus the source and discovery
                      rows under data/intelligence/** that name a source the table has never seen
    CAPTURE METADATA  url, source class, obtained path, licence note, robots verdict, terms
    LEGAL/ACCESS      access_classifier.classify -> one of the eleven labels
    EVIDENCE CLASS    credibility and predictive_state, INDEPENDENTLY of the access label
    RESEARCH          the row is written back, labelled, and the quarantine and refusal ledgers
                      are rebuilt from what this pass saw

THREE COLUMNS, NOT ONE SCORE. `access_label`, `credibility` and `predictive_state` land as
separate columns through `registry.EXTENSIONS` (ADD COLUMN; the CANON DDL is never touched), so
nothing downstream can accidentally read "unreliable" as "unlawful". `quarantine` is the fourth
and it is the anti-timid one: an ACCESS_UNCLEAR source keeps its metadata row forever and its
content is simply not consumed until somebody resolves the right.

IDEMPOTENT BY CONSTRUCTION. A source already carrying a label and a `routed_at` is skipped unless
its metadata hash changed or `--recheck` is passed, so the hourly pass costs the NEW rows only and
running it twice in a minute writes nothing the second time.

IT REFUSES NOTHING RETROACTIVELY AND DELETES NOTHING. A row that classifies PRIVATE,
CONFIDENTIAL_MNPI or STOLEN_UNAUTHORIZED is marked refused WITH THE REASON and its content stops
being an alpha input; the row itself stays, because a refusal nobody recorded gets re-proposed by
the next miner that finds the same domain.

    python desks/mt5/research/evidence_router.py --once --budget-s 600 [--dry-run] [--recheck]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from libs.research import access_classifier as ac  # noqa: E402

INTEL_ROOTS: tuple[Path, ...] = (DESK / "data" / "intelligence", ROOT / "data" / "intelligence")
QUARANTINE = DESK / "data" / "evidence_quarantine.json"
REPORT = DESK / "reports" / "EVIDENCE_ROUTER.json"
SOURCE_REGISTRY = DESK / "data" / "source_registry.json"
DEEP_FOREST = DESK / "data" / "deep_forest_sources.json"

#: Intelligence files one pass opens, newest first per seat directory. A bound on WALL CLOCK and
#: MEMORY on a box with 8 GB, never a view of what matters: whatever it defers is COUNTED and the
#: next pass takes it, because the cursor is the label itself (a labelled source is not re-read).
MAX_FILES_PER_SEAT = 6
MAX_ROWS_PER_FILE = 500
MAX_FILE_BYTES = 8 * 1024 * 1024
#: Wall budget for one pass. Legs get 600 s from the cycle; the organ stops early and says so.
BUDGET_S = 600.0

#: Seat directory -> the source class its rows belong to (LAWS 5f's ten). A seat absent from this
#: table is NOT guessed: it reads UNKNOWN and the classifier treats the row on its url alone.
#: Guessing a class would put a credibility PRIOR on a source nobody has assessed.
SEAT_CLASS: dict[str, str] = {
    "academic": "academic", "arxiv_qfin": "academic", "bis_speeches": "official",
    "central_banks": "official", "cot": "official", "investing": "media",
    "forexfactory": "media", "ff_calendar_vintage": "official", "fear_greed": "media",
    "google_trends": "app_ecosystem", "github": "app_ecosystem",
    "github_topics": "app_ecosystem", "mql5_catalog": "app_ecosystem",
    "mql5_prospector": "app_ecosystem", "mql5_reputation": "app_ecosystem",
    "aaii": "institutional", "china": "practitioner", "asia": "practitioner",
    "earnings": "institutional", "correlations": "institutional",
    "collective2": "retail_ecology", "darwinex": "retail_ecology",
    "duplitrade": "retail_ecology", "equiti_copy": "retail_ecology",
    "followme_cn": "retail_ecology", "forexpeacearmy": "retail_ecology",
    "forextsd_cdx": "retail_ecology", "fxblue": "retail_ecology",
    "fxmerge": "retail_ecology", "hfm_pamm": "retail_ecology",
    "instaforex_copy": "retail_ecology", "amarkets": "retail_ecology",
    "youtube": "media", "world": "source_graph", "frontier": "source_graph",
    "broker_swaps": "institutional", "anomalies": "source_graph",
    "alpha_evolution": "source_graph", "alpha_periodic_table": "source_graph",
    "axis_registry": "source_graph", "asia_endpoints": "physical_economy",
    "fund_playbook": "institutional", "event_response_atlas": "institutional",
    "factor_residual": "institutional", "discovery_compiler": "source_graph",
    "index_discovery": "institutional", "cohorts": "institutional", "brain": "source_graph",
    "fbs_tape": "retail_ecology", "global_frontier": "source_graph",
}

#: Registry `kind` values that already say what a source is.
KIND_CLASS: dict[str, str] = {
    "region": "source_graph", "execution_tape": "physical_economy", "dataset": "official",
    "paper": "academic", "repo": "app_ecosystem", "forum": "retail_ecology",
    "interview": "practitioner", "web": "media", "archive": "archive",
}

RULE = ("mine aggressively; classify precisely; restrict only the specific use that is actually "
        "prohibited -- five stages on every source, three independent labels, nothing discarded")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _atomic_write(path: Path, doc: Any) -> Path:
    """tmp + os.replace, utf-8. `os.replace` onto a read-only destination is legal on POSIX and
    WinError 5 on this box, which is how a VPS-tested fix once broke the box that trades."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    try:
        os.replace(tmp, path)
        return path
    except PermissionError:
        try:
            os.chmod(path, 0o666)
            os.replace(tmp, path)
            return path
        except OSError:
            pass
    path.write_bytes(tmp.read_bytes())
    return path


def _read_json(path: Path) -> Any:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def meta_hash(meta: dict[str, Any]) -> str:
    """The metadata this verdict was made on. A changed hash is what re-opens a settled row."""
    keys = ("url", "source_class", "obtained", "licence", "robots", "machine_use_allowed",
            "requires_auth", "is_open_data", "terms", "kind")
    return hashlib.sha256(
        json.dumps({k: meta.get(k) for k in keys}, sort_keys=True,
                   default=str).encode()).hexdigest()[:16]


def source_meta(row: dict[str, Any]) -> dict[str, Any]:
    """A registry `sources` row -> the metadata the classifier reads. Nothing is invented: a
    field the row does not carry is ABSENT, and absence is never a permission."""
    meta_json = row.get("meta_json")
    extra: dict[str, Any] = {}
    if isinstance(meta_json, str):
        loaded = None
        try:
            loaded = json.loads(meta_json)
        except ValueError:
            loaded = None
        if isinstance(loaded, dict):
            extra = loaded
    elif isinstance(meta_json, dict):
        extra = meta_json
    kind = str(row.get("kind") or "")
    out: dict[str, Any] = {
        "source_id": str(row.get("source_id") or ""),
        "url": str(row.get("url") or ""),
        "kind": kind,
        "licence_note": str(row.get("licence_note") or ""),
        "licence": str(extra.get("licence") or row.get("licence_note") or ""),
    }
    klass = str(extra.get("source_class") or KIND_CLASS.get(kind, ""))
    if klass in ac.SOURCE_CLASSES:
        out["source_class"] = klass
    for key in ("obtained", "robots", "machine_use_allowed", "requires_auth", "is_open_data",
                "terms", "credibility", "is_social"):
        if key in extra:
            out[key] = extra[key]
    if "obtained" not in out and out["url"].startswith(("http://", "https://")):
        out["obtained"] = "public_page"
    return out


def intel_rows(budget_s: float, t0: float) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Source metadata harvested from data/intelligence/**, keyed by the source id it implies.

    A discovery row is EVIDENCE ABOUT ITS SOURCE: the seat directory names the ground, the row's
    `url` names the page, and `source` names the miner that fetched it. Rows whose source the
    registry has never seen are exactly the sources nobody has ever classified.
    """
    found: dict[str, dict[str, Any]] = {}
    stats = {"files_read": 0, "files_deferred": 0, "rows_read": 0, "roots": []}
    for root in INTEL_ROOTS:
        if not root.is_dir():
            continue
        stats["roots"].append(str(root))
        for seat_dir in sorted(root.iterdir()):
            if time.monotonic() - t0 > budget_s:
                break
            if not seat_dir.is_dir():
                continue
            files = sorted(seat_dir.glob("*.json"), reverse=True)
            for path in files[:MAX_FILES_PER_SEAT]:
                doc = _read_json(path)
                if doc is None:
                    continue
                stats["files_read"] += 1
                rows = doc if isinstance(doc, list) else (
                    doc.get("discoveries") or doc.get("items") or doc.get("rows")
                    or doc.get("leads") or [])
                if not isinstance(rows, list):
                    continue
                for row in rows[:MAX_ROWS_PER_FILE]:
                    if not isinstance(row, dict):
                        continue
                    stats["rows_read"] += 1
                    url = str(row.get("url") or "")
                    sid = str(row.get("source_id") or row.get("source") or seat_dir.name)
                    key = sid if sid else url
                    if not key or key in found:
                        continue
                    meta: dict[str, Any] = {"source_id": key, "url": url,
                                            "seat": seat_dir.name}
                    klass = SEAT_CLASS.get(seat_dir.name, "")
                    if klass in ac.SOURCE_CLASSES:
                        meta["source_class"] = klass
                    for field_name in ("title", "text", "description", "licence_note"):
                        if row.get(field_name):
                            meta[field_name] = row[field_name]
                    if url.startswith(("http://", "https://")):
                        meta["obtained"] = "public_page"
                    found[key] = meta
            stats["files_deferred"] += max(0, len(files) - MAX_FILES_PER_SEAT)
    return found, stats


def _needs_routing(row: dict[str, Any], meta: dict[str, Any], recheck: bool) -> bool:
    """Idempotence: a labelled row whose metadata has not changed is left exactly alone."""
    if recheck:
        return True
    if not row.get("access_label") or not row.get("routed_at"):
        return True
    reason = str(row.get("route_reason") or "")
    return f"#{meta_hash(meta)}" not in reason


def route_source(meta: dict[str, Any]) -> dict[str, Any]:
    """One source through the five stages -> the four columns and the reason."""
    routed = ac.route(meta, {})
    v = routed.verdict
    klass = str(meta.get("source_class") or "")
    credibility = ac.credibility_of(klass, str(meta.get("credibility") or ""))
    return {
        "source_id": str(meta.get("source_id") or meta.get("url") or ""),
        "access_label": v.access_label,
        "credibility": credibility,
        # A SOURCE has not been tested; a CLAIM is. UNTESTED is the honest reading and it is a
        # verdict, not a zero -- research_roi is what later moves a source to PREDICTIVE.
        "predictive_state": "UNTESTED",
        "quarantine": 1 if v.quarantine else 0,
        "refused": v.refused,
        "machine_use_allowed": v.machine_use_allowed,
        "allowed_uses": list(v.allowed_uses),
        "evidence_weight_cap": v.evidence_weight_cap,
        "stage": routed.stage,
        "reason": f"{v.reason} [{v.basis}] #{meta_hash(meta)}",
        "url": str(meta.get("url") or ""),
        "source_class": klass or "UNKNOWN",
    }


def intel_row(sid: str, meta: dict[str, Any]) -> dict[str, Any]:
    """The registry row an intelligence-discovered source BECOMES.

    Built once and used both to INSERT and to classify, because the verdict hash written on this
    pass must be the hash the NEXT pass computes from the stored row. Measured 2026-09-17: routing
    the raw intelligence metadata and storing a registry-shaped row made the two hashes differ, so
    123 of 159 sources re-routed every pass -- an organ that rewrites its whole table every hour
    cannot be told apart from one that is looping.
    """
    return {"source_id": sid, "url": str(meta.get("url") or ""),
            "kind": str(meta.get("source_class") or "intelligence"),
            "meta_json": json.dumps({"seat": meta.get("seat"),
                                     "source_class": meta.get("source_class"),
                                     "discovered_via": "evidence_router"},
                                    ensure_ascii=False, default=str)}


def _merge(row: dict[str, Any], extra: dict[str, Any] | None) -> dict[str, Any]:
    """The registry row's metadata, filled in from what the intelligence rows also know."""
    meta = source_meta(row)
    for k, v in (extra or {}).items():
        meta.setdefault(k, v)
    return meta


def _ensure_source(conn: sqlite3.Connection, row: dict[str, Any]) -> bool:
    """Put an intelligence-discovered source in the graph. True when the row is new. A re-seed
    never overwrites an existing row -- `source_frontier.register_source`'s own contract."""
    sid = str(row["source_id"])
    if conn.execute("SELECT source_id FROM sources WHERE source_id=?", (sid,)).fetchone():
        return False
    conn.execute(
        "INSERT INTO sources(source_id, url, kind, first_seen, last_crawled, status, meta_json) "
        "VALUES(?,?,?,?,?,?,?)",
        (sid, row["url"], row["kind"], _now(), None, "active", row["meta_json"]))
    return True


def _write_labels(conn: sqlite3.Connection, verdict: dict[str, Any]) -> None:
    conn.execute(
        "UPDATE sources SET access_label=?, credibility=?, predictive_state=?, quarantine=?, "
        "routed_at=?, route_reason=? WHERE source_id=?",
        (verdict["access_label"], verdict["credibility"], verdict["predictive_state"],
         int(verdict["quarantine"]), _now(), verdict["reason"], verdict["source_id"]))


def _publish_coverage(conn: sqlite3.Connection, counts: dict[str, int],
                      by_class: dict[str, int]) -> str | None:
    """Counts by label into research memory, keyed so the coverage tensor can read them back.

    The tensor's ACCESSIBILITY axis (LAWS 5f: the FOREST tensor is country x language x source
    class x sector x mechanism x asset transmission x freshness x ACCESSIBILITY) has no other
    producer on this tree. Published under one memory key; its owner reads it there.
    """
    try:
        R.remember("access_coverage",
                   f"access labels over {sum(counts.values())} registered source(s)",
                   kind="access_label_counts", memory_key="access_coverage:by_label",
                   result="success",
                   payload={"by_label": counts, "by_source_class": by_class, "at": _now(),
                            "labels": list(ac.ACCESS_LABELS),
                            "read_with": 'registry.memories(category="access_coverage")',
                            "axis": "FOREST tensor accessibility axis (LAWS 5f)"},
                   conn=conn)
        return None
    except (sqlite3.Error, ValueError, TypeError) as exc:
        return f"{type(exc).__name__}: {exc}"


def run(*, budget_s: float = BUDGET_S, dry_run: bool = False, recheck: bool = False,
        conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """One pass. Never raises on a bad row: an unclassifiable source is ACCESS_UNCLEAR, which is
    a verdict, and an unreadable input is named in `unmeasured` rather than counted as zero."""
    t0 = time.monotonic()
    unmeasured: list[dict[str, str]] = []
    own = conn is None
    c = conn or R.connect()
    try:
        try:
            registry_rows = [dict(r) for r in c.execute("SELECT * FROM sources")]
        except sqlite3.Error as exc:
            registry_rows = []
            unmeasured.append({"what": "registry sources", "why": f"{type(exc).__name__}: {exc}"})

        discovered, intel_stats = intel_rows(budget_s * 0.4, t0)
        known = {str(r.get("source_id") or "") for r in registry_rows}
        new_ids = [k for k in discovered if k and k not in known]

        counts: Counter[str] = Counter()
        by_class: Counter[str] = Counter()
        quarantined: list[dict[str, Any]] = []
        refused: list[dict[str, Any]] = []
        routed = skipped = created = 0
        budget_hit = False

        for row in registry_rows:
            if time.monotonic() - t0 > budget_s:
                budget_hit = True
                break
            sid = str(row.get("source_id") or "")
            if not sid:
                continue
            meta = _merge(row, discovered.get(sid))
            v = route_source(meta)
            counts[v["access_label"]] += 1
            by_class[v["source_class"]] += 1
            if v["quarantine"]:
                quarantined.append(v)
            if v["refused"]:
                refused.append(v)
            if not _needs_routing(row, meta, recheck):
                skipped += 1
                continue
            routed += 1
            if not dry_run:
                _write_labels(c, v)

        for sid in new_ids:
            if time.monotonic() - t0 > budget_s:
                budget_hit = True
                break
            row = intel_row(sid, discovered[sid])
            v = route_source(_merge(row, discovered[sid]))
            counts[v["access_label"]] += 1
            by_class[v["source_class"]] += 1
            if v["quarantine"]:
                quarantined.append(v)
            if v["refused"]:
                refused.append(v)
            routed += 1
            if not dry_run:
                if _ensure_source(c, row):
                    created += 1
                _write_labels(c, v)

        coverage_err: str | None = None
        if not dry_run:
            c.commit()
            coverage_err = _publish_coverage(c, dict(counts), dict(by_class))
            if coverage_err:
                unmeasured.append({"what": "coverage counts", "why": coverage_err})
    finally:
        if own:
            c.close()

    total = sum(counts.values())
    doc: dict[str, Any] = {
        "at": _now(), "rule": RULE, "principle": ac.PRINCIPLE,
        "hard_boundary": list(ac.HARD_BOUNDARY), "stages": list(ac.STAGES),
        "n_sources_seen": total, "n_routed": routed, "n_skipped_already_labelled": skipped,
        "n_sources_created_from_intelligence": created,
        "n_quarantined": len(quarantined), "n_refused": len(refused),
        "by_label": {label: counts.get(label, 0) for label in ac.ACCESS_LABELS},
        "by_source_class": dict(sorted(by_class.items())),
        "coverage_tensor": {
            "axis": "accessibility (FOREST tensor, LAWS 5f)",
            "published_to": 'registry.memories(category="access_coverage")',
            "memory_key": "access_coverage:by_label",
            "status": "UNMEASURED" if (dry_run or coverage_err) else "PUBLISHED",
            "why": ("--dry-run: nothing published" if dry_run else
                    coverage_err or "counts by label and by source class written to research "
                                    "memory for the coverage tensor's accessibility axis"),
        },
        "machine_use_restricted": sorted(
            v["source_id"] for v in (*quarantined, *refused) if not v["machine_use_allowed"]),
        "intelligence_scan": intel_stats,
        "budget_s": budget_s, "budget_hit": budget_hit,
        "elapsed_s": round(time.monotonic() - t0, 2),
        "dry_run": dry_run, "recheck": recheck,
        "unmeasured": unmeasured,
        "limitation": ("predictive_state is UNTESTED for every SOURCE: a source is not a claim, "
                       "and only forward evidence moves it. research_roi.py is what later credits "
                       "a source whose claims survived"),
    }
    quarantine_doc = {
        "at": doc["at"],
        "rule": ("ACCESS_UNCLEAR is QUARANTINED -- metadata kept, content not consumed, until "
                 "access rights are resolved. PRIVATE, CONFIDENTIAL_MNPI and STOLEN_UNAUTHORIZED "
                 "are REFUSED with the reason and never become an alpha input. Nothing is "
                 "discarded."),
        "n_quarantined": len(quarantined), "n_refused": len(refused),
        "quarantined": sorted(quarantined, key=lambda r: str(r["source_id"])),
        "refused": sorted(refused, key=lambda r: str(r["source_id"])),
    }
    if not dry_run:
        _atomic_write(QUARANTINE, quarantine_doc)
        _atomic_write(REPORT, doc)
    doc["quarantine_ledger"] = str(QUARANTINE)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=str(__doc__ or "").split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg's shape)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true", help="classify and print; write nothing")
    ap.add_argument("--recheck", action="store_true",
                    help="re-route every source, including ones already labelled")
    a = ap.parse_args(argv)
    doc = run(budget_s=float(a.budget_s), dry_run=bool(a.dry_run), recheck=bool(a.recheck))
    print(f"evidence router {doc['at']}: {doc['n_sources_seen']} source(s) seen, "
          f"{doc['n_routed']} routed, {doc['n_skipped_already_labelled']} already labelled")
    for label, n in doc["by_label"].items():
        if n:
            print(f"  {label:<22} {n:>6d}")
    print(f"  quarantined {doc['n_quarantined']}, refused {doc['n_refused']}, "
          f"created from intelligence {doc['n_sources_created_from_intelligence']}")
    for u in doc["unmeasured"]:
        print(f"  UNMEASURED {u['what']}: {u['why']}")
    if a.dry_run:
        print("  --dry-run: nothing written")
        return 0
    print(f"-> {REPORT}\n-> {QUARANTINE}")
    print(f"YIELD routed={doc['n_routed']} quarantined={doc['n_quarantined']} "
          f"refused={doc['n_refused']} elapsed={doc['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
