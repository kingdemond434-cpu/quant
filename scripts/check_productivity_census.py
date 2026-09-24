#!/usr/bin/env python3
"""THE FENCE ON THE PRODUCTIVITY CENSUS -- it must be FRESH, and silence must be NAMED.

`desks/mt5/research/productivity_census.py` measures which producers turn compute into cells.
A census is only evidence while it is current, and a producer that burns compute for weeks and
returns no unique cell is either exploring on purpose or broken -- and the difference is a
SENTENCE somebody wrote, not something a checker can infer.

SO THIS FENCE FAILS ON EXACTLY THREE THINGS:

  1. STALENESS. No artifact, or an artifact older than the staleness window: a census nobody has
     re-run is a claim the desk cannot cash (L1.49). The leg runs hourly, so the window is
     generous and a breach means the leg is not running, which is the defect.
  2. SILENT ZERO-YIELD. A producer that has consumed compute for longer than the stated window
     while producing NO unique cell and carrying NO named blocker. The blocker lives in
     `docs/research/productivity_blockers.json` and is a sentence with an owner; adding one is
     how an exploratory organ declares itself and passes.
  3. MEASUREMENT COVERAGE FALLING (added 2026-09-24). Per-producer coverage of the six columns
     the producers panel renders -- cells, unique cells, cells judged, certificates,
     orthogonality added, compute hours -- is a RATCHET that rises and never falls, and
     `n_producers` rides with it so a share can never be improved by dropping producers out of
     the bottom (L1.50). This clause exists because the panel once published 1,981 producers with
     a compute cost on every row and UNMEASURED in all five columns beside it: the desk knew
     exactly what each organ COST and nothing about what it MADE, which is the wrong half of the
     pair to have, and nothing measured it so nothing could fail on it. Seeding an empty ratchet
     is not an improvement claim; it is the baseline the next run is judged against.

IT DOES NOT FAIL ON LOW PRODUCTIVITY, and that restraint is the design, not a gap. The principal's
standing order is that this desk never reduces its own aggressiveness, and a checker that killed
organs for producing few cells would do exactly that -- it would cut the tail of the search
distribution, which is where the uncorrelated mechanisms live. A genuinely exploratory organ is
allowed to be unproductive for as long as it likes PROVIDED IT SAYS SO. What is forbidden is
unproductive AND silent, which is indistinguishable from broken.

WITHOUT DESK STATE IT READS UNMEASURED AND PASSES. The census artifact lives under
`desks/mt5/reports/`, which no clean checkout and no CI runner has; a fence that reported FAIL on
every pull request would be switched off inside a week and would then protect nothing (L1.43,
and the same split `check_certificate_truth.py` and `check_scheduler_manifest.py` already make).
`--require-state` is the half that runs where the state exists -- the box and the VPS -- and it
turns an absent census back into the failure it is there.

Exit 0 pass, 1 fail. `--json` prints the verdict for a machine reader. The coverage ratchet is
tightened on every run (`--no-ratchet` to suppress) because the law gate calls this fence with no
arguments, and a bar that only moves under an extra flag never moves.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CENSUS = ROOT / "desks" / "mt5" / "reports" / "PRODUCTIVITY_CENSUS.json"
BLOCKERS = ROOT / "docs" / "research" / "productivity_blockers.json"

#: THE MEASUREMENT-COVERAGE RATCHET. Rises only. Its denominator (`n_producers`) is part of it,
#: because a coverage share improved by publishing fewer producers is a regression wearing an
#: improvement's number -- and the producer count on this desk only ever goes UP.
RATCHET = ROOT / "docs" / "research" / "productivity_census_ratchet.json"

#: The columns this fence ratchets are NOT listed here. They are the union of what the census
#: published this hour and what the ratchet has already recorded -- so a column added to the
#: census is fenced the same hour without anybody editing this file, and a column REMOVED from the
#: census still fails against its own recorded best instead of quietly leaving the gate. A
#: hand-copied list is how a new column comes to be published and never checked.

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
    """A declaration counts only if it actually says something with an owner behind it.

    TWO SHAPES, AND THIS FENCE ONLY READ ONE (measured 2026-09-24). `productivity_blockers.json`
    declares its own law -- "a BLOCKER (`why` of 20+ chars and an `owner`) says the production is
    broken and who owns the fix; an EXEMPTION (`exempt: true` with `produces` and `consumer`)
    says the organ makes something other than cells by design" -- and the sibling reader
    `scripts/check_producer_yield.py` honours both. This function accepted only the BLOCKER
    shape, so the EXEMPTION half of the desk's own remedy was uncashable HERE: a report builder
    that declared itself exactly as the law says still failed this fence, and the only way to
    pass was to call a by-design report builder "broken" and name an owner for a fix that is not
    needed. The 15 EXEMPTION rows already in the file pass today only because every one of them
    sits under MIN_COMPUTE_HOURS and is filtered out before this is ever called.

    Nothing is relaxed: an EXEMPTION must still NAME what it produces and NAME who reads it, the
    same evidence `check_producer_yield` requires, and silence is still a defect.
    """
    if isinstance(entry, str):
        return len(entry.strip()) >= 20
    if isinstance(entry, dict):
        why = str(entry.get("why") or entry.get("reason") or entry.get("blocker") or "").strip()
        who = str(entry.get("owner") or entry.get("by") or "").strip()
        produces = str(entry.get("produces") or "").strip()
        consumer = str(entry.get("consumer") or entry.get("read_by") or "").strip()
        if entry.get("exempt") and len(produces) >= 3 and len(consumer) >= 3:
            return True
        return len(why) >= 20 and bool(who)
    return False


def _ratchet_doc() -> dict[str, Any]:
    """The recorded bests. An absent or unreadable file is an empty ratchet, never an error."""
    try:
        with RATCHET.open(encoding="utf-8") as fh:
            doc = json.load(fh)
    except Exception:
        return {}
    return doc if isinstance(doc, dict) else {}


def _coverage_clause(census: dict[str, Any], out: dict[str, Any],
                     failures: list[str]) -> dict[str, Any] | None:
    """Judge per-producer measurement coverage against the ratchet. Returns the new doc, if moved.

    THREE STATES AND THEY ARE NOT THE SAME (L1.28a). A census that publishes no coverage block at
    all when the ratchet has never recorded one is UNMEASURED -- the code that publishes it has
    not reached this host yet, which is a fact about the deployment and not a broken law. Once the
    ratchet HOLDS a best, an absent or lower coverage is a REGRESSION and fails: the measurement
    existed, somebody stopped publishing it, and that is exactly the silence this clause is for.
    """
    doc = _ratchet_doc()
    # PER HOST, BECAUSE A BAR MEASURED ON ONE MACHINE IS NOT A BAR FOR ANOTHER. This file is in
    # the repository and both machines read it, and they do not hold the same registry: the
    # trading box censused 1,998 producers on the day this landed and the build box 1,653. A
    # single shared `n_producers_best` would have the box raise the bar to 1,998 and the build
    # box fail the denominator clause for being a different computer -- the same mistake as
    # sizing a memory floor off the other box, which this desk has already paid for once. Each
    # host ratchets against its own history; nothing is ever lowered, and a legacy flat document
    # is migrated into this host's block rather than discarded.
    host = str(census.get("host") or os.environ.get("COMPUTERNAME") or "UNKNOWN_HOST").strip()
    hosts = doc.get("hosts")
    if not isinstance(hosts, dict):
        hosts = {}
        doc["hosts"] = hosts
    legacy = {k: doc[k] for k in ("n_producers_best", "columns_best", "measured_best",
                                  "region_coverage_best", "region_measured_best")
              if isinstance(doc.get(k), (int, float, dict))}
    raw_host = hosts.get(host)
    rat: dict[str, Any] = raw_host if isinstance(raw_host, dict) else dict(legacy)
    hosts[host] = rat
    out["ratchet_host"] = host

    raw_best = rat.get("columns_best")
    best_cols: dict[str, Any] = dict(raw_best) if isinstance(raw_best, dict) else {}
    best_n = rat.get("n_producers_best")
    best_region = rat.get("region_coverage_best")
    had_ratchet = bool(best_cols) or isinstance(best_n, (int, float))
    reason = str(rat.get("regression_reason") or doc.get("regression_reason") or "").strip()

    cov = census.get("measurement_coverage")
    if not isinstance(cov, dict):
        out["coverage"] = {
            "verdict": "UNMEASURED",
            "why": ("the census on this host publishes no `measurement_coverage` block: the "
                    "organ that measures per-producer coverage has not reached it yet. That is a "
                    "deployment fact, not a passed gate."),
        }
        if had_ratchet and not reason:
            failures.append(
                "the census stopped publishing `measurement_coverage` while the ratchet holds "
                f"{best_cols} and n_producers {best_n}: a measurement that existed and is now "
                f"absent is a REGRESSION, not a fresh start. Restore it or state why in "
                f"{RATCHET.relative_to(ROOT)}")
        return None

    raw_cols = cov.get("columns")
    cols: dict[str, Any] = raw_cols if isinstance(raw_cols, dict) else {}
    raw_counts = rat.get("measured_best")
    best_counts: dict[str, Any] = dict(raw_counts) if isinstance(raw_counts, dict) else {}
    judged = sorted(set(cols) | set(best_cols) | set(best_counts))
    n_prod = cov.get("n_producers")
    raw_region = cov.get("region")
    rblock: dict[str, Any] = raw_region if isinstance(raw_region, dict) else {}
    region = rblock.get("coverage")
    region_n = ((rblock.get("regional") or 0) + (rblock.get("not_regional") or 0)
                if rblock else None)
    best_region_n = rat.get("region_measured_best")
    grew = (isinstance(n_prod, (int, float)) and isinstance(best_n, (int, float))
            and n_prod > best_n)
    out["coverage"] = {
        "n_producers": n_prod,
        "columns": {c: (cols.get(c) or {}).get("coverage") for c in judged},
        "measured": {c: (cols.get(c) or {}).get("measured") for c in judged},
        "region_coverage": region,
        "region_measured": region_n,
        "roster_grew": bool(grew),
        "fully_measured_rows": cov.get("fully_measured_rows"),
        "ratchet": {"n_producers_best": best_n, "columns_best": best_cols,
                    "measured_best": best_counts, "region_coverage_best": best_region,
                    "region_measured_best": best_region_n,
                    "regression_reason": reason or None},
    }

    # THE DENOMINATOR CLAUSE, FIRST, because it is the one a well-meaning pass breaks. Coverage
    # improved by publishing fewer producers is not an improvement; the producer count on this
    # desk only ever rises, and a fall here is a defect whatever the shares did.
    if isinstance(best_n, (int, float)) and isinstance(n_prod, (int, float)) and n_prod < best_n:
        failures.append(
            f"the census published {n_prod} producers against a recorded best of {best_n:g}: "
            "coverage may NEVER be improved by removing producers from the denominator. Whatever "
            "the column shares say, a smaller roster is a regression (L1.50)")

    # TWO RATCHETS, BECAUSE A SHARE ALONE IS THE WRONG GATE ON A GROWING DESK. The registry gained
    # five producers between two runs of this census while it was being written; a share-only
    # ratchet would have failed on the arrival of new work, which trains a reader to disable the
    # gate. So the COUNT of producers measured may never fall -- that is un-measuring, always a
    # defect -- and the SHARE may only be diluted by genuine growth in the roster. When the roster
    # did not grow, a falling share is a regression exactly as before. Neither clause can be
    # satisfied by publishing less of anything.
    def _num(v: Any) -> float | None:
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    def _judge(what: str, share: Any, share_best: Any, count: Any, count_best: Any) -> None:
        """One axis, both ratchets. Appends at most one failure -- the count one wins."""
        now_n, prev_n, now, prev = _num(count), _num(count_best), _num(share), _num(share_best)
        if reason:
            return
        if prev_n is not None and now_n is not None and now_n < prev_n:
            failures.append(
                f"{what} fell from {prev_n:g} producers to {now_n:g}: measuring FEWER producers "
                "is a regression however the share moved. Find what stopped reporting, or state "
                f"why in {RATCHET.relative_to(ROOT)} -- never raise a share by publishing less")
        elif prev is not None and now is not None and now + 1e-9 < prev and not grew:
            failures.append(
                f"{what} fell to {now:.4f} from a recorded best of {prev:.4f} over {n_prod} "
                "producers, with no growth in the roster to dilute it: this ratchet rises only")

    def _raise(store: dict[str, Any], key: str, value: Any) -> bool:
        """Record a new best. Returns True when the bar moved up."""
        now, prev = _num(value), _num(store.get(key))
        if now is None or (prev is not None and now <= prev):
            return False
        store[key] = round(now, 6) if isinstance(value, float) else int(now)
        return True

    moved = False
    for col in judged:
        raw_entry = cols.get(col)
        entry: dict[str, Any] = raw_entry if isinstance(raw_entry, dict) else {}
        share, count = entry.get("coverage"), entry.get("measured")
        if _num(share) is None and _num(best_cols.get(col)) is not None and not reason:
            failures.append(
                f"column `{col}` is no longer published while the ratchet holds "
                f"{best_cols[col]}: a measured column that vanished is a regression")
            continue
        _judge(f"per-producer coverage of `{col}`", share, best_cols.get(col), count,
               best_counts.get(col))
        moved |= _raise(best_cols, col, share)
        moved |= _raise(best_counts, col, count)
    _judge("region coverage", region, best_region, region_n, best_region_n)
    moved |= _raise(rat, "region_coverage_best", region)
    moved |= _raise(rat, "region_measured_best", region_n)
    moved |= _raise(rat, "n_producers_best", n_prod)
    rat["measured_best"] = best_counts
    if not moved:
        return None
    now = datetime.now(UTC).isoformat(timespec="seconds")
    rat["columns_best"] = best_cols
    if not rat.get("seeded"):                    # `setdefault` keeps an existing null forever
        rat["seeded"] = now
    rat["updated_utc"] = now
    doc["hosts"][host] = rat
    doc["updated_utc"] = now
    doc.setdefault("law", "PER-PRODUCER MEASUREMENT COVERAGE RATCHETS UP ONLY.")
    # The flat legacy bests are now the host block's; leaving copies at the top level would let a
    # second host read them as its own bar, which is the cross-host failure this split removes.
    for key in legacy:
        doc.pop(key, None)
    return doc


def check(require_state: bool = False, tighten: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "artifact": str(CENSUS.relative_to(ROOT) if CENSUS.is_relative_to(ROOT) else CENSUS),
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
        # NO DESK STATE IS NOT A BROKEN LAW. A clean checkout has no reports directory at all;
        # saying so is the verdict, and only the state half treats it as a failure.
        if not require_state and not CENSUS.parent.exists():
            out["ok"] = True
            out["verdict"] = "UNMEASURED"
            out["why"] = (f"no desk state on this host ({CENSUS.parent} does not exist): the "
                          "census cannot be judged here, which is a verdict and not a pass. Run "
                          "with --require-state on the box or the VPS, where the state lives")
            return out
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

    moved = _coverage_clause(census, out, failures)
    if moved is not None and tighten:
        try:
            RATCHET.parent.mkdir(parents=True, exist_ok=True)
            RATCHET.write_text(json.dumps(moved, indent=1) + "\n", encoding="utf-8")
            out["ratchet_tightened"] = True
        except OSError as exc:                       # a read-only checkout is not a broken law
            out["ratchet_tightened"] = f"UNMEASURED: {type(exc).__name__}: {exc}"

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
    ap.add_argument("--require-state", action="store_true",
                    help="treat an absent census as the failure it is: for the box and the VPS, "
                         "where the desk state exists")
    # TIGHTENED BY DEFAULT, exactly as `scripts/check_producer_yield.py` does, and for the reason
    # that decides it: this fence is already wired into `scripts/run_law_gate.py` with no
    # arguments, so a ratchet that only moved under an extra flag would never move at all -- an
    # unwired gate is a defect (III.16). The bar only ever rises, and it is recorded per HOST, so
    # a tighten from one machine can neither lower anything nor raise the bar on the other.
    ap.add_argument("--no-ratchet", action="store_true",
                    help="judge measurement coverage without recording a new best on disk")
    args = ap.parse_args(argv)
    verdict = check(require_state=args.require_state, tighten=not args.no_ratchet)
    if args.json:
        print(json.dumps(verdict, indent=2, default=str))
    elif verdict.get("verdict") == "UNMEASURED":
        print(f"PRODUCTIVITY CENSUS FENCE: UNMEASURED -- {verdict.get('why')}")
    elif verdict.get("failures"):
        print("PRODUCTIVITY CENSUS FENCE: FAIL")
        for f in verdict["failures"]:
            print(f"  - {f}")
    else:
        print(f"PRODUCTIVITY CENSUS FENCE: ok (age {verdict.get('age_hours')}h, "
              f"{len(verdict.get('declared_producers') or [])} declared exploratory)")
    cov = verdict.get("coverage")
    if isinstance(cov, dict) and not args.json:
        if cov.get("verdict") == "UNMEASURED":
            print(f"  coverage: UNMEASURED -- {cov.get('why')}")
        else:
            print(f"  coverage over {cov.get('n_producers')} producers: "
                  + "  ".join(f"{k}={v}" for k, v in (cov.get("columns") or {}).items())
                  + f"  region={cov.get('region_coverage')}")
    return 1 if verdict.get("failures") else 0


if __name__ == "__main__":
    sys.exit(main())
