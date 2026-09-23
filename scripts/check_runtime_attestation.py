#!/usr/bin/env python3
"""THE RUNTIME-ATTESTATION FENCE: the committed attestation is fresh, and it is about ONE host.

    python scripts/check_runtime_attestation.py [--require-state] [--json]

Two failures, and only two, because this fence guards the evidence rather than the desk:

  * STALE. The attestation is older than its own cadence (`runtime_attestation.MAX_SILENCE_S`).
    A committed file that says what ran is worse than no file at all once it is quietly out of
    date: it reads like current runtime state and is a photograph of a machine's past. Judged
    ONLY on the host the document names -- a checkout elsewhere is holding a report ABOUT that
    host, and its age there is the box's business, not the reader's.
  * HOST DRIFT. The document claims one host and describes another: `attests_to_host` disagreeing
    with `host.hostname`, or the file having been written on a machine other than the one it
    names. That is the specific lie this whole organ exists to make impossible, so it fails
    EVERYWHERE -- in CI, in a fresh clone, on either box -- because it is a fact about the
    document's own internals and needs no desk state to judge.

STATE FENCE. On any machine that is not the attesting host the freshness half reads UNMEASURED
and passes (L1.28a): the reader cannot re-measure a box they are not on. `--require-state` (the
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
    if age is not None and age > ra.MAX_SILENCE_S and out["on_attesting_host"]:
        out["failures"].append(
            f"stale on its own host: attested {age / 3600:.1f}h ago, past its "
            f"{ra.MAX_SILENCE_S / 3600:.1f}h max silence -- the hourly leg "
            f"`runtime_attestation` is not running here")
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
          + ("" if v["on_attesting_host"] else
             f" -- this machine is {v['this_host']}, so its freshness is UNMEASURED here"))
    failures = list(v["failures"])
    if a.require_state and not v["on_attesting_host"]:
        failures.append(f"--require-state on {v['this_host']} but the attestation describes "
                        f"{v['attests_to_host']}: this host publishes no attestation of its own")
    if a.require_state and v["age_s"] is not None and v["age_s"] > v["max_silence_s"] \
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
