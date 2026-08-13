#!/usr/bin/env python3
"""FREE-ROSTER CANARY (R0344) -- prove the degraded fallback is alive BEFORE the outage needs it.

THE PROMISE THIS ENFORCES. The NO-COST-DRIVEN-DEGRADATION corollary (principal 2026-07-20) says
the desk never CHOOSES a cheaper roster to save money, but an unfunded outage must not mean ZERO
external review: it "runs the strongest FREE fallback available and labels its output DEGRADED".
Measured 2026-08-01T16:58Z on a real run, that promise was FALSE. OpenRouter was unfunded
(-$0.59), the panel dropped to its 4 free seats, and ALL FOUR failed -- tencent HTTP 404 (dead
model id), cohere HTTP 400, nvidia-nano HTTP 400, nvidia KeyError('choices') (response shape
changed). 0/4 substantive, quorum failed, 26 files not credited as audited, and the desk had no
independent-review capability at all -- funded or not.

WHY A PASSIVE LOG READ CANNOT WORK, and this is the whole design. The free roster only RUNS when
the desk is unfunded. While funded, no free-roster run enters data/external_panel_log.jsonl, so a
check that reads the log learns nothing and goes quietly stale -- it would discover the dead
fallback during the outage it exists for, which is exactly the failure being fixed. The seats are
FREE, so exercising them costs nothing and there is no argument for not doing it. This canary
therefore PROBES: it asks each free seat a two-token question and counts who answers.

DAILY, NOT HOURLY, AND THE CADENCE IS PART OF THE MEASUREMENT (L1.28c). The binding ceiling here
is INFORMATION-ARRIVAL -- a model id dies when a catalog drifts, which is a weekly-scale event,
not an hourly one. It is also a RESOURCE ceiling pointing the same way: free-tier pools saturate,
that saturation is the desk's measured 400/429 class, and a canary hammering the pool would
BECOME the failure it is built to detect. A detector that causes its own positive is worse than
no detector.

WHAT IT CANNOT SEE, said out loud. This probe sends a tiny prompt, so it proves REACHABILITY --
the 404/400/KeyError class that killed all four seats -- and it CANNOT reproduce blank-on-large-
payload, the separate failure where a live seat returns an empty string to a ~40k-char dossier
(nvidia/nemotron-3-ultra-550b-a55b:free has blanked 3x that way). That half is measured by the
panel's own record_blank tally and reported here as evidence WITHOUT gating the verdict, because
it is read from history that may legitimately be empty. Two failure modes, two instruments; a
green canary means "the seats answer", never "the panel will succeed".

RETRY POLICY IS IMPORTED, NEVER RE-DECLARED. Free-tier 400/429 is transient pool saturation --
measured 2026-08-12, the identical seat flipped 400 at 03:36 and answered at 07:30 -- so a
single-shot probe would report DEAD on a flap, cry wolf, and get switched off (L1.43). This calls
run_external_panel._ask, so the canary and the panel share ONE retry policy by construction and
cannot drift into disagreeing about whether a seat is dead.

    python scripts/check_free_roster.py [--report-only] [--json] [--no-probe]
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.input_provenance import Inputs  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

#: The fallback roster. Box-local secrets: absent on a clean clone, which is UNCONFIGURED and
#: never OK -- "we could not look" and "we looked and it is fine" are opposite facts (L1.28a).
ROSTER = Path("data/secrets/llm_panel_free.json")
#: Real-run history. Read for the blank-under-load half only; never gates the verdict.
PANEL_LOG = Path("data/external_panel_log.jsonl")
OUT = _ROOT / "data/free_roster_canary.json"

#: Two tokens is all the question needs to be. The probe asks REACHABILITY, not capability, and a
#: long prompt would both cost the pool and blur the two.
_PROBE = "Reply with exactly one word: READY"
#: A seat "answered" if it returned ANY non-empty text. Deliberately the same bar the panel uses
#: to decide a seat counts (`"response" in r`) and to write its inbox, so a seat this canary calls
#: alive is a seat the panel would count. The panel's >=400-char SUBSTANTIVE bar is a different
#: question -- it grades an audit answer, and no two-token probe can be held to it.
_MIN_CHARS = 1
#: Short: a free seat that has not started answering in 90s is not going to carry a 40k dossier.
_TIMEOUT_S = 90.0

_PASSING = ("OK",)


def _probe_one(pv: dict[str, Any]) -> dict[str, Any]:
    """One seat -> {model, alive, chars|error}. Never raises: one dead seat is the measurement."""
    from scripts.run_external_panel import _ask
    model = str(pv.get("model", "?"))
    try:
        txt = _ask(str(pv["base_url"]), str(pv["key"]), model,
                   [{"role": "user", "content": _PROBE}], timeout=_TIMEOUT_S)
    except Exception as e:                       # 404 dead id / 400 payload / KeyError shape
        return {"model": model, "alive": False, "error": repr(e)[:200]}
    n = len(txt.strip())
    return {"model": model, "alive": n >= _MIN_CHARS, "chars": n,
            **({} if n >= _MIN_CHARS else {"error": "empty response"})}


def _blank_history() -> dict[str, Any]:
    """Per-seat blank tally from real panel runs -- the payload-size half this probe cannot see.

    Returns the tally, or an `unavailable` marker. NOT an empty dict on failure: {} would be
    indistinguishable from "no seat has ever blanked", which is the good news this evidence
    exists to withhold. Never gates the verdict -- it is history, and history may be honestly
    empty on a box that has not run a panel yet.
    """
    try:
        from scripts.build_audit_coverage import load
        tally = load().get("seat_blanks", {})
        return {k: int(v) for k, v in tally.items() if str(k).endswith(":free")}
    except Exception as e:
        return {"unavailable": repr(e)[:120]}


def build_report(*, probe: bool = True) -> dict[str, Any]:
    inp = Inputs(caller="check_free_roster.build_report")
    roster = inp.read_json(ROSTER, default=None, required=True)
    seats = list((roster or {}).get("providers", []))

    rep: dict[str, Any] = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "law": "R0344 / NO-COST-DRIVEN-DEGRADATION",
        "n_seats": len(seats),
        "probed": bool(probe),
        "seats": [],
        "n_alive": None,
        "blank_history": _blank_history(),
        "breaches": [],
        # L1.55: the inputs declared beside the numbers, plus the sibling flag. A verdict built
        # from an absent roster must never read as a measurement of a healthy one.
        "provenance": inp.block(),
        "measured": inp.measured(),
        "why": inp.why(),
    }

    if roster is None:
        rep["status"] = "UNCONFIGURED"
        rep["detail"] = (f"{ROSTER} is absent or unreadable -- this box cannot see the fallback "
                         "roster, so its health is UNMEASURED, which is not OK (L1.28a). On the "
                         "VPS this means the secrets file is gone; on a clean clone it is "
                         "expected and this fence belongs in the box gate, not CI.")
        rep["next_action"] = f"restore {ROSTER} on the box that runs the panel"
        return rep

    if not seats:
        rep["status"] = "EMPTY"
        rep["detail"] = ("the roster file exists but declares ZERO providers, so 'zero seats "
                         "answered' would be measured over nothing (vacuous denominator, L1.57). "
                         "The fallback does not exist rather than having failed -- a different "
                         "repair: configure seats, not fix them.")
        rep["next_action"] = "add free seat ids to the roster (see refresh_panel_roster.py)"
        rep["breaches"].append("free roster declares zero providers")
        return rep

    if not probe:
        rep["status"] = "NOT-PROBED"
        rep["detail"] = ("--no-probe: the roster was read but no seat was contacted, so liveness "
                         "is UNMEASURED. Reporting mode only; never a pass.")
        rep["next_action"] = "run without --no-probe on a box with egress"
        return rep

    with ThreadPoolExecutor(max_workers=min(8, len(seats))) as ex:
        rep["seats"] = list(ex.map(_probe_one, seats))
    alive = [s for s in rep["seats"] if s["alive"]]
    rep["n_alive"] = len(alive)

    if alive:
        rep["status"] = "OK"
        rep["detail"] = (f"{len(alive)}/{len(seats)} free seats answered -- the degraded fallback "
                         "can produce. This proves REACHABILITY only; blank-under-load is "
                         "measured by blank_history, not by this probe.")
        rep["next_action"] = "none"
    else:
        rep["status"] = "DEAD"
        rep["detail"] = (f"0/{len(seats)} free seats answered a two-token probe. The desk has NO "
                         "independent-review capability the moment credits run out, and the "
                         "NO-COST-DRIVEN-DEGRADATION promise is FALSE right now. This is the "
                         "2026-08-01 state (tencent 404 / cohere 400 / nvidia-nano 400 / nvidia "
                         "KeyError) caught BEFORE an outage rather than during one.")
        rep["next_action"] = ("repair the seat ids by ERROR CLASS -- a 404 is a dead model id "
                              "(scripts/refresh_panel_roster.py drops those from the live "
                              "catalog), a 400 is a payload/params mismatch, a KeyError is a "
                              "changed response shape. Three causes, do not treat as one.")
        for s in rep["seats"]:
            rep["breaches"].append(f"{s['model']}: {s.get('error', 'no answer')}")
    return rep


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-probe", action="store_true",
                    help="read the roster without contacting any seat (never passes)")
    args = ap.parse_args()

    rep = build_report(probe=not args.no_probe)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=2) + "\n", "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"free roster (R0344): {rep['status']} -- {rep['detail']}")
        n_alive = "?" if rep["n_alive"] is None else rep["n_alive"]
        print(f"  seats {n_alive}/{rep['n_seats']} alive")
        for s in rep["seats"]:
            mark = "alive" if s["alive"] else "DEAD "
            tail = f"{s['chars']}c" if s.get("chars") is not None else s.get("error", "")
            print(f"    [{mark}] {s['model']:<48} {str(tail)[:80]}")
        if rep["blank_history"]:
            print(f"  blank-under-load history (panel runs, not this probe): "
                  f"{rep['blank_history']}")
        for b in rep["breaches"]:
            print(f"  BREACH: {b}")
        print(f"  next: {rep['next_action']}")

    if args.report_only:
        return 0
    # The denominator is the seats actually contacted (L1.57): a pass over zero seats is refused
    # by fence_exit, which is the EMPTY branch above arriving at the exit site as well as in prose.
    return fence_exit(rep["status"], _PASSING, scanned=rep["n_seats"], of="free panel seats",
                      fence="check_free_roster.py")


if __name__ == "__main__":
    sys.exit(main())
