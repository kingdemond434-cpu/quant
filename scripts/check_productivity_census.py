#!/usr/bin/env python3
"""THE FENCE ON THE PRODUCTIVITY CENSUS -- it must be FRESH, and silence must be NAMED.

`desks/mt5/research/productivity_census.py` measures which producers turn compute into cells.
A census is only evidence while it is current, and a producer that burns compute for weeks and
returns no unique cell is either exploring on purpose or broken -- and the difference is a
SENTENCE somebody wrote, not something a checker can infer.

SO THIS FENCE FAILS ON EXACTLY TWO THINGS:

  1. STALENESS. No artifact, or an artifact older than the staleness window: a census nobody has
     re-run is a claim the desk cannot cash (L1.49). The leg runs hourly, so the window is
     generous and a breach means the leg is not running, which is the defect.
  2. SILENT ZERO-YIELD. A producer that has consumed compute for longer than the stated window
     while producing NO unique cell and carrying NO named blocker. The blocker lives in
     `docs/research/productivity_blockers.json` and is a sentence with an owner; adding one is
     how an exploratory organ declares itself and passes.

IT DOES NOT FAIL ON LOW PRODUCTIVITY, and that restraint is the design, not a gap. The principal's
standing order is that this desk never reduces its own aggressiveness, and a checker that killed
organs for producing few cells would do exactly that -- it would cut the tail of the search
distribution, which is where the uncorrelated mechanisms live. A genuinely exploratory organ is
allowed to be unproductive for as long as it likes PROVIDED IT SAYS SO. What is forbidden is
unproductive AND silent, which is indistinguishable from broken.

Exit 0 pass, 1 fail. `--json` prints the verdict for a machine reader.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CENSUS = ROOT / "desks" / "mt5" / "reports" / "PRODUCTIVITY_CENSUS.json"
BLOCKERS = ROOT / "docs" / "research" / "productivity_blockers.json"

# The leg runs hourly. Six hours of slack absorbs a slow cycle, a reboot and a pass the pricer
# deferred; beyond that the leg is not running and that is what the fence is for.
STALE_HOURS = 6.0

# How long a producer may burn compute with nothing to show before it must say why. Long on
# purpose: a week of silence is a fact, an afternoon of it is a schedule.
SILENT_WINDOW_HOURS = 168.0

# Below this, "compute consumed" is noise -- a single costed import, a probe, a leg that started
# and was interrupted. A fence that fired on a hundredth of an hour would train readers to ignore
# it, which is worse than not having it.
MIN_COMPUTE_HOURS = 0.25


def _age_hours(stamp: Any) -> float | None:
    if not stamp:
        return None
    try:
        when = datetime.fromisoformat(str(stamp))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return (datetime.now(UTC) - when).total_seconds() / 3600.0


def _blockers() -> dict[str, Any]:
    """Named blockers, keyed by producer. An absent file is an empty set, never an error.

    The file is optional BY DESIGN: a desk with nothing to declare should not have to keep an
    empty document current, and the fence's failure message says where to write one.
    """
    try:
        with BLOCKERS.open(encoding="utf-8") as fh:
            blob = json.load(fh)
    except Exception:
        return {}
    if isinstance(blob, dict):
        rows = blob.get("blockers") if isinstance(blob.get("blockers"), (dict, list)) else blob
    else:
        rows = blob
    out: dict[str, Any] = {}
    if isinstance(rows, dict):
        for key, val in rows.items():
            out[str(key).strip().lower()] = val
    elif isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                key = row.get("producer") or row.get("key")
                if key:
                    out[str(key).strip().lower()] = row
    return out


def _named(entry: Any) -> bool:
    """A blocker counts only if it actually says something with an owner behind it."""
    if isinstance(entry, str):
        return len(entry.strip()) >= 20
    if isinstance(entry, dict):
        why = str(entry.get("why") or entry.get("reason") or entry.get("blocker") or "").strip()
        who = str(entry.get("owner") or entry.get("by") or "").strip()
        return len(why) >= 20 and bool(who)
    return False


def check() -> dict[str, Any]:
    out: dict[str, Any] = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "artifact": str(CENSUS.relative_to(ROOT)),
        "stale_hours": STALE_HOURS,
        "silent_window_hours": SILENT_WINDOW_HOURS,
        "min_compute_hours": MIN_COMPUTE_HOURS,
        "failures": [],
        "silent_producers": [],
        "declared_producers": [],
        "note": ("this fence never fails on LOW productivity: an exploratory organ may produce "
                 "nothing for as long as it likes provided it declares a named blocker in "
                 "docs/research/productivity_blockers.json"),
    }
    failures: list[str] = out["failures"]

    if not CENSUS.exists():
        failures.append(
            f"no census artifact at {out['artifact']}: the leg `productivity_census` has never "
            "written one on this host, so which organs earn their compute is UNMEASURED and "
            "cannot be claimed")
        return out
    try:
        with CENSUS.open(encoding="utf-8") as fh:
            census = json.load(fh)
    except Exception as exc:
        failures.append(f"census at {out['artifact']} is unreadable: {type(exc).__name__}: {exc}")
        return out

    age = _age_hours(census.get("at"))
    out["age_hours"] = None if age is None else round(age, 2)
    if age is None:
        failures.append(f"census carries no readable `at` stamp (got {census.get('at')!r}): a "
                        "census that cannot be dated cannot be trusted to be current")
    elif age > STALE_HOURS:
        failures.append(
            f"census is {age:.1f}h old against a {STALE_HOURS:g}h window: the hourly leg "
            "`productivity_census` is not running, so every productivity number the desk would "
            "quote is stale (L1.49 -- a gate that never ran is a claim the desk cannot cash)")

    blockers = _blockers()
    out["n_blockers"] = len(blockers)
    for row in census.get("zero_cell_compute") or []:
        if not isinstance(row, dict):
            continue
        hours = row.get("compute_hours")
        if not isinstance(hours, (int, float)) or hours < MIN_COMPUTE_HOURS:
            continue
        key = str(row.get("key") or row.get("producer") or "").strip().lower()
        entry = blockers.get(key)
        item = {"producer": row.get("producer"), "key": key,
                "compute_hours": hours, "clock": row.get("clock"),
                "region": row.get("region")}
        if _named(entry):
            item["blocker"] = entry
            out["declared_producers"].append(item)
            continue
        out["silent_producers"].append(item)
        failures.append(
            f"producer `{row.get('producer')}` consumed {hours:.3f} compute hours and produced "
            "NO unique cell and no discovery, and carries no named blocker: declare it in "
            f"docs/research/productivity_blockers.json (a `why` of 20+ chars and an `owner`) or "
            "fix it -- unproductive AND silent is indistinguishable from broken")

    out["ok"] = not failures
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    verdict = check()
    if args.json:
        print(json.dumps(verdict, indent=2, default=str))
    elif verdict.get("failures"):
        print("PRODUCTIVITY CENSUS FENCE: FAIL")
        for f in verdict["failures"]:
            print(f"  - {f}")
    else:
        print(f"PRODUCTIVITY CENSUS FENCE: ok (age {verdict.get('age_hours')}h, "
              f"{len(verdict.get('declared_producers') or [])} declared exploratory)")
    return 1 if verdict.get("failures") else 0


if __name__ == "__main__":
    sys.exit(main())
