#!/usr/bin/env python3
"""THE RUNTIME-ATTESTATION FENCE: the committed attestation is fresh, and it is about ONE host.

    python scripts/check_runtime_attestation.py [--require-state] [--json]

Two failures, and only two, because this fence guards the evidence rather than the desk:

  * STALE. The attestation is older than its own cadence (`runtime_attestation.MAX_SILENCE_S`).
    A committed file that says what ran is worse than no file at all once it is quietly out of
    date: it reads like current runtime state and is a photograph of a machine's past. Judged
    ONLY on the TRADING BOX, and only when the document is the box's own: this machine is the
    host the document names AND that host's measured role (`host.role`, derived by
    `runtime_attestation.host_identity` from the gateway's heartbeat) is `trading_host`. Anywhere
    else -- a checkout holding a report ABOUT the box, or a cloud container (hostname `vm`) that
    attested itself as `non_trading_host` -- the age is printed as UNMEASURED with the age and the
    host, never as a clean verdict. Measured 2026-09-30: judging it on any attesting host made
    every PR's law gate red ~2h after the last cloud re-attestation, because every cloud
    container is named `vm` and so "was" the attesting host.
    STRUCTURALLY, since #151 stamps `host.desk_host` on every full pass: an attestation stamped
    `desk_host: false` is NOT A DESK ATTESTATION. It was measured on a machine that is not a
    declared desk host, so its age says nothing about the box's hourly leg: its staleness is
    UNMEASURED everywhere (even under `--require-state`) and it neither sets nor is judged
    against a ratchet floor. `desk_host: true` is judged exactly as above; a legacy stamp with no
    `desk_host` key keeps the hostname-and-role rule.
  * HOST DRIFT. The document claims one host and describes another: `attests_to_host` disagreeing
    with `host.hostname`, or the file having been written on a machine other than the one it
    names. That is the specific lie this whole organ exists to make impossible, so it fails
    EVERYWHERE -- in CI, in a fresh clone, on either box -- because it is a fact about the
    document's own internals and needs no desk state to judge.

STATE FENCE. On any machine that is not the attesting trading box the freshness half reads
UNMEASURED and passes (L1.28a): the reader cannot re-measure a box they are not on. `--require-state` (the
box's hourly law gate passes it) makes an absent or stale attestation a failure there, which is
where an absent one IS a defect.

Exit: 2 on host drift, or on staleness where staleness is judgeable; 0 clean.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT / "desks" / "mt5" / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def measure(root: Path | None = None) -> dict[str, Any]:
    """The verdict, derived from the committed document alone -- no organ re-run, no desk state.

    A fence that regenerated the artifact it judges could never catch a stopped clock: it would
    write a fresh file and then pass itself. This one reads what is committed, which is exactly
    what a reviewer on GitHub reads.
    """
    import runtime_attestation as ra  # type: ignore[import-not-found]

    base = Path(root or ROOT)
    paths = ra.Paths.at(base)
    here = socket.gethostname()
    out: dict[str, Any] = {
        "path": paths.out_json.relative_to(base).as_posix(),
        "this_host": here,
        "present": paths.out_json.is_file(),
        "attests_to_host": ra.UNMEASURED,
        "generated_at": ra.UNMEASURED,
        "age_s": None,
        "max_silence_s": ra.MAX_SILENCE_S,
        "on_attesting_host": False,
        "age_judged": False,
        "desk_host": ra.UNMEASURED,
        "desk_attestation": None,
        "staleness": ra.UNMEASURED,
        "failures": [],
        "census": {},
    }
    doc = ra._read_json(paths.out_json, max_bytes=ra.MAX_JSON_BYTES * 8)
    if doc is None:
        return out
    claimed = str(doc.get("attests_to_host") or ra.UNMEASURED)
    host = doc.get("host") if isinstance(doc.get("host"), dict) else {}
    measured = str(host.get("hostname") or ra.UNMEASURED)
    out["attests_to_host"] = claimed
    out["measured_hostname"] = measured
    out["role"] = str(host.get("role") or ra.UNMEASURED)
    out["generated_at"] = str(doc.get("generated_at") or ra.UNMEASURED)
    out["census"] = doc.get("census") if isinstance(doc.get("census"), dict) else {}
    out["organs"] = len(doc.get("organs") or [])
    stamp = ra.desk_stamp(doc)
    out["desk_host"] = "legacy (no desk_host stamp)" if stamp is None else stamp
    if stamp is not None and not isinstance(stamp, bool):
        out["failures"].append(f"host.desk_host is {stamp!r}: the stamp must be true or false")
    # None = legacy (the pre-#151 rule applies), False = measured off every declared desk host.
    out["desk_attestation"] = None if stamp is None else stamp is True
    non_desk = stamp is False

    if claimed == ra.UNMEASURED or measured == ra.UNMEASURED:
        out["failures"].append("the attestation names no host: it must say which machine it "
                               "measured or it is describing none")
    elif claimed != measured:
        out["failures"].append(f"host drift: the document claims host {claimed!r} while the "
                               f"measurement inside it was taken on {measured!r}")
    if not str(host.get("role_evidence") or "").strip():
        out["failures"].append("the attestation's role is asserted, not measured: no "
                               "role_evidence")

    out["on_attesting_host"] = (measured != ra.UNMEASURED and measured == here)
    try:
        gen = datetime.fromisoformat(out["generated_at"])
        age = (datetime.now(tz=UTC) - gen).total_seconds()
        out["age_s"] = int(age)
    except ValueError:
        out["failures"].append(f"generated_at {out['generated_at']!r} is not a timestamp")
        age = None
    # THE AGE IS JUDGED ON THE BOX ONLY. Structural checks above and the ratchet below fail
    # everywhere; wall-clock staleness is a fact about the box's hourly leg, so it is judged only
    # where that leg is supposed to run: on the host the document names, when that host measured
    # itself as the trading box. Elsewhere it is UNMEASURED (L1.28a), printed with age and host.
    out["age_judged"] = bool(not non_desk and out["on_attesting_host"]
                             and out["role"] == "trading_host")
    if age is None:
        out["staleness"] = f"{ra.UNMEASURED}: no readable generated_at"
    elif non_desk:
        out["staleness"] = (
            f"{ra.UNMEASURED}: not a desk attestation -- stamped desk_host: false on host "
            f"{measured}, attested {age / 3600:.1f}h ago; its age is not judged anywhere")
    elif not out["age_judged"]:
        out["staleness"] = (
            f"{ra.UNMEASURED}: attested {age / 3600:.1f}h ago on host {measured} "
            f"(role {out['role']}); this machine is {here} -- wall-clock staleness is judged "
            f"only on the trading box that owns the organs")
    elif age > ra.MAX_SILENCE_S:
        out["staleness"] = f"STALE: {age / 3600:.1f}h > {ra.MAX_SILENCE_S / 3600:.1f}h"
    else:
        out["staleness"] = f"fresh: {age / 3600:.1f}h <= {ra.MAX_SILENCE_S / 3600:.1f}h"
    if age is not None and age > ra.MAX_SILENCE_S and out["age_judged"]:
        out["failures"].append(
            f"stale on its own host: attested {age / 3600:.1f}h ago, past its "
            f"{ra.MAX_SILENCE_S / 3600:.1f}h max silence -- the hourly leg "
            f"`runtime_attestation` is not running here")

    # THE RATCHET. STALE, MISSING and NEVER may only fall on a given host (the principal's order,
    # 2026-09-23: "all organs must be switched to LIVE" is a floor, not a photograph). The floor
    # is per host because the two boxes run different halves of the desk -- the build box disables
    # every MT5 task by design, so its census is not the trading box's and neither may judge the
    # other. A host with no floor yet is UNMEASURED and sets one on its next attestation pass,
    # which is a measurement, not a pass by default.
    rdoc = ra._read_json(paths.ratchet, max_bytes=ra.MAX_JSON_BYTES) or {}
    _hosts = rdoc.get("hosts")
    floors: dict[str, Any] = _hosts if isinstance(_hosts, dict) else {}
    _floor = floors.get(claimed)
    floor: dict[str, Any] | None = _floor if isinstance(_floor, dict) else None
    out["ratchet_floor"] = floor or ra.UNMEASURED
    out["ratchet_regressions"] = []
    if non_desk:
        out["ratchet_floor"] = ra.UNMEASURED
        out["ratchet"] = (f"{ra.UNMEASURED}: not a desk attestation (desk_host: false on "
                          f"{claimed}) -- it sets no floor and is judged against none")
    elif floor is None:
        out["ratchet"] = (f"{ra.UNMEASURED}: no floor recorded for {claimed} -- the next "
                          f"attestation pass on that host sets one")
    else:
        for k in ra.RATCHET_KEYS:
            was, now_n = floor.get(k), out["census"].get(k)
            if not isinstance(was, int) or not isinstance(now_n, int):
                continue
            if now_n > was:
                out["ratchet_regressions"].append(f"{k} rose {was} -> {now_n}")
        if out["ratchet_regressions"]:
            out["failures"].append(
                "RATCHET BROKEN on " + str(claimed) + ": "
                + "; ".join(out["ratchet_regressions"])
                + f" (floor set {floor.get('at', ra.UNMEASURED)} at "
                f"{str(floor.get('git_sha', ra.UNMEASURED))[:12]}). These counts may only fall: "
                "an organ that stopped, an artifact that vanished or a clock that was removed "
                "is a defect, not a new baseline. Repair the organ through "
                "libs/ops/control_plane, or RETIRE it with a reason in "
                "docs/research/retirements.jsonl so it leaves the census honestly.")
        else:
            out["ratchet"] = "held: " + ", ".join(
                f"{k} {out['census'].get(k, ra.UNMEASURED)}<={floor.get(k, ra.UNMEASURED)}"
                for k in ra.RATCHET_KEYS)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--require-state", action="store_true",
                    help="an absent or stale attestation is a failure (the box's law gate)")
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    v = measure(a.root)
    if a.json:
        print(json.dumps(v, indent=1, default=str))

    if not v["present"]:
        print(f"runtime attestation: UNMEASURED -- {v['path']} is not in this tree"
              + (" (FAILED: --require-state)" if a.require_state else ""))
        return 2 if a.require_state else 0

    age_h = "UNMEASURED" if v["age_s"] is None else f"{v['age_s'] / 3600:.1f}h"
    c = v["census"]
    print(f"runtime attestation: host {v['attests_to_host']} ({v.get('role')}), "
          f"{v.get('organs', 0)} organ(s) LIVE {c.get('LIVE', '?')} / STALE {c.get('STALE', '?')} "
          f"/ MISSING {c.get('MISSING', '?')} / NEVER {c.get('NEVER', '?')}, attested {age_h} ago"
          + ("" if v["age_judged"] else
             " -- not a desk attestation (desk_host: false), so its freshness is UNMEASURED"
             if v.get("desk_host") is False else
             f" -- this machine is {v['this_host']}, so its freshness is UNMEASURED here"))
    print(f"   staleness: {v['staleness']}")
    print("   ratchet: " + str(v.get("ratchet")
                               or "; ".join(v.get("ratchet_regressions") or [])
                               or "UNMEASURED (the document carries no census to ratchet)"))
    failures = list(v["failures"])
    if a.require_state and not v["on_attesting_host"]:
        failures.append(f"--require-state on {v['this_host']} but the attestation describes "
                        f"{v['attests_to_host']}: this host publishes no attestation of its own")
    if a.require_state and v["age_s"] is not None and v["age_s"] > v["max_silence_s"] \
            and v.get("desk_host") is not False \
            and not any("stale on its own host" in f for f in failures):
        failures.append(f"stale: attested {v['age_s'] / 3600:.1f}h ago, past "
                        f"{v['max_silence_s'] / 3600:.1f}h")
    for f in failures:
        print(f"   FAILED {f}")
    if failures:
        print("   re-measure on the box: python desks/mt5/research/runtime_attestation.py "
              "--once --budget-s 180")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
