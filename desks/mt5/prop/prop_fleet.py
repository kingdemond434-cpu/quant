"""PROP FLEET -- the venue reader or the sleeve executor for every ADDITIONAL prop account.

WHY (zuck 2026-11-03 16:37Z, via the coordinator): run the same certified strategies on several
prop challenges at once -- two to four firms -- each sized to its own account's rules and phase.
The legacy FTMO account keeps its own tasks (MT5-FTMO-VenueReader, MT5-FTMO-Executor) untouched;
every other account registered in data/prop_accounts.json (`mt5desk.prop_accounts`) is run here,
so the box's task names stay static however many accounts the principal adds.

ONE PROCESS PER ACCOUNT. MetaTrader5 attaches one terminal per Python process, so each account is a
child process (`prop/ftmo_venue_reader.py --account <id>` or `prop/ftmo_executor.py --account
<id>`) with its own terminal, declaration and files. Children run in parallel; one that hangs is
killed at CHILD_TIMEOUT_S and the others are unaffected; one account's failure never blocks another's.

WHAT IT NEVER DOES: open an account, arm one, or touch the legacy account. A registry row that
fails validation is refused by `prop_accounts.load` and listed in the run report. An account with
"enabled": false still has its reader run and its executor run unarmed (positions managed, book
published for the opposite-side fence), exactly as the executor treats it.

    python prop/prop_fleet.py --role reader      (MT5-Prop-VenueReaders, every 5 minutes)
    python prop/prop_fleet.py --role executor    (MT5-Prop-Executors, every 5 minutes)
Report: reports/prop/FLEET_<ROLE>.json.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

SCRIPTS = {"reader": DESK / "prop" / "ftmo_venue_reader.py",
           "executor": DESK / "prop" / "ftmo_executor.py"}
#: A child is killed only when it is plainly hung: a reader pass is under a minute and an
#: executor pass a few H1 reads and at most one order per sleeve. A kill at a short limit could
#: land between order_send and the executor's state write (audit of 580b6f99), so the limit is far
#: above any healthy pass, and the children run IN PARALLEL (one terminal each), so N accounts
#: take as long as the slowest one, never N passes back to back.
CHILD_TIMEOUT_S = 600
REPORTS = DESK / "reports" / "prop"


def accounts(data: Path | None = None) -> tuple[list[Any], list[str]]:
    """(the non-legacy registered accounts, the registry's refusals)."""
    from mt5desk import prop_accounts as _pa
    accts, errors = _pa.load(data or DESK / "data")
    return [a for a in accts if not a.legacy], errors


def run_role(role: str, *, popen: Any = subprocess.Popen,
             data: Path | None = None) -> dict[str, Any]:
    accts, errors = accounts(data)
    started = datetime.now(tz=UTC)
    procs: list[tuple[Any, Any]] = []
    rows = []
    for a in accts:
        cmd = [sys.executable, str(SCRIPTS[role]), "--account", a.id]
        try:
            procs.append((a, popen(cmd, cwd=str(DESK), stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)))
        except OSError as exc:
            rows.append({"account": a.id, "firm": a.firm, "program": a.program,
                         "enabled": a.enabled, "rc": None,
                         "tail": f"not started ({type(exc).__name__}: {exc})"})
    for a, proc in procs:
        left = max(1.0, CHILD_TIMEOUT_S - (datetime.now(tz=UTC) - started).total_seconds())
        try:
            out, _ = proc.communicate(timeout=left)
            rc, tail = proc.returncode, (out or "")[-800:]
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _ = proc.communicate()
            rc, tail = None, f"killed after {CHILD_TIMEOUT_S}s (hung); " + (out or "")[-600:]
        rows.append({"account": a.id, "firm": a.firm, "program": a.program,
                     "enabled": a.enabled, "rc": rc,
                     "seconds": round((datetime.now(tz=UTC) - started).total_seconds(), 1),
                     "tail": tail.strip()})
    failed = [r["account"] for r in rows if r["rc"] != 0]
    return {"generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "role": role,
            "status": "OK" if not failed else "CHILD_FAILED", "failed": failed,
            "accounts": rows, "registry_errors": errors}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--role", choices=sorted(SCRIPTS), required=True)
    a = ap.parse_args(argv)
    doc = run_role(a.role)
    from prop.ftmo_follower import _atomic_write
    _atomic_write(REPORTS / f"FLEET_{a.role.upper()}.json", json.dumps(doc, indent=1))
    print(f"prop_fleet[{a.role}]: {len(doc['accounts'])} account(s), status {doc['status']}"
          + (f", registry refusals {doc['registry_errors']}" if doc["registry_errors"] else ""))
    return 0 if doc["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
