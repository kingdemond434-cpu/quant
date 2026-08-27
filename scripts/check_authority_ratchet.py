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
import os
import sys
import tempfile
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from libs.ops.canon_lease import hold
from libs.ops.repair_invoke import request_repair

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
FLOORS = ROOT / "data" / "authority_ratchet.json"
ALARM = ROOT / "data" / "AUTHORITY_ALARM.txt"
AUTHORITY_FILE = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
CANON_FILE = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"

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
    # SLEEVE IDENTITIES THAT ARE ACTUALLY PRE-REGISTRATIONS OF A VENUE. Counted by schema, not by
    # row: an hourly sync reverted this file to the desk box's stale copy TWICE during the fix
    # that landed the venue schema (2026-08-26, measured -- the reverted rows carried the old
    # cost_hash, the old data_venue and no schema at all), and a row count would not have moved,
    # so nothing would have noticed. A fall here means forward clocks silently went back to
    # identities frozen on a RETRIEVAL ROUTE, which is the state where no clock survives two
    # consecutive runs and nothing can ever reach promotion.
    "sleeve_identity_schema": (DESK / "data" / "sleeve_registry.json",
                               lambda d: sum(1 for v in (d.get("sleeves") or {}).values()
                                             if v.get("identity_schema"))),
}
#: A revocation must SAY it revoked. Any of these in the artifact excuses a fall.
REVOCATION_KEYS = ("revoked", "revocation", "retired_certificates", "revoked_at")


def read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _atomic_copy(source: Path, target: Path) -> None:
    """Copy a JSON authority artifact without exposing readers to a partial file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(source.read_bytes())
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, target)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(name)


def restore_authority() -> str | None:
    """Restore a silently shrunken authority file from its known-good canon copy.

    Detection alone left every production consumer reading the degraded authority file. A
    smaller authority is an interrupted/bad-writer state unless it carries an explicit
    revocation record; in that state the canon file is the recovery source by definition.
    """
    auth, canon = read(AUTHORITY_FILE), read(CANON_FILE)
    if not isinstance(auth, dict) or not isinstance(canon, dict):
        return None
    a_rows = auth.get("survivors") or {}
    c_rows = canon.get("survivors") or {}
    a_par = sum(1 for v in a_rows.values() if (v.get("shadow_spec") or {}).get("params"))
    c_par = sum(1 for v in c_rows.values() if (v.get("shadow_spec") or {}).get("params"))
    degraded = len(a_rows) < len(c_rows) or (len(a_rows) == len(c_rows) and a_par < c_par)
    explicitly_revoked = any(auth.get(key) for key in REVOCATION_KEYS)
    if not degraded or explicitly_revoked:
        return None
    artifact = "desks/mt5/reports/UNIVERSAL_SURVIVORS.json"
    with hold(artifact, "authority-ratchet"):
        _atomic_copy(CANON_FILE, AUTHORITY_FILE)
    return (f"authority restored from canon: {len(a_rows)} certs/{a_par} with params -> "
            f"{len(c_rows)}/{c_par}; no explicit revocation was present")


def heal_canon() -> str | None:
    """Canon may never be WORSE than the authority file. Restore it when it is.

    An alarm was not enough. Measured twice on 2026-08-26: canon went 21 certificates (15
    carrying their certified params) back to 14 with none, inside an automated commit, while the
    authority file stayed correct -- so the desk's restore-source was the degraded copy and the
    next reader would have enrolled 5 clocks instead of 15. Since canon exists purely as the
    known-good copy OF the authority file, "authority is strictly better" is a contradiction that
    can only be resolved one way, and resolving it needs no knowledge of which writer did it.

    Strictly better means: more certificates, or the same number with more of them carrying the
    params that make them runnable. Anything else is left alone -- this heals, it never overwrites
    a canon that is ahead.
    """
    auth, canon = read(AUTHORITY_FILE), read(CANON_FILE)
    if not isinstance(auth, dict) or not isinstance(canon, dict):
        return None
    a_rows = auth.get("survivors") or {}
    c_rows = canon.get("survivors") or {}
    a_par = sum(1 for v in a_rows.values() if (v.get("shadow_spec") or {}).get("params"))
    c_par = sum(1 for v in c_rows.values() if (v.get("shadow_spec") or {}).get("params"))
    if len(a_rows) > len(c_rows) or (len(a_rows) == len(c_rows) and a_par > c_par):
        artifact = "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json"
        with hold(artifact, "authority-ratchet"):
            _atomic_copy(AUTHORITY_FILE, CANON_FILE)
        return (f"canon healed from the authority file: {len(c_rows)} certs/{c_par} with params "
                f"-> {len(a_rows)}/{a_par}. Canon is the known-good COPY of authority; it being "
                f"behind is a contradiction, not a state to preserve.")
    return None


def main() -> int:
    now = datetime.now(tz=UTC)
    healed = heal_canon()
    if healed:
        print(f"authority ratchet: {healed}")
    restored = restore_authority()
    if restored:
        print(f"authority ratchet: {restored}")
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
        except Exception:
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
    request_repair("authority-ratchet breach")
    return 1


if __name__ == "__main__":
    sys.exit(main())
