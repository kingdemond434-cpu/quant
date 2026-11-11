#!/usr/bin/env python3
"""CERTIFICATE RE-CHECKS: a live certificate whose INPUTS changed under it is marked, re-judged
once by the sealed gauntlet in reproduction mode, and the verdict is published.

    python desks/mt5/research/certificate_recheck.py --once
    python desks/mt5/research/certificate_recheck.py --status     # read the marker, run nothing

WHY (#238 audit HOLD, 2026-11-11). The COT release labels moved to the bar clock: 57 of the 455
report weeks inside the EURUSD H1 span now read LATER than they did when the LIVE
`EURUSD.cot_positioning` sleeve was certified (none earlier). A later label is never look-ahead,
but the certificate was judged on the earlier ones, and nothing scheduled said so: it stayed
valid with no marker. This organ is that marker and the thing that clears it.

WHAT A PASS DOES, per row of `research/certificate_rechecks.json` (reviewed configuration beside
the code, never box state):
  1. If the row's reproduction report exists, read its verdicts and publish them. The report is
     the end state: the reproduction never runs again for that row.
  2. Otherwise the row is RECHECK_REQUIRED. At most once per RETRY_S it runs
         scripts/external_gauntlet.py --only <only> --report-to <report_to>
     -- REPRODUCTION MODE: the sealed ten gates on the named cell, no certificate written, no
     authority file touched (`external_gauntlet._cli_main`). A deferral (the certification lane
     is held), a cell absent from the docket or a timeout leaves no report: the row stays
     RECHECK_REQUIRED and says why, with the run's last lines.
  3. Write `reports/CERTIFICATE_RECHECKS.json`, every row's status. It is never a clean verdict
     by absence: no report is RECHECK_REQUIRED, a report with no measured verdict is UNMEASURED.

IT DECIDES NOTHING ABOUT CAPITAL. It edits no certificate, registry, sleeves.json, promoter or
gateway state; it publishes the reproduction's verdict beside the record so a FAIL can be acted
on by whoever owns the certificate. Clock: the `cot_positioning_flow` hourly leg calls `run`
after its own pass (the row it was written for is that leg's family's input change).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent
CONFIG = BASE / "research" / "certificate_rechecks.json"
OUT = BASE / "reports" / "CERTIFICATE_RECHECKS.json"
GAUNTLET = BASE / "scripts" / "external_gauntlet.py"

REQUIRED = "RECHECK_REQUIRED"
CLEARS = "RECHECKED_CLEARS"
FAILS = "RECHECKED_FAILS"
UNMEASURED = "RECHECKED_UNMEASURED"
#: Seconds between reproduction attempts while a row has no report (a deferral or a cell missing
#: from the docket must not re-run the sealed gauntlet every hour).
RETRY_S = 6 * 3600
#: One cell through the ten gates; the sweep's own measured peak is minutes, not hours.
REPRO_TIMEOUT_S = 900.0


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def rows(config: Path | None = None) -> list[dict[str, Any]]:
    doc = _read(config or CONFIG)
    got = (doc or {}).get("rechecks") if isinstance(doc, dict) else None
    return [r for r in (got or []) if isinstance(r, dict) and r.get("id") and r.get("only")
            and r.get("report_to")]


def _report_path(row: dict[str, Any]) -> Path:
    p = Path(str(row["report_to"]))
    return p if p.is_absolute() else BASE / p


def verdict(report: dict[str, Any], only: str) -> dict[str, Any]:
    """The reproduction's verdicts on cells matching `only`, and the row's status from them."""
    result = report.get("result") if isinstance(report.get("result"), dict) else {}
    vs = [v for v in (result.get("verdicts") or []) if isinstance(v, dict)
          and only in str(v.get("cell") or v.get("key") or only)]
    measured = [v for v in vs if not v.get("unmeasured")]
    if not measured:
        status = UNMEASURED
    elif all(v.get("passed") for v in measured):
        status = CLEARS
    else:
        status = FAILS
    return {"status": status, "reproduced_at": report.get("reproduced_at"),
            "n_verdicts": len(vs), "n_measured": len(measured),
            "passed": sum(1 for v in measured if v.get("passed")),
            "failed_gates": sorted({str(v.get("terminal_gate") or "?") for v in measured
                                    if not v.get("passed")})}


def _attempt(row: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    target = _report_path(row)
    cmd = [sys.executable, str(GAUNTLET), "--only", str(row["only"]), "--report-to", str(target)]
    started = time.monotonic()
    try:
        r = subprocess.run(cmd, cwd=str(BASE), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout_s, check=False)
        rc: int | str = r.returncode
        tail = ((r.stdout or "").strip().splitlines()[-6:]
                + (r.stderr or "").strip().splitlines()[-3:])
    except subprocess.TimeoutExpired:
        rc, tail = "TIMEOUT", [f"no report within {timeout_s:g}s"]
    except OSError as exc:
        rc, tail = "OSERROR", [f"{type(exc).__name__}: {exc}"[:300]]
    return {"at": _now().isoformat(timespec="seconds"), "rc": rc,
            "elapsed_s": round(time.monotonic() - started, 1), "tail": tail,
            "command": " ".join(cmd[1:])}


def run(*, timeout_s: float = REPRO_TIMEOUT_S, dry_run: bool = False,
        config: Path | None = None, out: Path | None = None,
        attempt=None) -> dict[str, Any]:
    """One pass over every configured re-check. `attempt` is the reproduction call (tests)."""
    target = out or OUT
    got = _read(target)
    prior = got if isinstance(got, dict) else {}
    before = {str(r.get("id")): r for r in (prior or {}).get("rechecks") or []
              if isinstance(r, dict)}
    now = _now()
    published: list[dict[str, Any]] = []
    for row in rows(config):
        rid = str(row["id"])
        prev = before.get(rid) or {}
        entry: dict[str, Any] = {k: row.get(k) for k in ("id", "sleeve", "only", "report_to",
                                                         "reason", "opened", "decision")}
        entry["attempts"] = list(prev.get("attempts") or [])[-5:]
        rep = _report_path(row)
        if not rep.exists() and not dry_run:
            last = entry["attempts"][-1]["at"] if entry["attempts"] else None
            due = last is None or (now - datetime.fromisoformat(last)).total_seconds() >= RETRY_S
            if due:
                entry["attempts"] = (entry["attempts"]
                                     + [(attempt or _attempt)(row, timeout_s)])[-5:]
        doc = _read(rep) if rep.exists() else None
        if isinstance(doc, dict):
            entry.update(verdict(doc, str(row["only"])))
            entry["why"] = "the reproduction reported; this row is closed"
        else:
            entry["status"] = REQUIRED
            entry["why"] = ("no reproduction report yet: the certificate was judged on inputs "
                            "that have since changed, and is unconfirmed until the sealed "
                            "gauntlet re-judges it (reproduction mode, no certificate written)")
        published.append(entry)
    doc_out = {"at": now.isoformat(timespec="seconds"),
               "organ": "desks/mt5/research/certificate_recheck.py",
               "rule": ("a row is RECHECK_REQUIRED until its reproduction report exists; the "
                        "reproduction runs at most once per RETRY_S while it is missing and never "
                        "again once it reports; nothing here edits a certificate"),
               "n_required": sum(1 for e in published if e["status"] == REQUIRED),
               "rechecks": published}
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc_out, indent=1, default=str), "utf-8")
        tmp.replace(target)
    return doc_out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--status", action="store_true", help="read only: run no reproduction")
    ap.add_argument("--timeout-s", type=float, default=REPRO_TIMEOUT_S)
    a = ap.parse_args(argv)
    doc = run(timeout_s=a.timeout_s, dry_run=a.status)
    for e in doc["rechecks"]:
        print(f"certificate_recheck: {e['id']}: {e['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
