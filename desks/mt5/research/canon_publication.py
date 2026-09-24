"""ATOMIC CANON PUBLICATION: the judge republishes, and until now nothing carried that forward.

MEASURED ON THE TRADING BOX 2026-09-24, and this is the whole reason the file exists:

    desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json   swept_at 2026-09-03T08:45:17   n=28
    desks/mt5/reports/UNIVERSAL_SURVIVORS.json      swept_at 2026-09-23T05:42      n=28
    desks/mt5/data/hypotheses/gate_verdict_ledger.jsonl   146,359 verdicts, latest 2026-09-23

The SEALED CANON -- the file `libs/research/memory.py`, `alpha_breadth`, `alpha_genome`,
`certificate_hygiene`, `clock_certificate`, `conversion_ledger`, `attribution_reconcile`,
`scripts/sync_research_ledger.py`, `scripts/check_dig_roi.py` and `scripts/run_desk_integrity.py`
all read as the desk's certificate store -- carried a sweep stamp TWENTY-ONE DAYS OLD while the
judge ran and appended verdicts the whole time. Its mtime was recent, which is worse than stale:
`certificate_truth` HEALS it and the retirement scripts PRUNE it, so the file kept moving while
its sweep stamp stood still. A reader checking freshness by mtime saw a live file.

WHY IT WENT STALE. `external_gauntlet.py` is SEALED and IS a faithful republisher: at the end of
every completed sweep it rewrites `reports/UNIVERSAL_SURVIVORS.json` with a fresh `swept_at`
(:3444-3457). Nothing on any clock copies that into the sealed canon. `recertify_canon` sounds
like the step that would and is not: it re-JUDGES the standing library under the current cost
model, writes `reports/recertification_audit.json`, and the hourly cycle only claims it when the
queue holds a `recertify` task -- which a fresh certificate does not raise. So the publication
path had a missing last link and every organ reading the seal was reading 2026-09-03.

WHAT THIS ORGAN DOES, AND THE FOUR THINGS IT REFUSES TO DO:

    IT MINTS NOTHING. A row reaches the seal only if it is already in the judge's report AND
    `gate_policy.all_ten_pass` holds on its own gates record. There is no path here that creates
    a certificate, and no threshold anywhere in the file.
    IT NEVER SHRINKS. The union of the seal's rows and the report's rows is written, never the
    report alone -- the never-shrink law of 2026-08-26 (the certifier wipe), restated at the
    second pen rather than assumed.
    IT NEVER REVIVES A RETIREMENT. A key in `retired_certificates` stays out, whatever the report
    says. Retirement is the retirers' call and this organ does not overturn it.
    IT NEVER WRITES A HALF FILE. tempfile + fsync + os.replace, in the destination directory, so
    a reader either sees the old seal or the new one and never the middle of a 137 KB write.

WHEN THE JUDGE DID NOT REPUBLISH -- killed at its cycle budget, halted on an empty docket, or
refusing a shrink -- the seal is LEFT ALONE and a DERIVED view is published instead, to
`reports/UNIVERSAL_SURVIVORS_DERIVED.json`, built from `gate_verdict_ledger.jsonl` and labelled
derived on every level: `derived: true`, `promotion_authority: false`, and a note saying in words
that its rows are PASSING CELL IDENTITIES and not certificates. The ledger records `passed` and
the terminal gate; it does not record a gates object, so nothing downstream can mistake a derived
row for something `all_ten_pass` would admit. A derived view that could be promoted from would be
a second certificate authority, which is the one thing this desk has never allowed.

    python desks/mt5/research/canon_publication.py [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
SEAL = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
DERIVED = DESK / "reports" / "UNIVERSAL_SURVIVORS_DERIVED.json"
OUT = DESK / "reports" / "CANON_PUBLICATION.json"
#: The admission screen's census, READ here so the whole funnel reads in one artifact: raw intake
#: -> admissible -> judged -> certified -> sealed. The two halves were published in different
#: files by different organs and nothing ever put them beside each other, which is how a 244,275
#: row bank came to be read as a 244,275 cell backlog against a 28 row certificate store.
ADMISSION = DESK / "reports" / "ADMISSION_SCREEN.json"

#: Keys the seal carries that are NOT the survivor set and must survive a republication. Every one
#: is another organ's record -- the retirers', the healer's, the hygiene pass's -- and dropping it
#: would erase their work under the banner of publishing the judge's.
CARRIED: tuple[str, ...] = ("retired_certificates", "revoked_at", "unrunnable_evicted",
                            "unrunnable_note", "healed_at", "healed_by")

#: A derived view is bounded so a 33 MB ledger can never become an hour of IO on the box that
#: holds the live terminal. It is a fallback view, not an index.
DERIVED_MAX_ROWS = 200_000


def _atomic_json(path: Path, value: dict[str, Any], *, indent: int = 2) -> None:
    """Write-and-rename, fsynced, in the destination directory.

    THE DIRECTORY MATTERS: `os.replace` is atomic only within one filesystem, and a temp file in
    the system temp dir is on a different volume on this box. Writing beside the target keeps the
    rename atomic, which is the property the whole function exists for.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=indent, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(name)


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
    except OSError:
        return None


