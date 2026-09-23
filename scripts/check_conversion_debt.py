#!/usr/bin/env python3
"""THE CONVERSION-DEBT RATCHET -- every mined row ends as a testable cell or a reasoned refusal.

THE HARSH RULE (principal's standing order 2026-09-23, LAWS 5b). "Permanently maximise 100
percent conversion to testable cells of all minings ... we always squeeze the life out of
everything we get and have." A mined row that is neither a gauntlet cell nor a recorded, reasoned
refusal is a DEFECT WITH AN OWNER, and the count of them is CONVERSION DEBT.

WHY A RATCHET AND NOT A THRESHOLD. The desk's coverage floors ratchet UP (L1.50) for exactly one
reason: a number a session may re-choose is a number that drifts to whatever this session found
convenient. Debt is the same quantity with the sign flipped, so it ratchets DOWN. Once the desk
has proved it can hold 5,578 unconverted rows it may never again hold 5,579 -- and the day it
reaches 4,000 that becomes the new ceiling, automatically, with no session's permission.

THE CEILING CANNOT BE RAISED, INCLUDING BY HAND. `data/conversion_debt_ratchet.json` carries both
the current ceiling and `lowest_ever`, and the EFFECTIVE ceiling is the minimum of the two. So an
edit that raises the file's ceiling changes nothing, and a fence that would otherwise be defeated
by one careless `json.dump` stays a fence. There is no `--force` and no environment override: the
only way past this gate is to convert the rows.

MEASURED WHERE IT MATTERS. The debt is counted in cheap SQL over the WHOLE registry population by
`conversion_maximiser.measure_debt` -- the same function the organ publishes -- in five named
components, so the fence and the organ can never disagree about what the number means:

    silent_discoveries   mined, never given any disposition at all
    unreasoned_blocks    BLOCKED with no reason -- a refusal nobody can audit
    donated_never_cell   donated to the docket, never offered to a judge
    untestable_queued    on the queue without the falsifier the contract requires (LAWS 5k)
    parked_past_grace    routed to an owner who never collected -- silence with extra steps

ABSENCE IS NEVER A CLEAN VERDICT (L1.28a). A machine with no registry reports UNMEASURED and
exits 1. That is a real answer -- "this checkout holds no registry to measure" -- and never a
pass. It is registered as a STATE fence for that reason, beside `check_ingestion_exploitation`.

    measure:  python scripts/check_conversion_debt.py --json
    ratchet:  data/conversion_debt_ratchet.json   (ceiling; may only fall)
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sqlite3
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

RATCHET = ROOT / "data" / "conversion_debt_ratchet.json"

#: How many passes of history the ratchet file keeps. Enough to see a drain from a plateau.
HISTORY = 60

UNMEASURED = "UNMEASURED"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True, default=str)
    try:
        os.replace(tmp, path)
    except PermissionError:                                              # pragma: no cover
        with contextlib.suppress(OSError):
            os.chmod(path, 0o644)
        os.replace(tmp, path)


def effective_ceiling(floor_doc: dict[str, Any]) -> int | None:
    """The ceiling this fence actually enforces: min(ceiling, lowest_ever).

    Both are read because a ratchet whose only record is its current value can be reset by one
    edit. The minimum of the pair is monotone by construction, so raising either number by hand
    is inert -- which is the whole point of writing the rule down as a fence instead of a habit.
    """
    vals = [int(v) for k in ("ceiling", "lowest_ever")
            if isinstance(v := floor_doc.get(k), (int, float))]
    return min(vals) if vals else None


def measure(registry_path: Path | None = None,
            ratchet_path: Path | None = None) -> dict[str, Any]:
    """Measure the debt, compare it to the ratchet, and lower the ratchet when it has fallen."""
    import conversion_maximiser as CM  # type: ignore[import-not-found]

    from libs.moat import registry as R

    floor_path = ratchet_path or RATCHET
    floor_doc = _read(floor_path)
    ceiling = effective_ceiling(floor_doc)
    db = Path(registry_path) if registry_path is not None else Path(R.path())
    out: dict[str, Any] = {"measured_at": _now(), "registry": str(db),
                           "ratchet_path": str(floor_path), "ceiling_before": ceiling,
                           "rule": CM.RULE}
    if not db.exists():
        out.update({"status": UNMEASURED, "rc": 1,
                    "why": f"no registry at {db} -- this checkout holds nothing to measure, "
                           "which is an absence of evidence and never a pass (L1.28a)"})
        return out
    try:
        conn = sqlite3.connect(str(db))
    except sqlite3.Error as exc:                                         # pragma: no cover
        out.update({"status": UNMEASURED, "rc": 1,
                    "why": f"the registry could not be opened ({type(exc).__name__}: {exc})"})
        return out
    try:
        debt = CM.measure_debt(conn)
        breadth = CM.measure_breadth(conn)
    finally:
        with contextlib.suppress(sqlite3.Error):
            conn.close()
    out["debt"] = debt
    out["breadth"] = breadth
    # THE VERDICTS THAT NEVER CROSSED (2026-09-23). Conversion does not end at a testable cell: a
    # cell the gauntlet has JUDGED whose verdict never reached the registry is converted work the
    # desk cannot cash, and it reads as zero in exactly the place that matters -- cells_judged per
    # source, per pack, per region. Measured: 3,368 verdicts on disk, no `gate_verdicts` cursor
    # key at all since the 2026-09-17 restore, and nothing anywhere said so. So the receipt and
    # the lag are now fenced: a stream the sync knows about with no cursor key, or a verdict older
    # than one sync cycle still unpoured, fails this gate.
    # Measured only when this IS the desk's own registry (the law gate's call): a synthetic
    # registry handed in with --registry belongs to no desk, and the desk's verdict ledger says
    # nothing about it.
    backlog = (R.verdict_backlog() if registry_path is None else
               {"status": "NOT_THIS_REGISTRY",
                "why": f"--registry {db} is not the desk's registry ({R.path()}), so the desk's "
                       f"verdict ledger is not evidence about it"})
    out["verdict_backlog"] = backlog
    if backlog.get("status") == "BREACH":
        out.update({"status": "BREACH", "rc": 2, "ceiling_after": ceiling,
                    "why": f"the gate verdict ledger is ahead of the registry: "
                           f"{backlog.get('why')}. The organ is "
                           f"desks/mt5/research/registry_sync.py (hourly leg `registry_sync`) -> "
                           f"libs/moat/registry.sync_from_desk"})
        return out
    total = debt.get("total_debt")
    if total is None:
        out.update({"status": UNMEASURED, "rc": 1,
                    "why": "a debt component could not be counted, so the total is unmeasured: "
                           + "; ".join(f"{u['component']} ({u['why']})"
                                       for u in debt.get("unmeasured") or [])})
        return out
    total = int(total)
    out["total_debt"] = total
    if ceiling is None:
        out.update({"status": "SEEDED", "rc": 0, "ceiling_after": total,
                    "why": f"first measurement: the ratchet is seeded at today's debt ({total}) "
                           "so it can never grow from here"})
    elif total > ceiling:
        out.update({"status": "BREACH", "rc": 2, "ceiling_after": ceiling,
                    "why": f"conversion debt {total} is ABOVE the ratchet {ceiling}: "
                           f"{total - ceiling} rows were mined and left neither testable nor "
                           f"refused for a reason. The owner of the largest class is named in "
                           f"desks/mt5/reports/CONVERSION_MAXIMISER.json"})
    else:
        out.update({"status": "OK", "rc": 0, "ceiling_after": total,
                    "why": f"conversion debt {total} is at or below the ratchet {ceiling}; "
                           f"the ratchet falls to {total}"})
    return out


def _persist(verdict: dict[str, Any], ratchet_path: Path | None = None) -> None:
    """Record the pass. The ceiling only ever falls, and `lowest_ever` is never raised."""
    path = ratchet_path or RATCHET
    doc = _read(path)
    after = verdict.get("ceiling_after")
    if verdict.get("status") in ("SEEDED", "OK") and isinstance(after, int):
        prior = effective_ceiling(doc)
        doc["ceiling"] = after if prior is None else min(prior, after)
        doc["lowest_ever"] = doc["ceiling"]
    elif "ceiling" not in doc and isinstance(verdict.get("ceiling_before"), int):
        doc["ceiling"] = doc["lowest_ever"] = verdict["ceiling_before"]
    doc.setdefault("seeded_at", verdict.get("measured_at"))
    doc["measured_at"] = verdict.get("measured_at")
    doc["last_status"] = verdict.get("status")
    doc["last_total_debt"] = verdict.get("total_debt")
    doc["components"] = (verdict.get("debt") or {}).get("components")
    doc["effective_breadth"] = (verdict.get("breadth") or {}).get("effective_breadth")
    doc["rule"] = verdict.get("rule")
    doc["law"] = ("docs/LAWS.md 5b -- every mined row ends as a testable cell or a recorded, "
                  "reasoned refusal; the ratchet only ever falls and no organ may raise it")
    history = [h for h in (doc.get("history") or []) if isinstance(h, dict)]
    history.append({"at": verdict.get("measured_at"), "total_debt": verdict.get("total_debt"),
                    "ceiling": doc.get("ceiling"), "status": verdict.get("status")})
    doc["history"] = history[-HISTORY:]
    _write(path, doc)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--registry", type=Path, default=None)
    ap.add_argument("--ratchet", type=Path, default=None)
    ap.add_argument("--no-write", action="store_true",
                    help="measure without touching the ratchet file")
    a = ap.parse_args(argv)
    try:
        verdict = measure(a.registry, a.ratchet)
    except Exception as exc:                                             # pragma: no cover
        print(f"conversion debt: UNMEASURED -- {type(exc).__name__}: {exc}")
        return 1
    if not a.no_write:
        with contextlib.suppress(OSError):
            _persist(verdict, a.ratchet)
    if a.json:
        print(json.dumps(verdict, indent=1, default=str))
    status = verdict.get("status")
    total = verdict.get("total_debt")
    ceiling = verdict.get("ceiling_after", verdict.get("ceiling_before"))
    print(f"conversion debt: {status} -- debt {total}, ratchet {ceiling}; {verdict.get('why')}")
    if status in ("OK", "SEEDED"):
        comp = (verdict.get("debt") or {}).get("components") or {}
        if comp:
            worst = max(comp.items(), key=lambda kv: int(kv[1]))
            print(f"  largest debt component: {worst[0]} = {worst[1]}")
    return int(verdict.get("rc", 1))


if __name__ == "__main__":                                               # pragma: no cover
    raise SystemExit(main())
