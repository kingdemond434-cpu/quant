#!/usr/bin/env python3
"""AUTHORITY RATCHET -- evidence counts may not silently fall (principal 2026-08-26:
"these mistakes/regressions should always be noticed and fixed immediately").

THE REGRESSION THIS EXISTS FOR, measured tonight. A scheduled certifier rewrote
UNIVERSAL_SURVIVORS.json from n=1 to n=0 at 00:45:16 -- destroying the desk's only earned
certificate -- with exit code 0, no alarm, and no log line saying anything had been lost. It
was found by a human reading the file by hand hours later. Every existing fence looked at the
wrong thing: the money-path fence watches CODE, the P0 watch watches liveness, max_audit watches
structure. Nothing watched the COUNT OF EARNED EVIDENCE.

THE RULE. Earned evidence is a RATCHET: certificates, survivors and cohort members may rise
freely, and may only fall through an explicit, recorded revocation. A fall with no revocation
record is a data-loss event, full stop -- it does not matter whether the writer exited 0, and
it does not matter that a later run might re-derive it. Re-running a gauntlet is not the same
as revoking a pass (L1.28a: unmeasured is never a verdict).

Fires the P0 repair path on breach, so detection is minutes rather than "whenever somebody
looks". Floors live in data/authority_ratchet.json and rise on their own.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
FLOORS = ROOT / "data" / "authority_ratchet.json"
ALARM = ROOT / "data" / "AUTHORITY_ALARM.txt"

#: artifact -> (path, how to count it). Each is EARNED evidence that time and compute produced.
WATCH = {
    "certificates": (DESK / "reports" / "UNIVERSAL_SURVIVORS.json",
                     lambda d: len(d.get("survivors") or {})),
    "canon_certificates": (DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json",
                           lambda d: len(d.get("survivors") or {})),
    "cohort_members": (DESK / "data" / "intelligence" / "cohorts" / "cohort_registry.json",
                       lambda d: len(d) if isinstance(d, dict) else 0),
    "research_queue": (DESK / "data" / "research_queue.json",
                       lambda d: len(d) if isinstance(d, list) else 0),
    "source_populations": (DESK / "data" / "intelligence" / "source_populations.json",
                           lambda d: len(d.get("populations") or {})),
}
#: A revocation must SAY it revoked. Any of these in the artifact excuses a fall.
REVOCATION_KEYS = ("revoked", "revocation", "retired_certificates", "revoked_at")


def read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def main() -> int:
    now = datetime.now(tz=UTC)
    floors = read(FLOORS) or {"note": "earned-evidence floors; rise freely, fall only on an "
                                      "explicit recorded revocation", "counts": {}}
    breaches: list[str] = []
    counts: dict[str, int] = {}

    for name, (path, counter) in WATCH.items():
        data = read(path)
        if data is None:
            # Absent is not zero: a missing file is its own alarm only if we HAD a floor.
            if floors["counts"].get(name, 0) > 0:
                breaches.append(f"{name}: artifact MISSING ({path.name}) while the floor stands "
                                f"at {floors['counts'][name]} -- earned evidence has vanished, "
                                f"not merely gone unmeasured")
            continue
        try:
            n = int(counter(data))
        except Exception:                                                # noqa: BLE001
            continue
        counts[name] = n
        floor = int(floors["counts"].get(name, 0))
        if n < floor:
            revoked = any(k in json.dumps(data)[:20000] for k in REVOCATION_KEYS)
            if revoked:
                floors["counts"][name] = n          # an explicit revocation lowers the floor
                continue
            breaches.append(
                f"{name}: {n} < floor {floor} in {path.name} -- {floor - n} piece(s) of EARNED "
                f"evidence lost with no revocation record. Re-running a gauntlet is not "
                f"revoking a pass; restore from the canon copy or git before the next writer "
                f"overwrites it again.")
        else:
            floors["counts"][name] = n              # ratchet up

    floors["checked_at"] = now.isoformat(timespec="seconds")
    floors["last_counts"] = counts
    FLOORS.write_text(json.dumps(floors, indent=1), "utf-8")

    if not breaches:
        if ALARM.exists():
            ALARM.unlink()
        print(f"authority ratchet: ok {counts}")
        return 0

    body = (f"AUTHORITY RATCHET BREACH {now.isoformat(timespec='seconds')}\n\n"
            + "\n".join(f"  - {b}" for b in breaches) + "\n")
    ALARM.write_text(body, "utf-8")
    print("AUTHORITY RATCHET BREACH\n" + body)
    # Fire the repair organ immediately -- this class is data loss, not a queue item.
    subprocess.Popen(["systemctl", "--user", "start", "--no-block",
                      "quant-gap-wirer.service"])
    return 1


if __name__ == "__main__":
    sys.exit(main())
