#!/usr/bin/env python3
"""CAMPAIGN RETENTION FENCE (R0270; L1.0 ratchet, L2.0 fence, L1.28a unmeasured-is-not-OK).

THE GAP THIS CLOSES. `libs/autodiscovery/orchestrator.py` writes a `campaign_strata` audit row
every campaign carrying how much of the desk's data the campaign actually tested on. Until now the
sole repo reference to `campaign_strata` was that writer: NOTHING READ IT. History length is the
binding constraint on discovery power here, so a silent return to min-length truncation would
restore an 82.9% discard of the observations on disk with no alarm anywhere.

WHAT IT FIRES ON, and the second one is the sharp one:
  * REGRESSED  -- retained observation share fell below its recorded floor (L1.0: floors only rise)
  * FALLBACK   -- `plan_strata` truncated to min-length because nothing cleared its floors. It is
                  CORRECT behaviour that must never become the steady state, and it degrades
                  QUIETLY by design. Note the direction: the fallback drives n_untested DOWN to
                  zero, so a fence watching only for untested RISING would read this regression as
                  the campaign becoming more inclusive.
  * STALE      -- the newest row is older than two campaign cadences (the factory is daily)
  * ABSENT     -- no campaign has ever recorded a plan. NOT the same defect as STALE or REGRESSED
                  (L1.55): they send you to different organs.
  * UNMEASURED -- no audit store could be discovered at all. Never a pass (L1.28a).

UNTESTED SHARE IS MEASURED AND PUBLISHED BUT DELIBERATELY NOT FENCED YET, and saying why is the
point. R0270 asked for a fire on "n_untested rises materially". Two things stop that from being
honest today. First the direction: the fallback drives untested to ZERO, so a rising-only check
would miss the sharp failure entirely and read it as the campaign becoming more inclusive. Second
the band: `materially` needs the natural day-to-day variance of the quantity, and the desk has
exactly ONE distinct campaign shape on record (810 candidates, k=32, 36.7% untested). A tolerance
picked from n=1 is a constant wearing a measurement's clothes (L1.55) and would either never fire
or fire on ordinary shape drift -- a welded gate either way (L1.43). So the share is computed and
written to the artifact every run, which is what makes the calibration possible later, and R0435
rows it. Retention already covers both failures this would have caught, from the observation side.

WHAT IT DOES NOT DO. It judges no candidate, promotes nothing, sizes nothing and touches no
statistical bar. Retention is a MEASUREMENT of how much data the campaign used; this fence only
asserts that the number never falls and is never fabricated. Anti-timidity reading (L1.28): it can
only ever push the desk to test on MORE of its own data, never less.

    python scripts/check_campaign_retention.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.campaign_retention import (  # noqa: E402
    Reading,
    audit_dbs,
    newest_reading,
)

_OUT = _ROOT / "data" / "campaign_retention.json"
_FLOORS = _ROOT / "data" / "ratchet_floors.json"
#: The crypto factory runs daily (01:30). Two cadences of grace, so one missed night is not a
#: page and two consecutive misses are -- the same convention the other daily ratchets use.
MAX_AGE_H = 48.0
_METRIC = "campaign_obs_retained"
_PASSING = frozenset({"OK", "NO-FLOOR"})


def _floor(root: Path | None = None) -> float | None:
    """The recorded retention floor, or None if this metric has never been floored.

    Read from the committed ratchet artifact rather than kept here, so there is ONE floor with one
    provenance and `check_ratchets --ratchet` remains the only thing that can move it -- upward.
    """
    path = (root or _ROOT) / "data" / "ratchet_floors.json"
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    entry = doc.get(_METRIC) if isinstance(doc, dict) else None
    if isinstance(entry, dict) and isinstance(entry.get("value"), (int, float)):
        return float(entry["value"])
    return None


def _age_h(created_at: str) -> float | None:
    try:
        t = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return (datetime.now(tz=UTC) - t).total_seconds() / 3600.0


def _verdict(rd: Reading | None, n_dbs: int, n_rows: int,
             floor: float | None) -> tuple[str, str, str]:
    """(status, why, next_action) -- the whole judgement, in one place, from arguments in hand."""
    if n_dbs == 0:
        return ("UNMEASURED",
                "no sqlite store carrying an audit_log table was found under data/ -- this fence "
                "examined NOTHING, which is not evidence that campaigns are healthy",
                "repair scope discovery in libs.research.campaign_retention.audit_dbs")
    if rd is None:
        detail = (f"{n_rows} campaign_strata row(s) found but none carried the fields this fence "
                  "judges -- a malformed row is never read past to a greener one underneath"
                  ) if n_rows else (
                  f"no campaign has ever written a campaign_strata row across {n_dbs} audit "
                  "store(s). The plan is unrecorded, so retention is unknowable -- not healthy")
        return ("ABSENT", detail,
                "run the campaign (ops/run_crypto_factory.sh) and confirm the orchestrator's "
                "audit append fires")

    frac = rd.retained_fraction
    untested = rd.untested_fraction
    age = _age_h(rd.created_at)
    head = (f"campaign {rd.campaign_id[:16]} in {rd.db}: {rd.obs_retained:,}/"
            f"{rd.obs_available:,} observations "
            f"({'n/a' if frac is None else f'{frac:.1%}'}) across k={rd.k_strata} strata, "
            f"{rd.n_tested}/{rd.n_candidates} candidates tested")

    # FALLBACK FIRST. It is a statement about the planner's own state, so it outranks the numeric
    # comparisons -- and its retention collapse would otherwise be reported as a plain regression,
    # sending the reader to look for a data problem instead of a floors problem.
    if rd.is_fallback:
        return ("FALLBACK",
                f"{head} -- plan_strata TRUNCATED TO MIN-LENGTH: nothing cleared its floors, so "
                "the campaign is a single underpowered stratum over every candidate. Correct "
                "behaviour, never a steady state; a null result from this campaign is not "
                "evidence about the space. Note n_untested went to 0, which reads as inclusive",
                "find why no stratum cleared MIN_COHORT=12/MIN_OBS=250 -- generation shape or a "
                "collapsed length distribution upstream")
    if frac is None:
        return ("ABSENT",
                f"{head} -- obs_available is 0, so retention has no denominator and any "
                "percentage computed from it would be an opinion (L1.57)",
                "check the campaign's series preparation: zero available observations means the "
                "data provider returned nothing")
    if rd.structurally_single_stratum and floor is not None and frac + 1e-9 < floor:
        return ("FALLBACK",
                f"{head} -- one stratum holding every candidate AND retention {frac:.1%} below "
                f"the {floor:.1%} floor. The planner did not label it, but that is the shape and "
                "the cost of the min-length fallback",
                "confirm against plan_strata's floors; if this is a legitimate single stratum, "
                "the retention regression still stands on its own")
    if floor is None:
        return ("NO-FLOOR",
                f"{head} -- measured, but no floor is recorded for {_METRIC}. A number without a "
                "floor cannot regress, so it is not yet fenced",
                "python scripts/check_ratchets.py --ratchet   (records the floor; never lowers)")
    if frac + 1e-9 < floor:
        return ("REGRESSED",
                f"{head} -- retention {frac:.1%} is BELOW the recorded floor {floor:.1%}. "
                "Observations on disk that no test ran on are edge already paid for and declined",
                "compare this campaign's length distribution against the floored run; floors only "
                "rise, so this is repaired upstream and never by lowering the floor")
    if age is not None and age > MAX_AGE_H:
        return ("STALE",
                f"{head} -- newest plan is {age:.1f}h old, past {MAX_AGE_H:.0f}h (two daily "
                "cadences). A frozen artifact steers decisions exactly as a live one does",
                "check the crypto factory cron (01:30 daily) and its lock file")
    unt = "" if untested is None else f", {untested:.1%} of candidates untested (measured, "
    unt += "" if untested is None else "not fenced -- see the module docstring and R0435)"
    return ("OK",
            f"{head}; retention {frac:.1%} at or above the {floor:.1%} floor"
            + (f", plan {age:.1f}h old" if age is not None else "") + unt,
            "none")


def build(root: Path | None = None) -> dict[str, Any]:
    rd, n_dbs, n_rows = newest_reading(root)
    floor = _floor(root)
    status, why, nxt = _verdict(rd, n_dbs, n_rows, floor)
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.0 universal ratchet / L2.0 fence -- campaign observation-retention is a "
               "measured metric whose floor only rises; R0270.",
        "status": status,
        "n_audit_dbs": n_dbs,
        "n_rows_seen": n_rows,
        "floor": floor,
        "max_age_h": MAX_AGE_H,
        "retained_fraction": None if rd is None else rd.retained_fraction,
        "untested_fraction": None if rd is None else rd.untested_fraction,
        "k_strata": None if rd is None else rd.k_strata,
        "campaign": None if rd is None else {
            "db": rd.db, "campaign_id": rd.campaign_id, "created_at": rd.created_at,
            "age_h": None if _age_h(rd.created_at) is None else round(_age_h(rd.created_at), 1),
            "n_candidates": rd.n_candidates, "n_tested": rd.n_tested,
            "n_untested": rd.n_untested, "obs_retained": rd.obs_retained,
            "obs_available": rd.obs_available, "strata_alpha": rd.strata_alpha,
            "outcome": rd.outcome,
        },
        "detail": why,
        "next_action": nxt,
        "proving_command": "python scripts/check_campaign_retention.py",
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report-only", action="store_true",
                    help="write the artifact and always exit 0")
    ap.add_argument("--json", action="store_true", help="print the artifact")
    args = ap.parse_args()

    rep = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        frac = rep["retained_fraction"]
        flr = rep["floor"]
        print(f"campaign retention (R0270): {rep['status']} -- "
              f"{'n/a' if frac is None else f'{frac:.1%}'} retained "
              f"(floor {'none' if flr is None else f'{flr:.1%}'}), "
              f"{rep['n_rows_seen']} row(s) across {rep['n_audit_dbs']} audit store(s)")
        print(f"  {rep['detail']}")
        print(f"  next: {rep['next_action']}")

    if args.report_only:
        return 0
    # Subject to L1.57: the denominator is how many audit stores this run actually discovered, so
    # a scope discovery that finds nothing refuses its own pass instead of reporting a clean board.
    return fence_exit(rep["status"], _PASSING, scanned=len(audit_dbs()),
                      of="data/*.sqlite audit stores", fence="check_campaign_retention.py")


if __name__ == "__main__":
    raise SystemExit(main())