def _age_hours(stamp: Any, now: datetime) -> float | None:
    try:
        then = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=UTC)
    return round((now - then).total_seconds() / 3600.0, 2)


def _funnel(admission: Path = ADMISSION) -> dict[str, Any]:
    """Raw intake and the admissible population, from the admission screen's own census.

    ABSENT IS UNMEASURED, NEVER ZERO (L1.28a). A missing screen artifact says the screen has not
    run on this box yet; it does not say the bank is empty, and reporting 0 here would make the
    funnel read as "nothing to judge" when the truth is "nobody has counted".
    """
    doc = _read(admission)
    if not doc:
        return {"status": "UNMEASURED",
                "why": f"{admission.name} absent or unreadable -- the admission screen has not "
                       f"run here yet. That is not a claim that the docket is empty."}
    return {"status": doc.get("status"), "measured_at": doc.get("measured_at"),
            "raw_cells": doc.get("raw_cells"), "admissible_cells": doc.get("admissible_cells"),
            "refused_cells": doc.get("refused_cells"),
            "refused_by_reason": doc.get("refused_by_reason"),
            "source": str(admission)}


def derive_from_ledger(ledger: Path = GATE_LEDGER,
                       *, max_rows: int = DERIVED_MAX_ROWS) -> dict[str, Any]:
    """The DERIVED view: which cells the judge's ledger says passed. Not certificates.

    The ledger row is `{at, cell, sym, family, graph_id, passed, terminal_gate,
    downstream_status}`. There is no gates object in it, so this view can state WHICH cells passed
    and WHEN, and it can never state that they hold a ten-gate certificate. That limit is the
    point: it is what makes the fallback safe to publish while the seal is untouched.
    """
    now = datetime.now(UTC)
    passing: dict[str, dict[str, Any]] = {}
    rows = 0
    terminal: Counter[str] = Counter()
    if not ledger.exists():
        return {"derived": True, "status": "UNMEASURED", "n": 0, "cells": {},
                "why": f"{ledger} does not exist", "derived_at": now.isoformat()}
    with ledger.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows += 1
            if rows > max_rows:
                break
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict):
                continue
            terminal[str(row.get("terminal_gate"))] += 1
            if row.get("passed") is not True:
                continue
            cell = str(row.get("cell") or "")
            if cell:
                passing[cell] = {"cell": cell, "sym": row.get("sym"),
                                 "family": row.get("family"), "at": row.get("at"),
                                 "graph_id": row.get("graph_id")}
    return {
        "derived": True,
        "status": "MEASURED",
        "promotion_authority": False,
        "note": ("DERIVED VIEW, NOT A CERTIFICATE STORE. These are cell identities the sealed "
                 "judge's verdict ledger records as having passed; the ledger carries no gates "
                 "object, so no row here can satisfy gate_policy.all_ten_pass and nothing may be "
                 "promoted, enrolled or funded from this file. It exists so a session can see "
                 "what the judge found while the canonical seal is waiting on a completed sweep."),
        "source": str(ledger),
        "derived_at": now.isoformat(),
        "ledger_rows_read": rows,
        "terminal_gates": dict(terminal.most_common()),
        "n": len(passing),
        "cells": passing,
    }


def publish(report: Path = REPORT, seal: Path = SEAL) -> dict[str, Any]:
    """Seal the judge's latest completed sweep into the canonical store, atomically.

    Returns the publication record. The seal is written only when the report carries the exact
    ten-gate attestation; anything else leaves it untouched and says why, because a canonical
    store overwritten from an unattested source is the certifier wipe with a different cause.
    """
    try:
        from gate_policy import all_ten_pass, is_exact_policy
        from survivor_publication import unrunnable_reason
    except ImportError:                                  # pragma: no cover - import-context dep
        from research.gate_policy import all_ten_pass, is_exact_policy  # type: ignore[no-redef]
        from research.survivor_publication import unrunnable_reason  # type: ignore[no-redef]

    now = datetime.now(UTC)
    doc_report = _read(report)
    doc_seal = _read(seal)
    seal_before = doc_seal.get("survivors")
    seal_before = dict(seal_before) if isinstance(seal_before, dict) else {}
    retired = doc_seal.get("retired_certificates")
    retired = retired if isinstance(retired, dict) else {}
    # THE EVICTION RECORD. `certificate_hygiene` moves rows the enrolment engine can never run to
    # reports/UNIVERSAL_SURVIVORS_UNRUNNABLE.json and lists their keys here. They still stand in
    # the judge's report -- eviction is not revocation -- so without this the seal re-admits every
    # one of them on every publication.
    _ev = doc_seal.get("unrunnable_evicted")
    evicted = set(_ev) if isinstance(_ev, list) else set()

    record: dict[str, Any] = {
        "published_at": now.isoformat(),
        "publisher": "desks/mt5/research/canon_publication.py",
        "judge": "desks/mt5/scripts/external_gauntlet.py (sealed; never edited)",
        "report": str(report),
        "report_swept_at": doc_report.get("swept_at"),
        "report_mtime": _mtime(report),
        "report_n": doc_report.get("n"),
        "seal": str(seal),
        "seal_swept_at_before": doc_seal.get("swept_at"),
        "seal_n_before": len(seal_before),
        "seal_lag_hours_before": _age_hours(doc_seal.get("swept_at"), now),
        "run_lag_hours": _age_hours(doc_report.get("swept_at"), now),
        "funnel": _funnel(),
    }

    if not doc_report:
        record.update(status="NO_REPORT", sealed=False, admitted=0,
                      why=(f"{report} is absent or unreadable. The judge has not republished; the "
                           "seal is left exactly as it stands and a derived view is published "
                           "instead."))
        return record
    if not is_exact_policy(doc_report.get("gate_policy")):
        record.update(status="UNATTESTED_REPORT", sealed=False, admitted=0,
                      why=("the judge's report does not carry the exact ten-gate attestation, so "
                           "nothing in it may enter the canonical store. The seal is untouched."))
        return record

    survivors = doc_report.get("survivors")
    survivors = survivors if isinstance(survivors, dict) else {}
    merged = dict(seal_before)
    admitted: list[str] = []
    refused_rows: Counter[str] = Counter()
    for key, row in survivors.items():
        if not isinstance(row, dict):
            refused_rows["not_a_row"] += 1
            continue
        if key in retired:
            # RETIREMENT IS NOT OVERTURNED BY A REPUBLICATION. The retirers own that record and
            # the judge's own restore loop is the only thing that may bring a row back.
            refused_rows["retired"] += 1
            continue
        if key in evicted:
            # NEITHER IS AN EVICTION, AND THIS ONE WAS MEASURED THE FIRST TIME THIS ORGAN RAN.
            # Six keys were admitted on the first pass and ALL SIX were rows `certificate_hygiene`
            # had already moved to reports/UNIVERSAL_SURVIVORS_UNRUNNABLE.json: they pass all ten
            # gates and cannot be enrolled, which is precisely why counting them inflated the
            # desk's belief about its own edge. A republisher that re-admits them is a second pen
            # undoing the first one every hour, quietly, while reporting +6 certificates.
            refused_rows["unrunnable_evicted"] += 1
            continue
        if not all_ten_pass(row.get("gates")):
            refused_rows["not_all_ten_pass"] += 1
            continue
        why_unrunnable = unrunnable_reason(row)
        if why_unrunnable:
            # THE SHARED JUDGE, NOT A LIST LOOKUP. `unrunnable_evicted` is the RECORD of past
            # evictions; this is the RULE, and it is the one all four certificate pens already
            # use (research/survivor_publication.unrunnable_reason). Without it a row that became
            # unenrollable AFTER the last hygiene pass would enter the seal and wait an hour to
            # be evicted again.
            refused_rows["unrunnable_spec"] += 1
            continue
        if key not in merged:
            admitted.append(key)
        merged[key] = row

    # THE REFUSAL CENSUS IS A MEASUREMENT AND IS NEVER WITHHELD BY AN EARLY RETURN. A publication
    # that refused every row and says only "REFUSED_EMPTY" is the shape that hides a judge quietly
    # emitting rows the seal cannot take -- the count, by named reason, is the thing that says so.
    record["refused_rows"] = dict(refused_rows)
    if len(merged) < len(seal_before):
        # Unreachable by construction (merged starts as a copy of the seal) and asserted anyway:
        # the never-shrink law is the one this desk has actually lost certificates to.
        record.update(status="REFUSED_SHRINK", sealed=False, admitted=0,
                      why=f"merge would shrink the seal {len(seal_before)} -> {len(merged)}")
        return record
    if not merged:
        record.update(status="REFUSED_EMPTY", sealed=False, admitted=0,
                      why="an empty canon is never published; an empty docket does not revoke "
                          "past verdicts")
        return record

    doc_new = dict(doc_seal)
    for key in CARRIED:
        if key in doc_seal:
            doc_new[key] = doc_seal[key]
    doc_new.update({
        "n": len(merged),
        "survivors": merged,
        "gate_policy": doc_report.get("gate_policy"),
        "note": "UNIVERSAL 10-GATE PASS ONLY.",
        # THE TIME OF THE RUN THAT PRODUCED IT, which is the judge's stamp and not this organ's.
        # `published_at` says when the seal was written; `swept_at` says when the evidence in it
        # was gathered, and conflating the two is how a stale store looked fresh by mtime.
        "swept_at": doc_report.get("swept_at"),
        "published_at": now.isoformat(),
        "published_by": "research/canon_publication.py",
        "published_from": str(report.relative_to(DESK)) if report.is_relative_to(DESK)
        else str(report),
    })
    _atomic_json(seal, doc_new)
    record.update(status="SEALED", sealed=True, admitted=len(admitted),
                  admitted_keys=admitted[:24], refused_rows=dict(refused_rows),
                  seal_n_after=len(merged), seal_swept_at_after=doc_report.get("swept_at"),
                  atomic="tempfile + fsync + os.replace in the destination directory")
    return record


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report", type=Path, default=REPORT)
    ap.add_argument("--seal", type=Path, default=SEAL)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    record = publish(args.report, args.seal)
    if not record.get("sealed"):
        # THE JUDGE DID NOT REPUBLISH. Say so precisely and publish the derived view, which is
        # labelled derived on every level and carries no promotion authority.
        view = derive_from_ledger()
        _atomic_json(DERIVED, view)
        record["derived_view"] = {"path": str(DERIVED), "n": view.get("n"),
                                  "status": view.get("status"),
                                  "why": ("the sealed judge did not republish this pass, so the "
                                          "canonical seal stands and this view is what the "
                                          "verdict ledger shows instead")}
    _atomic_json(args.out, record)
    before = record.get("seal_n_before")
    after = record.get("seal_n_after", before)
    print(f"canon publication: {record['status']} seal {before} -> {after} "
          f"(+{record.get('admitted', 0)}); report swept_at {record.get('report_swept_at')}; "
          f"seal lag before {record.get('seal_lag_hours_before')}h -> {args.out.name}")
    if args.json:
        print(json.dumps(record, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
